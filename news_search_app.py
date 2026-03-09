import streamlit as st
import requests
import plotly.express as px
import pandas as pd

# ===== 右上角語言切換 =====
col1, col2 = st.columns([8, 1])
with col2:
    interface_lang = st.selectbox(
        "Language / 語言",
        ["English", "中文"],
        index=0,
        label_visibility="collapsed"
    )

# ===== 語言文字設定 =====
if interface_lang == "English":
    page_title = "Global Real-time News Explorer"
    search_label = "Search location or event"
    search_button = "Search News"
    loading_text = "Fetching news..."
    no_results = "No news found. Try other keywords."
    error_timeout = "Connection timed out. Please check network or VPN."
    error_api = "API Error"
    x_section_title = "Real-time Eyewitness Info (X / Twitter)"
    x_section_note = "(This feature requires an X API Key, approx. $0.005 per post)"
    x_section_info = "If you have an X API Key, I can help integrate it!"
    map_title = "🌍 Global Event Map"
    map_click_tip = "Click a country to see hot news (10 headlines with date, source, link)"
else:
    page_title = "全球即時新聞探索器"
    search_label = "搜尋地點或事件"
    search_button = "開始搜尋"
    loading_text = "正在抓取新聞..."
    no_results = "沒有找到新聞，請試其他關鍵字"
    error_timeout = "連接超時，請檢查網路或 VPN"
    error_api = "API 錯誤"
    x_section_title = "社交媒體目擊者即時資訊（X）"
    x_section_note = "（這部分目前需要 X API Key，單篇貼文約 0.005 美元）"
    x_section_info = "如果你有 X API Key，我可以再給你完整程式碼加入這裡！"
    map_title = "🌍 全球事件地圖"
    map_click_tip = "點擊國家查看熱門新聞（10 條標題、日期、來源、連結）"

st.set_page_config(page_title=page_title, page_icon="🌍", layout="wide")

# ===== 美工背景 =====
st.markdown("""
<style>
.stApp {
    background-color: #f0f2f6;
}
</style>
""", unsafe_allow_html=True)

st.title(f"🌍 {page_title}")

# ===== 上半部：新聞搜尋 + X 社交提示 =====
query = st.text_input(search_label, "Tehran Iran" if interface_lang == "English" else "伊朗德黑蘭")

if st.button(search_button):
    if not query:
        st.error("Please enter keywords" if interface_lang == "English" else "請輸入關鍵字")
    else:
        st.info(loading_text)
        try:
            url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={query}&size=10"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                articles = data.get("results", [])
                st.subheader("📰 Search Results" if interface_lang == "English" else "📰 搜尋結果")
                if not articles:
                    st.warning(no_results)
                for article in articles:
                    st.write(f"**{article.get('title', 'No title')}**")
                    st.write(article.get('description', 'No description'))
                    st.write(f"Source: {article.get('source_id', 'Unknown')} | Time: {article.get('pubDate', 'Unknown')}")
                    st.write(f"[Read full article]({article.get('link', '#')})")
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

st.divider()

# ===== 下半部：世界地圖 + 點擊顯示國家新聞 =====
st.subheader(map_title)
st.caption(map_click_tip)

# 地圖使用 Plotly choropleth（國家單位，顏色深淺代表熱度）
country_news = {
    'USA': 25, 'IRN': 15, 'CHN': 20, 'JPN': 10, 'RUS': 18, 'ISR': 12, 'UKR': 22, 'FRA': 8, 'DEU': 9, 'GBR': 11
}  # 假熱度數據（之後可從 API 動態計算）

df = pd.DataFrame(list(country_news.items()), columns=['iso_alpha', 'news_count'])

fig = px.choropleth(
    df,
    locations="iso_alpha",
    color="news_count",
    hover_name="iso_alpha",
    color_continuous_scale="Reds",
    title="Global Hot News Intensity by Country (Click a country to see news)"
)

fig.update_layout(
    geo=dict(showframe=False, showcoastlines=True),
    margin={"r":0,"t":0,"l":0,"b":0}
)

# 顯示地圖並捕捉點擊
clicked_country = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

# 如果點擊國家，顯示新聞
if clicked_country and 'points' in clicked_country and clicked_country['points']:
    selected_country = clicked_country['points'][0]['location']  # iso_alpha
    st.subheader(f"Hot News in {selected_country}")
    try:
        country_url = f"https://newsdata.io/api/1/news?apikey={api_key}&country={selected_country.lower()}&size=10"
        response = requests.get(country_url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            articles = data.get("results", [])
            if not articles:
                st.warning("No news for this country.")
            for article in articles:
                st.write(f"**{article.get('title', 'No title')}**")
                st.write(f"Source: {article.get('source_id', 'Unknown')} | Time: {article.get('pubDate', 'Unknown')}")
                st.write(f"[Read full article]({article.get('link', '#')})")
                st.divider()
        else:
            st.error(f"{error_api}: {response.status_code}")
    except Exception as e:
        st.error(f"Other error: {str(e)}")

st.success("Platform prototype running successfully")