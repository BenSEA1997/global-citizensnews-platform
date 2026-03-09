import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import datetime

# ===== 快取新聞函數（移到最前面） =====
@st.cache_data(ttl=600)  # 快取 10 分鐘
def fetch_news(query, api_key):
    url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={query}&size=10"
    r = requests.get(url, timeout=15)
    if r.status_code == 200:
        return r.json()
    else:
        raise Exception(f"API Error {r.status_code}: {r.text}")

st.set_page_config(page_title="Global Real-time News Explorer", page_icon="🌍", layout="wide")

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
    page_title = "Global Real-time News Explorer"
    search_label = "Search location or event"
    search_button = "Search News"
    breaking_title = "🚨 Breaking News"
    map_title = "🌍 Global Event Map"
    loading_text = "Fetching news..."
    no_results = "No news found. Try other keywords."
    error_timeout = "Connection timed out. Please check network or VPN."
    error_api = "API Error"
    error_generic = "An error occurred"
    x_section_title = "Real-time Eyewitness Info (X / Twitter)"
    x_section_note = "(This feature requires an X API Key, approx. $0.005 per post)"
    x_section_info = "If you have an X API Key, I can help integrate it!"
    success_text = "Search completed!"
else:
    page_title = "全球即時新聞探索器"
    search_label = "搜尋地點或事件"
    search_button = "開始搜尋"
    breaking_title = "🚨 突發新聞"
    map_title = "🌍 全球事件地圖"
    loading_text = "正在抓取新聞..."
    no_results = "沒有找到新聞，請試其他關鍵字"
    error_timeout = "連接超時，請檢查網路或 VPN"
    error_api = "API 錯誤"
    error_generic = "發生錯誤"
    x_section_title = "社交媒體目擊者即時資訊（X）"
    x_section_note = "（這部分目前需要 X API Key，單篇貼文約 0.005 美元）"
    x_section_info = "如果你有 X API Key，我可以再給你完整程式碼加入這裡！"
    success_text = "✅ 搜尋完成！"

st.title(f"🌍 {page_title}")

# ===== API Key =====
api_key = st.secrets.get("NEWS_API_KEY", "")

if not api_key:
    st.error("API Key not set in Streamlit Secrets. Please add NEWS_API_KEY.")
    st.stop()

# ===== Breaking News =====
st.subheader(breaking_title)
try:
    breaking_data = fetch_news("breaking OR world", api_key)
    breaking_articles = breaking_data.get("results", [])[:5]
    if breaking_articles:
        for art in breaking_articles:
            title = art.get("title", "No title")
            link = art.get("link", "#")
            source = art.get("source_id", "Unknown")
            pub_date = art.get("pubDate", "")
            try:
                pub_date = datetime.datetime.fromisoformat(pub_date.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
            except:
                pass
            st.markdown(f"**{title}**")
            st.caption(f"{source} | {pub_date}")
            st.markdown(f"[Read more]({link})")
            st.divider()
    else:
        st.info("No breaking news available at the moment.")
except Exception as e:
    st.warning(f"Breaking news error: {str(e)}")

st.divider()

# ===== Search Section =====
query = st.text_input(search_label, "Ukraine war")

if st.button(search_button):
    if not query:
        st.error("Please enter keywords" if interface_lang == "English" else "請輸入關鍵字")
    else:
        st.info(loading_text)
        try:
            data = fetch_news(query, api_key)
            articles = data.get("results", [])
            if not articles:
                st.warning(no_results)
            for article in articles:
                title = article.get("title", "No title")
                desc = article.get("description", "")
                source = article.get("source_id", "Unknown")
                pub = article.get("pubDate", "")
                link = article.get("link", "#")
                with st.container():
                    st.markdown(f"### {title}")
                    st.write(desc)
                    st.caption(f"{source} | {pub}")
                    st.markdown(f"[Read full article]({link})")
                    st.divider()
        except Exception as e:
            st.error(f"{error_generic}: {str(e)}")

# ===== Global Event Map =====
st.subheader(map_title)

m = folium.Map(
    location=[20, 0],
    zoom_start=2,
    tiles="CartoDB positron"  # 純英文底圖
)

# 簡單熱點標記（可擴充成從 API 動態抓取）
events = [
    ("Ukraine War", 48.3794, 31.1656, "Ongoing conflict reports - Multiple sources"),
    ("Middle East Tension", 31.5, 34.8, "Regional developments - Al Jazeera, Reuters"),
    ("US Politics", 38.9072, -77.0369, "Election updates - CNN, NYT"),
    ("China Economy", 39.9042, 116.4074, "Policy changes - Xinhua, Bloomberg"),
    ("Japan Tech", 35.6762, 139.6503, "Tech innovations - Nikkei")
]

for name, lat, lon, desc in events:
    folium.Marker(
        location=[lat, lon],
        popup=f"<b>{name}</b><br>{desc}<br><a href='https://news.google.com/search?q={name}' target='_blank'>More news</a>",
        tooltip=name
    ).add_to(m)

st_folium(m, width=900, height=500)

st.success("Platform prototype running successfully")