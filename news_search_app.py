import streamlit as st
import requests
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor
from dateutil import parser as date_parser

# --- 1. 設定與權重定義 (整合您的 PDF 白名單) ---
HKT = pytz.timezone('Asia/Hong_Kong')

# 媒體權重字典：用於排序 (Tier 10 為最優先)
# 邏輯：只要 Google 回傳的網址包含以下關鍵字，即給予高分
MEDIA_TIERS = {
    "rthk.hk": 10, "now.com": 10, "metroradio.com.hk": 10, "i-cable.com": 10,
    "881903.com": 10, "tvb.com": 10, "yahoo.com": 10, "epochtimes.com": 10,
    "inmediahk.net": 10, "orangenews.hk": 10, "scmp.com": 10, "on.cc": 10,
    "mingpao.com": 10, "stheadline.com": 10, "hkej.com": 10, "hket.com": 10,
    "bbc.com": 10, "nytimes.com": 10, "reuters.com": 10, "apnews.com": 10,
    "cna.com.tw": 10, "udn.com": 10, "people.com.cn": 10, "xinhuanet.com": 10
}

# --- 2. 核心搜尋邏輯 ---

def fetch_google_news(query, cx, api_key, lr=None):
    """Google PSE 搜尋：負責深層搜尋您的白名單內容"""
    try:
        url = "https://googleapis.com"
        params = {
            "key": api_key, "cx": cx, "q": query,
            "dateRestrict": "m1", "num": 10, "hl": "zh-Hant"
        }
        if lr: params["lr"] = lr
        
        resp = requests.get(url, params=params, timeout=10).json()
        articles = []
        for item in resp.get("items", []):
            link = item.get("link", "").lower()
            # 自動匹配權重
            article_tier = 1
            source_display = item.get("displayLink", "")
            for key, val in MEDIA_TIERS.items():
                if key in link:
                    article_tier = val
                    source_display = key
                    break
            
            articles.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "source": source_display,
                "summary": item.get("snippet", ""),
                "published": None, # Google API 有時不提供精確發布時間
                "tier": article_tier,
                "origin": "Google/Bing"
            })
        return articles
    except: return []

def fetch_newsdata(query, api_key, country=None, language="cn"):
    """NewsData API：負責抓取白名單內的即時新聞"""
    try:
        url = f"https://newsdata.io{api_key}&q={query}&language={language}"
        if country: url += f"&country={country}"
        
        resp = requests.get(url, timeout=10).json()
        articles = []
        for item in resp.get("results", []):
            link = item.get("link", "").lower()
            article_tier = 1
            for key, val in MEDIA_TIERS.items():
                if key in link: article_tier = val; break
            
            dt = date_parser.parse(item.get("pubDate")).astimezone(HKT)
            articles.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "source": item.get("source_id"),
                "summary": item.get("description", "")[:200] + "...",
                "published": dt,
                "tier": article_tier,
                "origin": "NewsData"
            })
        return articles
    except: return []

# --- 3. UI 介面 (保留您的分類設計) ---

st.set_page_config(page_title="Global Citizens News Search", layout="wide")
st.title("🌐 全球公民新聞搜尋平台")

category = st.radio(
    "選擇媒體區域", 
    ["1. 香港媒體", "2. 中文地區媒體", "3. 世界英文媒體"],
    horizontal=True
)

search_query = st.text_input("輸入關鍵字 (過去 30 天)", placeholder="例如：香港經濟, AI 發展...")

if st.button("開始搜尋"):
    if not search_query:
        st.warning("請輸入關鍵字")
    else:
        with st.spinner("正在同步請求多方引擎與白名單..."):
            g_key = st.secrets["GOOGLE_API_KEY"]
            n_key = st.secrets["NEWSDATA_API_KEY"]
            
            # 分類切換邏輯
            if category == "1. 香港媒體":
                cx = st.secrets["CX_HK"]
                c_code, lang, lr = "hk", "cn", None
            elif category == "2. 中文地區媒體":
                cx = st.secrets["CX_WORLD"]
                c_code, lang, lr = None, "cn", "lang_zh-TW|lang_zh-CN"
            else: # 世界英文媒體
                cx = st.secrets["CX_WORLD"]
                c_code, lang, lr = None, "en", "lang_en"

            # 併發請求提高速度
            with ThreadPoolExecutor() as executor:
                f_google = executor.submit(fetch_google_news, search_query, cx, g_key, lr)
                f_newsdata = executor.submit(fetch_newsdata, search_query, n_key, c_code, lang)
                
                results = f_google.result() + f_newsdata.result()

            # 去重與排序 (權重分 > 時間)
            seen = set()
            unique = []
            for r in results:
                if r['link'] not in seen:
                    unique.append(r); seen.add(r['link'])

            sorted_news = sorted(
                unique, 
                key=lambda x: (x['tier'], x['published'].timestamp() if x['published'] else 0), 
                reverse=True
            )[:20]

            if not sorted_news:
                st.info("查無相關新聞。")
            else:
                for news in sorted_news:
                    st.markdown(f"### {news['title']}")
                    pub = news['published'].strftime('%Y-%m-%d %H:%M') if news['published'] else "近期結果"
                    st.caption(f"📅 {pub} | 🏛️ {news['source']} | 🏷️ 權重分: {news['tier']}")
                    st.write(news['summary'])
                    st.markdown(f"[閱讀全文]({news['link']})")
                    st.divider()
                st.info("💡 搜尋結果基於您的白名單名冊。")

