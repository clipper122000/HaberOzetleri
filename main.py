import argparse
import logging
import os
import sys
import warnings
from datetime import datetime, timezone, timedelta

# Suppress google deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Configure Windows DLL search paths for WeasyPrint/cffi
if sys.platform == "win32":
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    dll_dirs = [
        base_dir,
        os.path.join(base_dir, "gtk_bin"),
        r"C:\msys64\mingw64\bin",
        r"C:\Program Files\GTK3-Runtime Win64\bin",
        r"C:\Program Files (x86)\GTK3-Runtime Win64\bin"
    ]
    for d in dll_dirs:
        if os.path.exists(d):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass

    # Set FONTCONFIG_PATH dynamically so it loads bundled fonts.conf if available
    fontconfig_dir = os.path.join(base_dir, "etc", "fonts")
    if os.path.exists(fontconfig_dir):
        os.environ["FONTCONFIG_PATH"] = fontconfig_dir
    else:
        # Check inside gtk_bin as well
        fontconfig_dir_fallback = os.path.join(base_dir, "gtk_bin", "etc", "fonts")
        if os.path.exists(fontconfig_dir_fallback):
            os.environ["FONTCONFIG_PATH"] = fontconfig_dir_fallback

# Get absolute directory of the script or executable
if getattr(sys, 'frozen', False):
    script_dir = os.path.dirname(sys.executable)
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, ".env")

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=dotenv_path, override=True)
except ImportError:
    pass

# Configure logging immediately with force=True
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(script_dir, "daily_report.log"), encoding="utf-8")
    ],
    force=True
)
logger = logging.getLogger("Orchestrator")

from scraper import scrape_all_sources
from analyzer import analyze_news
from pdf_generator import generate_pdf
from mailer import send_report_email

def run_pipeline(recipient_email: str = None, skip_email: bool = False, limit: int = None):
    """
    Orchestrates the entire news summary reporting pipeline:
    1. Scrapes local and global RSS feeds.
    2. Filters out articles older than 2 days.
    3. Analyzes, translates, deduplicates, and categorizes news via Gemini.
    4. Generates a beautifully formatted PDF report (using Weasyprint).
    5. Emails the PDF report to the user (via secure Gmail SMTP) with stats.
    """
    if limit is None:
        val = os.environ.get("ANALYSIS_LIMIT")
        if val is None or val.strip() == "":
            limit = 800
        else:
            try:
                limit = int(val)
            except ValueError:
                limit = 800

    logger.info("=========================================")
    logger.info("Starting Daily News Summary Report Pipeline")
    logger.info("=========================================")
    
    start_time = datetime.now()
    
    # Step 1: Scrape news items
    logger.info("Step 1: Scraping all RSS feeds...")
    raw_news = scrape_all_sources()
    if not raw_news:
        logger.warning("Scraping completed but no news articles were retrieved. Pipeline stopping.")
        return
        
    total_scraped = len(raw_news)
    logger.info(f"Step 1: Scraped {total_scraped} raw news articles.")
    
    # Filter by date: keep only last 24 hours
    logger.info("Filtering news to only keep the last 24 hours...")
    now_utc = datetime.now(timezone.utc)
    cutoff_utc = now_utc - timedelta(hours=24)
    
    remaining_news = []
    excluded_by_date = 0
    for item in raw_news:
        if not item.iso_date:
            remaining_news.append(item)
            continue
        try:
            item_dt = datetime.fromisoformat(item.iso_date)
            if item_dt >= cutoff_utc:
                remaining_news.append(item)
            else:
                excluded_by_date += 1
        except Exception:
            remaining_news.append(item)
            
    remaining_after_date = len(remaining_news)
    logger.info(f"Date filtering: {excluded_by_date} articles excluded. {remaining_after_date} articles remaining.")
    
    # Pre-deduplicate to count how many unique remaining articles we have before capping
    seen_titles = set()
    deduped_remaining = []
    for item in remaining_news:
        title_normalized = item.title.strip().lower()
        if title_normalized not in seen_titles:
            seen_titles.add(title_normalized)
            deduped_remaining.append(item)
            
    unique_remaining_count = len(deduped_remaining)
    excluded_by_limit = max(0, unique_remaining_count - limit)
    logger.info(f"Pre-deduplication: {unique_remaining_count} unique articles out of {remaining_after_date} remaining.")
    logger.info(f"Limit capping: {excluded_by_limit} unique articles will be excluded because of analysis limit ({limit}).")
    
    # Step 2: Analyze and summarize news with LLM
    logger.info(f"Step 2: Sending articles to Gemini API for analysis (limit: {limit})...")
    analysis_result = analyze_news(remaining_news, max_items=limit)
    analyzed_data = analysis_result["reports"]
    category_stats = analysis_result["stats"]
    
    # Quick count of analyzed articles for logging
    total_analyzed = sum(len(items) for items in analyzed_data.values())
    logger.info(f"Step 2: Analysis completed. Categorized {total_analyzed} unique summarized articles.")
    
    # Step 3: Generate the PDF Report
    logger.info("Step 3: Generating PDF document...")
    try:
        pdf_path = generate_pdf(analyzed_data)
        logger.info(f"Step 3: PDF generated successfully at: {pdf_path}")
    except Exception as e:
        logger.error(f"Step 3 failed: PDF generation failed. Error: {e}")
        return
        
    # Step 4: Email the PDF report
    if skip_email:
        logger.info("Step 4: Skipped email sending (flag --skip-email active). PDF file retained for local review.")
    else:
        logger.info("Step 4: Sending email report...")
        email_sent = send_report_email(
            pdf_path=pdf_path,
            recipient_email=recipient_email,
            total_scraped=total_scraped,
            excluded_by_date=excluded_by_date,
            remaining_after_date=remaining_after_date,
            excluded_by_limit=excluded_by_limit,
            limit=limit,
            category_stats=category_stats,
            analyzed_data=analyzed_data
        )
        if email_sent:
            logger.info("Step 4: Email sent successfully.")
        else:
            logger.error("Step 4: Email sending failed. Review SMTP configuration in logs.")
            
        # Clean up PDF file to prevent repository/project clutter
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                logger.info(f"Cleaned up generated PDF file to prevent repository clutter: {pdf_path}")
            except Exception as cleanup_err:
                logger.error(f"Failed to delete PDF file during cleanup: {cleanup_err}")
            
    end_time = datetime.now()
    duration = end_time - start_time
    logger.info("=========================================")
    logger.info(f"Pipeline finished successfully in {duration.total_seconds():.2f} seconds.")
    logger.info("=========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Haber Ozetleri Email Reporter System")
    parser.add_argument(
        "--recipient", 
        type=str, 
        default=None, 
        help="Email address to receive the PDF report (defaults to GMAIL_USER)."
    )
    parser.add_argument(
        "--skip-email", 
        action="store_true", 
        help="Generate the PDF report locally but do not send the email."
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=None, 
        help="Maximum number of unique news articles to send for Gemini analysis. Defaults to environment variable ANALYSIS_LIMIT, or 800 if not set."
    )
    
    args = parser.parse_args()
    
    run_pipeline(
        recipient_email=args.recipient,
        skip_email=args.skip_email,
        limit=args.limit
    )
