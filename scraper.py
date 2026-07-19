import logging
import requests
import feedparser
from typing import List, Dict, Any
from models import NewsItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# User-Agent header to bypass potential scraper blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Source configurations
SOURCES = [
    # Yerel Kaynaklar (Turkish Sources)
    {"name": "TRT Haber", "url": "https://www.trthaber.com/sondakika.rss", "type": "local"},
    {"name": "AA", "url": "https://www.aa.com.tr/tr/rss/default?cat=guncel", "type": "local"},
    {"name": "Hürriyet", "url": "https://www.hurriyet.com.tr/rss/anasayfa", "type": "local"},
    {"name": "Milliyet", "url": "https://www.milliyet.com.tr/rss/rssNew/gundemRss.xml", "type": "local"},
    {"name": "Cumhuriyet", "url": "https://www.cumhuriyet.com.tr/rss/son_dakika.xml", "type": "local"},
    {"name": "Yeni Şafak", "url": "https://www.yenisafak.com/rss?xml=gundem", "type": "local"},
    {"name": "Yeni Akit", "url": "https://www.yeniakit.com.tr/rss/haber/gundem.xml", "type": "local"},
    {"name": "Sözcü", "url": "https://www.sozcu.com.tr/feeds-son-dakika", "type": "local"},
    {"name": "Habertürk", "url": "https://www.haberturk.com/rss", "type": "local"},
    {"name": "Bloomberg HT", "url": "https://www.bloomberght.com/rss", "type": "local"},

    # Global Kaynaklar (Global Sources with Turkey focus)
    {
        "name": "Google News Global",
        "url": "https://news.google.com/rss/search?q=Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "BBC",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "type": "global",
        "filter": True
    },
    {
        "name": "Reuters",
        "url": "https://news.google.com/rss/search?q=site:reuters.com+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    }
]

# Keywords for global sources that require programmatic filtering (like BBC World)
FILTER_KEYWORDS = ["turkey", "turkiye", "turkish", "ankara", "istanbul", "erdogan"]

def fetch_feed(source: Dict[str, Any]) -> List[NewsItem]:
    """
    Fetches news from a single RSS source.
    Employs robust try-except error handling to prevent the program from crashing.
    """
    name = source["name"]
    url = source["url"]
    is_global = source.get("type") == "global"
    should_filter = source.get("filter", False)
    
    items = []
    logger.info(f"Fetching RSS feed for: {name} ({url})")
    
    try:
        # Fetching content with timeout and custom headers
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        # Parse XML content
        feed = feedparser.parse(response.content)
        
        if not feed.entries:
            logger.warning(f"No entries found for {name}")
            return []
            
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            description = entry.get("summary", entry.get("description", "")).strip()
            pub_date = entry.get("published", entry.get("pubDate", "")).strip()
            
            if not title or not link:
                continue
                
            # Perform programmatic keyword filtering for specific global sources (like BBC)
            if should_filter:
                text_to_check = f"{title} {description}".lower()
                if not any(keyword in text_to_check for keyword in FILTER_KEYWORDS):
                    continue
            
            # Map RSS fields to our NewsItem model
            news_item = NewsItem(
                title=title,
                link=link,
                source=name,
                description=description,
                pub_date=pub_date
            )
            items.append(news_item)
            
        logger.info(f"Successfully fetched {len(items)} items from {name}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching {name} feed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing {name} feed: {e}")
        
    return items

def scrape_all_sources() -> List[NewsItem]:
    """
    Iterates through all sources, aggregates feed items into a single list.
    """
    all_news: List[NewsItem] = []
    
    for source in SOURCES:
        feed_items = fetch_feed(source)
        all_news.extend(feed_items)
        
    logger.info(f"Scraping completed. Total aggregated articles: {len(all_news)}")
    return all_news

if __name__ == "__main__":
    logger.info("Running scraper directly for smoke testing...")
    results = scrape_all_sources()
    print(f"\n--- Scrape Summary: Aggregated {len(results)} articles ---")
    if results:
        print(f"Sample Article: {results[0].model_dump()}")
