import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Diagnostic")

def run_diagnostics():
    logger.info("=== Starting HaberOzetleri Diagnostics ===")
    
    # 1. Check Python Version
    logger.info(f"Python Version: {sys.version}")
    
    # 2. Check environment variables
    llm_key = os.environ.get("LLM_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    
    logger.info("--- Environment Variables Check ---")
    logger.info(f"LLM_API_KEY: {'SET (Ends with ...' + llm_key[-4:] + ')' if llm_key else 'MISSING'}")
    logger.info(f"GEMINI_API_KEY: {'SET (Ends with ...' + gemini_key[-4:] + ')' if gemini_key else 'MISSING'}")
    logger.info(f"GMAIL_USER: {'SET (' + gmail_user + ')' if gmail_user else 'MISSING'}")
    logger.info(f"GMAIL_APP_PASSWORD: {'SET' if gmail_pass else 'MISSING'}")
    
    if not llm_key and not gemini_key:
        logger.warning("❌ Missing Gemini API Key! The news analyzer will return empty lists.")
    else:
        logger.info("✅ Gemini API Key is present.")
        
    if not gmail_user or not gmail_pass:
        logger.warning("❌ Missing Gmail SMTP credentials! Email reports will not be sent.")
    else:
        logger.info("✅ Gmail SMTP credentials are present.")

    # 3. Check WeasyPrint dependencies
    logger.info("--- Weasyprint Dependencies Check ---")
    try:
        from weasyprint import HTML
        logger.info("✅ Weasyprint imported successfully. GTK+ libraries are installed and configured correctly.")
    except Exception as e:
        logger.error(f"❌ Weasyprint import failed: {e}")
        logger.error("Please ensure GTK3 is installed and added to your PATH environment variable.")

    # 4. Check Gemini API Connection & Key Validity
    if llm_key or gemini_key:
        logger.info("--- Gemini API Test Call ---")
        try:
            import google.generativeai as genai
            active_key = llm_key or gemini_key
            genai.configure(api_key=active_key)
            
            logger.info("Testing Gemini connection with simple prompt...")
            model = genai.GenerativeModel("models/gemini-3.5-flash")
            response = model.generate_content("Say 'Gemini is connected' in Turkish.")
            logger.info(f"✅ Gemini Response: {response.text.strip()}")
        except Exception as e:
            logger.error(f"❌ Gemini API test call failed: {e}")
            logger.error("Please verify that your API key is valid and has enough quota.")
            
    logger.info("=== Diagnostics Completed ===")

if __name__ == "__main__":
    run_diagnostics()
