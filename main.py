import requests
import xml.etree.ElementTree as ET
from collections import Counter
import datetime
import time
import urllib.parse
import json

# === 설정 ===
SEARCH_TERM = "Rheumatology"
DAYS_BACK = 30
MAX_PAPERS = 1000
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

def get_data(term, days, journal_list):
    journal_query = " OR ".join([f'"{j}"[Journal]' for j in journal_list])
    today = datetime.date.today()
    past_date = today - datetime.timedelta(days=days)
    date_query_str = f'"{past_date.strftime("%Y/%m/%d")}":"{today.strftime("%Y/%m/%d")}"[dp]'
    full_query = f"({journal_query}) AND {term} AND {date_query_str}"
    
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": full_query, "retmode": "json", "retmax": MAX_PAPERS, "sort": "date"}
    resp = requests.get(search_url, params=params)
    if 'esearchresult' not in resp.json(): return [], "", ""
    id_list = resp.json()['esearchresult']['idlist']
    if not id_list: return [], "", ""

    keywords = []
    batch_size = 100
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    for i in range(0, len(id_list), batch_size):
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
    return Counter(keywords).most_common(80), journal_query, date_query_str

word_data, j_query, d_query = get_data(SEARCH_TERM, DAYS_BACK, TOP_JOURNALS)

if word_data:
    d3_data = []
    max_count = word_data[0][1] if word_data else 1
    for word, count in word_data:
        raw_query = f"({j_query}) AND {word} AND {d_query}"
        safe_query = urllib.parse.quote(raw_query)
        link = f"https://pubmed.ncbi.nlm.nih.gov/?term={safe_query}"
        size = 10 + (count / max_count) * 90 
        d3_data.append({"text": word, "size": size, "url": link, "count": count})

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Rheumatology Trends Cloud</title>
        <script src="https://d3js.org/d3.v5.min.js"></script>
        <script src="https://cdn.jsdelivr.net/gh/holtzy/D3-graph-gallery@master/LIB/d3.layout.cloud.js"></script>
        <style>
            body {{ 
                margin: 0; padding: 0; 
                background-color: #ffffff; 
                text-align: center; 
            }}
            #container {{ 
                width: 100%; 
                margin: 0 auto; 
                padding: 10px 0;
            }}
            h2 {{ color: #2c3e50; margin: 10px 0; font-family: 'Segoe UI', sans-serif; font-size: 24px; }}
            .footer {{ font-size: 12px; color: #95a5a6; font-family: sans-serif; margin-bottom: 5px; }}
            .word-link {{ cursor: pointer; transition: all 0.2s ease; }}
            .word-link:hover {{ opacity: 0.7 !important; }}
            
            /* [핵심 수정] 무조건 꽉 차게 만들기 */
            svg {{ 
                width: 95%; /* 화면의 95%를 차지해라 */
                height: auto; /* 높이는 알아서 맞춰라 */
                max-width: 900px; /* 너무 커지지는 마라 */
                display: block;
                margin: 0 auto;
            }}
        </style>
    </head>
    <body>
        <div id="container">
            <h2>☁️ Rheumatology Live Trends</h2>
            <p class="footer">Top 30 Journals • Last 30 Days • Updated: {datetime.date.today().strftime('%Y-%m-%d')}</p>
            <div id="cloud-area"></div>
        </div>

        <script>
            var words = {json.dumps(d3_data)};
