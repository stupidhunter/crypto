"""
CongDongCrypto News Bot
Chạy hằng ngày qua GitHub Actions — scrape RSS feeds và đẩy lên Supabase
"""
import os, feedparser, requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# ── NGUỒN QUỐC TẾ ────────────────────────────────────────────────────
FEEDS_INTL = [
    {"url": "https://feeds.feedburner.com/CoinDesk",             "name": "CoinDesk",      "cat": "Tin tức"},
    {"url": "https://cointelegraph.com/rss/tag/bitcoin",         "name": "CoinTelegraph", "cat": "Bitcoin"},
    {"url": "https://cointelegraph.com/rss/tag/ethereum",        "name": "CoinTelegraph", "cat": "DeFi"},
    {"url": "https://cointelegraph.com/rss/tag/altcoin",         "name": "CoinTelegraph", "cat": "Altcoin"},
    {"url": "https://decrypt.co/feed",                           "name": "Decrypt",       "cat": "Tin tức"},
    {"url": "https://cryptoslate.com/feed/",                     "name": "CryptoSlate",   "cat": "Tin tức"},
    {"url": "https://cryptopotato.com/feed/",                    "name": "CryptoPotato",  "cat": "Altcoin"},
    {"url": "https://ambcrypto.com/feed/",                       "name": "AMBCrypto",     "cat": "Tin tức"},
    {"url": "https://bitcoinist.com/feed/",                      "name": "Bitcoinist",    "cat": "Bitcoin"},
    {"url": "https://newsbtc.com/feed/",                         "name": "NewsBTC",       "cat": "Tin tức"},
]

# ── NGUỒN VIỆT NAM ────────────────────────────────────────────────────
# Các nguồn crypto/blockchain uy tín tại VN, có RSS hoạt động
FEEDS_VN = [
    # Blog Tiền Ảo — cộng đồng crypto lớn nhất VN (169K Facebook)
    {"url": "https://blogtienao.com/feed/",                      "name": "BlogTiềnẢo",    "cat": "Việt Nam"},
    # BitcoinVN News — sàn Bitcoin lâu đời nhất VN
    {"url": "https://bitcoinvn.io/news/feed/",                   "name": "BitcoinVN",     "cat": "Việt Nam"},
    # Tiền Ảo — tin tức crypto tiếng Việt
    {"url": "https://tienao.com/feed/",                          "name": "TiềnÁo.com",   "cat": "Việt Nam"},
    # CoinViet
    {"url": "https://coinviet.net/feed/",                        "name": "CoinViet",      "cat": "Việt Nam"},
    # Vietnam Blockchain — tin tức blockchain VN
    {"url": "https://vietnamblockchain.asia/feed/",              "name": "VN Blockchain", "cat": "Việt Nam"},
    # Coin68 — tin crypto tiếng Việt phổ biến
    {"url": "https://coin68.com/feed/",                          "name": "Coin68",        "cat": "Việt Nam"},
    # CafeF công nghệ — mảng fintech/crypto
    {"url": "https://cafef.vn/tai-chinh-ngan-hang.rss",          "name": "CafeF",         "cat": "Việt Nam"},
    # news.bitcoin.com tag vietnam
    {"url": "https://news.bitcoin.com/tag/vietnam/feed/",        "name": "Bitcoin News VN","cat": "Việt Nam"},
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
    print(f"  ✗ Lấy existing URLs lỗi: {res.status_code} {res.text[:100]}")
    return set()

def parse_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        ts = getattr(entry, field, None)
        if ts:
            try:
                dt = datetime(*ts[:6], tzinfo=timezone.utc)
                return dt.isoformat()
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

def scrape_feed(feed: dict, existing: set) -> int:
    print(f"\n→ {feed['name']} ({feed['url']})")
    try:
        parsed = feedparser.parse(feed["url"])
        status  = parsed.get("status", "N/A")
        entries = len(parsed.entries)
        print(f"  HTTP status: {status} | Entries: {entries}")
        if parsed.bozo:
            print(f"  Bozo warning: {parsed.bozo_exception}")
        if entries == 0:
            print("  ⚠ Không có entry — feed trống hoặc bị block")
            return 0
    except Exception as e:
        print(f"  ✗ Parse lỗi: {e}")
        return 0

    inserted = 0
    for entry in parsed.entries[:MAX_PER_FEED]:
        url = entry.get("link", "")
        if not url or url in existing:
            continue

        title = entry.get("title", "").strip()
        if not title:
            continue

        summary = entry.get("summary", "").strip()[:500]

        # Lấy ảnh từ media:content hoặc enclosures
        image_url = None
        media = entry.get("media_content", [])
        if media:
            image_url = media[0].get("url")
        if not image_url:
            for enc in entry.get("enclosures", []):
                if enc.get("type", "").startswith("image"):
                    image_url = enc.get("href") or enc.get("url")
                    break

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
            inserted += 1
            print(f"  ✓ {title[:70]}...")
        else:
            print(f"  ✗ Insert thất bại: {title[:40]}")

    return inserted

def main():
    print("=" * 60)
    print(f"CongDongCrypto Bot — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    existing = get_existing_urls()
    print(f"Đã có {len(existing)} bài trong DB")

    total_intl = 0
    print("\n📡 NGUỒN QUỐC TẾ")
    for feed in FEEDS_INTL:
        total_intl += scrape_feed(feed, existing)

    total_vn = 0
    print("\n🇻🇳 NGUỒN VIỆT NAM")
    for feed in FEEDS_VN:
        total_vn += scrape_feed(feed, existing)

    print(f"\n{'='*60}")
    print(f"✅ Hoàn thành — Quốc tế: {total_intl} bài | Việt Nam: {total_vn} bài")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
