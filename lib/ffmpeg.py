"""
FFmpeg 非同期ラッパー
asyncio.create_subprocess_exec を使用し、OS 依存のない形で実装。
stderr からの進捗情報をリアルタイムにログ出力する。
"""

from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger(__name__)

# FFmpeg の stderr から時間進捗を抽出する正規表現
_TIME_RE = re.compile(r"time=(\d+:\d+:\d+\.\d+)")
_DURATION_RE = re.compile(r"Duration:\s*(\d+:\d+:\d+\.\d+)")
_SPEED_RE = re.compile(r"speed=\s*([\d.]+)x")


def _parse_seconds(ts: str) -> float:
    """HH:MM:SS.ff 形式を秒数に変換"""
    try:
        h, m, s = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return 0.0


async def _read_stderr_with_progress(
    proc: asyncio.subprocess.Process,
    label: str,
) -> str:
    """
    ffmpeg の stderr を非同期で読み取り、進捗をログに出す。
    完全な stderr テキストを返す。
    """
    lines: list[str] = []
    duration_sec: float = 0.0
    last_log_sec: float = 0.0

    assert proc.stderr is not None

    while True:
        try:
            # ffmpeg は \r で進捗を上書きするため readline では取れない場合がある
            # 1024バイトずつ読む
            chunk = await asyncio.wait_for(proc.stderr.read(1024), timeout=5.0)
        except asyncio.TimeoutError:
            # タイムアウトで EOF 判定（プロセス終了待ち）
            if proc.returncode is not None:
                break
            continue
        except Exception:
            break

        if not chunk:
            break

        text = chunk.decode("utf-8", errors="replace")
        lines.append(text)

        # Duration を一度だけ取得
        if duration_sec == 0.0:
            m = _DURATION_RE.search(text)
            if m:
                duration_sec = _parse_seconds(m.group(1))
                logger.debug("[ffmpeg:%s] 総時間: %.1fs", label, duration_sec)

        # 進捗時間の抽出（10秒ごとにログ）
        for tm in _TIME_RE.finditer(text):
            current_sec = _parse_seconds(tm.group(1))
            if current_sec - last_log_sec >= 10.0 or current_sec == 0:
                speed_m = _SPEED_RE.search(text)
                speed = speed_m.group(1) if speed_m else "?"
                if duration_sec > 0:
                    pct = min(current_sec / duration_sec * 100, 100)
                    logger.info(
                        "[ffmpeg:%s] 進捗: %.0f%% (%.1fs/%.1fs) speed=%sx",
                        label, pct, current_sec, duration_sec, speed
                    )
                else:
                    logger.info(
                        "[ffmpeg:%s] 処理中: %.1fs speed=%sx",
                        label, current_sec, speed
                    )
                last_log_sec = current_sec

    return "".join(lines)


async def run_ffmpeg(
    args: list[str],
    label: str = "ffmpeg",
    input_data: bytes | None = None,
) -> bytes:
    """
    ffmpeg を非同期で実行し、stdout の bytes を返す。

    Args:
        args: ffmpeg に渡す引数リスト（"ffmpeg" 自体は不要）
        label: ログ用ラベル
        input_data: stdin に流すデータ（None の場合は stdin を使わない）

    Returns:
        stdout の bytes

    Raises:
        RuntimeError: ffmpeg がエラーで終了した場合
    """
    cmd = ["ffmpeg", "-hide_banner", "-y", *args]
    logger.debug("[ffmpeg:%s] コマンド: %s", label, " ".join(cmd))

    stdin_mode = asyncio.subprocess.PIPE if input_data is not None else asyncio.subprocess.DEVNULL

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=stdin_mode,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # stderr 進捗読み取りと stdout 読み取りを並行実行
    if input_data is not None:
        stderr_task = asyncio.create_task(
            _read_stderr_with_progress(proc, label)
        )
        stdout_data, _ = await proc.communicate(input=input_data)
        stderr_text = await stderr_task
    else:
        stderr_task = asyncio.create_task(
            _read_stderr_with_progress(proc, label)
        )
        stdout_data = await proc.stdout.read()
        await proc.wait()
        stderr_text = await stderr_task

    if proc.returncode != 0:
        # エラー時は stderr の末尾 1000 文字をログに出す
        tail = stderr_text[-1000:] if len(stderr_text) > 1000 else stderr_text
        logger.error("[ffmpeg:%s] エラー終了 (returncode=%d):\n%s",
                     label, proc.returncode, tail)
        raise RuntimeError(
            f"ffmpeg [{label}] failed (returncode={proc.returncode})"
        )

    logger.info("[ffmpeg:%s] 完了 (出力 %d bytes)", label, len(stdout_data))
    return stdout_data


