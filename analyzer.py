import os
import json
import logging
import warnings
from typing import List, Dict, Any
from pydantic import BaseModel, Field, create_model

# Suppress google deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from models import NewsItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Pydantic schemas for structured Gemini output
class AnalyzedNewsItem(BaseModel):
    id: int = Field(description="The unique integer ID of the article from the input list.")
    title: str = Field(description="The Turkish title of the news article, clear and informative.")
    summary: str = Field(description="A concise summary of the article in fluent Turkish (1-3 sentences).")

class CategoryStats(BaseModel):
    total_evaluated: int = Field(description="Total number of input articles matching this category's scope that were evaluated.")
    reported_count: int = Field(description="Number of articles selected and reported in this category.")
    unreported_count: int = Field(description="Number of articles evaluated but not reported in this category.")
    reasons_for_exclusion: List[str] = Field(description="Primary reasons why some articles in this category were not reported (in Turkish).")

class StatsResponse(BaseModel):
    genel_gundem: CategoryStats = Field(description="Stats for 'genel_gundem' category.")
    savunma_sanayii: CategoryStats = Field(description="Stats for 'savunma_sanayii' category.")
    spor: CategoryStats = Field(description="Stats for 'spor' category.")
    dunya_basininda_turkiye: CategoryStats = Field(description="Stats for 'dunya_basininda_turkiye' category.")

