import streamlit as st
import requests
import re
import datetime
from operator import itemgetter

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
    search_placeholder = "e.g. Tehran Iran, Li Ka-shing"
    search_button = "Search"
    loading_text = "Fetching news..."
    no_results = "No news found. Try other keywords."
    error_timeout = "Connection timed out. Check network or VPN."
    error_generic = "An error occurred"
    success_text = "Search completed!"
else:
    page_title = "全球即時新聞搜尋"
    search_label = "搜尋地點或事件"
    search_placeholder = "例如：伊朗德黑蘭、李家超"
    search_button = "開始搜尋"
    loading_text = "正在抓取新聞..."
    no_results = "沒有找到新聞，請試其他關鍵字"
    error_timeout = "連接超時，請檢查網路或 VPN"
    error_generic = "發生錯誤"
    success_text = "✅ 搜尋完成！"

st.title(page_title)

# ===== 搜尋提示 =====
st.caption("提示：可輸入多個關鍵字，例如 Iran China US 或 Iran OR China OR US。用引號包住精準搜尋，例如 \"李家超\"")

# ===== 搜尋區塊 =====
query = st.text_input(search_label, placeholder=search_placeholder)

# 使用 session_state 保存搜尋結果
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
            
            # 自動精準處理中文名字
            precise_query = query
            if re.search(r'[\u4e00-\u9fff]', query):  # 有中文
                precise_query = f'"{query}"'
            
            # 精準搜尋：鎖定主流媒體 + 中英文 + 20 條 + 特定域名
            url_precise = f"https://newsdata.io/api/1/news?apikey={api_key}&q={precise_query}&language=zh,en&prioritydomain=top&domain=bbc.co.uk,cnn.com,reuters.com,nytimes.com,scmp.com&size=20"
            response = requests.get(url_precise, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results.extend(data.get("results", []))

            # 如果結果少於 5 條，切模糊搜尋
            if len(results) < 5:
                url_fuzzy = f"https://newsdata.io/api/1/news?apikey={api_key}&q={query}&language=zh,en&prioritydomain=top&domain=bbc.co.uk,cnn.com,reuters.com,nytimes.com,scmp.com&size=20"
                response = requests.get(url_fuzzy, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    results.extend(data.get("results", []))

            # 按時間排序（從近到遠）
            results = sorted(results, key=itemgetter('publishedAt'), reverse=True) if results else []

            st.session_state.search_results = results
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
            col1, col2 = st.columns([1, 5])
            with col1:
                st.image("https://placekitten.com/100/100", width=100)  # 替換成真圖片
            with col2:
                st.markdown(f"**{title}**")
                st.write(desc)
                st.caption(f"{source} | {pub}")
                st.markdown(f"[閱讀全文 / Read full article]({link})")
            st.divider()