# ------------------------------------------------------------------ #
# エンコード関数
# ------------------------------------------------------------------ #

async def encode_video_from_url(
    url: str,
    encode_mode: str = "copy",
    crf: int = 28,
) -> bytes:
    """
    動画URLをダウンロードしてエンコードする。

    encode_mode:
        "x265" → H.265 再エンコード
        "copy" → ストリームコピー（再エンコードなし）
    """
    if encode_mode == "x265":
        args = [
            "-i", url,
            "-c:v", "libx265",
            "-crf", str(crf),
            "-c:a", "copy",
            "-movflags", "frag_keyframe+empty_moov+default_base_moof+faststart",
            "-pix_fmt", "yuv420p",
            "-tag:v", "hvc1",
            "-f", "mp4",
            "pipe:1",
        ]
        label = f"video-x265-crf{crf}"
    else:
        args = [
            "-i", url,
            "-c:v", "copy",
            "-c:a", "copy",
            "-movflags", "frag_keyframe+empty_moov+default_base_moof+faststart",
            "-f", "mp4",
            "pipe:1",
        ]
        label = "video-copy"

    return await run_ffmpeg(args, label=label)


async def encode_gif_to_gif(url: str, fpsmax: int = 15) -> bytes:
    """アニメーション GIF → GIF（パレット最適化）"""
    args = [
        "-i", url,
        "-filter_complex",
        f"[0:v] fps={fpsmax},split [a][b];[a] palettegen [p];[b][p] paletteuse",
        "-f", "gif",
        "pipe:1",
    ]
    return await run_ffmpeg(args, label=f"gif2gif-fps{fpsmax}")


async def encode_gif_to_video(url: str, crf: int = 28) -> bytes:
    """アニメーション GIF → H.265 動画"""
    args = [
        "-i", url,
        "-c:v", "libx265",
        "-crf", str(crf),
        "-movflags", "frag_keyframe+empty_moov+default_base_moof+faststart",
        "-pix_fmt", "yuv420p",
        "-tag:v", "hvc1",
        "-f", "mp4",
        "pipe:1",
    ]
    return await run_ffmpeg(args, label=f"gif2video-crf{crf}")


async def encode_image_to_avif(image_data: bytes, quality: int = 60) -> bytes:
    """
    画像データ（bytes）を AVIF に変換する。
    stdin から受け取り stdout へ出力。
    Pillow がない環境でも動作する（ffmpeg のみ依存）。
    """
    args = [
        "-f", "image2pipe",
        "-i", "pipe:0",
        "-c:v", "libaom-av1",
        "-crf", str(max(0, 63 - quality)),  # quality 0-100 → crf 63-0 に変換
        "-b:v", "0",
        "-f", "avif",
        "pipe:1",
    ]
    try:
        return await run_ffmpeg(args, label=f"img2avif-q{quality}", input_data=image_data)
    except RuntimeError:
        # libaom-av1 がない ffmpeg 環境では PNG/JPEG そのまま返す
        logger.warning("AVIF エンコード失敗。元データをそのまま使用します")
        return image_data