def analyze_news(news_items: List[NewsItem], max_items: int = 800) -> Dict[str, List[Dict[str, str]]]:
    """
    Sends the aggregated list of raw news items to Gemini API for translation,
    deduplication, categorization, and summarization.
    """
    # Read category limits from environment variables
    limit_genel = int(os.environ.get("LIMIT_GENEL_GUNDEM", 10))
    limit_savunma = int(os.environ.get("LIMIT_SAVUNMA_SANAYII", 10))
    limit_spor = int(os.environ.get("LIMIT_SPOR", 10))
    limit_dunya = int(os.environ.get("LIMIT_DUNYA_BASININDA_TURKIYE", 15))

    # Dynamically build the AnalysisResponse model with user-defined limits in the field descriptions
    AnalysisResponse = create_model(
        'AnalysisResponse',
        genel_gundem=(List[AnalyzedNewsItem], Field(description=f"General news related to Turkey. Select and return up to EXACTLY {limit_genel} of the most important unique news items from the input.")),
        savunma_sanayii=(List[AnalyzedNewsItem], Field(description=f"Developments related to Defense Industry (Savunma Sanayii). Select and return up to EXACTLY {limit_savunma} of the most important unique news items from the input.")),
        spor=(List[AnalyzedNewsItem], Field(description=f"Sports news and sports achievements. Select and return up to EXACTLY {limit_spor} of the most important unique news items from the input.")),
        dunya_basininda_turkiye=(List[AnalyzedNewsItem], Field(description=f"Articles from global/foreign media focusing on Turkey/Turkiye. Select and return up to EXACTLY {limit_dunya} of the most important unique news items from the input.")),
        stats=(StatsResponse, Field(description="Statistics for each category."))
    )

    logger.info(f"Loaded category limits from environment: Genel={limit_genel}, Savunma={limit_savunma}, Spor={limit_spor}, Dünya={limit_dunya}")

    # 1. Setup API key
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("Neither LLM_API_KEY nor GEMINI_API_KEY is found in environment variables!")
        return {
            "reports": {
                "Genel Gündem": [],
                "Savunma Sanayii": [],
                "Spor": [],
                "Dünya Basınında Türkiye": []
            },
            "stats": {}
        }
        
    genai.configure(api_key=api_key)
    
    # 2. Check for empty input
    if not news_items:
        logger.warning("No news items provided for analysis.")
        return {
            "reports": {
                "Genel Gündem": [],
                "Savunma Sanayii": [],
                "Spor": [],
                "Dünya Basınında Türkiye": []
            },
            "stats": {}
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
    
    # Cap total payload to max_items, prioritizing global items to ensure we get international news summaries
    local_items = [item for item in deduped_items if item.type == "local"]
    global_items = [item for item in deduped_items if item.type == "global"]
    
    logger.info(f"Unique articles: local={len(local_items)}, global={len(global_items)}")
    
    if len(local_items) + len(global_items) > max_items:
        # Keep up to 62.5% of max_items as global items, fill the rest with local items
        keep_global_cap = int(max_items * 0.625)
        keep_global = min(len(global_items), keep_global_cap)
        keep_local = max_items - keep_global
        
        subset_local = local_items[:keep_local]
        subset_global = global_items[:keep_global]
        deduped_items = subset_local + subset_global
        logger.info(f"Capped input to top {max_items} articles: kept {len(subset_local)} local and {len(subset_global)} global unique items.")
    
    # Assign IDs and build a lookup map
    original_items_map = {}
    raw_articles_data = []
    for idx, item in enumerate(deduped_items):
        original_items_map[idx] = item
        desc = item.description if item.description else ""
        if len(desc) > 150:
            desc = desc[:150] + "..."
        raw_articles_data.append({
            "id": idx,
            "title": item.title,
            "source": item.source,
            "description": desc,
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
       
    2. **Deduplication & Selection & Quantity Rules**: 
        - Merge/combine articles reporting on the same event or news.
        - Select only the most important, critical, and news-worthy developments for each category.
        - **CRITICAL QUANTITY & LIMIT RULE**: For each category, you MUST select and report **as many high-quality, unique news items as possible up to the specified limit**. Do not artificially stop at 10 items if there are more important news items available in the input. If there are enough news items, you should try to fill the slots up to these limits:
          * Up to {limit_genel} items for `genel_gundem`
          * Up to {limit_savunma} items for `savunma_sanayii`
          * Up to {limit_spor} items for `spor`
          * Up to {limit_dunya} items for `dunya_basininda_turkiye`
        Choose the most important, headline-worthy stories to populate these slots!
        
     3. **Translation & Summarization**:
        - Translate all articles from foreign languages (e.g. English, German, Spanish, French, etc.) to fluent, natural, and professional Turkish.
        - Summarize each selected news item in a brief, concise, and clear paragraph (1 to 3 sentences max) in Turkish      4. **Link & Date Integrity**:
        - Use the input article's `"id"` in the output to link it back to the original article.
        
      5. **Metadata & Statistics**:
        - Calculate statistics for each category and output them in the 'stats' field of the schema.
        - 'total_evaluated' must count how many of the unique input articles fell into that category's scope.
        - 'reported_count' must match the number of items you selected and returned in that category's list.
        - 'unreported_count' must be 'total_evaluated' minus 'reported_count'.
        - 'reasons_for_exclusion' must list the primary reasons why articles in this category were not reported (e.g. "Mükerrer haberler birleştirildi", "Haber değeri düşük bulundu" vb.). Write these reasons in Turkish.
          **CRITICAL**: Do NOT include "Kategori limitine ulaşıldığı için elendi" or similar limit-related reasons unless the number of reported items (`reported_count`) in that category is EXACTLY equal to that category's limit (i.e. {limit_genel} for `genel_gundem`, {limit_savunma} for `savunma_sanayii`, {limit_spor} for `spor`, {limit_dunya} for `dunya_basininda_turkiye`). If the reported count is less than the limit, any exclusions are solely due to low news value or deduplication, not the limit.
 
      6. **Style & Repetition Constraints**:
        - Ensure all Turkish text is clean and professional.
        - **NEVER** repeat words, sentences, or phrases. Avoid repeating starting phrases.
        - **NEVER** output repetitive filler words such as "Kesinlikle", "Şüphesiz" or other synonyms in a repeating loop. Each news item title and summary must be unique, concise, and structured naturally.

    Raw Articles Data (JSON):
    {json.dumps(raw_articles_data, ensure_ascii=False, indent=2)}
    """
    
    # 6. Call Gemini API
    # Use gemini-3.5-flash by default, allow overriding via GEMINI_MODEL env var
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()
    if not model_name.startswith("models/"):
        model_path = f"models/{model_name}"
    else:
        model_path = model_name
        
    model = genai.GenerativeModel(model_path)
    
    for attempt in range(1, 4):
        # Vary temperature on attempts: attempt 1 = 0.2, attempt 2 = 0.45, attempt 3 = 0.70
        current_temp = 0.2 + (attempt - 1) * 0.25
        try:
            logger.info(f"Calling Gemini API ({model_path}) - Attempt {attempt}/3 with temperature {current_temp:.2f}...")
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": AnalysisResponse,
                    "max_output_tokens": 8192,
                    "temperature": current_temp
                },
                request_options={"timeout": 120.0}
            )
            
            # Parse output
            raw_response_text = response.text
            logger.debug(f"Gemini API Raw Output: {raw_response_text}")
            
            data = json.loads(raw_response_text)
            
            # Map response keys to the Turkish display categories and reconstruct original values from IDs
            mapped_result = {
                "Genel Gündem": [],
                "Savunma Sanayii": [],
                "Spor": [],
                "Dünya Basınında Türkiye": []
            }
            
            category_mapping = [
                ("genel_gundem", "Genel Gündem"),
                ("savunma_sanayii", "Savunma Sanayii"),
                ("spor", "Spor"),
                ("dunya_basininda_turkiye", "Dünya Basınında Türkiye")
            ]
            
            for key, display_name in category_mapping:
                items = data.get(key, [])
                reconstructed_items = []
                for item in items:
                    item_id = item.get("id")
                    # Retrieve the original item using item_id
                    orig_item = original_items_map.get(item_id)
                    if orig_item:
                        reconstructed_items.append({
                            "title": item.get("title", orig_item.title),
                            "summary": item.get("summary", ""),
                            "source": orig_item.source,
                            "link": orig_item.link,
                            "pub_date": orig_item.pub_date
                        })
                    else:
                        logger.warning(f"Gemini returned an invalid ID: {item_id}")
                mapped_result[display_name] = reconstructed_items
            
            logger.info(f"Gemini analysis complete. Categories: "
                        f"Genel: {len(mapped_result['Genel Gündem'])}, "
                        f"Savunma: {len(mapped_result['Savunma Sanayii'])}, "
                        f"Spor: {len(mapped_result['Spor'])}, "
                        f"Dünya: {len(mapped_result['Dünya Basınında Türkiye'])}")
                        
            return {
                "reports": mapped_result,
                "stats": data.get("stats", {})
            }
            
        except json.JSONDecodeError as je:
            logger.warning(f"Attempt {attempt}/3 failed to decode JSON from Gemini API response: {je}")
            logger.warning(f"Raw response text: {response.text if 'response' in locals() else 'N/A'}")
            if attempt < 3:
                import time
                logger.info("Waiting 5 seconds before retrying...")
                time.sleep(5)
        except Exception as e:
            logger.warning(f"Attempt {attempt}/3 failed during Gemini API news analysis: {e}")
            if attempt < 3:
                import time
                sleep_time = 30 if "429" in str(e) or "quota" in str(e).lower() else 5
                logger.info(f"Waiting {sleep_time} seconds before retrying...")
                time.sleep(sleep_time)
            
    logger.error("All 3 attempts to analyze news via Gemini API failed.")
        
    # Return empty response in case of any failures
    return {
        "reports": {
            "Genel Gündem": [],
            "Savunma Sanayii": [],
            "Spor": [],
            "Dünya Basınında Türkiye": []
        },
        "stats": {}
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
