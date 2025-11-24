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
    print(f"-> 검색 시작: {term}")
    journal_query = " OR ".join([f'"{j}"[Journal]' for j in journal_list])
    today = datetime.date.today()
    past_date = today - datetime.timedelta(days=days)
    date_query_str = f'"{past_date.strftime("%Y/%m/%d")}":"{today.strftime("%Y/%m/%d")}"[dp]'
    full_query = f"({journal_query}) AND {term} AND {date_query_str}"
    
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": full_query, "retmode": "json", "retmax": MAX_PAPERS, "sort": "date"}
    
    try:
        resp = requests.get(search_url, params=params)
        data = resp.json()
        if 'esearchresult' not in data: return [], "", ""
        id_list = data['esearchresult']['idlist']
    except Exception as e:
        print(f"검색 에러: {e}")
        return [], "", ""
        
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

# === 메인 실행 ===
try:
    word_data, j_query, d_query = get_data(SEARCH_TERM, DAYS_BACK, TOP_JOURNALS)
except Exception as e:
    print(f"데이터 처리 중 오류: {e}")
    word_data = []

# === HTML 템플릿 (봉인 해제 버전) ===
html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rheumatology Trends Cloud</title>
    <script src="https://d3js.org/d3.v5.min.js"></script>
    <script src="https://cdn.jsdelivr.net/gh/holtzy/D3-graph-gallery@master/LIB/d3.layout.cloud.js"></script>
    <style>
        body { 
            margin: 0; padding: 0; 
            background-color: #ffffff; 
            text-align: center; 
            overflow: hidden; 
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            height: 100vh;
        }
        #container { 
            width: 100%; 
            height: 100%;
            display: flex; flex-direction: column; align-items: center; 
        }
        h2 { color: #2c3e50; margin: 20px 0 5px 0; font-family: 'Segoe UI', sans-serif; font-size: 2.5em; font-weight: 800; }
        .footer { font-size: 1em; color: #95a5a6; font-family: sans-serif; margin-bottom: 10px; }
        .word-link { cursor: pointer; transition: all 0.2s ease; }
        .word-link:hover { opacity: 0.7 !important; }
        
        /* [핵심 수정] 제한을 풀고 화면에 꽉 차게 설정 */
        #cloud-area { width: 100%; flex-grow: 1; display: flex; align-items: center; justify-content: center; }
        svg { width: 100%; height: 100%; display: block; }
    </style>
</head>
<body>
    <div id="container">
        <h2>☁️ Rheumatology Live Trends</h2>
        <p class="footer">Top 30 Journals • Last 30 Days • Updated: __DATE_PLACEHOLDER__</p>
        <div id="cloud-area"></div>
    </div>

    <script>
        var words = __DATA_PLACEHOLDER__;
        var myColor = d3.scaleOrdinal().range(["#2c3e50", "#c0392b", "#2980b9", "#8e44ad", "#27ae60", "#d35400", "#006064"]);

        // 캔버스 크기를 조금 더 키워서 해상도를 높임
        var layoutWidth = 1000;
        var layoutHeight = 600;

        var layout = d3.layout.cloud()
            .size([layoutWidth, layoutHeight])
            .words(words.map(function(d) { return {text: d.text, size: d.size, url: d.url, count: d.count}; }))
            .padding(4) 
            .rotate(function() { return (~~(Math.random() * 6) - 3) * 30; })
            .font("Impact")
            .fontSize(function(d) { return d.size; })
            .on("end", draw);

        layout.start();

        function draw(words) {
          d3.select("#cloud-area").append("svg")
              // viewBox를 사용하여 브라우저 크기에 맞춰 늘어나게 함
              .attr("viewBox", "0 0 " + layoutWidth + " " + layoutHeight)
              .attr("preserveAspectRatio", "xMidYMid meet")
            .append("g")
              .attr("transform", "translate(" + layoutWidth / 2 + "," + layoutHeight / 2 + ")")
            .selectAll("text")
              .data(words)
            .enter().append("text")
              .attr("class", "word-link")
              .style("font-size", function(d) { return d.size + "px"; })
              .style("font-family", "Impact, sans-serif")
              .style("fill", function(d, i) { return myColor(i); })
              .attr("text-anchor", "middle")
              .attr("transform", function(d) {
                return "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")";
              })
              .text(function(d) { return d.text; })
              .on("click", function(d) { window.open(d.url, '_blank'); })
              .append("title")
              .text(function(d) { return d.text + " (" + d.count + " papers)"; });
        }
    </script>
</body>
</html>
"""

if word_data:
    d3_data = []
    max_count = word_data[0][1] if word_data else 1
    for word, count in word_data:
        raw_query = f"({j_query}) AND {word} AND {d_query}"
        safe_query = urllib.parse.quote(raw_query)
        link = f"https://pubmed.ncbi.nlm.nih.gov/?term={safe_query}"
        
        # 글자 크기를 더 키움 (최대 100px)
        size = 15 + (count / max_count) * 100
        d3_data.append({"text": word, "size": size, "url": link, "count": count})

    json_str = json.dumps(d3_data)
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    final_html = html_template.replace("__DATA_PLACEHOLDER__", json_str).replace("__DATE_PLACEHOLDER__", today_str)
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("성공: index.html 생성 완료")
else:
    print("데이터 없음")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write("<h2>No Data Found</h2>")
