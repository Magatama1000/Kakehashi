"""
ロギング設定モジュール
config.toml の [log] セクションに従ってロガーを設定する。
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def setup_logging(config_log: dict | None = None) -> None:
    """
    アプリケーション全体のロギングを設定する。

    config_log キー:
        level: str  ログレベル（DEBUG / INFO / WARNING / ERROR）デフォルト: INFO
        file:  str  ログファイルパス。空文字列 or 未指定でファイル出力なし
        max_bytes: int  ログファイル最大サイズ（バイト）デフォルト: 10MB
        backup_count: int  ローテーション保持数 デフォルト: 5
        console: bool  コンソール出力するか デフォルト: true
    """
    if config_log is None:
        config_log = {}

    level_str: str = config_log.get("level", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    log_file: str = config_log.get("file", "Kakehashi-bot.log")
    max_bytes: int = config_log.get("max_bytes", 10 * 1024 * 1024)  # 10MB
    backup_count: int = config_log.get("backup_count", 5)
    console_out: bool = config_log.get("console", True)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # 既存ハンドラをクリア（二重登録防止）
    root.handlers.clear()

    # コンソールハンドラ
    if console_out:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    # ファイルハンドラ（ローテーション付き）
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(fmt)
        root.addHandler(fh)

    # サードパーティの冗長ログを抑制
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)
