"""
url-cleaner ラッパーモジュール
config の url_cleaner = true の場合に UrlCleaner インスタンスを提供する。

周回セット開始時に update_url_cleaner_rules() を呼び出してルールを最新化する。
url_cleaner = false の場合は None を返すため、呼び出し側は None チェックするだけでよい。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def make_url_cleaner(enabled: bool):
    """
    url_cleaner が有効な場合は UrlCleaner インスタンスを返す。
    無効な場合は None を返す。
    初期化時に一度ルールを更新する。
    """
    if not enabled:
        return None

    try:
        from url_cleaner import UrlCleaner
        cleaner = UrlCleaner()
        try:
            _update_rules_utf8(cleaner)
            logger.info("url-cleaner: ルールを初期化・更新しました")
        except Exception as e:
            logger.warning("url-cleaner: 初期ルール更新失敗（オフライン？）: %s", e)
        return cleaner
    except ImportError:
        logger.error("url-cleaner: モジュールが見つかりません。`uv sync` を実行してください。")
        return None
    except Exception as e:
        logger.error("url-cleaner: 初期化失敗: %s", e)
        return None


def _update_rules_utf8(cleaner) -> None:
    """
    update_rules() を UTF-8 強制環境で実行する。
    Windows の cp932 デフォルトエンコーディングで url-cleaner が
    ファイル書き込みに失敗するのを回避するため、open() をモンキーパッチする。
    """
    import builtins
    _original_open = builtins.open

    def _utf8_open(file, mode="r", buffering=-1, encoding=None, **kwargs):
        # テキストモードかつ encoding 未指定の場合のみ utf-8 を強制
        if encoding is None and "b" not in mode:
            encoding = "utf-8"
        return _original_open(file, mode, buffering, encoding=encoding, **kwargs)

    builtins.open = _utf8_open
    try:
        cleaner.ruler.update_rules()
    finally:
        builtins.open = _original_open


def update_url_cleaner_rules(cleaner) -> None:
    """
    周回セット開始時に呼び出してルールを最新化する。
    cleaner が None（無効時）の場合は何もしない。
    """
    if cleaner is None:
        return

    try:
        _update_rules_utf8(cleaner)
        logger.debug("url-cleaner: ルールを更新しました")
    except Exception as e:
        logger.warning("url-cleaner: ルール更新失敗（オフライン？）: %s", e)