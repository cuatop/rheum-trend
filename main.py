import requests
import xml.etree.ElementTree as ET
from collections import Counter
import datetime
import time
import urllib.parse
import random

# === 설정 ===
SEARCH_TERM = "Rheumatology"
DAYS_BACK = 30
MAX_PAPERS = 1000

# === Top 30 저널 (공식 약어) ===
TOP_JOURNALS = [
    "Nat Rev Rheumatol", "Ann Rheum Dis", "Lancet Rheumatol", "Arthritis Rheumatol",
    "N Engl J Med", "Lancet", "JAMA", "BMJ",
    "Arthritis Care Res (Hoboken)", "Rheumatology (Oxford)", "Semin Arthritis Rheum",
    "Autoimmun Rev", "J Autoimmun", "RMD Open", "Arthritis Res Ther",
    "Osteoarthritis Cartilage", "Bone", "J Bone Miner Res",
    "Clin Rheumatol", "Best Pract Res Clin Rheumatol", "Curr Opin Rheumatol",
    "Ther Adv Musculoskelet Dis", "Scand J Rheumatol", "Joint Bone Spine",
    "Lupus Sci Med", "Lupus", "Clin Exp Rheumatol", "Mod Rheumatol",
    "Front Immunol", "J Rheum Dis"
]

def normalize_word(word):
    if not word: return ""
    garbage = ["Treatment Outcome", "Humans", "Female", "Male", "Adult", "Middle Aged", "Aged", "Adolescent", "Young Adult", "Child", "Animals", "Mice", "Rats", "Pregnancy", "Risk Factors", "Retrospective Studies", "Prospective Studies", "Case-Control Studies", "Incidence", "Prevalence", "Surveys and Questionnaires", "Sensitivity and Specificity", "Predictive Value of Tests", "Questionnaires", "Cohort Studies", "Severity of Illness Index"]
    if word in garbage: return None
    if ", " in word:
        parts = word.split(", ")
        if len(parts) == 2: return f"{parts[1]} {parts[0]}"
    return word

def generate_interactive_cloud(term, days, journal_list):
    journal_query = " OR ".join([f'"{j}"[Journal]' for j in journal_list])
    today = datetime.date.today()
    past_date = today - datetime.timedelta(days=days)
    
    date_query_str = f'"{past_date.strftime("%Y/%m/%d")}":"{today.strftime("%Y/%m/%d")}"[dp]'
    full_query = f"({journal_query}) AND {term} AND {date_query_str}"
    
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": full_query, "retmode": "json", "retmax": MAX_PAPERS, "sort": "date"}
    resp = requests.get(search_url, params=params)
    
    if 'esearchresult' not in resp.json(): return []
    id_list = resp.json()['esearchresult']['idlist']
    
    total = len(id_list)
    if not id_list: return []

    keywords = []
    batch_size = 100
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    
    for i in range(0, total, batch_size):
        batch_ids = id_list[i : i + batch_size]
        params = {"db": "pubmed", "id": ",".join(batch_ids), "retmode": "xml"}
        try:
            resp = requests.post(fetch_url, data=params)
            root = ET.fromstring(resp.content)
            for article in root.findall(".//PubmedArticle"):
                for mesh in article.findall(".//DescriptorName"):
                    clean = normalize_word(mesh.text)
                    if clean: keywords.append(clean)
                for kw in article.findall(".//Keyword"):
                    clean = normalize_word(kw.text.title())
                    if clean: keywords.append(clean)
            time.sleep(0.1)
        except: continue

    return Counter(keywords).most_common(60), journal_query, date_query_str

# 실행 및 HTML 파일 저장
word_data, j_query, d_query = generate_interactive_cloud(SEARCH_TERM, DAYS_BACK, TOP_JOURNALS)

if word_data:
    # 워드클라우드 HTML 생성
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Rheumatology Trends</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background-color: #f9f9f9; text-align: center; }}
            .cloud-container {{ 
                max-width: 800px; margin: 0 auto; background: white; padding: 40px; 
                border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); 
            }}
            h2 {{ color: #333; margin-bottom: 30px; }}
            a {{ 
                text-decoration: none; font-weight: bold; transition: all 0.3s ease; 
                display: inline-block; padding: 2px 5px;
            }}
            a:hover {{ transform: scale(1.2); opacity: 1 !important; text-decoration: underline; }}
            .footer {{ margin-top: 20px; font-size: 12px; color: #888; }}
        </style>
    </head>
    <body>
        <div class="cloud-container">
            <h2>☁️ Rheumatology Live Trends</h2>
            <p style="color:#666; font-size:14px;">Top 30 Journals • Last 30 Days</p>
            <div style="line-height: 1.8;">
    """
    
    colors = ["#2c3e50", "#c0392b", "#2980b9", "#8e44ad", "#27ae60", "#d35400", "#16a085", "#34495e"]
    random.shuffle(word_data)
    
    for word, count in word_data:
        font_size = max(14, min(50, 12 + (count * 1.5)))
        color = random.choice(colors)
        opacity = 0.7 + (min(count, 20) / 100)
        
        raw_query = f"({j_query}) AND {word} AND {d_query}"
        safe_query = urllib.parse.quote(raw_query)
        link = f"https://pubmed.ncbi.nlm.nih.gov/?term={safe_query}"
        
        html_content += f"""
        <a href="{link}" target="_blank" style="font-size: {font_size}px; color: {color}; opacity: {opacity}; margin: 5px 10px;">
           {word}
        </a>
        """
        
    html_content += f"""
            </div>
            <div class="footer">Updated: {datetime.date.today().strftime('%Y-%m-%d')}</div>
        </div>
    </body>
    </html>
    """
    
    # [핵심] 화면 출력이 아니라 파일로 저장합니다.
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("index.html 파일이 성공적으로 생성되었습니다.")

else:
    print("데이터 수집 실패")
