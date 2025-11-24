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
        print(f"검색 중 에러 발생: {e}")
        return [], "", ""
        
    if not id_list: 
        print("검색 결과 없음")
        return [], "", ""

    print(f"-> 논문 {len(id_list)}편 발견. 키워드 추출 중...")
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
    print(f"데이터 수집 중 치명적 오류: {e}")
    word_data = []

# === HTML 템플릿 (안전한 일반 문자열) ===
# 이곳에는 파이썬 변수 {} 가 없어서 에러가 절대 안 납니다.
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
        body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; text-align: center; }
        #container { max-width: 950px; margin: 0 auto; background: white; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); padding: 30px; }
        h2 { color: #2c3e50; margin: 10px 0; font-weight: 800; letter-spacing: -1px; }
        .footer { font-size: 13px; color: #95a5a6; margin-bottom: 20px; }
        .word-link { cursor: pointer; transition: all 0.2s ease; }
        .word-link:hover { opacity: 0.8 !important; }
    </style>
</head>
<body>
    <div id="container">
        <h2>☁️ Rheumatology Live Trends</h2>
        <p class="footer">Top 30 Journals • Last 30 Days • Updated: __DATE_PLACEHOLDER__</p>
        <div id="cloud-area"></div>
    </div>

    <script>
        // 데이터 주입되는 곳
        var words = __DATA_PLACEHOLDER__;
        
        var myColor = d3.scaleOrdinal().range(["#2c3e50", "#c0392b", "#2980b9", "#8e44ad", "#27ae60", "#d35400", "#006064"]);

        var layout = d3.layout.cloud()
            .size([900, 600])
            .words(words.map(function(d) { return {text: d.text, size: d.size, url: d.url, count: d.count}; }))
            .padding(4)
            .rotate(function() { return (~~(Math.random() * 6) - 3) * 30; })
            .font("Impact")
            .fontSize(function(d) { return d.size; })
            .on("end", draw);

        layout.start();

        function draw(words) {
          d3.select("#cloud-area").append("svg")
              .attr("width", layout.size()[0])
              .attr("height", layout.size()[1])
            .append("g")
              .attr("transform", "translate(" + layout.size()[0] / 2 + "," + layout.size()[1] / 2 + ")")
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

# === 데이터 주입 및 파일 저장 ===
if word_data:
    d3_data = []
    max_count = word_data[0][1] if word_data else 1
    for word, count in word_data:
        raw_query = f"({j_query}) AND {word} AND {d_query}"
        safe_query = urllib.parse.quote(raw_query)
        link = f"https://pubmed.ncbi.nlm.nih.gov/?term={safe_query}"
        
        # 격차 확대 (10~90)
        size = 10 + (count / max_count) * 80
        d3_data.append({"text": word, "size": size, "url": link, "count": count})

    # 파이썬 데이터를 JSON 문자로 변환
    json_str = json.dumps(d3_data)
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    # 템플릿의 구멍(__DATA_PLACEHOLDER__)을 실제 데이터로 메꾸기
    final_html = html_template.replace("__DATA_PLACEHOLDER__", json_str)
    final_html = final_html.replace("__DATE_PLACEHOLDER__", today_str)
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("성공: index.html 생성 완료")
else:
    print("데이터 없음")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write("<h2>No Data Found</h2>")
