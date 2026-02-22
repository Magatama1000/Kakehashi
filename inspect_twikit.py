from __future__ import annotations

import asyncio
import json
from pprint import pformat

from twikit import Client

# ============================================================
# 検証対象のツイートID（該当するものを入力、不要なものは空文字のまま）
# ============================================================

TWEET_ID_NORMAL      = "1969311281946464702"   # 通常ツイート（テキストのみ）
TWEET_ID_WITH_URL    = "2025541086572093550"   # URLを含むツイート
TWEET_ID_WITH_IMAGE  = "2025406091824431467"   # 画像を含むツイート
TWEET_ID_WITH_VIDEO  = "2021419809683259496"   # 動画を含むツイート
TWEET_ID_WITH_GIF    = "1970669938475163692"   # GIFを含むツイート
TWEET_ID_REPLY       = "2021510128378462546"   # 返信ツイート
TWEET_ID_RETWEET     = "2024674762417684951"   # リツイート
TWEET_ID_QUOTE       = "2021479314081055146"   # 引用ツイート

# 監視対象アカウントのスクリーンネーム（ユーザー情報の確認用）
SCREEN_NAME = "Blue_ArchiveJP"

# ============================================================

AUTH_FILE = "auth.json"


def dump(label: str, obj) -> None:
    """オブジェクトの全属性を見やすく出力する"""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    if obj is None:
        print("  (None)")
        return

    # __dict__ があればそれを使う
    if hasattr(obj, "__dict__"):
        attrs = {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    else:
        attrs = {}

    # よく使う属性を先に個別表示
    important = [
        "id", "text", "full_text", "created_at", "created_at_datetime",
        "user", "media", "urls", "entities",
        "retweeted_tweet", "quote", "in_reply_to",
        "profile_image_url", "profile_banner_url",
        "screen_name", "name",
        "pinned_tweet_ids",
        "type", "url", "expanded_url", "display_url",
        "media_url_https", "media_url", "variants",
        "bitrate", "content_type",
        "has_card", "card",
    ]

    printed = set()
    for key in important:
        if hasattr(obj, key):
            val = getattr(obj, key)
            print(f"  [{key}] = {repr(val)[:300]}")
            printed.add(key)

    # 残りの属性
    remaining = {k: v for k, v in attrs.items() if k not in printed}
    if remaining:
        print(f"\n  --- その他の属性 ---")
        for k, v in remaining.items():
            print(f"  [{k}] = {repr(v)[:200]}")


def dump_media(media_list) -> None:
    """メディアリストの詳細を出力する"""
    if not media_list:
        print("  メディア: なし")
        return
    print(f"  メディア: {len(media_list)} 件")
    for i, m in enumerate(media_list):
        print(f"\n  --- media[{i}] ---")
        print(f"  type(object) = {type(m)}")
        dump(f"media[{i}]", m)
        # variants がある場合は展開
        variants = getattr(m, "variants", None)
        if variants:
            print(f"  variants: {len(variants)} 件")
            for j, v in enumerate(variants):
                print(f"    variants[{j}]: type={type(v)}")
                dump(f"  variants[{j}]", v)


def dump_urls(urls) -> None:
    """URLエンティティの詳細を出力する"""
    if not urls:
        print("  urls: なし")
        return
    print(f"  urls: {len(urls)} 件")
    for i, u in enumerate(urls):
        print(f"\n  --- urls[{i}] ---")
        print(f"  type(object) = {type(u)}")
        dump(f"urls[{i}]", u)


async def inspect_tweet(client: Client, tweet_id: str, label: str) -> None:
    """指定ツイートIDの詳細を出力する"""
    print(f"\n{'#'*60}")
    print(f"# {label} (id={tweet_id})")
    print(f"{'#'*60}")
    try:
        tweet = await client.get_tweet_by_id(tweet_id)
        dump("Tweet", tweet)
        print(f"\n  --- media ---")
        dump_media(getattr(tweet, "media", None))
        print(f"\n  --- urls ---")
        dump_urls(getattr(tweet, "urls", None))

        # RTの場合
        rt = getattr(tweet, "retweeted_tweet", None)
        if rt:
            print(f"\n  --- retweeted_tweet ---")
            dump("retweeted_tweet", rt)
            dump_media(getattr(rt, "media", None))
            dump_urls(getattr(rt, "urls", None))

        # 引用の場合
        qt = getattr(tweet, "quote", None)
        if qt:
            print(f"\n  --- quote ---")
            dump("quote", qt)
            dump_media(getattr(qt, "media", None))
            dump_urls(getattr(qt, "urls", None))

    except Exception as e:
        print(f"  [ERROR] 取得失敗: {e}")
        import traceback
        traceback.print_exc()


async def inspect_user(client: Client, screen_name: str) -> None:
    """ユーザー情報の詳細を出力する"""
    print(f"\n{'#'*60}")
    print(f"# User: @{screen_name}")
    print(f"{'#'*60}")
    try:
        user = await client.get_user_by_screen_name(screen_name)
        dump("User", user)
    except Exception as e:
        print(f"  [ERROR] 取得失敗: {e}")
        import traceback
        traceback.print_exc()


async def main() -> None:
    # 認証
    with open(AUTH_FILE, "r", encoding="utf-8") as f:
        auth = json.load(f)

    client = Client(language="en-US")
    client.set_cookies(auth["twitter"])
    print("✓ twikit クライアント初期化完了")

    # ユーザー情報
    if SCREEN_NAME:
        await inspect_user(client, SCREEN_NAME)

    # 各ツイートパターン
    patterns = [
        (TWEET_ID_NORMAL,     "通常ツイート"),
        (TWEET_ID_WITH_URL,   "URLを含むツイート"),
        (TWEET_ID_WITH_IMAGE, "画像を含むツイート"),
        (TWEET_ID_WITH_VIDEO, "動画を含むツイート"),
        (TWEET_ID_WITH_GIF,   "GIFを含むツイート"),
        (TWEET_ID_REPLY,      "返信ツイート"),
        (TWEET_ID_RETWEET,    "リツイート"),
        (TWEET_ID_QUOTE,      "引用ツイート"),
    ]

    for tweet_id, label in patterns:
        if tweet_id:
            await inspect_tweet(client, tweet_id, label)

    print(f"\n{'='*60}")
    print("  検証完了")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())