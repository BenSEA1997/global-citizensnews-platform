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
    if not date_str: return "未知"
    try:
        dt = parser.parse(date_str)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=pytz.UTC)
        now = datetime.datetime.now(pytz.UTC)
        diff = now - dt
        sec = diff.total_seconds()
        if sec < 60: return "現在"
        elif sec < 3600: return f"{int(sec//60)} 分鐘前"
        elif sec < 86400: return f"{int(sec//3600)} 小時前"
        else: return f"{int(sec//86400)} 天前"
    except: return date_str

# ===== 介面佈局 =====
col_top1, col_top2 = st.columns([8, 1])
with col_top2:
    interface_lang = st.selectbox("Lang", ["English", "中文"], index=1, label_visibility="collapsed")

country_options = {"Global / 全球": "", "Hong Kong / 香港": "hk", "Taiwan / 台灣": "tw", "China / 大陸": "cn"}
selected_country = st.selectbox("選擇地區 / Region", list(country_options.keys()), index=1)
country_code = country_options[selected_country]

st.title("全球即時新聞搜尋" if interface_lang == "中文" else "Global News Search")

# ===== 搜尋區塊 =====
query = st.text_input("搜尋關鍵字", placeholder="例如：伊朗、李家超", label_visibility="collapsed")

if 'search_results' not in st.session_state:
    st.session_state.search_results = None

if st.button("開始搜尋" if interface_lang == "中文" else "Search"):
    if not query:
        st.error("請輸入關鍵字")
    else:
        with st.spinner("正在搜尋多個新聞來源..."):
            results = []
            headers = {'User-Agent': ua.random if ua else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

            # 1. NewsData.io (12h Delay)
            try:
                api_key = st.secrets["NEWS_API_KEY"].strip().replace('"', '')
                nd_params = {"apikey": api_key, "q": query, "language": "zh,en", "size": 10}
                if country_code: nd_params["country"] = country_code
                res_nd = requests.get("https://newsdata.io", params=nd_params, timeout=10, headers=headers)
                if res_nd.status_code == 200:
                    data = res_nd.json()
                    for item in data.get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "source": item.get("source_id", "NewsData"),
                            "date": item.get("pubDate"),
                            "link": item.get("link", "#"),
                            "img": item.get("image_url")
                        })
            except:
                pass

            # 2. Google News RSS (強化解析安全性)
            try:
                encoded_q = quote(query)
                g_url = f"https://google.com{encoded_q}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant"
                res_g = requests.get(g_url, timeout=12, headers=headers)
                
                # 只有當內容以 < 開頭（可能是 XML）時才解析
                if res_g.status_code == 200 and res_g.content.strip().startswith(b'<'):
                    try:
                        root = ET.fromstring(res_g.content)
                        for item in root.findall(".//item")[:15]:
                            title_raw = item.find("title").text or ""
                            source_match = re.search(r' - (.+)$', title_raw)
                            results.append({
                                "title": re.sub(r' - .+$', '', title_raw),
                                "source": source_match.group(1) if source_match else "Google News",
                                "date": item.find("pubDate").text,
                                "link": item.find("link").text,
                                "img": None
                            })
                    except:
                        st.sidebar.warning("Google 回傳格式異常")
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

# ===== 結果顯示 =====
if st.session_state.search_results is not None:
    if not st.session_state.search_results:
        st.warning("找不到新聞。建議：\n1. 換個關鍵字\n2. 換個 VPN 節點（如香港）")
    else:
        for art in st.session_state.search_results:
            c1, c2 = st.columns([1, 4]) # 設定比例：圖片1，文字4
            with c1:
                if art.get('img'):
                    st.image(art['img'], use_column_width=True)
                else:
                    st.image("https://placeholder.com", use_column_width=True)
            with c2:
                st.markdown(f"#### [{art['title']}]({art['link']})")
                st.caption(f"📍 {art['source']} • 🕒 {art['time_display']}")
            st.divider()
