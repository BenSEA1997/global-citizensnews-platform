import streamlit as st
import requests
from datetime import datetime, timedelta
import pytz
from concurrent.futures import ThreadPoolExecutor
from dateutil import parser as date_parser

# --- 1. 設定與權重定義 (白名單 Tier) ---
HKT = pytz.timezone('Asia/Hong_Kong')

# 根據您的白名單整理的權重表
MEDIA_TIERS = {
    # 香港 Tier 10 (最優先)
    "rthk.hk": 10, "on.cc": 10, "mingpao.com": 10, "scmp.com": 10, "hkej.com": 10, "hket.com": 10,
    "stheadline.com": 10, "now.com": 10, "tvb.com": 10, "am730.com.hk": 10, "hk01.com": 10,
    # 國際/兩岸 Tier 10
    "bbc.com": 10, "nytimes.com": 10, "reuters.com": 10, "apnews.com": 10, "cna.com.tw": 10,
    "udn.com": 10, "ltn.com.tw": 10, "people.com.cn": 10, "xinhuanet.com": 10, "zaobao.com": 10,
    # 其他權重 (可根據需要續加)
}

# --- 2. 核心搜尋函式 ---

def fetch_google_news(query, cx, api_key, lr=None):
    """從 Google Custom Search 抓取 (負責深度與副頁)"""
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
            domain = item.get("displayLink", "").lower().replace("www.", "")
            articles.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "source": domain,
                "summary": item.get("snippet", ""),
                "published": None, # Google API 有時不提供精確時間
                "tier": MEDIA_TIERS.get(domain, 1),
                "origin": "Google/Bing"
            })
        return articles
    except: return []

def fetch_newsdata(query, api_key, country=None, language="cn"):
    """從 NewsData.io 抓取 (負責即時新聞流)"""
    try:
        url = f"https://newsdata.io{api_key}&q={query}&language={language}"
        if country: url += f"&country={country}"
        
        resp = requests.get(url, timeout=10).json()
        articles = []
        for item in resp.get("results", []):
            domain = item.get("source_id", "").lower()
            # 轉換時間
            dt = date_parser.parse(item.get("pubDate")).astimezone(HKT)
            articles.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "source": domain,
                "summary": item.get("description", "")[:200] + "...",
                "published": dt,
                "tier": MEDIA_TIERS.get(domain, 1),
                "origin": "NewsData"
            })
        return articles
    except: return []

# --- 3. Streamlit UI 介面 ---

st.set_page_config(page_title="Global Citizens News Search", layout="wide")
st.title("🌐 全球公民新聞搜尋平台 (測試版)")

# 分類與提示
category = st.radio(
    "選擇媒體區域", 
    ["香港媒體", "台灣/中國/世界華文媒體", "世界英文媒體"],
    horizontal=True
)

search_query = st.text_input("輸入關鍵字 (搜尋範圍：過去 30 天)", placeholder="例如：AI 發展, 香港經濟...")

if st.button("開始精準搜尋"):
    if not search_query:
        st.warning("請輸入關鍵字")
    else:
        with st.spinner("正在同步請求多方引擎，請稍候..."):
            # 根據分類選擇參數
            google_key = st.secrets["GOOGLE_API_KEY"]
            newsdata_key = st.secrets["NEWSDATA_API_KEY"]
            
            if category == "香港媒體":
                cx = st.secrets["CX_HK"]
                c_code, lang, lr = "hk", "cn", None
            elif category == "台灣/中國/世界華文媒體":
                cx = st.secrets["CX_WORLD"]
                c_code, lang, lr = None, "cn", "lang_zh-TW|lang_zh-CN"
            else: # 世界英文媒體
                cx = st.secrets["CX_WORLD"]
                c_code, lang, lr = None, "en", "lang_en"

            # 7. 同時發出搜尋請求 (並發處理)
            with ThreadPoolExecutor() as executor:
                future_google = executor.submit(fetch_google_news, search_query, cx, google_key, lr)
                future_newsdata = executor.submit(fetch_newsdata, search_query, newsdata_key, c_code, lang)
                
                google_results = future_google.result()
                newsdata_results = future_newsdata.result()

            # 5. 整合與排序：白名單 Tier 優先，NewsData 補足
            all_results = google_results + newsdata_results
            
            # 去重 (根據網址)
            seen_links = set()
            unique_results = []
            for r in all_results:
                if r['link'] not in seen_links:
                    unique_results.append(r)
                    seen_links.add(r['link'])

            # 最終排序：Tier 分數 (高到低) -> 時間 (新到舊)
            # 註：Google 沒時間的會排在同 Tier 的後面
            sorted_results = sorted(
                unique_results, 
                key=lambda x: (x['tier'], x['published'].timestamp() if x['published'] else 0), 
                reverse=True
            )[:20] # 限制顯示 20 則

            # 顯示結果
            if not sorted_results:
                st.info("查無過去 30 天內的相關新聞。")
            else:
                for idx, news in enumerate(sorted_results):
                    st.markdown(f"### {idx+1}. {news['title']}")
                    # 6. 顯示時間、來源與部分內容
                    pub_str = news['published'].strftime('%Y-%m-%d %H:%M') if news['published'] else "近期 (Google 深層結果)"
                    st.caption(f"📅 發布時間: {pub_str} | 🏛️ 來源: {news['source']} | 🏷️ 權重分: {news['tier']}")
                    st.write(news['summary'])
                    st.markdown(f"[閱讀全文]({news['link']})")
                    st.divider()
                
                st.info("💡 搜尋結果為過去 30 天。部分深層結果由 Google/Bing 提供，可能不含精確發布時間。")

# 頁尾保持不變
st.markdown("---")
st.caption("© 2026 全球公民新聞平台 - 測試版 | API 配額有限，請節約使用")
