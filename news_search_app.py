import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單 (保持不變) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# ==================== 工具函數 (保持不變) ====================
def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "")
    except: return "未知來源"

def clean_title_and_source(title):
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return title.strip(), ""

def clean_summary(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    return text.replace('&nbsp;', ' ').strip()

def is_relevant(title: str, summary: str, query: str) -> bool:
    if not query: return True
    q = query.lower().strip()
    return q in title.lower() or q in (summary or "").lower()

def filter_by_date(articles, start_date, end_date):
    if not start_date or not end_date: return articles
    filtered = []
    for item in articles:
        pub = item.get("published")
        try:
            if isinstance(pub, str): dt = datetime.fromisoformat(pub.replace("Z", "+00:00")).date()
            else: dt = date(*pub[:3])
            if start_date <= dt <= end_date: filtered.append(item)
        except: filtered.append(item)
    return filtered

# ==================== API 抓取 (修正重點) ====================
def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        return [{
            "title": e.get('title', '無標題'),
            "link": e.get('link', ''),
            "summary": clean_summary(e.get('summary', e.get('description', ''))),
            "published": e.get('published_parsed'),
            "source_type": "Google"
        } for e in feed.entries if e.get('link')]
    except: return []

GNEWS_API_URL = "https://gnews.io/api/v4/search"

def fetch_gnews(query, start_date, end_date, lang, country, api_key, max_articles=60):
    try:
        params = {
            "token": api_key, "q": query, "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "to": end_date.strftime("%Y-%m-%dT23:59:59Z"), "lang": lang, "country": country,
            "max": max_articles, "sortby": "publishedAt"
        }
        resp = requests.get(GNEWS_API_URL, params=params, timeout=25)
        data = resp.json()
        articles = []
        for a in data.get("articles", []):
            articles.append({
                "title": a.get("title", "無標題"),
                "link": a.get("url", ""), # 這裡定義了 link
                "summary": a.get("description", ""),
                "published": a.get("publishedAt"),
                "source_type": "GNews"
            })
        return articles, data.get("totalArticles", 0)
    except: return [], 0

def build_url(query, gl, hl, ceid, start_date=None, end_date=None, sites=None):
    q = query.strip().replace(" ", "+")
    if sites: q = f"({q})+({'+OR+'.join(f'site:{s}' for s in sites)})"
    date_str = ""
    if start_date: date_str += f"+after:{start_date.strftime('%Y-%m-%d')}"
    if end_date: date_str += f"+before:{end_date.strftime('%Y-%m-%d')}"
    return f"https://news.google.com/rss/search?q={q}{date_str}&hl={hl}&gl={gl}&ceid={ceid}"

# ==================== UI & 邏輯 (修正重點) ====================
st.set_page_config(page_title="全球新聞搜尋平台", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("Ver 6.9.1 - 修正 Gnews 顯示邏輯")

api_key = st.text_input("GNews API Key", type="password")
region_options = ["1. 香港媒體（優先白名單）", "2. 台灣/世界華文媒體", "3. 英文全球媒體", "4. 中國大陸媒體（簡體中文）"]
region = st.radio("選擇主要搜尋區域", region_options, horizontal=True)
use_hybrid = st.checkbox("✅ 啟用合併搜尋測試模式（90 天分界測試）", value=False)
query = st.text_input("輸入關鍵字")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()
    
    # 區域設定 (簡化邏輯不變)
    if "中國大陸" in region: white_list, gl, hl, ceid, g_l, g_c = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region: white_list, gl, hl, ceid, g_l, g_c = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif "香港" in region: white_list, gl, hl, ceid, g_l, g_c = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else: white_list, gl, hl, ceid, g_l, g_c = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("搜尋中..."):
        all_results = []
        google_raw, gnews_raw, gnews_total = 0, 0, 0
        is_old_news = (end_date - start_date).days > 90

        # 1. 抓取 Google News
        batch_size = 8
        for i in range(0, len(white_list), batch_size):
            batch = list(white_list)[i:i+batch_size]
            url = build_url(query, gl, hl, ceid, start_date, end_date, batch)
            res = fetch_google_news(url)
            google_raw += len(res)
            all_results.extend(res)

        # 2. 處理 Gnews (修正重點)
        if is_old_news or use_hybrid:
            gn_articles, gnews_total = fetch_gnews(query, start_date, end_date, g_l, g_c, api_key)
            gnews_raw = len(gn_articles)
            
            seen_links = {item["link"] for item in all_results if item.get("link")}
            for a in gn_articles:
                if a["link"] not in seen_links:
                    all_results.append(a) # 直接添加 fetch_gnews 格式化後的字典

        # 3. 過濾與去重
        if not is_old_news:
            unique_results = filter_by_date(all_results, start_date, end_date)
            unique_results = [item for item in unique_results if is_relevant(item.get("title", ""), item.get("summary", ""), query)]
        else:
            # 舊新聞模式去重
            temp_seen = set()
            unique_results = []
            for item in all_results:
                if item["link"] not in temp_seen:
                    unique_results.append(item)
                    temp_seen.add(item["link"])

        # 4. 格式化顯示 (修正 Key 讀取)
        for item in unique_results:
            orig_title = item.get("title", "無標題")
            clean_t, src_t = clean_title_and_source(orig_title)
            item["display_title"] = clean_t
            base_src = src_t or get_domain(item.get("link", ""))
            item["display_source"] = f"{base_src} ({item['source_type']})"

            try:
                pub = item.get("published")
                if isinstance(pub, str): dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                else: dt = datetime(*pub[:6])
                item["hkt"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")
            except: item["hkt"] = "未知時間"

        unique_results.sort(key=lambda x: x.get("published", ""), reverse=True)

        # 5. 渲染 UI
        st.success(f"找到 {len(unique_results)} 則新聞")
        for news in unique_results:
            st.markdown(f"### [{news['display_title']}]({news['link']})")
            st.caption(f"來源：{news['display_source']} | {news['hkt']}")
            st.write(news.get("summary", ""))
            st.divider()

        with st.expander("🔍 診斷面板"):
            st.write(f"Google 抓取: {google_raw} | GNews 抓取: {gnews_raw} | API 總量: {gnews_total}")


