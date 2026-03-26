# Code Version: Ver 4.61 - 新增中國大陸媒體模式
# ====================

import streamlit as st
import feedparser
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}

TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}

# 中國大陸媒體白名單（重點優化簡體中文來源）
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}

# 英文國際媒體白名單
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

def get_domain(link):
    try:
        return urlparse(link).netloc.replace("www.", "")
    except:
        return "未知來源"

def clean_title_and_source(title):
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return title.strip(), ""

def clean_summary(text):
    if not text:
        return ""
    if '<a href' in text:
        text = text.split('<a href', 1)[0]
    if '<font color' in text:
        text = text.split('<font color', 1)[0]
    text = text.replace('<', ' ').replace('>', ' ').replace('&nbsp;', ' ').strip()
    return text

def is_relevant(title: str, summary: str, query: str) -> bool:
    if not query or not title:
        return True
    q_lower = query.lower().strip()
    title_lower = title.lower()
    summary_lower = summary.lower() if summary else ""
    return q_lower in title_lower or q_lower in summary_lower

def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        articles = []
        for entry in feed.entries:
            link = entry.get('link', '')
            if link:
                articles.append({
                    "title": entry.get('title', '無標題'),
                    "link": link,
                    "summary": clean_summary(entry.get('summary', entry.get('description', ''))),
                    "published": entry.get('published_parsed')
                })
        return articles
    except Exception as e:
        st.error(f"Google News 拉取失敗: {e}")
        return []

def build_url(query, gl, hl, ceid, start_date=None, end_date=None, sites=None, use_exact=True):
    q_clean = query.strip()
    if not q_clean:
        q = ""
    else:
        if use_exact and not any(c.isascii() and not c.isalnum() and c not in " -'" for c in q_clean):
            phrase = q_clean.replace(" ", "+")
            q = f"%22{phrase}%22"
        else:
            words = q_clean.split()
            q = "+AND+".join(words) if len(words) > 1 else q_clean
    
    if sites:
        site_str = "+OR+".join(f"site:{s}" for s in sites)
        q = f"({q})+({site_str})" if q else site_str
    
    date_parts = []
    if start_date:
        date_parts.append(f"after:{start_date.strftime('%Y-%m-%d')}")
    if end_date:
        date_parts.append(f"before:{end_date.strftime('%Y-%m-%d')}")
    date_str = "+" + "+".join(date_parts) if date_parts else ""
    
    return f"https://news.google.com/rss/search?q={q}{date_str}&hl={hl}&gl={gl}&ceid={ceid}"

# ==================== UI ====================
st.set_page_config(page_title="全球新聞搜尋平台", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("🔧 Ver 4.61 - 新增中國大陸媒體模式")

region_options = [
    "1. 香港媒體（優先白名單）", 
    "2. 台灣/世界華文媒體", 
    "3. 英文全球媒體",
    "4. 中國大陸媒體（簡體中文）"
]
region = st.radio("選擇搜尋區域", region_options, horizontal=True)

query = st.text_input("輸入關鍵字", placeholder="例如：宏福苑、Larry Fink、Trump Gold Card、习近平")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("開始日期（預設3天）", value=date.today() - timedelta(days=3))
with col2:
    end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query:
        st.warning("請輸入關鍵字")
        st.stop()

    is_hk = "香港" in region
    is_taiwan_world = "台灣/世界華文" in region
    is_english_global = "英文全球" in region
    is_mainland = "中國大陸" in region

    if is_mainland:
        white_list = MAINLAND_CHINA_WHITE_LIST
        gl = "CN"
        hl = "zh-CN"
        ceid = "CN:zh-Hans"
        use_exact = True
    elif is_english_global:
        white_list = ENGLISH_GLOBAL_LIST
        gl = "US"
        hl = "en"
        ceid = "US:en"
        use_exact = False
    elif is_hk:
        white_list = HK_WHITE_LIST
        gl = "HK"
        hl = "zh-HK"
        ceid = "HK:zh-Hant"
        use_exact = True
    else:  # 台灣/世界華文媒體
        white_list = TAIWAN_WORLD_WHITE_LIST
        gl = "TW"
        hl = "zh-TW"
        ceid = "TW:zh-Hant"
        use_exact = True

    with st.spinner("正在搜尋並過濾..."):
        batch_size = 8
        white_results = []
        for i in range(0, len(white_list), batch_size):
            batch = list(white_list)[i:i+batch_size]
            url = build_url(query, gl, hl, ceid, start_date, end_date, batch, use_exact)
            white_results.extend(fetch_google_news(url))

        full_url = build_url(query, gl, hl, ceid, start_date, end_date, None, use_exact)
        supplement = fetch_google_news(full_url)

        seen_links = {item["link"] for item in white_results}
        supplement = [item for item in supplement if item["link"] not in seen_links]

        all_results = white_results + supplement
        all_results = [item for item in all_results if is_relevant(item["title"], item.get("summary", ""), query)]

        for item in all_results:
            clean_title, source_from_title = clean_title_and_source(item["title"])
            item["title"] = clean_title
            item["source"] = source_from_title or get_domain(item["link"])
            if item.get("published"):
                dt = datetime(*item["published"][:6])
                item["published_hkt"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")
            else:
                item["published_hkt"] = "未知時間"

        all_results.sort(key=lambda x: x.get("published", (0,)), reverse=True)

        st.success(f"找到 {len(all_results)} 則相關新聞")

        for news in all_results:
            st.markdown(f"### {news['title']}")
            st.caption(f"來源：{news['source']} | {news['published_hkt']}")
            st.write(news.get("summary", ""))
            st.markdown(f"[閱讀全文]({news['link']})")
            st.divider()