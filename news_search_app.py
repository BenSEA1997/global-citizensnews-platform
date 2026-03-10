import streamlit as st
import requests
import re
import datetime
from xml.etree import ElementTree as ET
from urllib.parse import quote
from dateutil import parser
from bs4 import BeautifulSoup
import pytz
from fake_useragent import UserAgent

# 頁面配置
st.set_page_config(page_title="全球即時新聞搜尋", page_icon="🌍", layout="wide")

# 初始化工具
ua = UserAgent()
HKT = pytz.timezone('Asia/Hong_Kong')

# ===== 輔助函數：體感時間顯示 =====
def get_relative_time(date_str, lang):
    if not date_str:
        return "未知" if lang == "中文" else "Unknown"
    try:
        dt = parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        now = datetime.datetime.now(pytz.UTC)
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60: return "現在" if lang == "中文" else "Just now"
        elif seconds < 3600:
            mins = int(seconds // 60)
            return f"{mins} 分鐘前" if lang == "中文" else f"{mins}m ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} 小時前" if lang == "中文" else f"{hours}h ago"
        else:
            days = int(seconds // 86400)
            return f"{days} 天前" if lang == "中文" else f"{days}d ago"
    except:
        return date_str

# ===== 輔助函數：抓取網頁 OG Image =====
def fetch_og_image(url):
    if not url or url == "#" or "google.com" in url:
        return None
    try:
        headers = {'User-Agent': ua.random}
        res = requests.get(url, timeout=5, headers=headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, 'lxml')
            og_img = soup.find("meta", property="og:image")
            if og_img: return og_img.get("content")
    except:
        pass
    return None

# ===== 介面語言與地區設定 =====
col1, col2 = st.columns([8, 1])
with col2:
    interface_lang = st.selectbox("Lang", ["English", "中文"], index=1, label_visibility="collapsed")

country_options = {"Global / 全球": "", "Hong Kong / 香港": "hk", "Taiwan / 台灣": "tw", "China / 大陸": "cn"}
selected_country = st.selectbox("選擇地區 / Region", list(country_options.keys()), index=1)
country_code = country_options[selected_country]

title_text = "全球即時新聞搜尋" if interface_lang == "中文" else "Global News Search"
st.title(title_text)

# ===== 搜尋區塊 =====
query = st.text_input("搜尋關鍵字", placeholder="例如：伊朗、李家超", label_visibility="collapsed")

if 'search_results' not in st.session_state:
    st.session_state.search_results = None

if st.button("開始搜尋" if interface_lang == "中文" else "Search"):
    if not query:
        st.error("請輸入關鍵字")
    else:
        with st.spinner("正在搜尋新聞..."):
            results = []
            headers = {'User-Agent': ua.random}

            # 1. NewsData.io (12小時延遲版本)
            try:
                api_key = st.secrets["NEWS_API_KEY"].strip().replace('"', '')
                nd_url = "https://newsdata.io"
                nd_params = {"apikey": api_key, "q": query, "language": "zh,en", "size": 5}
                if country_code: nd_params["country"] = country_code
                
                res_nd = requests.get(nd_url, params=nd_params, timeout=10, headers=headers)
                if res_nd.status_code == 200:
                    for item in res_nd.json().get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "source": item.get("source_id", "NewsData"),
                            "date": item.get("pubDate"),
                            "link": item.get("link", "#"),
                            "img": item.get("image_url")
                        })
            except:
                pass

            # 2. Google News RSS (強化版)
            try:
                encoded_q = quote(query)
                g_url = f"https://google.com{encoded_q}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant"
                res_g = requests.get(g_url, timeout=12, headers=headers)
                if res_g.status_code == 200:
                    root = ET.fromstring(res_g.content)
                    for item in root.findall(".//item")[:15]:
                        link = item.find("link").text
                        title_raw = item.find("title").text or ""
                        source_match = re.search(r' - (.+)$', title_raw)
                        source = source_match.group(1) if source_match else "Google News"
                        title = re.sub(r' - .+$', '', title_raw)
                        results.append({
                            "title": title, "source": source,
                            "date": item.find("pubDate").text, "link": link,
                            "img": None # 稍後異步加載或點擊顯示
                        })
            except Exception as e:
                st.sidebar.error(f"Google 暫時無法連線: {e}")

            # 去重與排序
            if results:
                unique = {r['link']: r for r in results if r['link'] != "#"}.values()
                sorted_res = sorted(unique, key=lambda x: parser.parse(x['date']) if x['date'] else datetime.datetime.min, reverse=True)
                for r in sorted_res:
                    r['time_display'] = get_relative_time(r['date'], interface_lang)
                st.session_state.search_results = sorted_res
            else:
                st.session_state.search_results = []

# ===== 顯示結果 =====
if st.session_state.search_results is not None:
    if not st.session_state.search_results:
        st.warning("找不到新聞，請嘗試換個關鍵字。")
    else:
        for art in st.session_state.search_results:
            c1, c2 = st.columns([1, 3])
            with c1:
                # 為了搜尋速度，如果原本沒圖就顯示預設圖，不現場抓取
                if art.get('img'):
                    st.image(art['img'], use_column_width=True)
                else:
                    st.image("https://placeholder.com", use_column_width=True)
            with c2:
                st.markdown(f"#### [{art['title']}]({art['link']})")
                st.caption(f"📍 {art['source']} • 🕒 {art['time_display']}")
            st.divider()
