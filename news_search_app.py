import streamlit as st
import requests

# --- 1. 媒體權重定義 ---
MEDIA_TIERS = {
    "rthk.hk": 10, "on.cc": 10, "mingpao.com": 10, "scmp.com": 10,
    "now.com": 10, "tvb.com": 10, "stheadline.com": 10, "hkej.com": 10,
    "hket.com": 10, "bbc.com": 10, "nytimes.com": 10, "reuters.com": 10,
    "cna.com.tw": 10, "udn.com": 10, "people.com.cn": 10, "xinhuanet.com": 10
}

# --- 2. 核心搜尋邏輯 (URL 絕對修正版) ---

def fetch_google_news(query, cx, api_key):
    # 這是 Google API 的絕對路徑，確保沒有多餘斜槓或空格
    api_url = "https://googleapis.com"
    
    # 清理所有金鑰中的換行或空格
    clean_key = api_key.strip().replace('\n', '').replace(' ', '')
    clean_cx = cx.strip().replace('\n', '').replace(' ', '')

    params = {
        "key": clean_key,
        "cx": clean_cx,
        "q": query,
        "num": 10,
        "hl": "zh-Hant"
    }

    try:
        # 使用傳遞 params 的方式，由 requests 函式庫處理 URL 編碼
        resp = requests.get(api_url, params=params, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            articles = []
            for item in items:
                link = item.get("link", "").lower()
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
                    "tier": article_tier
                })
            return articles
        else:
            # 如果還是 404，印出 Google 的原始報錯 JSON
            st.error(f"❌ Google 引擎拒絕請求 (HTTP {resp.status_code})")
            st.json(resp.json())
            return []
    except Exception as e:
        st.error(f"⚠️ 連線異常: {e}")
        return []

# --- 3. UI 介面 ---

st.set_page_config(page_title="Global Citizens News Platform", layout="wide")
st.title("🌐 全球公民新聞搜尋平台")

category = st.radio(
    "選擇媒體區域", 
    ["1. 香港媒體 (Engine A)", "2. 其他媒體 (Engine B)"],
    horizontal=True
)

search_query = st.text_input("輸入關鍵字 (例如：香港經濟)", placeholder="請輸入關鍵字後按搜尋")

if st.button("開始搜尋"):
    if not search_query:
        st.warning("請先輸入關鍵字")
    else:
        with st.spinner("正在連線 Google 雲端 API..."):
            try:
                g_key = st.secrets["GOOGLE_API_KEY"]
                cx = st.secrets["CX_HK"] if "Engine A" in category else st.secrets["CX_WORLD"]
            except Exception as e:
                st.error(f"❌ Secrets 設定缺失: {e}")
                st.stop()

            results = fetch_google_news(search_query, cx, g_key)

            if results:
                # 按照權重排序
                sorted_results = sorted(results, key=lambda x: x['tier'], reverse=True)
                for news in sorted_results:
                    st.markdown(f"### {news['title']}")
                    st.caption(f"🏛️ 來源: {news['source']} | 🏷️ 權重分: {news['tier']}")
                    st.write(news['summary'])
                    st.markdown(f"[閱讀全文]({news['link']})")
                    st.divider()
            else:
                st.info("💡 目前此組合無結果，請確認關鍵字或檢查 Google Cloud 控制台 API 是否已「啟用」。")






