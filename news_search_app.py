import streamlit as st
import requests
import re  # 加入這一行，解決 re not defined 錯誤

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
    search_tip = "Tip: For names or exact phrases, use quotes e.g. \"Li Ka-shing\""
else:
    page_title = "全球即時新聞搜尋"
    search_label = "搜尋地點或事件"
    search_placeholder = "例如：伊朗德黑蘭、李嘉誠"
    search_button = "開始搜尋"
    loading_text = "正在抓取新聞..."
    no_results = "沒有找到新聞，請試其他關鍵字"
    error_timeout = "連接超時，請檢查網路或 VPN"
    error_generic = "發生錯誤"
    success_text = "✅ 搜尋完成！"
    search_tip = "提示：人名或專有名詞建議用引號包住，例如 \"李家超\" 或 \"伊朗核協議\""

st.title(page_title)

# ===== 搜尋提示 =====
st.caption(search_tip)

# ===== 搜尋區塊 =====
query = st.text_input(search_label, placeholder=search_placeholder)

# 使用 session_state 保存搜尋結果
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

if st.button(search_button):
    if not query:
        st.error("請輸入關鍵字" if interface_lang == "中文" else "Please enter keywords")
    else:
        st.session_state.search_query = query
        st.info(loading_text)
        try:
            api_key = st.secrets["NEWS_API_KEY"]
            
            results = None
            
            # 自動精準處理中文名字（偵測中文自動加引號）
            precise_query = query
            if re.search(r'[\u4e00-\u9fff]', query):  # 有中文
                precise_query = f'"{query}"'
            
            # 鎖定主流媒體 + 中英文 + 10 條
            url_precise = f"https://newsdata.io/api/1/news?apikey={api_key}&q={precise_query}&language=zh,en&prioritydomain=top&size=10"
            response = requests.get(url_precise, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
            
            # 如果精準結果少於 4 條，自動切模糊搜尋
            if results is None or len(results) < 4:
                url_fuzzy = f"https://newsdata.io/api/1/news?apikey={api_key}&q={query}&language=zh,en&prioritydomain=top&size=10"
                response = requests.get(url_fuzzy, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])

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
            st.markdown(f"**{title}**")
            st.write(desc)
            st.caption(f"{source} | {pub}")
            st.markdown(f"[閱讀全文 / Read full article]({link})")
            st.divider()