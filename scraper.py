"""
CongDongCrypto News Bot
Chạy hằng ngày qua GitHub Actions — scrape RSS feeds và đẩy lên Supabase
"""
import os, feedparser, requests, hashlib
from datetime import datetime, timezone
from newspaper import Article

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# ── Nguồn RSS crypto (thêm/bớt tùy ý) ──────────────────────────────────────
FEEDS = [
    {"url": "https://cointelegraph.com/rss",           "name": "CoinTelegraph", "cat": "Tin tức"},
    {"url": "https://coindesk.com/arc/outboundfeeds/rss/", "name": "CoinDesk", "cat": "Tin tức"},
    {"url": "https://decrypt.co/feed",                 "name": "Decrypt",      "cat": "Tin tức"},
    {"url": "https://bitcoinmagazine.com/.rss/full/",  "name": "Bitcoin Mag",  "cat": "Bitcoin"},
    {"url": "https://thedefiant.io/feed",              "name": "The Defiant",  "cat": "DeFi"},
    {"url": "https://www.cryptopolitan.com/feed/",     "name": "Cryptopolitan","cat": "Altcoin"},
    # Nguồn Việt Nam
    {"url": "https://tienao.com/feed/",                "name": "TiềnÁo.com",   "cat": "Việt Nam"},
    {"url": "https://coinviet.net/feed",               "name": "CoinViet",     "cat": "Việt Nam"},
]

MAX_PER_FEED = 5  # Số bài tối đa mỗi nguồn mỗi lần chạy

def get_existing_urls() -> set:
    """Lấy danh sách URL đã có trong DB để tránh trùng"""
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/articles",
        headers=HEADERS,
        params={"select": "source_url", "limit": 1000}
    )
    if res.ok:
        return {row["source_url"] for row in res.json()}
    return set()

def extract_full_article(url: str) -> dict:
    """Dùng newspaper3k để lấy full text và ảnh"""
    try:
        art = Article(url, language="en")
        art.download()
        art.parse()
        return {
            "content": art.text[:5000] if art.text else None,
            "image_url": art.top_image or None,
            "author": ", ".join(art.authors) if art.authors else None,
        }
    except Exception:
        return {"content": None, "image_url": None, "author": None}

def parse_date(entry) -> str:
    """Parse published date từ RSS entry"""
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
    """Insert 1 bài vào Supabase, trả về True nếu thành công"""
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/articles",
        headers={**HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
        json=article,
    )
    return res.status_code in (200, 201)

def scrape_feed(feed: dict, existing: set) -> int:
    """Scrape 1 RSS feed, trả về số bài đã insert"""
    print(f"\n→ {feed['name']} ({feed['url']})")
    try:
        parsed = feedparser.parse(feed["url"])
    except Exception as e:
        print(f"  ✗ Parse lỗi: {e}")
        return 0

    inserted = 0
    for entry in parsed.entries[:MAX_PER_FEED]:
        url = entry.get("link", "")
        if not url or url in existing:
            continue

        title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()[:500]
        if not title:
            continue

        # Lấy full content nếu summary quá ngắn
        extra = {}
        if len(summary) < 100:
            extra = extract_full_article(url)
        else:
            extra = {"content": None, "image_url": None, "author": None}

        # Thử lấy ảnh từ media:content trong RSS
        image_url = extra.get("image_url")
        if not image_url:
            media = entry.get("media_content", [])
            if media:
                image_url = media[0].get("url")

        article = {
            "title":        title,
            "summary":      summary or extra.get("content", "")[:400],
            "content":      extra.get("content"),
            "source_url":   url,
            "source_name":  feed["name"],
            "category":     feed["cat"],
            "image_url":    image_url,
            "author":       extra.get("author"),
            "published_at": parse_date(entry),
        }

        if insert_article(article):
            existing.add(url)
            inserted += 1
            print(f"  ✓ {title[:60]}...")

    return inserted

def main():
    print("=" * 60)
    print(f"CongDongCrypto Bot — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    existing = get_existing_urls()
    print(f"Đã có {len(existing)} bài trong DB")

    total = 0
    for feed in FEEDS:
        total += scrape_feed(feed, existing)

    print(f"\n✅ Hoàn thành — đã thêm {total} bài mới")

if __name__ == "__main__":
    main()
