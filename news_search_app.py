import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單 (保持原樣) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

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
    if '<a href' in text: text = text.split('<a href', 1)[0]
    if '<font color' in text: text = text.split('<font color', 1)[0]
    text = re.sub(r'<[^>]+>', ' ', text)
    return text.replace('&nbsp;', ' ').strip()

def is_relevant(title: str, summary: str, query: str) -> bool:
    if not query or not title: return True
    q = query.lower().strip()
    return q in title.lower() or q in (summary or "").lower()

def filter_by_date(articles, start_date, end_date):
    if not start_date or not end_date: return articles
    filtered = []
    for item in articles:
        pub = item.get("published")
        if pub:
            try:
                if isinstance(pub, str): dt = datetime.fromisoformat(pub.replace("Z", "+00:00")).date()
                else: dt = date(*pub[:3])
                if start_date <= dt <= end_date: filtered.append(item)
            except: filtered.append(item)
        else: filtered.append(item)
    return filtered

def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        return [{"title": e.get('title', '無標題'), "link": e.get('link', ''), "summary": clean_summary(e.get('summary', e.get('description', ''))), "published": e.get('published_parsed'), "source_type": "Google"} for e in feed.entries if e.get('link')]
    except: return []

GNEWS_API_URL = "https://gnews.io/api/v4/search"

def fetch_gnews(query, start_date, end_date, lang, country, api_key, max_articles=60):
    try:
        params = {"token": api_key, "q": query, "from": start_date.strftime("%Y-%m-%dT00:00:00Z"), "to": end_date.strftime("%Y-%m-%dT23:59:59Z"), "lang": lang, "country": country, "max": max_articles, "sortby": "publishedAt"}
        data = requests.get(GNEWS_API_URL, params=params, timeout=25).json()
        articles = [{"title": a.get("title", "無標題"), "link": a.get("url", ""), "summary": a.get("description", ""), "published": a.get("publishedAt"), "source_type": "GNews"} for a in data.get("articles", [])]
        return articles, data.get("totalArticles", 0)
    except: return [], 0

def build_url(query, gl, hl, ceid, start_date=None, end_date=None, sites=None):
    q = query.strip().replace(" ", "+")
    if sites: q = f"({q})+({'+OR+'.join(f'site:{s}' for s in sites)})"
    d_str = (f"+after:{start_date.strftime('%Y-%m-%d')}" if start_date else "") + (f"+before:{end_date.strftime('%Y-%m-%d')}" if end_date else "")
    return f"https://news.google.com/rss/search?q={q}{d_str}&hl={hl}&gl={gl}&ceid={ceid}"

# ==================== UI ====================
st.set_page_config(page_title="全球新聞搜尋平台", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("🔧 Ver 6.9.2 - 修正舊新聞排序 TypeError 問題")

api_key = st.text_input("GNews API Key", type="password")
region_opt = ["1. 香港媒體（優先 white list）", "2. 台灣/世界華文媒體", "3. 英文全球媒體", "4. 中國大陸媒體（簡體中文）"]
region = st.radio("選擇主要搜尋區域", region_opt, horizontal=True)
use_hybrid = st.checkbox("✅ 啟用合併搜尋測試模式", value=False)
query = st.text_input("輸入關鍵字")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()
    
    if "中國大陸" in region: white_list, gl, hl, ceid, g_l, g_c = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region: white_list, gl, hl, ceid, g_l, g_c = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif "香港" in region: white_list, gl, hl, ceid, g_l, g_c = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else: white_list, gl, hl, ceid, g_l, g_c = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("正在搜尋..."):
        all_results = []
        google_raw, gnews_raw, gnews_total = 0, 0, 0
        is_old_news = (end_date - start_date).days > 90

        # 抓取 Google
        batch_size = 8
        for i in range(0, len(white_list), batch_size):
            res = fetch_google_news(build_url(query, gl, hl, ceid, start_date, end_date, list(white_list)[i:i+batch_size]))
            google_raw += len(res)
            all_results.extend(res)

        # 抓取 Gnews
        if is_old_news or use_hybrid:
            gn_res, gnews_total = fetch_gnews(query, start_date, end_date, g_l, g_c, api_key)
            gnews_raw = len(gn_res)
            seen = {item.get("link") for item in all_results if item.get("link")}
            all_results.extend([a for a in gn_res if a.get("link") not in seen])

        # 處理與排序 (修正 TypeError 處)
        processed = filter_by_date(all_results, start_date, end_date) if not is_old_news else all_results
        
        # 統一時間格式供排序與顯示
        final_list = []
        seen_final = set()
        for item in processed:
            if item.get("link") in seen_final: continue
            seen_final.add(item.get("link"))
            
            # 清洗標題與來源
            t, s_t = clean_title_and_source(item.get("title", ""))
            item["title"] = t
            base_s = s_t or get_domain(item.get("link", ""))
            item["source"] = f"{base_s} ({item['source_type']})"
            
            # 轉換時間物件
            try:
                pub = item.get("published")
                if isinstance(pub, str): dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                else: dt = datetime(*pub[:6], tzinfo=pytz.UTC)
                item["sort_dt"] = dt
                item["display_time"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")
            except:
                item["sort_dt"] = datetime(1970, 1, 1, tzinfo=pytz.UTC)
                item["display_time"] = "未知時間"
            
            if is_old_news or is_relevant(item["title"], item.get("summary", ""), query):
                final_list.append(item)

        final_list.sort(key=lambda x: x["sort_dt"], reverse=True)

        st.success(f"找到 {len(final_list)} 則相關新聞")
        for news in final_list:
            st.markdown(f"### [{news['title']}]({news['link']})")
            st.caption(f"來源：{news['source']} | {news['display_time']}")
            st.write(news.get("summary", ""))
            st.divider()

        st.subheader("🔍 詳細搜尋診斷面板")
        st.write(f"Google 抓取: **{google_raw}** | GNews 抓取: **{gnews_raw}** | API 總計: **{gnews_total}** | 最終顯示: **{len(final_list)}**")