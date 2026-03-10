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
    try:
        headers = {'User-Agent': ua.random}
        res = requests.get(url, timeout=5, headers=headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, 'lxml')
            og_img = soup.find("meta", property="og:image")
            if og_img:
                return og_img["content"]
    except:
        pass
    return None

# ===== 右上角語言切換 =====
col1, col2 = st.columns([8, 1])
with col2:
    interface_lang = st.selectbox(
        "Language / 語言",
        ["English", "中文"],
        index=0,
        label_visibility="collapsed",
        key="lang_switch"
    )

# ===== 地區選擇 =====
country_options = {
    "Global / 全球": "",
    "Hong Kong / 香港": "hk",
    "Taiwan / 台灣": "tw",
    "China / 大陸": "cn"
}
country_label = "Select Region / 選擇地區" if interface_lang == "English" else "選擇地區 / Select Region"
selected_country = st.selectbox(country_label, list(country_options.keys()), index=1)
country_code = country_options[selected_country]

# ===== 語言文字設定 =====
if interface_lang == "English":
    page_title = "Global Real-time News Search"
    search_label = "Search location or event"
    search_placeholder = "e.g. Tehran Iran, Li Ka-shing"
    search_button = "Search"
    loading_text = "Fetching news & images..."
    no_results = "No news found. Try other keywords."
    error_timeout = "Connection timed out."
    error_generic = "An error occurred"
    success_text = "Search completed!"
    search_tip = "Tip: Use quotes for exact names."
else:
    page_title = "全球即時新聞搜尋"
    search_label = "搜尋地點或事件"
    search_placeholder = "例如：伊朗德黑蘭、李家超"
    search_button = "開始搜尋"
    loading_text = "正在抓取新聞與圖片..."
    no_results = "沒有找到新聞，請試其他關鍵字"
    error_timeout = "連接超時，請檢查網路"
    error_generic = "發生錯誤"
    success_text = "✅ 搜尋完成！"
    search_tip = "提示：人名或專有名詞建議用引號包住。"

st.title(page_title)
st.caption(search_tip)

query = st.text_input(search_label, placeholder=search_placeholder)

if 'search_results' not in st.session_state:
    st.session_state.search_results = None

if st.button(search_button):
    if not query:
        st.error("請輸入關鍵字" if interface_lang == "中文" else "Please enter keywords")
    else:
        st.info(loading_text)
        try:
            api_key = st.secrets["NEWS_API_KEY"]
            results = []
            precise_query = f'"{query}"' if re.search(r'[\u4e00-\u9fff]', query) else query

            # 1. NewsData.io
            url_nd = f"https://newsdata.io{api_key}&q={quote(precise_query)}&language=zh,en&country={country_code}&size=10"
            res_nd = requests.get(url_nd, timeout=10)
            if res_nd.status_code == 200:
                for item in res_nd.json().get("results", []):
                    img = item.get("image_url")
                    # 如果 API 沒給圖，現場抓取
                    if not img:
                        img = fetch_og_image(item.get("link"))
                    
                    results.append({
                        "title": item.get("title", ""),
                        "description": item.get("description") or "",
                        "source_id": item.get("source_id", "NewsData"),
                        "pubDate": item.get("pubDate"),
                        "link": item.get("link", "#"),
                        "image_url": img
                    })

            # 2. Google News RSS
            google_query = quote(query)
            url_google = f"https://google.com{google_query}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant"
            res_g = requests.get(url_google, timeout=10)
            if res_g.status_code == 200:
                root = ET.fromstring(res_g.content)
                for item in root.findall(".//item")[:10]:
                    link = item.find("link").text
                    # Google News RSS 必定無圖，啟動現場抓取
                    img = fetch_og_image(link)
                    
                    title_raw = item.find("title").text or ""
                    match = re.search(r' - (.+?)(?=\s*\(|$)', title_raw)
                    source = match.group(1).strip() if match else "Google News"
                    title = re.sub(r' - .+$', '', title_raw).strip()

                    results.append({
                        "title": title,
                        "description": "", 
                        "source_id": source,
                        "pubDate": item.find("pubDate").text,
                        "link": link,
                        "image_url": img
                    })

            # 去重
            unique_results = {r['link']: r for r in results if r['link'] != "#"}.values()
            
            # 排序
            sorted_results = sorted(
                unique_results,
                key=lambda x: parser.parse(x['pubDate']) if x['pubDate'] else datetime.datetime.min,
                reverse=True
            )

            # 處理顯示時間
            for r in sorted_results:
                r['relative_time'] = get_relative_time(r['pubDate'], interface_lang)

            st.session_state.search_results = sorted_results

        except Exception as e:
            st.error(f"{error_generic}: {str(e)}")
        else:
            st.success(success_text)

# ===== 顯示搜尋結果 =====
if st.session_state.search_results is not None:
    for article in st.session_state.search_results:
        col1, col2 = st.columns([1, 4])
        with col1:
            if article['image_url']:
                st.image(article['image_url'], use_column_width=True)
            else:
                st.image("https://placeholder.com", width=150)
        with col2:
            st.markdown(f"### [{article['title']}]({article['link']})")
            st.caption(f"📍 {article['source_id']} • 🕒 {article['relative_time']}")
            if article['description']:
                st.write(article['description'][:150] + "...")
        st.divider()
