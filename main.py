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
# Top 30 저널 공식 약어
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

# === 데이터 처리 함수들 (기존과 동일) ===
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
    return Counter(keywords).most_common(70), journal_query, date_query_str

# === 메인 실행 ===
word_data, j_query, d_query = get_data(SEARCH_TERM, DAYS_BACK, TOP_JOURNALS)

if word_data:
    # D3.js가 이해할 수 있는 데이터 형식으로 변환
    d3_data = []
    max_count = word_data[0][1] if word_data else 1
    for word, count in word_data:
        # 링크 생성
        raw_query = f"({j_query}) AND {word} AND {d_query}"
        safe_query = urllib.parse.quote(raw_query)
        link = f"https://pubmed.ncbi.nlm.nih.gov/?term={safe_query}"
        # 글자 크기 정규화 (15~60px 사이)
        size = 15 + (count / max_count) * 45
        d3_data.append({"text": word, "size": size, "url": link, "count": count})

    # [핵심] D3.js를 이용한 HTML 생성
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Rheumatology Trends Cloud</title>
        <script src="https://d3js.org/d3.v5.min.js"></script>
        <script src="https://cdn.jsdelivr.net/gh/holtzy/D3-graph-gallery@master/LIB/d3.layout.cloud.js"></script>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background-color: #ffffff; text-align: center; overflow: hidden; }}
            #cloud-area {{ width: 100%; height: 700px; margin: 0 auto; }}
            .word-link {{ cursor: pointer; transition: opacity 0.2s; }}
            .word-link:hover {{ opacity: 0.7 !important; }}
            h2 {{ color: #333; margin: 20px 0 10px; }}
            .footer {{ font-size: 12px; color: #999; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h2>☁️ Rheumatology Live Trends</h2>
        <p class="footer">Top 30 Journals • Last 30 Days • Updated: {datetime.date.today().strftime('%Y-%m-%d')}</p>
        <div id="cloud-area"></div>

        <script>
            // 파이썬에서 만든 데이터를 자바스크립트로 가져옴
            var words = {json.dumps(d3_data)};

            // 색상 팔레트
            var myColor = d3.scaleOrdinal().range(["#2c3e50", "#c0392b", "#2980b9", "#8e44ad", "#27ae60", "#d35400", "#006064", "#16a085"]);

            // 워드클라우드 레이아웃 설정
            var layout = d3.layout.cloud()
                .size([window.innerWidth * 0.95, 700]) // 영역 크기
                .words(words.map(function(d) {{ return {{text: d.text, size: d.size, url: d.url, count: d.count}}; }}))
                .padding(5)        // 단어 간격
                .rotate(function() {{ return (~~(Math.random() * 2) * 90) - (~~(Math.random() * 2) * 45); }}) // 랜덤 회전 (0, 90, -45도 등)
                .font("Impact")    // 폰트
                .fontSize(function(d) {{ return d.size; }})
                .on("end", draw);

            layout.start();

            // 그리기 함수
            function draw(words) {{
              d3.select("#cloud-area").append("svg")
                  .attr("width", layout.size()[0])
                  .attr("height", layout.size()[1])
                .append("g")
                  .attr("transform", "translate(" + layout.size()[0] / 2 + "," + layout.size()[1] / 2 + ")")
                .selectAll("text")
                  .data(words)
                .enter().append("text")
                  .attr("class", "word-link")
                  .style("font-size", function(d) {{ return d.size + "px"; }})
                  .style("font-family", "Impact, sans-serif")
                  .style("fill", function(d, i) {{ return myColor(i); }})
                  .attr("text-anchor", "middle")
                  .attr("transform", function(d) {{
                    return "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")";
                  }})
                  .text(function(d) {{ return d.text; }})
                  .on("click", function(d) {{ window.open(d.url, '_blank'); }}) // 클릭 시 새 창 열기
                  .append("title") // 마우스 올리면 건수 표시
                  .text(function(d) {{ return d.text + " (" + d.count + " papers)"; }});
            }}
        </script>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

else:
    # 데이터가 없을 때 표시할 기본 화면
    with open("index.html", "w", encoding="utf-8") as f:
        f.write("<html><body><h2>No data found for the last 30 days.</h2></body></html>")
