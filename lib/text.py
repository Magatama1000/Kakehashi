"""
テキスト処理モジュール
- URL展開: twikit の Tweet.urls（XのAPIデータ）から展開済みURLを取得する
  → requests で t.co を叩かないため弾かれない
- @メンションのMFMリンク化
- HTMLエンティティのデコード
"""

from __future__ import annotations

import html
import logging
import re

logger = logging.getLogger(__name__)


def expand_urls_from_entities(text: str, urls: list | None, url_cleaner=None) -> str:
    """
    twikit の Tweet.urls から展開済みURLを使って t.co を置換する。
    url_cleaner が指定された場合、展開後のURLにトラッキングパラメーター削除を適用する。
    X API から取れない t.co が残った場合はそのまま残す。
    """
    if not urls:
        return text

    for entity in urls:
        if isinstance(entity, dict):
            short = entity.get("url", "")
            expanded = entity.get("expanded_url", "")
        else:
            short = getattr(entity, "url", "")
            expanded = getattr(entity, "expanded_url", "")

        if short and expanded and short in text:
            if url_cleaner is not None:
                try:
                    cleaned = url_cleaner.clean(expanded)
                    if cleaned != expanded:
                        logger.debug("url-cleaner: %s → %s", expanded, cleaned)
                    expanded = cleaned
                except Exception as e:
                    logger.debug("url-cleaner 失敗 (%s): %s", expanded, e)
            text = text.replace(short, expanded)
            logger.debug("URL展開: %s → %s", short, expanded)

    return text


def remove_media_tco(text: str) -> str:
    """末尾の t.co（メディア添付時に残るもの）を除去する"""
    return re.sub(r"\s*https://t\.co/\S+$", "", text).rstrip()


def remove_quote_url(text: str, quote_tweet_id: str) -> str:
    """引用ツイートのURLを本文から除去する"""
    text = re.sub(
        rf"\s*https://twitter\.com/\S+/status/{re.escape(quote_tweet_id)}\S*",
        "", text
    )
    text = re.sub(
        rf"\s*https://x\.com/\S+/status/{re.escape(quote_tweet_id)}\S*",
        "", text
    )
    return text.rstrip()


def replace_mentions(text: str) -> str:
    """
    @mention を MFM リンク形式に変換する。

    処理順:
      1. Fediverse メンション @user@host を <plain> で保護
      2. 変換済み MFM リンク ?[@xxx](...) 内の @ を一時エスケープ（二重変換防止）
      3. 通常 @mention → ?[@xxx](https://x.com/xxx) に変換
      4. エスケープを元に戻す
    """
    # Step1: Fediverse メンション @user@host を先に plain 化
    text = re.sub(
        r"(?<![a-zA-Z0-9_])@([a-zA-Z0-9_]+)@([a-zA-Z0-9._-]+\.[a-zA-Z]{2,})",
        lambda m: f"<plain>{m.group(0)}</plain>",
        text,
    )
    # Step2: 変換済み MFM リンク内の @xxx を一時エスケープ（二重変換防止）
    placeholders: dict[str, str] = {}

    def _escape_mfm(m: re.Match) -> str:
        key = f"MFM{len(placeholders)}"
        placeholders[key] = m.group(0)
        return key

    text = re.sub(r"\?\[(@[a-zA-Z0-9_]+)\]\(https?://[^\)]+\)", _escape_mfm, text)

    # Step3: 通常 @mention → MFM リンク
    # 後読み: 英数字・_・@ の直後でなければ変換（文頭・括弧・記号等はOK）
    # 先読み: 英数字・_・@ が続かなければ変換
    text = re.sub(
        r"(?<![a-zA-Z0-9_@])\B@([a-zA-Z0-9_]{1,50})(?![a-zA-Z0-9_@])",
        lambda m: f"?[@{m.group(1)}](https://x.com/{m.group(1)})",
        text,
    )

    # Step4: プレースホルダーを元に戻す
    for key, val in placeholders.items():
        text = text.replace(key, val)

    return text


def decode_html_entities(text: str) -> str:
    return html.unescape(text)


def normalize_hashtags(text: str) -> str:
    """
    ハッシュタグの全角シャープ・全角英数字を半角に変換する。
    Xは全角ハッシュタグ（＃タグ）を受け付けるが、Misskeyは半角(#)のみ対応。

    unicodedata.normalize(NFKC) で全角→半角変換を行う。
    ひらがな・カタカナ・漢字は NFKC でも変化しないため日本語タグは保持される。

    例: ＃ブルアカ    → #ブルアカ
        ＃BlueArchive → #BlueArchive
        #通常タグ     → #通常タグ  （変化なし）
    """
    import unicodedata

    def _replace(m: re.Match) -> str:
        # タグ全体（＃ + 本文）を NFKC 正規化して全角→半角
        return unicodedata.normalize("NFKC", m.group(0))

    # ＃（U+FF03 全角シャープ）で始まるタグを対象
    return re.sub(r"＃\S+", _replace, text)


def build_tweet_url(screen_name: str, tweet_id: str) -> str:
    return f"https://x.com/{screen_name}/status/{tweet_id}"


def append_tweet_link(text: str, tweet_url: str, suppress_preview: bool = True) -> str:
    if suppress_preview:
        return f"{text}\nX : ?[{tweet_url}]({tweet_url})"
    else:
        return f"{text}\nX : {tweet_url}"


def process_tweet_text(
    text: str,
    screen_name: str,
    tweet_id: str,
    urls: list | None = None,
    mfm_mention: bool = True,
    mfm_tweeturl: bool = True,
    url_cleaner=None,
    is_rt_text: bool = False,
) -> str:
    """ツイートテキストの一連の処理を実行する"""
    tweet_url = build_tweet_url(screen_name, tweet_id)
    text = decode_html_entities(text)
    text = normalize_hashtags(text)
    text = remove_media_tco(text)
    text = expand_urls_from_entities(text, urls, url_cleaner=url_cleaner)
    if mfm_mention and not is_rt_text:
        text = replace_mentions(text)
    if mfm_tweeturl:
        text = append_tweet_link(text, tweet_url, suppress_preview=True)
    else:
        text = append_tweet_link(text, tweet_url, suppress_preview=False)
    return text


def process_rt_text(
    rt_screen_name: str,
    rt_text: str,
    rt_urls: list | None = None,
    mfm_mention: bool = True,
    url_cleaner=None,
) -> str:
    """RT 用テキストの処理"""
    rt_text = decode_html_entities(rt_text)
    rt_text = normalize_hashtags(rt_text)
    rt_text = remove_media_tco(rt_text)
    rt_text = expand_urls_from_entities(rt_text, rt_urls, url_cleaner=url_cleaner)
    if mfm_mention:
        rt_text = replace_mentions(rt_text)
    return f"RT ?[@{rt_screen_name}](https://x.com/{rt_screen_name}): {rt_text}"


def process_quote_text(
    qt_screen_name: str,
    qt_text: str,
    qt_urls: list | None = None,
    mfm_mention: bool = True,
    url_cleaner=None,
) -> str:
    """引用ツイート埋め込み用テキストの処理"""
    qt_text = decode_html_entities(qt_text)
    qt_text = normalize_hashtags(qt_text)
    qt_text = remove_media_tco(qt_text)
    qt_text = expand_urls_from_entities(qt_text, qt_urls, url_cleaner=url_cleaner)
    if mfm_mention:
        qt_text = replace_mentions(qt_text)
    return f"QT ?[@{qt_screen_name}](https://x.com/{qt_screen_name}): {qt_text}"