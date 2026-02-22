"""Video/AnimatedGif の詳細構造を追加調査するスクリプト"""
import asyncio, json

from twikit import Client

TWEET_ID_VIDEO = "2021419809683259496"
TWEET_ID_GIF   = "1970669938475163692"
AUTH_FILE = "auth.json"

def deep_dump(obj, indent=0):
    prefix = "  " * indent
    if obj is None:
        print(f"{prefix}None")
        return
    print(f"{prefix}type = {type(obj)}")
    if hasattr(obj, "__dict__"):
        for k, v in vars(obj).items():
            if k.startswith("_"):
                continue
            print(f"{prefix}[{k}] = {repr(v)[:400]}")
            if hasattr(v, "__dict__") and not isinstance(v, type):
                deep_dump(v, indent+1)
            elif isinstance(v, list) and v:
                for i, item in enumerate(v[:5]):
                    print(f"{prefix}  [{k}][{i}]:")
                    deep_dump(item, indent+2)

async def main():
    with open(AUTH_FILE) as f:
        auth = json.load(f)
    client = Client(language="en-US")
    client.set_cookies(auth["twitter"])

    for tweet_id, label in [(TWEET_ID_VIDEO, "Video"), (TWEET_ID_GIF, "GIF")]:
        print(f"\n{'='*60}\n# {label} tweet_id={tweet_id}\n{'='*60}")
        tweet = await client.get_tweet_by_id(tweet_id)
        media_list = getattr(tweet, "media", []) or []
        for i, m in enumerate(media_list):
            print(f"\n--- media[{i}] deep dump ---")
            deep_dump(m)
            for attr in ["_data", "_json", "data", "video_info", "variants",
                         "additional_media_info", "source_status_id"]:
                if hasattr(m, attr):
                    print(f"  ** [{attr}] = {repr(getattr(m, attr))[:2000]}")

asyncio.run(main())
