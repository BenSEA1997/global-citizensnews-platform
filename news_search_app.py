import streamlit as st
import requests
from concurrent.futures import ThreadPoolExecutor

# --- 1. 媒體權重定義 (白名單 Tier) ---
# 只要網址中包含這些關鍵字，搜尋結果就會排在最前面
MEDIA_TIERS = {
    "rthk.hk": 10, "on.cc": 10, "mingpao.com": 10, "scmp.com": 10,
    "now.com": 10, "tvb.com": 10, "stheadline.com": 10, "hkej.com": 10,
    "hket.com": 10, "bbc.com": 10, "nytimes.com": 10, "reuters.com": 10,
    "cna.com.tw": 10, "udn.com": 10, "people.com.cn": 10, "xinhuanet.com": 10
}

# --- 2. 核心搜尋函式 (最寬鬆模式用於測試) ---

def fetch_google_news(query, cx, api_key):
    try:
        url = "https://googleapis.com"
        # 移除所有限制參數 (dateRestrict, lr) 以確保能搜到內容
        params = {
            "key": api_key, 
            "cx": cx, 
            "q": query,
            "num": 10,
            "hl": "zh-Hant"
        }
        
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if "error" in data:
            st.error(f"❌ Google API 報錯: {data['error'].get('message')}")
            return []
            
        items = data.get("items", [])
        
        # 除錯資訊：顯示當前引擎搜到的數量
        st.write(f"🔍 引擎狀態：當前白名單組合搜到 {len(items)} 則結果")
        
        articles = []
        for item in items:
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
                "tier": article_tier
            })
        return articles
    except Exception as e:
        st.error(f"⚠️ 連線異常: {e}")
        return []

# --- 3. Streamlit UI 介面 ---

st.set_page_config(page_title="News Search Test Tool", layout="wide")
st.title("🌐 新聞搜尋除錯測試平台")

# 分類切換 (對應您的兩個 Engine ID)
category = st.radio(
    "選擇測試引擎", 
    ["1. 香港媒體 (Engine A)", "2. 其他媒體 (Engine B)"],
    horizontal=True
)

search_query = st.text_input("輸入測試關鍵字 (建議用絕對會有的詞，如：香港)", placeholder="輸入後按 Enter 或點擊搜尋")

if st.button("開始測試搜尋"):
    if not search_query:
        st.warning("請先輸入關鍵字")
    else:
        with st.spinner("正在向 Google API 請求數據..."):
            # 從 Secrets 讀取金鑰
            try:
                g_key = st.secrets["GOOGLE_API_KEY"]
                cx = st.secrets["CX_HK"] if "Engine A" in category else st.secrets["CX_WORLD"]
            except KeyError as e:
                st.error(f"❌ Secrets 設定缺失: {e}")
                st.stop()

            # 執行搜尋
            results = fetch_google_news(search_query, cx, g_key)

            if not results:
                st.info("💡 目前此白名單組合無搜尋結果。請檢查 PSE 後台是否有此關鍵字。")
            else:
                # 按照權重排序顯示
                for news in sorted(results, key=lambda x: x['tier'], reverse=True):
                    st.markdown(f"### {news['title']}")
                    st.caption(f"🏛️ 來源: {news['source']} | 🏷️ 權重分: {news['tier']}")
                    st.write(news['summary'])
                    st.markdown(f"[閱讀全文]({news['link']})")
                    st.divider()

st.markdown("---")
st.caption("提示：若搜尋不到，請在 Google PSE 後台嘗試簡化網址格式（例如從 news.rthk.hk 改為 rthk.hk）")


