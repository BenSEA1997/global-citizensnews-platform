import streamlit as st
import requests

# 右上方語言切換（使用 columns 讓它靠右）
col1, col2 = st.columns([6, 1])
with col2:
    interface_lang = st.selectbox(
        "Language / 語言",
        ["English", "中文"],
        index=0,
        label_visibility="collapsed",
        key="lang_switch"
    )

# 根據語言設定所有顯示文字
if interface_lang == "English":
    page_title = "Global Real-time News Explorer"
    page_desc = "Enter location or event, e.g. Tehran Iran, Tokyo Ueno Park cherry blossoms"
    search_label = "Search Keywords"
    search_placeholder = "Tehran Iran"
    search_button = "Search"
    loading_text = "Fetching news from credible sources (NewsData.io)..."
    no_results = "No related news found. Try other keywords."
    error_timeout = "Connection timed out. Please check your network or VPN."
    error_api = "API Error"
    x_section_title = "Real-time Eyewitness Info (X / Twitter)"
    x_section_note = "(This feature requires an X API Key, approx. $0.005 per post)"
    x_section_info = "If you have an X API Key, I can help integrate it!"
    success_text = "Search completed!"
else:
    page_title = "全球即時目擊新聞搜尋器"
    page_desc = "輸入地點或事件，例如：伊朗德黑蘭、東京上野公園櫻花"
    search_label = "搜尋關鍵字"
    search_placeholder = "伊朗德黑蘭"
    search_button = "開始搜尋"
    loading_text = "正在抓取傳統新聞媒體（使用 NewsData.io）..."
    no_results = "沒有找到相關新聞，請試其他關鍵字或英文查詢"
    error_timeout = "連接超時，請檢查網路或 VPN"
    error_api = "API 錯誤"
    x_section_title = "社交媒體目擊者即時資訊（X）"
    x_section_note = "（這部分目前需要 X API Key，單篇貼文約 0.005 美元）"
    x_section_info = "如果你有 X API Key，我可以再給你完整程式碼加入這裡！"
    success_text = "✅ 搜尋完成！這就是你的新聞搜尋器原型"

st.set_page_config(page_title=page_title, page_icon="🌍")
st.title(f"🌍 {page_title}")
st.write(page_desc)

query = st.text_input(search_label, search_placeholder)

if st.button(search_button):
    if not query:
        st.error("Please enter keywords" if interface_lang == "English" else "請輸入關鍵字")
    else:
        st.info(loading_text)
        
        # 從 Streamlit Secrets 讀取 API Key（安全）
        api_key = st.secrets.get("NEWS_API_KEY", "your-key-here-if-not-set")
        
        # 不再限制語言，讓 API 依關鍵字自然返回相關結果
        url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={query}&size=10"
        
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                articles = data.get("results", [])
                st.subheader("📰 Credible Media Reports" if interface_lang == "English" else "📰 傳統公信力媒體報導")
                if not articles:
                    st.warning(no_results)
                for article in articles:
                    title = article.get('title', 'No title' if interface_lang == "English" else '無標題')
                    desc = article.get('description', 'No description' if interface_lang == "English" else '無描述')
                    source = article.get('source_id', 'Unknown' if interface_lang == "English" else '未知')
                    pub_date = article.get('pubDate', 'Unknown' if interface_lang == "English" else '未知')
                    link = article.get('link', '#')
                    
                    st.write(f"**{title}**")
                    st.write(desc)
                    st.write(f"Source: {source} | Time: {pub_date}")
                    st.write(f"[Read full article]({link})")
                    st.divider()
            else:
                st.error(f"{error_api}: {response.status_code} - {response.text}")
        except requests.exceptions.Timeout:
            st.error(error_timeout)
        except Exception as e:
            st.error(f"Other error: {str(e)}")
        
        st.subheader(x_section_title)
        st.write(x_section_note)
        st.info(x_section_info)
        
        st.success(success_text)
        # Updated for English default + language switch - 2026-03-08