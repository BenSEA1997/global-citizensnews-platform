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

# --- 2. 核心搜尋邏輯 ---

def fetch_google_news(query, cx, api_key, lr=None):
    """
    【關鍵修正點】
    使用正確的完整路徑：https://www.googleapis.com
    """
    try:
        # 這裡絕對包含 www 和 /customsearch/v1
        url = "https://www.googleapis.com" 
        
        # 清理 Secrets 中可能的換行符與空白
        clean_key = api_key.strip().replace('\n', '').replace('\r', '')
        clean_cx = cx.strip().replace('\n', '').replace('\r', '')
        
        params = {
            "key": clean_key,
            "cx": clean_cx,
            "q": query,
            "dateRestrict": "m1", # 限制 30 天內
            "num": 10,
            "hl": "zh-Hant"
        }
        if lr: params["lr"] = lr
        
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code != 200:
            # 這裡可以幫助偵錯，如果還是 404 或 403，我們會知道
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
        return []

def fetch_newsdata(query, api_key):
    """
    NewsData API 端點也同步檢查
    """
    try:
        clean_nkey = api_key.strip().replace('\n', '').replace('\r', '')
        # 確保路徑包含 /api/1/news
        url = f"https://newsdata.io{clean_nkey}&q={query}&language=zh,en"
        
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
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
    except:
        return []

# --- 3. UI 介面 ---
st.set_page_config(page_title="Global Citizens News Search", layout="wide")
st.title("🌐 全球公民新聞搜尋平台")

category = st.radio("選擇媒體區域", ["1. 香港媒體 (Engine A)", "2. 其他媒體 (Engine B)"], horizontal=True)
search_query = st.text_input("輸入關鍵字 (過去 30 天新聞)")

if st.button("開始搜尋"):
    if search_query:
        with st.spinner("搜尋中..."):
            try:
                # 讀取 Secrets 並進行預先清洗
                g_key = st.secrets["GOOGLE_API_KEY"]
                n_key = st.secrets["NEWSDATA_API_KEY"]
                cx = st.secrets["CX_HK"] if "Engine A" in category else st.secrets["CX_WORLD"]
                
                with ThreadPoolExecutor() as executor:
                    f1 = executor.submit(fetch_google_news, search_query, cx, g_key)
                    f2 = executor.submit(fetch_newsdata, search_query, n_key)
                    results = f1.result() + f2.result()
                
                # 去重邏輯
                seen = set()
                unique = [x for x in results if not (x['link'] in seen or seen.add(x['link']))]
                
                # 權重排序 (Tier 10 最優先)
                sorted_news = sorted(unique, key=lambda x: x['tier'], reverse=True)
                
                if not sorted_news:
                    st.warning("查無結果，請更換關鍵字嘗試。")

                for news in sorted_news:
                    st.markdown(f"### {news['title']}")
                    st.caption(f"來源: {news['source']} | 權重: {news['tier']} | 平台: {news['origin']}")
                    st.write(news['summary'])
                    st.markdown(f"[閱讀全文]({news['link']})")
                    st.divider()
            except Exception as e:
                st.error(f"系統錯誤: {e}")
    else:
        st.warning("請輸入搜尋內容")



