"""
リトライユーティリティ
twikit の呼び出しや一般的な非同期処理に対してリトライ・バックオフを提供する。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# twikit のエラークラス（インポート時エラーを防ぐため遅延インポート）
_TWIKIT_RETRYABLE = None


def _get_twikit_retryable() -> tuple:
    global _TWIKIT_RETRYABLE
    if _TWIKIT_RETRYABLE is None:
        try:
            from twikit.errors import (
                TwitterException,
                TooManyRequests,
                RequestTimeout,
                ServerError,
            )
            _TWIKIT_RETRYABLE = (TwitterException, TooManyRequests, RequestTimeout, ServerError)
        except ImportError:
            _TWIKIT_RETRYABLE = (Exception,)
    return _TWIKIT_RETRYABLE


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 5,
    backoff_base: float = 3.0,
    backoff_max: float = 120.0,
    label: str = "",
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    **kwargs: Any,
) -> T:
    """
    非同期関数をリトライする汎用ラッパー。

    Args:
        func: 呼び出す非同期関数
        *args: func への位置引数
        max_attempts: 最大試行回数
        backoff_base: 指数バックオフの底（秒）
        backoff_max: バックオフの上限（秒）
        label: ログ用ラベル
        retryable_exceptions: リトライ対象の例外クラスタプル（None で全例外）
        **kwargs: func へのキーワード引数

    Returns:
        func の戻り値

    Raises:
        最後に発生した例外
    """
    label = label or getattr(func, "__name__", str(func))
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if retryable_exceptions and not isinstance(e, retryable_exceptions):
                raise  # リトライ対象外はそのまま raise

            wait = min(backoff_base ** attempt, backoff_max)
            logger.warning(
                "[retry] %s 失敗 (attempt %d/%d): %s — %.1fs 後にリトライ",
                label, attempt, max_attempts, e, wait
            )
            last_exc = e

            if attempt < max_attempts:
                await asyncio.sleep(wait)

    raise last_exc  # type: ignore[misc]


async def retry_twikit(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 5,
    backoff_base: float = 5.0,
    label: str = "",
    **kwargs: Any,
) -> T:
    """
    twikit の API 呼び出しに特化したリトライラッパー。
    TooManyRequests 時は長めに待機する。
    """
    label = label or getattr(func, "__name__", str(func))
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            err_name = type(e).__name__
            # TooManyRequests は長く待つ
            if "TooManyRequests" in err_name or "RateLimitError" in err_name:
                wait = min(60.0 * attempt, 300.0)
            elif "Locked" in err_name or "Suspended" in err_name:
                logger.error("[retry_twikit] %s アカウントロック/凍結: %s", label, e)
                raise
            else:
                wait = min(backoff_base ** attempt, 120.0)

            logger.warning(
                "[retry_twikit] %s 失敗 (attempt %d/%d): %s — %.1fs 後にリトライ",
                label, attempt, max_attempts, e, wait
            )
            last_exc = e

            if attempt < max_attempts:
                await asyncio.sleep(wait)

    raise last_exc  # type: ignore[misc]
