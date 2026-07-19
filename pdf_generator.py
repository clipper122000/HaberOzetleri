import os
import logging
from datetime import datetime
from typing import List, Dict, Any
from weasyprint import HTML

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Mapping of categories to their corresponding emojis
CATEGORY_EMOJIS = {
    "Genel Gündem": "🇹🇷",
    "Savunma Sanayii": "🛡️",
    "Spor": "🏆",
    "Dünya Basınında Türkiye": "🌍"
}

def generate_pdf(analyzed_data: Dict[str, List[Dict[str, str]]], output_path: str = None) -> str:
    """
    Takes the structured news summary data and renders a beautiful corporate PDF
    using Weasyprint. Strictly avoids display: flex/grid in compliance with Weasyprint limits.
    """
    # 1. Determine date and output file name
    today = datetime.now()
    date_str = today.strftime("%d.%m.%Y")  # Turkish standard format for header
    filename_date = today.strftime("%Y.%m.%d")  # Naming convention YYYY.MM.DD
    
    if not output_path:
        output_filename = f"Haber Ozeti {filename_date}.pdf"
        output_path = os.path.join(os.getcwd(), output_filename)
        
    logger.info(f"Starting PDF generation for date: {date_str}")
    
    # 2. Build news items HTML markup
    sections_html = ""
    for category, items in analyzed_data.items():
        emoji = CATEGORY_EMOJIS.get(category, "📰")
        
        items_html = ""
        if not items:
            items_html = """
            <div class="no-news">
                Bu kategoriye ait bugün güncel bir haber bulunmamaktadır.
            </div>
            """
        else:
            for item in items:
                title = item.get("title", "Başlıksız Haber")
                summary = item.get("summary", "Özet bulunamadı.")
                source = item.get("source", "Bilinmeyen Kaynak")
                link = item.get("link", "#")
                
                items_html += f"""
                <div class="news-item">
                    <h3 class="news-title">{title}</h3>
                    <p class="news-summary">{summary}</p>
                    <div class="news-meta">
                        <a href="{link}" class="news-link">Kaynak: {source}</a>
                    </div>
                </div>
                """
                
        sections_html += f"""
        <div class="category-section">
            <h2 class="category-title">{emoji} {category}</h2>
            <div class="category-underline"></div>
            {items_html}
        </div>
        """

    # 3. HTML and CSS template
    html_content = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>Günlük Haber Özetleri Raporu - {date_str}</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            @page {{
                size: A4;
                margin: 20mm 15mm;
                background-color: #f8f9fa;
                @bottom-right {{
                    content: counter(page);
                    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                    font-size: 8pt;
                    color: #64748b;
                }}
                @bottom-left {{
                    content: "Günlük Haber Özetleri Raporu — {date_str}";
                    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                    font-size: 8pt;
                    color: #64748b;
                }}
            }}
            
            body {{
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                color: #1e293b;
                margin: 0;
                padding: 0;
                background-color: #f8f9fa;
                font-size: 10pt;
                line-height: 1.5;
            }}
            
            /* Corporate Header Banner (No Flex/Grid) */
            .header-banner {{
                background-color: #0f172a;
                padding: 24px 30px;
                border-radius: 8px;
                margin-bottom: 25px;
                border-bottom: 4px solid #1d4ed8;
            }}
            
            .header-title {{
                color: #ffffff;
                font-size: 20pt;
                font-weight: 700;
                margin: 0;
                letter-spacing: -0.5px;
                text-transform: uppercase;
            }}
            
            .header-subtitle {{
                color: #94a3b8;
                font-size: 10.5pt;
                margin: 6px 0 0 0;
                font-weight: 500;
            }}
            
            /* Category Sections Layout */
            .category-section {{
                margin-bottom: 25px;
                page-break-inside: auto;
            }}
            
            .category-title {{
                font-size: 13.5pt;
                font-weight: 700;
                color: #0f172a;
                margin: 25px 0 6px 0;
                letter-spacing: 0.2px;
                text-transform: uppercase;
            }}
            
            .category-underline {{
                height: 1.5px;
                background-color: #cbd5e1;
                width: 100%;
                margin-bottom: 15px;
            }}
            
            /* News Card Design */
            .news-item {{
                background-color: #ffffff;
                padding: 16px 20px;
                margin-bottom: 12px;
                border-radius: 6px;
                border-left: 4.5px solid #1d4ed8;
                border-top: 1px solid #e2e8f0;
                border-right: 1px solid #e2e8f0;
                border-bottom: 1px solid #e2e8f0;
                page-break-inside: avoid; /* Prevent card splitting across pages */
            }}
            
            .news-title {{
                font-size: 11pt;
                font-weight: 700;
                color: #0f172a;
                margin: 0 0 8px 0;
                line-height: 1.4;
            }}
            
            .news-summary {{
                font-size: 9.5pt;
                color: #475569;
                line-height: 1.55;
                margin: 0 0 10px 0;
                text-align: justify;
            }}
            
            .news-meta {{
                font-size: 8.5pt;
                font-weight: 500;
            }}
            
            .news-link {{
                color: #1a73e8;
                text-decoration: none;
            }}
            
            .news-link:hover {{
                text-decoration: underline;
            }}
            
            .no-news {{
                background-color: #f1f5f9;
                padding: 15px;
                border-radius: 6px;
                color: #64748b;
                font-size: 9.5pt;
                font-style: italic;
                border: 1px dashed #cbd5e1;
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="header-banner">
            <h1 class="header-title">Günlük Gündem Raporu</h1>
            <p class="header-subtitle">📅 {date_str} &bull; Türkiye ve Dünya Gelişmeleri Basın Özeti</p>
        </div>
        
        {sections_html}
    </body>
    </html>
    """
    
    # 4. Generate PDF using Weasyprint HTML compiler
    try:
        HTML(string=html_content).write_pdf(output_path)
        logger.info(f"Successfully generated PDF at: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to generate PDF using Weasyprint: {e}")
        raise e

if __name__ == "__main__":
    # Smoke test data
    test_data = {
        "Genel Gündem": [
            {
                "title": "Merkez Bankası Faiz Kararını Açıkladı",
                "summary": "Türkiye Cumhuriyet Merkez Bankası (TCMB) Para Politikası Kurulu, politika faizini piyasa beklentileri doğrultusunda yüzde 50 seviyesinde sabit tutma kararı aldı.",
                "source": "Habertürk",
                "link": "https://www.haberturk.com/tcmb-faiz-karari"
            }
        ],
        "Savunma Sanayii": [
            {
                "title": "Milli Muharip Uçak KAAN İkinci Uçuşunu Yaptı",
                "summary": "Türk Havacılık ve Uzay Sanayii (TUSAŞ) tarafından geliştirilen KAAN, sabah saatlerinde gerçekleştirilen test uçuşunda havada 14 dakika kalarak planlanan tüm testleri başarıyla tamamladı.",
                "source": "TRT Haber",
                "link": "https://www.trthaber.com/kaan-ikinci-ucus"
            }
        ],
        "Spor": [
            {
                "title": "Filenin Sultanları Yarı Finalde",
                "summary": "A Milli Kadın Voleybol Takımımız, Milletler Ligi çeyrek final mücadelesinde İtalya'yı heyecan dolu bir maçın ardından 3-2 mağlup ederek adını yarı finale yazdırdı.",
                "source": "AA",
                "link": "https://www.aa.com.tr/filenin-sultanlari-yari-finalde"
            }
        ],
        "Dünya Basınında Türkiye": [
            {
                "title": "Reuters: Turkey’s Drone Power Expands in Europe",
                "summary": "İngiliz haber ajansı Reuters, Türkiye'nin insansız hava araçlarının Avrupa pazarındaki artan nüfuzunu ele alarak yerli İHA'ların teknolojik avantajlarını analiz etti.",
                "source": "Reuters",
                "link": "https://www.reuters.com/turkey-drones"
            }
        ]
    }
    
    print("Testing PDF generator with mock data...")
    path = generate_pdf(test_data, "test_output.pdf")
    print(f"PDF successfully generated at: {os.path.abspath(path)}")
