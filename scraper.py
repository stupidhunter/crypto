"""
CongDongCrypto News Bot
Chạy 4 lần/ngày qua GitHub Actions — scrape RSS + gửi Telegram
"""
import os, feedparser, requests
from datetime import datetime, timezone

SUPABASE_URL        = os.environ["SUPABASE_URL"]
SUPABASE_KEY        = os.environ["SUPABASE_KEY"]
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

FEEDS_INTL = [
    {"url": "https://feeds.feedburner.com/CoinDesk",           "name": "CoinDesk",      "cat": "Tin tức"},
    {"url": "https://cointelegraph.com/rss/tag/bitcoin",       "name": "CoinTelegraph", "cat": "Bitcoin"},
    {"url": "https://cointelegraph.com/rss/tag/ethereum",      "name": "CoinTelegraph", "cat": "DeFi"},
    {"url": "https://cointelegraph.com/rss/tag/altcoin",       "name": "CoinTelegraph", "cat": "Altcoin"},
    {"url": "https://decrypt.co/feed",                         "name": "Decrypt",       "cat": "Tin tức"},
    {"url": "https://cryptoslate.com/feed/",                   "name": "CryptoSlate",   "cat": "Tin tức"},
    {"url": "https://cryptopotato.com/feed/",                  "name": "CryptoPotato",  "cat": "Altcoin"},
    {"url": "https://ambcrypto.com/feed/",                     "name": "AMBCrypto",     "cat": "Tin tức"},
    {"url": "https://bitcoinist.com/feed/",                    "name": "Bitcoinist",    "cat": "Bitcoin"},
    {"url": "https://newsbtc.com/feed/",                       "name": "NewsBTC",       "cat": "Tin tức"},
]

FEEDS_VN = [
    {"url": "https://blogtienao.com/feed/",                    "name": "BlogTiềnẢo",    "cat": "Việt Nam"},
    {"url": "https://bitcoinvn.io/news/feed/",                 "name": "BitcoinVN",     "cat": "Việt Nam"},
    {"url": "https://tienao.com/feed/",                        "name": "TiềnÁo.com",   "cat": "Việt Nam"},
    {"url": "https://coinviet.net/feed/",                      "name": "CoinViet",      "cat": "Việt Nam"},
    {"url": "https://vietnamblockchain.asia/feed/",            "name": "VN Blockchain", "cat": "Việt Nam"},
    {"url": "https://coin68.com/feed/",                        "name": "Coin68",        "cat": "Việt Nam"},
    {"url": "https://cafef.vn/tai-chinh-ngan-hang.rss",        "name": "CafeF",         "cat": "Việt Nam"},
    {"url": "https://news.bitcoin.com/tag/vietnam/feed/",      "name": "Bitcoin News VN","cat": "Việt Nam"},
]

FEEDS = FEEDS_INTL + FEEDS_VN
MAX_PER_FEED = 5

feedparser.USER_AGENT = "Mozilla/5.0 (compatible; CongDongCryptoBot/1.0)"

def get_existing_urls() -> set:
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/articles",
        headers=HEADERS,
        params={"select": "source_url", "limit": 2000}
    )
    if res.ok:
        return {row["source_url"] for row in res.json()}
    print(f"  ✗ Lấy existing URLs lỗi: {res.status_code}")
    return set()

def parse_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        ts = getattr(entry, field, None)
        if ts:
            try:
                return datetime(*ts[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()

def insert_article(article: dict) -> bool:
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/articles",
        headers={**HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
        json=article,
    )
    return res.status_code in (200, 201)

def scrape_feed(feed: dict, existing: set) -> list:
    """Trả về list bài mới insert được"""
    print(f"\n→ {feed['name']} ({feed['url']})")
    new_articles = []
    try:
        parsed  = feedparser.parse(feed["url"])
        status  = parsed.get("status", "N/A")
        entries = len(parsed.entries)
        print(f"  HTTP: {status} | Entries: {entries}")
        if entries == 0:
            return []
    except Exception as e:
        print(f"  ✗ Lỗi: {e}")
        return []

    for entry in parsed.entries[:MAX_PER_FEED]:
        url   = entry.get("link", "")
        title = entry.get("title", "").strip()
        if not url or not title or url in existing:
            continue

        summary   = entry.get("summary", "").strip()[:500]
        image_url = None
        for m in entry.get("media_content", []):
            image_url = m.get("url"); break
        if not image_url:
            for enc in entry.get("enclosures", []):
                if enc.get("type", "").startswith("image"):
                    image_url = enc.get("href") or enc.get("url"); break

        article = {
            "title":        title,
            "summary":      summary,
            "content":      None,
            "source_url":   url,
            "source_name":  feed["name"],
            "category":     feed["cat"],
            "image_url":    image_url,
            "author":       entry.get("author", None),
            "published_at": parse_date(entry),
        }

        if insert_article(article):
            existing.add(url)
            new_articles.append(article)
            print(f"  ✓ {title[:70]}...")
        else:
            print(f"  ✗ Insert thất bại: {title[:40]}")

    return new_articles

def send_telegram(articles: list):
    """Gửi điểm tin lên Telegram channel"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n⚠ Không có Telegram config, bỏ qua.")
        return
    if not articles:
        print("\n📭 Không có bài mới để gửi Telegram.")
        return

    now  = datetime.now().strftime("%d/%m/%Y %H:%M")
    text = f"🚀 *ĐIỂM TIN CRYPTO* — {now}\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Gửi tối đa 6 bài, ưu tiên Việt Nam lên đầu
    vn   = [a for a in articles if a.get("category") == "Việt Nam"]
    intl = [a for a in articles if a.get("category") != "Việt Nam"]
    top  = (vn + intl)[:6]

    cat_emoji = {
        "Bitcoin":  "₿",
        "DeFi":     "⬡",
        "Altcoin":  "◎",
        "Việt Nam": "🇻🇳",
        "Tin tức":  "📰",
    }

    for i, a in enumerate(top, 1):
        emoji = cat_emoji.get(a.get("category"), "🌐")
        text += f"{emoji} *{a['title'][:80]}*\n"
        if a.get("summary"):
            text += f"_{a['summary'][:120]}..._\n"
        text += f"🔗 [Đọc tiếp]({a['source_url']}) — {a['source_name']}\n\n"

    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "📊 [Xem thêm tại CộngĐồngCrypto](https://cryptocommunity-rose.vercel.app)"

    res = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id":                  TELEGRAM_CHAT_ID,
            "text":                     text,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=10,
    )

    if res.ok:
        print(f"\n✅ Đã gửi Telegram — {len(top)} bài")
    else:
        print(f"\n✗ Telegram lỗi: {res.status_code} {res.text[:100]}")

def main():
    print("=" * 60)
    print(f"CongDongCrypto Bot — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    existing     = get_existing_urls()
    print(f"Đã có {len(existing)} bài trong DB")

    all_new = []

    print("\n📡 NGUỒN QUỐC TẾ")
    for feed in FEEDS_INTL:
        all_new.extend(scrape_feed(feed, existing))

    print("\n🇻🇳 NGUỒN VIỆT NAM")
    for feed in FEEDS_VN:
        all_new.extend(scrape_feed(feed, existing))

    print(f"\n{'='*60}")
    print(f"✅ Hoàn thành — đã thêm {len(all_new)} bài mới")
    print(f"{'='*60}")

    # Gửi Telegram nếu có bài mới
    send_telegram(all_new)

if __name__ == "__main__":
    main()
