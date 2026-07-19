import os
import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import google.generativeai as genai
from models import NewsItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Pydantic schemas for structured Gemini output
class AnalyzedNewsItem(BaseModel):
    title: str = Field(description="The Turkish title of the news article, clear and informative.")
    summary: str = Field(description="A concise summary of the article in fluent Turkish (1-3 sentences).")
    source: str = Field(description="The original source name of the article.")
    link: str = Field(description="The exact original URL link of the article.")

class AnalysisResponse(BaseModel):
    genel_gundem: List[AnalyzedNewsItem] = Field(description="General news related to Turkey.")
    savunma_sanayii: List[AnalyzedNewsItem] = Field(description="Developments related to Defense Industry (Savunma Sanayii).")
    spor: List[AnalyzedNewsItem] = Field(description="Sports news and sports achievements.")
    dunya_basininda_turkiye: List[AnalyzedNewsItem] = Field(description="Articles from global/foreign media focusing on Turkey/Turkiye.")

def analyze_news(news_items: List[NewsItem]) -> Dict[str, List[Dict[str, str]]]:
    """
    Sends the aggregated list of raw news items to Gemini API for translation,
    deduplication, categorization, and summarization.
    """
    # 1. Setup API key
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("Neither LLM_API_KEY nor GEMINI_API_KEY is found in environment variables!")
        return {
            "Genel Gündem": [],
            "Savunma Sanayii": [],
            "Spor": [],
            "Dünya Basınında Türkiye": []
        }
        
    genai.configure(api_key=api_key)
    
    # 2. Check for empty input
    if not news_items:
        logger.warning("No news items provided for analysis.")
        return {
            "Genel Gündem": [],
            "Savunma Sanayii": [],
            "Spor": [],
            "Dünya Basınında Türkiye": []
        }
        
    # 3. Python-side Pre-Deduplication to optimize token usage and avoid output truncation
    seen_titles = set()
    deduped_items = []
    
    for item in news_items:
        title_normalized = item.title.strip().lower()
        if title_normalized not in seen_titles:
            seen_titles.add(title_normalized)
            deduped_items.append(item)
            
    logger.info(f"Pre-deduplication filtered raw articles from {len(news_items)} down to {len(deduped_items)} unique titles.")
    
    # Cap the list at 500 items to fit perfectly within LLM context and JSON generation limits
    MAX_ITEMS = 500
    if len(deduped_items) > MAX_ITEMS:
        logger.info(f"Capping input articles list to top {MAX_ITEMS} for the LLM call.")
        # Try to keep a balanced distribution or just take the first 250
        deduped_items = deduped_items[:MAX_ITEMS]

    # 4. Format news items for the LLM prompt
    raw_articles_data = []
    for item in deduped_items:
        raw_articles_data.append({
            "title": item.title,
            "link": item.link,
            "source": item.source,
            "description": item.description,
            "pub_date": item.pub_date
        })
        
    logger.info(f"Sending {len(raw_articles_data)} clean articles to Gemini API...")
    
    # 5. Construct prompt
    prompt = f"""
    You are an expert Turkish news editor and translator. You are given a list of raw news articles scraped from local and global RSS feeds.
    
    Your task is to process these articles and return a structured JSON object according to the schema provided.
    
    Instructions:
    1. **Categorization**: Group all articles into one of the following 4 categories:
       - `genel_gundem`: General news and political/economic developments in Turkey.
       - `savunma_sanayii`: Turkish and global developments regarding the Turkish Defense Industry (Savunma Sanayii).
       - `spor`: Turkish sports news, football, olympics, and other sports achievements.
       - `dunya_basininda_turkiye`: News about Turkey/Turkiye from global sources (e.g. BBC, Reuters, Google News, and various country-level publications).
       
    2. **Deduplication**: Merge/combine articles reporting on the same event or news.
       - For duplicate entries, create a single consolidated article.
       - Select the most representative title.
       - Retain a valid original URL link and source name from one of the merged articles. Do not invent links!
       
    3. **Translation & Summarization**:
       - Translate all articles from foreign languages (e.g. English, German, Spanish, French, etc.) to fluent, natural, and professional Turkish.
       - Summarize each article/merged news item in a brief, concise, and clear paragraph (1 to 3 sentences max) in Turkish.
       
    4. **Link Integrity**:
       - The 'link' and 'source' fields MUST be exactly preserved from the input articles. Never invent or hallucinate URL paths.

    Raw Articles Data (JSON):
    {json.dumps(raw_articles_data, ensure_ascii=False, indent=2)}
    """
    
    # 6. Call Gemini API
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        logger.info("Calling Gemini API...")
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": AnalysisResponse
            }
        )
        
        # Parse output
        raw_response_text = response.text
        logger.debug(f"Gemini API Raw Output: {raw_response_text}")
        
        data = json.loads(raw_response_text)
        
        # Map response keys to the Turkish display categories
        mapped_result = {
            "Genel Gündem": data.get("genel_gundem", []),
            "Savunma Sanayii": data.get("savunma_sanayii", []),
            "Spor": data.get("spor", []),
            "Dünya Basınında Türkiye": data.get("dunya_basininda_turkiye", [])
        }
        
        logger.info(f"Gemini analysis complete. Categories: "
                    f"Genel: {len(mapped_result['Genel Gündem'])}, "
                    f"Savunma: {len(mapped_result['Savunma Sanayii'])}, "
                    f"Spor: {len(mapped_result['Spor'])}, "
                    f"Dünya: {len(mapped_result['Dünya Basınında Türkiye'])}")
                    
        return mapped_result
        
    except json.JSONDecodeError as je:
        logger.error(f"Failed to decode JSON from Gemini API response: {je}")
    except Exception as e:
        logger.error(f"Error during Gemini API news analysis: {e}")
        
    # Return empty response in case of any failures
    return {
        "Genel Gündem": [],
        "Savunma Sanayii": [],
        "Spor": [],
        "Dünya Basınında Türkiye": []
    }

if __name__ == "__main__":
    # Small test
    test_items = [
        NewsItem(
            title="S-400 testleri başarıyla tamamlandı",
            link="https://www.trthaber.com/s-400",
            source="TRT Haber",
            description="Türkiye savunma sanayisinde yerli testler başarıyla bitti.",
            pub_date="19.07.2026"
        ),
        NewsItem(
            title="Turkey's Bayraktar drone wins new export contract",
            link="https://www.reuters.com/bayraktar",
            source="Reuters",
            description="Turkish drone maker Baykar has secured another export contract for its TB2 drone.",
            pub_date="19.07.2026"
        ),
        NewsItem(
            title="Fenerbahçe transferde bombayı patlattı",
            link="https://www.sozcu.com.tr/fb-transfer",
            source="Sözcü",
            description="Sarı lacivertliler yeni forvetiyle sözleşme imzaladı.",
            pub_date="19.07.2026"
        )
    ]
    print("Testing analyzer with mock data...")
    res = analyze_news(test_items)
    print(json.dumps(res, ensure_ascii=False, indent=2))
