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

# ===== 介面語言與地區設定 =====
# 修正：st.columns 必須傳入參數 [比例]
col1, col2 = st.columns([8, 2])
with col2:
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
        with st.spinner("正在搜尋新聞..."):
            results = []
            headers = {'User-Agent': ua.random if ua else 'Mozilla/5.0'}

            # 1. NewsData.io (12小時延遲)
            try:
                api_key = st.secrets["NEWS_API_KEY"].strip().replace('"', '')
                nd_url = "https://newsdata.io"
                nd_params = {"apikey": api_key, "q": query, "language": "zh,en", "size": 10}
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

                       # 2. Google News RSS (拆分拼接，防止路徑丟失)
            try:
                base_g_url = "https://google.com"
                encoded_q = quote(query)
                # 使用 params 方式讓 requests 自動處理拼接，不要用 f-string
                g_params = {
                    "q": query,
                    "hl": "zh-TW",
                    "gl": "HK",
                    "ceid": "HK:zh-Hant"
                }
                res_g = requests.get(base_g_url, params=g_params, timeout=12, headers=headers)
                
                if res_g.status_code == 200:
                    # 偵錯用：如果在側邊欄看到這個，代表連線成功
                    # st.sidebar.success("Google 連線成功")
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
                            "img": None
                        })
                else:
                    st.sidebar.error(f"Google 狀態碼: {res_g.status_code}")
            except Exception as e:
                st.sidebar.error(f"Google 連線偵錯: {e}")


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
            c1, c2 = st.columns([1, 3]) # 修正：這裡也加入了比例 [1, 3]
            with c1:
                if art.get('img'):
                    st.image(art['img'], use_column_width=True)
                else:
                    st.image("https://placeholder.com", use_column_width=True)
            with c2:
                st.markdown(f"#### [{art['title']}]({art['link']})")
                st.caption(f"📍 {art['source']} • 🕒 {art['time_display']}")
            st.divider()
