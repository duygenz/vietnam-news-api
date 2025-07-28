# main.py

import asyncio
import feedparser
import httpx
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# --- Configuration ---
# List of RSS feeds to aggregate
RSS_FEEDS = {
    "CafeF - Thị trường Chứng khoán": "https://cafef.vn/thi-truong-chung-khoan.rss",
    "VnEconomy - Chứng khoán": "https://vneconomy.vn/chung-khoan.rss",
    "VnEconomy - Tài chính": "https://vneconomy.vn/tai-chinh.rss",
    "VnEconomy - Thị trường": "https://vneconomy.vn/thi-truong.rss",
    "VnEconomy - Nhịp cầu Doanh nghiệp": "https://vneconomy.vn/nhip-cau-doanh-nghiep.rss",
    "VnEconomy - Tin mới": "https://vneconomy.vn/tin-moi.rss",
}

# --- In-memory Cache ---
# This dictionary will store our fetched news articles.
news_cache = {"articles": [], "last_updated": datetime.now(timezone.utc)}

async def fetch_single_feed(name: str, url: str, client: httpx.AsyncClient):
    """Fetches and parses a single RSS feed."""
    articles = []
    try:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
        
        feed = feedparser.parse(response.text)
        for entry in feed.entries:
            articles.append({
                "source_name": name,
                "title": entry.get("title", "N/A"),
                "link": entry.get("link", "#"),
                "summary": entry.get("summary", ""),
                "published_time": entry.get("published", "N/A"),
            })
    except httpx.HTTPStatusError as e:
        print(f"Error fetching status {e.response.status_code} for feed: {name}")
    except Exception as e:
        print(f"An unexpected error occurred for feed {name}: {e}")
    return articles

async def update_news_cache():
    """Concurrently fetches all RSS feeds and updates the cache."""
    print("Starting news cache update...")
    async with httpx.AsyncClient() as client:
        tasks = [fetch_single_feed(name, url, client) for name, url in RSS_FEEDS.items()]
        results = await asyncio.gather(*tasks)
    
    # Flatten the list of lists and sort by published time (if available)
    all_articles = [article for feed_articles in results for article in feed_articles]
    
    # Update the global cache
    news_cache["articles"] = all_articles
    news_cache["last_updated"] = datetime.now(timezone.utc)
    print(f"Cache updated successfully with {len(all_articles)} articles.")

async def scheduled_cache_update():
    """Runs the cache update task every 15 minutes."""
    while True:
        await update_news_cache()
        await asyncio.sleep(900) # 15 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup, run the first cache update and schedule future updates
    asyncio.create_task(scheduled_cache_update())
    yield
    # (No cleanup needed on shutdown for this simple case)

# --- FastAPI Application ---
app = FastAPI(
    title="Vietnam News API",
    description="An API to aggregate news from various Vietnamese financial RSS feeds.",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/", include_in_schema=False)
async def root():
    """Redirects the root URL to the interactive API documentation."""
    return RedirectResponse(url="/docs")

@app.get("/api/v1/news")
async def get_all_news():
    """
    Returns a list of all aggregated news articles from the cache.
    """
    return news_cache
