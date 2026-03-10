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
try:
    ua = UserAgent()
except:
    ua = None

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
        if seconds < 60:
            return "現在" if lang == "中文" else "Just now"
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
        headers = {'User-Agent': ua.random if ua else 'Mozilla/5.0'}
        res = requests.get(url, timeout=5, headers=headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, 'lxml')
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                return og_img["content"]
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

texts = {
    "title": "全球即時新聞搜尋" if interface_lang == "中文" else "Global News Search",
    "btn": "開始搜尋" if interface_lang == "中文" else "Search",
    "loading": "正在抓取最新資訊..." if interface_lang == "中文" else "Fetching latest info...",
    "tip": "提示：NewsData 提供 12 小時前新聞，Google 提供即時新聞。" if interface_lang == "中文" else "Tip: Mixed real-time and delayed news."
}

st.title(texts["title"])
st.caption(texts["tip"])

# ===== 搜尋區塊 =====
query = st.text_input("Keyword", placeholder="例如：伊朗、李家超", label_visibility="collapsed")

if 'search_results' not in st.session_state:
    st.session_state.search_results = None

if st.button(texts["btn"]):
    if not query:
        st.error("請輸入關鍵字")
    else:
        with st.spinner(texts["loading"]):
            results = []
            # 1. NewsData.io (嘗試抓取 12 小時前新聞)
            try:
                api_key = st.secrets["NEWS_API_KEY"].strip().replace('"', '')
                nd_url = "https://newsdata.io"
                nd_params = {
                    "apikey": api_key,
                    "q": query,
                    "language": "zh,en",
                    "size": 5
                }
                if country_code:
                    nd_params["country"] = country_code
                
                res_nd = requests.get(nd_url, params=nd_params, timeout=10)
                if res_nd.status_code == 200:
                    data = res_nd.json()
                    for item in data.get("results", []):
                        link = item.get("link", "#")
                        results.append({
                            "title": item.get("title", ""),
                            "source": item.get("source_id", "NewsData (12h Delay)"),
                            "date": item.get("pubDate"),
                            "link": link,
                            "img": item.get("image_url") or fetch_og_image(link)
                        })
            except:
                pass # NewsData 報錯時靜默跳過，不影響使用者

            # 2. Google News RSS (100% 穩定備援)
            try:
                g_url = f"https://google.com{quote(query)}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant"
                res_g = requests.get(g_url, timeout=12)
                if res_g.status_code == 200:
                    root = ET.fromstring(res_g.content)
                    for item in root.findall(".//item")[:12]:
                        link = item.find("link").text
                        title_raw = item.find("title").text or ""
                        source_match = re.search(r' - (.+)$', title_raw)
                        source = source_match.group(1) if source_match else "Google News"
                        title = re.sub(r' - .+$', '', title_raw)
                        results.append({
                            "title": title, "source": f"{source} (Real-time)",
                            "date": item.find("pubDate").text, "link": link,
                            "img": fetch_og_image(link)
                        })
            except:
                pass

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
        st.info("找不到新聞，請試試其他關鍵字。")
    else:
        for art in st.session_state.search_results:
            c1, c2 = st.columns([1, 3])
            with c1:
                if art['img']:
                    st.image(art['img'], use_column_width=True)
                else:
                    st.image("https://placeholder.com", use_column_width=True)
            with c2:
                st.markdown(f"#### [{art['title']}]({art['link']})")
                st.caption(f"📍 {art['source']} • 🕒 {art['time_display']}")
            st.divider()
