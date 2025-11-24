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
        size = 10 + (count / max_count) * 80 
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
            /* [핵심 수정] 스크롤바 없애기 & 여백 최소화 */
            body {{ 
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
                margin: 0; padding: 0; 
                background-color: #ffffff; 
                text-align: center; 
                overflow: hidden; /* 스크롤바 강제 제거 */
            }}
            #container {{ width: 100%; height: 100%; margin: 0 auto; padding: 10px; box-sizing: border-box; }}
            h2 {{ color: #2c3e50; margin: 5px 0 0 0; font-weight: 800; font-size: 24px; }}
            .footer {{ font-size: 12px; color: #95a5a6; margin-bottom: 5px; }}
            .word-link {{ cursor: pointer; transition: all 0.2s ease; }}
            .word-link:hover {{ opacity: 0.8 !important; }}
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
            var myColor = d3.scaleOrdinal().range(["#2c3e50", "#c0392b", "#2980b9", "#8e44ad", "#27ae60", "#d35400", "#006064"]);

            var layout = d3.layout.cloud()
                .size([700, 550]) // [핵심 수정] 가로폭을 900 -> 700으로 줄임 (블로그에 딱 맞게)
                .words(words.map(function(d) {{ return {{text: d.text, size: d.size, url: d.url, count: d.count}}; }}))
                .padding(3) 
                .rotate(function() {{ return (~~(Math.random() * 6) - 3) * 30; }})
                .font("Impact")
                .fontSize(function(d) {{ return d.size; }})
                .on("end", draw);

            layout.start();

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
                  .on("click", function(d) {{ window.open(d.url, '_blank'); }})
                  .append("title")
                  .text(function(d) {{ return d.text + " (" + d.count + " papers)"; }});
            }}
        </script>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)
else:
    with open("index.html", "w", encoding="utf-8") as f: f.write("<h2>No data found.</h2>")
