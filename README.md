# Kakehashi-bot

X (Twitter) の指定アカウントの投稿を Misskey に自動転載するボットです。

## 注意事項
- Xの非公式API(Web版のAPI)を利用するtwikitを採用しています。**自己責任下**でご利用ください。  
そのため、メインアカウントの利用はなるべく避けることを強く推奨します。

- ご利用になるMisskeyインスタンスの規約に沿い、過剰投稿を避け、アカウントをbot指定してください。NSFWに注意してください。
- ノート投稿が連続3回失敗したツイートはスキップされます。
- クロール間隔は120~300秒以上を推奨します。

## 必要環境

- Python 3.11 以上（3.13 / 3.14 推奨）
- [uv](https://docs.astral.sh/uv/)（パッケージ管理）
- [FFmpeg](https://ffmpeg.org/)（動画・GIF処理）

---

## セットアップ

### 1. uv のインストール

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 依存パッケージのインストール

```bash
uv sync
```

### 3. FFmpeg のインストール

```powershell
# Windows（winget）
winget install Gyan.FFmpeg
```

```bash
# macOS（Homebrew）
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 4. 認証情報の設定

```bash
uv run python login.py
```

X (Twitter) の認証と Misskey の MiAuth 認証を対話形式で設定します。  
`auth.json` が生成されます（`.gitignore` 済み。**絶対にコミットしないこと**）。

#### X (Twitter) の認証方法について

login.py 起動時に以下の2つから選択できます。

**方法1: twikit login()（推奨）**  
ユーザー名・パスワードを入力してログインします。  
現在使用しているフォーク版 twikit では動作確認済みです。

**方法2: Cookie 手動入力（フォールバック）**  
twikit のアップデートで `login()` が壊れた際のフォールバックです。  
ブラウザの開発者ツールから Cookie を直接コピーして入力します。

| Cookie名 | 場所 | 説明 |
|----------|------|------|
| `auth_token` | F12 → Application → Cookies → https://x.com | 約40文字 |
| `ct0` | 同上 | 約160文字 |

> `login()` に失敗した場合、自動的に方法2への切り替えを提案します。

### 5. 設定の編集

`config_default.toml`をコピーして`config.toml`にリネームしてください。  
`config.toml` を編集します（各項目にコメントあり）。

特にNSFW周りに注意してください。掲載画像に少しでも含まれる場合は、すべてNSFWとして投稿することを推奨します。

### 6. 起動テスト

```bash
uv run python main.py
```

---

## 自動起動の設定

### Windows — タスクスケジューラ

ログオン不要でバックグラウンド常駐させる場合は**タスクスケジューラ**を使います。

#### 設定手順

1. **タスクスケジューラ**を開く（スタートメニューで検索）
2. 右ペインの「**タスクの作成**」をクリック
3. 各タブを以下のように設定する：

**全般タブ**
- 名前: `Kakehashi-bot`
- 「ユーザーがログオンしているかどうかにかかわらず実行する」を選択
- 「最上位の特権で実行する」にチェック

**トリガータブ**  
「新規」→「タスクの開始: コンピューターの起動時」

**操作タブ**  
「新規」→ 以下を入力：

| 項目 | 値 |
|------|-----|
| プログラム/スクリプト | `C:\Users\<ユーザー名>\.local\bin\uv.exe` |
| 引数の追加 | `run python main.py` |
| 開始（オプション） | プロジェクトのフルパス（例: `D:\x2m\Kakehashi-bot`） |

**設定タブ**
- 「タスクを停止するまでの時間」のチェックを外す
- 「タスクが失敗した場合の再起動の間隔」: 1分（任意）

4. OK → パスワード入力で完了

#### ログの確認・操作

```powershell
# ログをリアルタイムで確認
Get-Content x2misskey.log -Wait -Tail 50

# 手動起動
schtasks /Run /TN "Kakehashi-bot"

# 手動停止
schtasks /End /TN "Kakehashi-bot"
```

---

### Linux — systemd

systemd サービスとして登録することでシステム起動時に自動起動します。

#### サービスファイルの作成

```bash
sudo nano /etc/systemd/system/Kakehashi-bot.service
```

以下を記述（`youruser` とパスは環境に合わせて変更）：

```ini
[Unit]
Description=Kakehashi-bot - X to Misskey crosspost bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/Kakehashi-bot
ExecStart=/home/youruser/.local/bin/uv run python main.py
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### 有効化と起動

```bash
# サービスを登録・有効化
sudo systemctl daemon-reload
sudo systemctl enable Kakehashi-bot
sudo systemctl start Kakehashi-bot

# 状態確認
sudo systemctl status Kakehashi-bot

# ログの確認（リアルタイム）
sudo journalctl -u Kakehashi-bot -f
```

#### 手動での停止・再起動

```bash
sudo systemctl stop Kakehashi-bot
sudo systemctl restart Kakehashi-bot
```

---

## ファイル構成

```
Kakehashi-bot/
├── main.py               # エントリーポイント・常駐ループ
├── login.py              # 認証セットアップ（対話式）
├── config.toml           # 動作設定
├── pyproject.toml        # uv 用パッケージ定義
├── auth.json             # 認証情報（自動生成・gitignore済み）
├── lib/
│   ├── crawler.py        # クロール・投稿ロジック
│   ├── ffmpeg.py         # FFmpeg 非同期ラッパー（進捗ログ付き）
│   ├── logger_setup.py   # ロギング設定
│   ├── media.py          # メディア処理（非同期）
│   ├── misskey_client.py # Misskey API 独自実装クライアント
│   ├── retry.py          # リトライユーティリティ
│   └── text.py           # テキスト処理（URL展開・MFM変換）
└── data/                 # 自動生成・gitignore済み
    ├── state_{name}.json # アカウントごとの処理状態
    └── id_data.db        # tweet_id ↔ note_id マッピング（SQLite）
```

## config.toml 主な設定

| セクション | キー | 説明 |
|-----------|------|------|
| `[crawl]` | `crawl_duration` | クロール間隔（秒） |
| `[note]` | `retweet` | RTを転載するか |
| `[note]` | `visibility` | 公開範囲 public/home/followers |
| `[note]` | `mfm_mention` | @メンションをMFMリンクに変換 |
| `[media]` | `video_encode` | 動画エンコード copy/x265 |
| `[media]` | `pic_encode_avif` | 静止画をAVIF変換 |
| `[nsfw]` | `nsfw_forced` | 全メディアに強制NSFW |
| `[nsfw]` | `nsfw_forced_video` | 動画・GIFに強制NSFW |
| `[log]` | `level` | DEBUG/INFO/WARNING/ERROR |
| `[log]` | `file` | ログファイルパス |
