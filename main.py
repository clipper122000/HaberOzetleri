import argparse
import logging
import os
import sys
from datetime import datetime

from scraper import scrape_all_sources
from analyzer import analyze_news
from pdf_generator import generate_pdf
from mailer import send_report_email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("daily_report.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("Orchestrator")

def run_pipeline(recipient_email: str = None, skip_email: bool = False):
    """
    Orchestrates the entire news summary reporting pipeline:
    1. Scrapes local and global RSS feeds.
    2. Analyzes, translates, deduplicates, and categorizes news via Gemini.
    3. Generates a beautifully formatted PDF report (using Weasyprint).
    4. Emails the PDF report to the user (via secure Gmail SMTP).
    """
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
        
    logger.info(f"Step 1: Scraped {len(raw_news)} raw news articles.")
    
    # Step 2: Analyze and summarize news with LLM
    logger.info("Step 2: Sending articles to Gemini API for analysis...")
    analyzed_data = analyze_news(raw_news)
    
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
        email_sent = send_report_email(pdf_path, recipient_email)
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
    
    args = parser.parse_args()
    
    run_pipeline(
        recipient_email=args.recipient,
        skip_email=args.skip_email
    )
