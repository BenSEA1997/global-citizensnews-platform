import streamlit as st
import requests
import re
from xml.etree import ElementTree as ET
from urllib.parse import quote
from dateutil import parser
import datetime

st.set_page_config(page_title="全球即時新聞搜尋", layout="wide")

# ===== 1. 徹底清理 API Key 函數 =====
def get_clean_key():
    try:
        # 從 Secrets 讀取並刪除所有空格與引號
        raw_key = st.secrets["NEWS_API_KEY"]
        clean_key = raw_key.strip().replace('"', '').replace("'", "")
        return clean_key
    except:
        return None

# ===== 2. 快取搜尋結果 (節省點數且提速) =====
@st.cache_data(ttl=600) # 10分鐘內重複搜尋不扣點
def fetch_all_news(query, country_code):
    results = []
    api_key = get_clean_key()
    
    if not api_key:
        return [], "Missing API Key"

    # --- NewsData.io 抓取 ---
    try:
        # 使用 params 字典最安全，自動處理編碼
        nd_params = {
            "apikey": api_key,
            "q": query,
            "language": "zh,en"
        }
        # 如果有選擇地區才加進去，否則搜全球
        if country_code:
            nd_params["country"] = country_code
            
        res_nd = requests.get("https://newsdata.io", params=nd_params, timeout=10)
        
        if res_nd.status_code == 200:
            data = res_nd.json()
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", "無標題"),
                    "source": item.get("source_id", "NewsData"),
                    "date": item.get("pubDate"),
                    "link": item.get("link", "#"),
                    "img": item.get("image_url")
                })
        else:
            print(f"NewsData Error: {res_nd.status_code}")
    except Exception as e:
        print(f"NewsData Exception: {e}")

    # --- Google News RSS 抓取 (備援) ---
    try:
        g_url = f"https://google.com{quote(query)}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant"
        res_g = requests.get(g_url, timeout=10)
        if res_g.status_code == 200 and b'<?xml' in res_g.content:
            root = ET.fromstring(res_g.content)
            for item in root.findall(".//item")[:10]:
                results.append({
                    "title": item.find("title").text,
                    "source": "Google News",
                    "date": item.find("pubDate").text,
                    "link": item.find("link").text,
                    "img": None
                })
    except:
        pass

    return results, None

# ===== 3. UI 介面 =====
st.title("🌍 全球即時新聞搜尋")

col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("輸入關鍵字", placeholder="例如：伊朗、李家超", label_visibility="collapsed")
with col2:
    country_options = {"全球": "", "香港": "hk", "台灣": "tw", "中國": "cn"}
    sel_country = st.selectbox("地區", list(country_options.keys()), label_visibility="collapsed")

if st.button("開始搜尋", use_container_width=True):
    if not query:
        st.error("請輸入關鍵字")
    else:
        with st.spinner("正在聯動全球媒體庫..."):
            news_list, error = fetch_all_news(query, country_options[sel_country])
            
            if news_list:
                # 排序 (由新到舊)
                try:
                    news_list = sorted(news_list, key=lambda x: parser.parse(x['date']), reverse=True)
                except:
                    pass
                
                st.success(f"找到 {len(news_list)} 則新聞")
                for art in news_list:
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        if art['img']:
                            st.image(art['img'], use_column_width=True)
                        else:
                            st.image("https://placeholder.com", use_column_width=True)
                    with c2:
                        st.markdown(f"#### [{art['title']}]({art['link']})")
                        st.caption(f"📍 {art['source']} | 📅 {art['date']}")
                    st.divider()
            else:
                st.warning("目前搜不到結果。請嘗試：1. 縮短關鍵字 2. 切換地區為『全球』")
