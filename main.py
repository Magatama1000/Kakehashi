"""
X2Misskey メインエントリーポイント
設定を読み込み、複数アカウントペアを順次クロールして常駐する。
Python 3.11+ (tomllib 標準搭載) 対応。3.14 向けに from __future__ 注釈を使用。
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import time
import traceback
from pathlib import Path

# Python 3.11+ 標準搭載 tomllib
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        print("[ERROR] tomllib が利用できません。Python 3.11+ を使用してください。")
        sys.exit(1)

from twikit import Client

from lib.crawler import crawl_account
from lib.logger_setup import setup_logging

AUTH_FILE = "auth.json"
CONFIG_FILE = "config.toml"

logger = logging.getLogger(__name__)
stop_loop = False


def signal_handler(sig, frame) -> None:
    global stop_loop
    logger.info("終了シグナルを受け取りました。現在の処理が完了後に終了します...")
    stop_loop = True


def load_auth() -> dict:
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] {AUTH_FILE} が見つかりません。login.py を先に実行してください。")
        sys.exit(1)


def load_config() -> dict:
    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        print(f"[WARN] {CONFIG_FILE} が見つかりません。デフォルト設定を使用します。")
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)


async def setup_twitter_client(twitter_cookies: dict) -> Client:
    client = Client(language="en-US")
    client.set_cookies(twitter_cookies)
    return client


async def run_once(accounts: list, twitter_client: Client, config: dict) -> None:
    for account in accounts:
        if stop_loop:
            break
        try:
            await crawl_account(account, twitter_client, config)
        except Exception:
            logger.exception(
                "@%s のクロール中に予期せぬ例外が発生しました",
                account.get("twitter_screen_name", "?")
            )


async def main() -> None:
    global stop_loop

    # シグナル設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 設定・認証読み込み
    config = load_config()

    # ロギング設定（config より先に最低限の設定をしておく）
    setup_logging(config.get("log", {}))

    logger.info("=" * 50)
    logger.info("  X2Misskey 起動")
    logger.info("=" * 50)

    auth = load_auth()

    if "auth_token" not in auth.get("twitter", {}):
        logger.error("X (Twitter) の認証情報が不正です。login.py を再実行してください。")
        sys.exit(1)

    accounts: list = auth.get("accounts", [])
    if not accounts:
        logger.error("アカウントペアが登録されていません。login.py でアカウントを追加してください。")
        sys.exit(1)

    crawl_duration: int = config.get("crawl", {}).get("crawl_duration", 60)

    logger.info("監視アカウント数: %d", len(accounts))
    for acc in accounts:
        logger.info("  @%s → %s", acc["twitter_screen_name"], acc["misskey_url"])
    logger.info("クロール間隔: %ds", crawl_duration)

    Path("data").mkdir(exist_ok=True)

    # twikit クライアント初期化
    twitter_client = await setup_twitter_client(auth["twitter"])
    logger.info("X (Twitter) クライアント初期化完了")

    # メインループ
    while not stop_loop:
        import datetime
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S JST")
        logger.info("\n%s\nクロール開始: %s\n%s", "=" * 50, now, "=" * 50)

        await run_once(accounts, twitter_client, config)

        if stop_loop:
            break

        logger.info("次のクロールまで %ds 待機...", crawl_duration)
        for _ in range(crawl_duration):
            if stop_loop:
                break
            await asyncio.sleep(1)

    logger.info("終了しました。")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
