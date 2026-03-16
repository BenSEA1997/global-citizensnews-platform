import streamlit as st
import requests
from datetime import datetime, timedelta
import pytz
from concurrent.futures import ThreadPoolExecutor

# --- 1. 設定與權重定義 ---
HKT = pytz.timezone('Asia/Hong_Kong')

# 媒體權重字典 (Tier 10 優先)
MEDIA_TIERS = {
    "rthk.hk": 10, "on.cc": 10, "mingpao.com": 10, "scmp.com": 10,
    "now.com": 10, "tvb.com": 10, "stheadline.com": 10, "hkej.com": 10,
    "hket.com": 10, "bbc.com": 10, "nytimes.com": 10, "reuters.com": 10,
    "cna.com.tw": 10, "udn.com": 10, "people.com.cn": 10, "xinhuanet.com": 10
}

# --- 2. 核心搜尋邏輯（已修正連線問題）---
def fetch_google_news(query, cx, api_key, lr=None):
    """
    已修正：完整官方路徑 + key 清理 + dateRestrict 30天 + 錯誤顯示
    """
    try:
        url = "https://www.googleapis.com/customsearch/v1"
       
        params = {
            "key": api_key.strip().replace('\n', '').replace('\r', ''),
            "cx": cx.strip().replace('\n', '').replace('\r', ''),
            "q": query,
            "dateRestrict": "m1",   # 官方支援：過去 1 個月 ≈ 30 天
            "num": 10,
            "hl": "zh-Hant"
        }
        if lr:
            params["lr"] = lr
       
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code != 200:
            st.error(f"Google API 回應 {resp.status_code}：{resp.text[:300]}...")
            return []
           
        data = resp.json()
        articles = []
        for item in data.get("items", []):
            link = item.get("link", "").lower()
            tier = 1
            for key, val in MEDIA_TIERS.items():
                if key in link:
                    tier = val
                    break
            articles.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "source": item.get("displayLink", ""),
                "summary": item.get("snippet", ""),
                "published": None,
                "tier": tier,
                "origin": "Google"
            })
        return articles
    except Exception as e:
        st.error(f"Google 搜尋異常：{str(e)}")
        return []

def fetch_newsdata(query, api_key):
    """
    已修正：正確 endpoint + 使用 params（不再直接拼接 key）
    """
    try:
        api_key_clean = api_key.strip().replace('\n', '').replace('\r', '')
        
        url = "https://newsdata.io/api/1/news"
        
        params = {
            "apikey": api_key_clean,
            "q": query,
            "language": "zh,en"
        }
       
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code != 200:
            st.error(f"NewsData API 回應 {resp.status_code}：{resp.text[:300]}...")
            return []
           
        data = resp.json()
        articles = []
        for item in data.get("results", []):
            link = item.get("link", "").lower()
            tier = 1
            for key, val in MEDIA_TIERS.items():
                if key in link:
                    tier = val
                    break
            articles.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "source": item.get("source_id"),
                "summary": item.get("description", ""),
                "published": item.get("pubDate"),
                "tier": tier,
                "origin": "NewsData"
            })
        return articles
    except Exception as e:
        st.error(f"NewsData 異常：{str(e)}")
        return []

# --- 3. UI 介面（完全維持原版面與邏輯）---
st.set_page_config(page_title="Global Citizens News Search", layout="wide")
st.title("🌐 全球公民新聞搜尋平台")

category = st.radio("選擇媒體區域", ["1. 香港媒體 (Engine A)", "2. 其他媒體 (Engine B)"], horizontal=True)
search_query = st.text_input("輸入關鍵字 (檢索過去 30 天新聞)")

if st.button("開始搜尋"):
    if search_query:
        with st.spinner("正在從多方引擎獲取新聞..."):
            try:
                # 從 Secrets 讀取金鑰
                g_key = st.secrets["GOOGLE_API_KEY"]
                n_key = st.secrets["NEWSDATA_API_KEY"]
               
                # 根據選擇切換 Engine ID
                cx = st.secrets["CX_HK"] if "Engine A" in category else st.secrets["CX_WORLD"]
               
                # 並行執行搜尋提升速度
                with ThreadPoolExecutor() as executor:
                    f1 = executor.submit(fetch_google_news, search_query, cx, g_key)
                    f2 = executor.submit(fetch_newsdata, search_query, n_key)
                   
                    results = f1.result() + f2.result()
               
                # 去重邏輯
                seen = set()
                unique_results = []
                for x in results:
                    if x['link'] not in seen:
                        unique_results.append(x)
                        seen.add(x['link'])
               
                # 權重排序 (Tier 10 最前)
                sorted_news = sorted(unique_results, key=lambda x: x['tier'], reverse=True)
               
                if not sorted_news:
                    st.warning("未找到相關新聞，請嘗試更換關鍵字。")
               
                for news in sorted_news:
                    st.markdown(f"### {news['title']}")
                    st.caption(f"來源: {news['source']} | 權重: Tier {news['tier']} | 平台: {news['origin']}")
                    st.write(news['summary'])
                    st.markdown(f"[閱讀全文]({news['link']})")
                    st.divider()
                   
            except Exception as e:
                st.error(f"執行出錯: {e}")
    else:
        st.warning("請先輸入搜尋關鍵字")


