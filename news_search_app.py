import streamlit as st
import requests
import plotly.express as px
import pandas as pd

# ===== 強化搜尋框外觀（CSS） =====
st.markdown("""
<style>
    .stTextInput > div > div > input {
        border: 2px solid #4CAF50 !important;
        border-radius: 8px !important;
        padding: 10px !important;
        font-size: 16px !important;
    }
    .stTextInput > div > label {
        font-size: 18px !important;
        color: #333 !important;
    }
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="全球即時新聞搜尋", page_icon="🌍", layout="wide")

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

# ===== 語言文字設定 =====
if interface_lang == "English":
    page_title = "Global Real-time News Search"
    search_label = "Search location or event"
    search_placeholder = "e.g. Tehran Iran, Tokyo Ueno Park"
    search_button = "Search"
    loading_text = "Fetching news..."
    no_results = "No news found. Try other keywords."
    error_timeout = "Connection timed out. Check network or VPN."
    error_generic = "An error occurred"
    map_title = "🌍 Global Hot News Map"
    map_click_tip = "Click a country to see top 10 news"
else:
    page_title = "全球即時新聞搜尋"
    search_label = "搜尋地點或事件"
    search_placeholder = "例如：伊朗德黑蘭、東京上野公園"
    search_button = "開始搜尋"
    loading_text = "正在抓取新聞..."
    no_results = "沒有找到新聞，請試其他關鍵字"
    error_timeout = "連接超時，請檢查網路或 VPN"
    error_generic = "發生錯誤"
    map_title = "🌍 全球熱門新聞地圖"
    map_click_tip = "點擊國家查看前 10 條新聞"

st.title(f"🌍 {page_title}")

# ===== 搜尋區塊 =====
query = st.text_input(
    search_label,
    placeholder=search_placeholder,
    help="可輸入多個關鍵字，例如 Iran China US 或 Iran OR China OR US"
)

# 使用 session_state 保存搜尋結果（避免閃退）
if 'search_results' not in st.session_state:
    st.session_state.search_results = None

if st.button(search_button):
    if not query:
        st.error("請輸入關鍵字" if interface_lang == "中文" else "Please enter keywords")
    else:
        st.info(loading_text)
        try:
            api_key = st.secrets["NEWS_API_KEY"]  # 確保從 secrets 讀取
            url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={query}&size=10"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                st.session_state.search_results = data.get("results", [])
            else:
                st.error(f"API 錯誤：{response.status_code} - {response.text}")
                st.session_state.search_results = None
        except Exception as e:
            st.error(f"{error_generic}: {str(e)}")
            st.session_state.search_results = None

# 顯示搜尋結果（持久顯示）
if st.session_state.search_results is not None:
    articles = st.session_state.search_results
    st.subheader("搜尋結果" if interface_lang == "中文" else "Search Results")
    if not articles:
        st.warning(no_results)
    else:
        for article in articles:
            title = article.get('title', '無標題' if interface_lang == "中文" else 'No title')
            desc = article.get('description', '無描述' if interface_lang == "中文" else 'No description')
            source = article.get('source_id', '未知' if interface_lang == "中文" else 'Unknown')
            pub = article.get('pubDate', '未知' if interface_lang == "中文" else 'Unknown')
            link = article.get('link', '#')
            st.markdown(f"**{title}**")
            st.write(desc)
            st.caption(f"{source} | {pub}")
            st.markdown(f"[閱讀全文 / Read full article]({link})")
            st.divider()