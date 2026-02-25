"""
認証セットアップスクリプト
Xアカウント（共通1つ）とMisskeyアカウント（複数）の認証情報を
auth.json に保存する。

X認証の方法:
  1. twikit login()  ... フォーク版で修正済み。通常はこちらを使う。
  2. Cookie手動入力  ... login() が壊れたときのフォールバック。
                         ブラウザの開発者ツールから auth_token / ct0 を取得する。
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
import uuid
from getpass import getpass
from urllib.parse import urlencode

import httpx
from twikit import Client

AUTH_FILE = "auth.json"

MISSKEY_PERMISSIONS = [
    "write:notes",
    "write:drive",
    "write:account",
]


# ------------------------------------------------------------------ #
# Misskey MiAuth（httpx 直接実装）
# ------------------------------------------------------------------ #

def misskey_auth() -> tuple[str, str]:
    """MiAuth フローで Misskey アクセストークンを取得する"""
    print("\n--- Misskey 認証 ---")
    print("認証前に、投稿先アカウントでログインした状態でブラウザを開いてください。\n")

    misskey_url = input("Misskey ドメイン (例: misskey.io): ").strip().rstrip("/")
    while not misskey_url:
        misskey_url = input("ドメインは必須です: ").strip().rstrip("/")

    if not misskey_url.startswith("http"):
        misskey_url = f"https://{misskey_url}"

    session = str(uuid.uuid4())
    params = urlencode({
        "name": "Kakehashi-bot",
        "permission": ",".join(MISSKEY_PERMISSIONS),
    })
    auth_url = f"{misskey_url}/miauth/{session}?{params}"

    print(f"\n以下のURLをブラウザで開き、認証を許可してください:\n\n  {auth_url}\n")

    if sys.platform == "win32":
        import subprocess
        subprocess.call("PAUSE", shell=True)
    else:
        input("認証を完了したら Enter を押してください...")

    check_url = f"{misskey_url}/api/miauth/{session}/check"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(check_url, json={})
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Misskey トークン取得失敗 (HTTP {e.response.status_code}): {e.response.text}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Misskey トークン取得失敗: {e}") from e

    if not result.get("ok"):
        raise RuntimeError(f"Misskey 認証が拒否されました: {result}")

    token: str = result.get("token", "")
    if not token:
        raise RuntimeError(f"トークンが空です。レスポンス: {result}")

    host = misskey_url.removeprefix("https://").removeprefix("http://")

    # 認証したユーザー名を取得して表示
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"https://{host}/api/i",
                json={"i": token},
            )
            resp.raise_for_status()
            mk_username = resp.json().get("username", "?")
        print(f"✓ Misskey 認証成功: @{mk_username}@{host}\n")
    except Exception:
        print("✓ Misskey 認証成功\n")

    return host, token


# ------------------------------------------------------------------ #
# X (Twitter) 認証 — 方法1: twikit login()
# ------------------------------------------------------------------ #

async def twitter_auth_login() -> dict:
    """
    twikit の login() でXにログインし Cookie を返す。
    フォーク版では修正済み。公式版が壊れている場合は twitter_auth_cookie() を使う。
    """
    print("\n--- X (Twitter) 認証 [login() 方式] ---")
    print("何が起きてもいいサプアカウントの利用を強く推奨します！\n")

    client = Client(language="en-US")

    auth_info = input("ユーザー名 / メールアドレス / 電話番号: ").strip()
    while not auth_info:
        auth_info = input("IDは必須です: ").strip()

    password = getpass("パスワード（入力は非表示）: ")
    while not password:
        password = getpass("パスワードは必須です: ")

    await client.login(auth_info_1=auth_info, password=password)
    cookies = client.get_cookies()
    print("✓ X (Twitter) login() 認証成功\n")
    return cookies


# ------------------------------------------------------------------ #
# X (Twitter) 認証 — 方法2: Cookie 手動入力
# ------------------------------------------------------------------ #

async def twitter_auth_cookie() -> dict:
    """
    ブラウザの開発者ツールから Cookie を手動入力して認証情報を返す。
    twikit の login() が動作しないときのフォールバック。

    取得手順:
      1. ブラウザで https://x.com にログイン
      2. 開発者ツールを開く (F12 または Ctrl+Shift+I)
      3. [Application] タブ → [Cookies] → [https://x.com]
      4. auth_token と ct0 の値をコピーする
    """
    print("\n--- X (Twitter) 認証 [Cookie 手動入力方式] ---")
    print("何が起きてもいいサプアカウントの利用を強く推奨します！\n")
    print("ブラウザの開発者ツールから Cookie を取得して入力してください。")
    print()
    print("取得手順:")
    print("  1. ブラウザで https://x.com にログイン")
    print("  2. 開発者ツール (F12) → [Application] → [Cookies] → [https://x.com]")
    print("  3. auth_token（約40文字）と ct0（約160文字）をコピー")
    print()

    auth_token = input("auth_token: ").strip()
    while not auth_token:
        auth_token = input("auth_token は必須です: ").strip()

    ct0 = input("ct0: ").strip()
    while not ct0:
        ct0 = input("ct0 は必須です: ").strip()

    cookies = {
        "auth_token": auth_token,
        "ct0": ct0,
    }
    print("✓ X (Twitter) Cookie を保存します\n")
    return cookies


# ------------------------------------------------------------------ #
# auth.json の読み書き
# ------------------------------------------------------------------ #

def load_auth() -> dict:
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_auth(data: dict) -> None:
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"✓ {AUTH_FILE} に保存しました\n")


# ------------------------------------------------------------------ #
# X 認証メニュー
# ------------------------------------------------------------------ #

async def twitter_auth_menu() -> dict | None:
    """X 認証方法の選択メニュー"""
    print("\nX (Twitter) の認証方法を選択してください:")
    print("  1. twikit login()  （推奨: フォーク版で動作確認済み）")
    print("  2. Cookie 手動入力 （login() が動作しない場合のフォールバック）")
    choice = input("選択 (1/2): ").strip()

    if choice == "1":
        try:
            return await twitter_auth_login()
        except Exception as e:
            print(f"\n[ERROR] login() 認証に失敗しました: {e}")
            retry = input("Cookie 手動入力に切り替えますか？ (y/N): ").strip().lower()
            if retry == "y":
                return await twitter_auth_cookie()
            return None
    elif choice == "2":
        return await twitter_auth_cookie()
    else:
        print("1 か 2 を入力してください")
        return None


# ------------------------------------------------------------------ #
# メイン
# ------------------------------------------------------------------ #

async def main() -> None:
    print("=" * 50)
    print("  Kakehashi-bot 認証セットアップ")
    print("=" * 50)

    data = load_auth()

    # ---- X 認証（共通1アカウント） ----
    if "auth_token" in data.get("twitter", {}):
        print("✓ X (Twitter) の認証情報が既に存在します")
        refresh = input("再認証しますか？ (y/N): ").strip().lower()
        if refresh == "y":
            try:
                result = await twitter_auth_menu()
                if result:
                    data["twitter"] = result
            except Exception:
                traceback.print_exc()
                print("X認証に失敗しました。既存の情報を維持します。")
        else:
            print("スキップ\n")
    else:
        try:
            result = await twitter_auth_menu()
            if result:
                data["twitter"] = result
        except Exception:
            traceback.print_exc()
            print("X認証に失敗しました。Misskeyの設定だけ続けます。")

    # ---- Misskey アカウントペアの管理 ----
    accounts: list = data.get("accounts", [])

    print(f"\n現在登録されているアカウントペア: {len(accounts)} 件")
    for i, acc in enumerate(accounts):
        print(f"  [{i+1}] @{acc['twitter_screen_name']} → {acc['misskey_url']}")

    while True:
        print("\nアカウントペアの操作:")
        print("  1. 新しいアカウントペアを追加")
        print("  2. アカウントペアを削除")
        print("  3. 設定を保存して終了")
        choice = input("選択 (1/2/3): ").strip()

        if choice == "1":
            print("\n--- 新しいアカウントペアを追加 ---")

            twitter_screen_name = input("X のスクリーンネーム (@なし): ").strip().lstrip("@")
            while not twitter_screen_name:
                twitter_screen_name = input("スクリーンネームは必須です: ").strip().lstrip("@")

            if any(a["twitter_screen_name"] == twitter_screen_name for a in accounts):
                print(f"@{twitter_screen_name} は既に登録されています。Misskeyの情報を上書きします。")
                accounts = [a for a in accounts if a["twitter_screen_name"] != twitter_screen_name]

            try:
                misskey_host, misskey_token = misskey_auth()
            except Exception:
                traceback.print_exc()
                print("Misskey認証に失敗しました。スキップします。")
                continue

            accounts.append({
                "twitter_screen_name": twitter_screen_name,
                "misskey_url": misskey_host,
                "misskey_token": misskey_token,
            })
            print(f"✓ @{twitter_screen_name} → {misskey_host} を追加しました")

        elif choice == "2":
            if not accounts:
                print("削除できるアカウントペアがありません")
                continue
            for i, acc in enumerate(accounts):
                print(f"  [{i+1}] @{acc['twitter_screen_name']} → {acc['misskey_url']}")
            idx_str = input("削除する番号: ").strip()
            try:
                idx = int(idx_str) - 1
                removed = accounts.pop(idx)
                print(f"✓ @{removed['twitter_screen_name']} を削除しました")
            except (ValueError, IndexError):
                print("無効な番号です")

        elif choice == "3":
            break
        else:
            print("1, 2, 3 のいずれかを入力してください")

    data["accounts"] = accounts
    save_auth(data)
    print("セットアップ完了！ main.py を実行してください。")


if __name__ == "__main__":
    asyncio.run(main())