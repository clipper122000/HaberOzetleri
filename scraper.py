import logging
import requests
import feedparser
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
import email.utils
from models import NewsItem

def clean_and_format_date(entry) -> tuple[str, str]:
    """
    Parses entry pub_date to a timezone-aware UTC datetime and a Turkish-formatted display string.
    Returns: (formatted_display_string, iso_date_utc_string)
    """
    dt = None
    parsed_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_struct:
        try:
            dt = datetime(*parsed_struct[:6], tzinfo=timezone.utc)
        except Exception:
            pass
            
    if not dt:
        for field in ["published", "pubDate", "updated", "date"]:
            val = entry.get(field)
            if val:
                try:
                    parsed_dt = email.utils.parsedate_to_datetime(val)
                    if parsed_dt.tzinfo is None:
                        dt = parsed_dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = parsed_dt.astimezone(timezone.utc)
                    break
                except Exception:
                    pass
                    
    if dt:
        # Convert to Turkish time (UTC+3)
        trt_tz = timezone(timedelta(hours=3))
        local_dt = dt.astimezone(trt_tz)
        formatted_str = local_dt.strftime("%d.%m.%Y %H:%M")
        return formatted_str, dt.isoformat()
    else:
        # Fallback to whatever string is present
        raw_val = entry.get("published", entry.get("pubDate", "")).strip()
        return raw_val, None


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# User-Agent header to bypass potential scraper blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Source configurations - Local sources filtered as requested
SOURCES = [
    # --- YEREL KAYNAKLAR (13 Turkish Sources) ---
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
    {"name": "NTV", "url": "https://www.ntv.com.tr/gundem.rss", "type": "local"},
    {"name": "Sabah", "url": "https://www.sabah.com.tr/rss/anasayfa.xml", "type": "local"},
    {"name": "CNN Türk", "url": "https://www.cnnturk.com/feed/rss/all/news", "type": "local"},

    # --- GLOBAL KAYNAKLAR (Targeted searches by country + BBC World) ---
    {
        "name": "US Media",
        "url": "https://news.google.com/rss/search?q=site:nytimes.com+OR+site:washingtonpost.com+OR+site:cnn.com+OR+site:wsj.com+OR+site:bloomberg.com+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "UK Media",
        "url": "https://news.google.com/rss/search?q=site:theguardian.com+OR+site:thetimes.co.uk+OR+site:ft.com+OR+site:independent.co.uk+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
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
    },
    {
        "name": "Germany Media",
        "url": "https://news.google.com/rss/search?q=site:dw.com+OR+site:spiegel.de+OR+site:zeit.de+OR+site:welt.de+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Spain Media",
        "url": "https://news.google.com/rss/search?q=site:elpais.com+OR+site:elmundo.es+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Italy Media",
        "url": "https://news.google.com/rss/search?q=site:corriere.it+OR+site:repubblica.it+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "France Media",
        "url": "https://news.google.com/rss/search?q=site:lemonde.fr+OR+site:lefigaro.fr+OR+site:france24.com+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Greece Media",
        "url": "https://news.google.com/rss/search?q=site:ekathimerini.com+OR+site:tovima.com+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Israel Media",
        "url": "https://news.google.com/rss/search?q=site:haaretz.com+OR+site:jpost.com+OR+site:timesofisrael.com+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Russia Media",
        "url": "https://news.google.com/rss/search?q=site:rt.com+OR+site:tass.com+OR+site:sputniknews.com+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Iran Media",
        "url": "https://news.google.com/rss/search?q=site:presstv.ir+OR+site:irna.ir+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "China Media",
        "url": "https://news.google.com/rss/search?q=site:xinhuanet.com+OR+site:cgtn.com+OR+site:scmp.com+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Sweden Media",
        "url": "https://news.google.com/rss/search?q=site:svt.se+OR+site:dn.se+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Norway Media",
        "url": "https://news.google.com/rss/search?q=site:nrk.no+OR+site:aftenposten.no+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Denmark Media",
        "url": "https://news.google.com/rss/search?q=site:dr.dk+OR+site:politiken.dk+Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    },
    {
        "name": "Google News Global",
        "url": "https://news.google.com/rss/search?q=Turkey+OR+Turkiye&hl=en-US&gl=US&ceid=US:en",
        "type": "global"
    }
]

# Keywords for global sources programmatic filtering (like BBC World), expanded with famous Turks
FILTER_KEYWORDS = [
    # General terms
    "turkey", "turkiye", "turkish", "ankara", "istanbul", "erdogan", "tayyip",
    
    # World-famous Turkish names
    "orhan pamuk", "nuri bilge ceylan", "muhtar kent", "daron acemoglu", "daron acemoğlu",
    "ugur sahin", "ugur şahin", "ozlem tureci", "özlem türeci", "mehmet oz", "dr. oz",
    "hakan calhanoglu", "hakan çalhanoğlu", "arda guler", "arda güler", "kenan yildiz",
    "kenan yıldız", "selcuk bayraktar", "selçuk bayraktar", "haluk bayraktar", "aziz sancar",
    "can yaman", "ebrar karakurt", "melissa vargas", "ferzan ozpetek", "ferzan özpetek",
    "alper gezeravci", "alper gezeravcı"
]

def fetch_feed(source: Dict[str, Any]) -> List[NewsItem]:
    """
    Fetches news from a single RSS source.
    Employs robust try-except error handling to prevent the program from crashing.
    """
    name = source["name"]
    url = source["url"]
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
            pub_date_display, iso_date_utc = clean_and_format_date(entry)
            
            if not title or not link:
                continue
                
            # Perform programmatic keyword filtering for specific global sources (like BBC)
            if should_filter:
                text_to_check = f"{title} {description}".lower()
                if not any(keyword in text_to_check for keyword in FILTER_KEYWORDS):
                    continue
            
            # --- Dynamically extract exact publisher name from Google News feeds ---
            dynamic_source = name
            source_info = entry.get("source")
            
            if source_info and isinstance(source_info, dict) and "title" in source_info:
                dynamic_source = source_info["title"].strip()
            elif " - " in title:
                # Fallback: Google News appends " - Publisher Name" at the end of the title
                parts = title.rsplit(" - ", 1)
                if len(parts) > 1:
                    dynamic_source = parts[1].strip()
                    title = parts[0].strip()  # Clean title for layout
            
            # Map RSS fields to our NewsItem model
            news_item = NewsItem(
                title=title,
                link=link,
                source=dynamic_source,
                description=description,
                pub_date=pub_date_display,
                iso_date=iso_date_utc,
                type=source.get("type", "local")
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
    logger.info("Running optimized scraper directly for testing...")
    results = scrape_all_sources()
    print(f"\n--- Scrape Summary: Aggregated {len(results)} articles ---")
