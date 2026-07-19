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
        
    # 3. Python-side Pre-Deduplication to optimize token usage and avoid exact duplicate processing
    seen_titles = set()
    deduped_items = []
    
    for item in news_items:
        title_normalized = item.title.strip().lower()
        if title_normalized not in seen_titles:
            seen_titles.add(title_normalized)
            deduped_items.append(item)
            
    logger.info(f"Pre-deduplication filtered raw articles from {len(news_items)} down to {len(deduped_items)} unique titles.")
    
    # Cap total payload to 400, prioritizing global items to ensure we get international news summaries
    MAX_ITEMS = 400
    local_items = [item for item in deduped_items if item.type == "local"]
    global_items = [item for item in deduped_items if item.type == "global"]
    
    logger.info(f"Unique articles: local={len(local_items)}, global={len(global_items)}")
    
    if len(local_items) + len(global_items) > MAX_ITEMS:
        # Keep up to 250 global items, fill the rest (at least 150) with local items
        keep_global = min(len(global_items), 250)
        keep_local = MAX_ITEMS - keep_global
        
        subset_local = local_items[:keep_local]
        subset_global = global_items[:keep_global]
        deduped_items = subset_local + subset_global
        logger.info(f"Capped input to top {MAX_ITEMS} articles: kept {len(subset_local)} local and {len(subset_global)} global unique items.")
    
    # 4. Format news items for the LLM prompt
    raw_articles_data = []
    for item in deduped_items:
        raw_articles_data.append({
            "title": item.title,
            "link": item.link,
            "source": item.source,
            "description": item.description,
            "pub_date": item.pub_date,
            "type": item.type
        })
        
    logger.info(f"Sending {len(raw_articles_data)} unique articles to Gemini API...")
    
    # 5. Construct prompt with strict output capping to prevent output token truncation
    prompt = f"""
    You are an expert Turkish news editor and translator. You are given a list of raw news articles scraped from local and global RSS feeds.
    
    Your task is to process these articles and return a structured JSON object according to the schema provided.
    
    Instructions:
    1. **Categorization & Source Rules**: Group all articles into one of the following 4 categories:
       - `genel_gundem`: General news and political/economic developments in Turkey. MUST ONLY contain articles that have `"type": "local"` in the input data. Do not include global articles here.
       - `savunma_sanayii`: Turkish and global developments regarding the Turkish Defense Industry (Savunma Sanayii). Can contain articles with BOTH `"type": "local"` and `"type": "global"`.
       - `spor`: Turkish sports news and sports achievements. MUST ONLY contain articles that have `"type": "local"` in the input data.
       - `dunya_basininda_turkiye`: News about Turkey/Turkiye from global sources (e.g. BBC, Reuters, NYT, DW, El Pais, Le Monde, TASS, Sputnik, etc.). MUST ONLY contain articles that have `"type": "global"` in the input data. Under no circumstances should local Turkish sources (where `"type": "local"`) be categorized here!
       
    2. **Deduplication & Selection**: 
       - Merge/combine articles reporting on the same event or news.
       - Select only the most important, critical, and news-worthy developments for each category.
       - **CRITICAL OUTPUT LIMIT**: To prevent JSON output truncation (due to API token limitations), limit the returned list to a maximum of:
         * 10 items for `genel_gundem`
         * 10 items for `savunma_sanayii`
         * 10 items for `spor`
         * 15 items for `dunya_basininda_turkiye`
       Choose the most important, headline-worthy stories for these slots!
       
    3. **Translation & Summarization**:
       - Translate all articles from foreign languages (e.g. English, German, Spanish, French, etc.) to fluent, natural, and professional Turkish.
       - Summarize each selected news item in a brief, concise, and clear paragraph (1 to 3 sentences max) in Turkish.
       
    4. **Link Integrity**:
       - The 'link' and 'source' fields MUST be exactly preserved from the input articles. Never invent or hallucinate URL paths.

    Raw Articles Data (JSON):
    {json.dumps(raw_articles_data, ensure_ascii=False, indent=2)}
    """
    
    # 6. Call Gemini API
    try:
        # Using gemini-3.5-flash as requested by the user
        model = genai.GenerativeModel("models/gemini-3.5-flash")
        
        logger.info("Calling Gemini API (gemini-3.5-flash)...")
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
