import streamlit as st
import requests
from concurrent.futures import ThreadPoolExecutor

# --- 1. 媒體權重定義 (白名單 Tier) ---
MEDIA_TIERS = {
    "rthk.hk": 10, "on.cc": 10, "mingpao.com": 10, "scmp.com": 10,
    "now.com": 10, "tvb.com": 10, "stheadline.com": 10, "hkej.com": 10,
    "hket.com": 10, "bbc.com": 10, "nytimes.com": 10, "reuters.com": 10,
    "cna.com.tw": 10, "udn.com": 10, "people.com.cn": 10, "xinhuanet.com": 10
}

# --- 2. 核心搜尋邏輯 ---

def fetch_google_news(query, cx, api_key, lr=None):
    try:
        url = "https://googleapis.com"
        params = {
            "key": api_key.strip(), 
            "cx": cx.strip(), 
            "q": query,
            "num": 10,
            "hl": "zh-Hant"
        }
        if lr: params["lr"] = lr
        
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            st.error(f"Google 引擎報錯 (HTTP {resp.status_code})")
            return []
            
        data = resp.json()
        articles = []
        for item in data.get("items", []):
            link = item.get("link", "").lower()
            article_tier = 1
            source_display = item.get("displayLink", "")
            
            # 權重匹配邏輯
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
                "tier": article_tier,
                "origin": "Google"
            })
        return articles
    except: return []

# --- 3. Streamlit UI 介面 ---

st.set_page_config(page_title="Global Citizens News Search", layout="wide")
st.title("🌐 全球公民新聞搜尋平台")

category = st.radio(
    "選擇媒體區域", 
    ["1. 香港媒體 (Engine A)", "2. 其他媒體 (Engine B)"],
    horizontal=True
)

search_query = st.text_input("輸入關鍵字 (過去 30 天)", placeholder="例如：香港經濟, AI 發展...")

if st.button("開始搜尋"):
    if not search_query:
        st.warning("請輸入關鍵字")
    else:
        with st.spinner("正在搜尋白名單新聞..."):
            try:
                g_key = st.secrets["GOOGLE_API_KEY"]
                cx = st.secrets["CX_HK"] if "Engine A" in category else st.secrets["CX_WORLD"]
            except Exception as e:
                st.error(f"Secrets 設定有誤: {e}")
                st.stop()

            # 執行搜尋
            results = fetch_google_news(search_query, cx, g_key)

            if not results:
                st.info("💡 目前此組合無搜尋結果。請檢查關鍵字或更換區域。")
            else:
                # 按照權重排序
                sorted_results = sorted(results, key=lambda x: x['tier'], reverse=True)
                for news in sorted_results:
                    st.markdown(f"### {news['title']}")
                    st.caption(f"🏛️ 來源: {news['source']} | 🏷️ 權重分: {news['tier']}")
                    st.write(news['summary'])
                    st.markdown(f"[閱讀全文]({news['link']})")
                    st.divider()

st.markdown("---")
st.caption("© 2026 全球公民新聞平台 - 基於您的自定義白名單")







