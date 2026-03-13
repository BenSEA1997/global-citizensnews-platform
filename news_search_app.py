import streamlit as st
import feedparser
import datetime
from dateutil import parser as date_parser
import pytz
from bs4 import BeautifulSoup

st.set_page_config(page_title="全球新聞搜尋", page_icon="🌍", layout="wide")

# 香港時區
HKT = pytz.timezone('Asia/Hong_Kong')

# 語言切換
col1, col2 = st.columns([8, 1])
with col2:
    interface_lang = st.selectbox("Language / 語言", ["English", "中文"], index=0, label_visibility="collapsed", key="lang_switch")

# 語言設定
if interface_lang == "English":
    page_title = "Global News Search"
    search_label = "Search keywords"
    search_placeholder = "e.g. Tehran Iran, Li Ka-shing"
    search_button = "Search"
    loading_text = "Fetching news..."
    no_results = "No news found. Try other keywords."
    error_generic = "An error occurred"
    success_text = "Search completed!"
    search_tip = "Tip: All searches are exact match (quotes added automatically)"
    source_filter_label = "Source Category"
    hk_sources = "Hong Kong"
    tw_sources = "Taiwan"
    cn_sources = "China Mainland"
    world_chinese = "World Chinese"
    world_english = "World English"
    cn_note = "China Mainland media may have fewer international reports. Try World Chinese or English."
    tw_note = "Taiwan media may have fewer international reports. Try World Chinese or English."
else:
    page_title = "全球新聞搜尋"
    search_label = "搜尋關鍵字"
    search_placeholder = "例如：伊朗德黑蘭、李家超"
    search_button = "開始搜尋"
    loading_text = "正在抓取新聞..."
    no_results = "沒有找到新聞，請試其他關鍵字"
    error_generic = "發生錯誤"
    success_text = "✅ 搜尋完成！"
    search_tip = "提示：所有搜尋已自動精準匹配（系統已加引號）"
    source_filter_label = "來源分類"
    hk_sources = "香港"
    tw_sources = "台灣"
    cn_sources = "中國大陸"
    world_chinese = "世界華文"
    world_english = "世界英文"
    cn_note = "中國大陸媒體國際報導較少，請試「世界華文」或「世界英文」分類。"
    tw_note = "台灣媒體國際報導較少，請試「世界華文」或「世界英文」分類。"

st.markdown(f"<h1 style='text-align: center; margin-bottom: 0;'>{page_title}</h1>", unsafe_allow_html=True)
st.caption(search_tip)

# 白名單 RSS（香港完整，其他補國際子頻道）
rss_sources = {
    "香港": [
        {"name": "香港電台 (RTHK)", "rss": "https://news.rthk.hk/rthk/ch/rss.htm"},
        {"name": "明報", "rss": "https://news.mingpao.com/php/rss.php"},
        {"name": "南華早報 (SCMP)", "rss": "https://www.scmp.com/rss/91/feed"},
        {"name": "香港01", "rss": "https://www.hk01.com/rss"},
        {"name": "經濟日報", "rss": "https://www.hket.com/rss"},
        {"name": "am730", "rss": "https://www.am730.com.hk/rss"},
        {"name": "香港自由新聞 (HKFP)", "rss": "https://hongkongfp.com/feed/"},
        {"name": "Now 新聞", "rss": "https://news.now.com/home/rss"},
        # 你可以繼續加其他香港來源
    ],
    "台灣": [
        {"name": "聯合報", "rss": "https://udn.com/rssfeed/news/2/7225?ch=news"},
        {"name": "自由時報", "rss": "https://news.ltn.com.tw/rss"},
        {"name": "中國時報", "rss": "https://www.chinatimes.com/realtimenews/?chdtv=rss"},
        {"name": "中央社", "rss": "https://www.cna.com.tw/rss"},
        {"name": "ETtoday", "rss": "https://www.ettoday.net/news/newslist.rss"},
        {"name": "關鍵評論網", "rss": "https://www.thenewslens.com/rss"},
        {"name": "聯合報國際", "rss": "https://udn.com/rssfeed/news/2/7227?ch=news"},  # 補國際分類
        {"name": "中央社國際", "rss": "https://www.cna.com.tw/rss/aopl.aspx"},  # 補國際分類
    ],
    "中國大陸": [
        {"name": "人民日報", "rss": "http://paper.people.com.cn/rmrb/rss.xml"},
        {"name": "新華社", "rss": "http://www.xinhuanet.com/english/rss.xml"},
        {"name": "中國日報", "rss": "https://www.chinadaily.com.cn/rss/china_rss.xml"},
        {"name": "環球時報", "rss": "https://www.globaltimes.cn/rss.xml"},
        {"name": "澎湃新聞", "rss": "https://www.thepaper.cn/rss"},
        {"name": "新華社國際", "rss": "http://www.news.cn/world/rss.xml"},  # 補國際分類
        {"name": "環球時報國際", "rss": "https://www.globaltimes.cn/rss/world.xml"},  # 補國際分類
    ],
    "世界華文": [
        {"name": "聯合早報", "rss": "https://www.zaobao.com.sg/rss"},
        {"name": "BBC 中文", "rss": "https://feeds.bbci.co.uk/zhongwen/trad/rss.xml"},
        {"name": "紐約時報中文", "rss": "https://cn.nytimes.com/rss"},
        {"name": "德國之聲中文", "rss": "https://rss.dw.com/rdf/rss-chi-all"},
        {"name": "法廣中文", "rss": "https://www.rfi.fr/cn/rss"},
    ],
    "世界英文": [
        {"name": "Reuters", "rss": "https://www.reuters.com/rss"},
        {"name": "BBC News", "rss": "https://feeds.bbci.co.uk/news/rss.xml"},
        {"name": "The Guardian", "rss": "https://www.theguardian.com/rss"},
        {"name": "The New York Times", "rss": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"},
        {"name": "Al Jazeera English", "rss": "https://www.aljazeera.com/xml/rss/all.xml"},
    ]
}

# 來源分類過濾（無「全部來源」）
source_category = st.selectbox(source_filter_label, [hk_sources, tw_sources, cn_sources, world_chinese, world_english])

# 決定分類
category_map = {
    hk_sources: "香港",
    tw_sources: "台灣",
    cn_sources: "中國大陸",
    world_chinese: "世界華文",
    world_english: "世界英文"
}
selected_group = category_map[source_category]

# 提示（針對中國/台灣）
if selected_group in ["中國大陸", "台灣"]:
    st.caption(cn_note if selected_group == "中國大陸" else tw_note)

query = st.text_input(search_label, placeholder=search_placeholder)

if 'search_results' not in st.session_state:
    st.session_state.search_results = None

@st.cache_data(ttl=600)
def fetch_rss_articles(selected_group, query):
    all_articles = []
    query_lower = query.lower()

    for source in rss_sources[selected_group]:
        try:
            feed = feedparser.parse(source["rss"])
            for entry in feed.entries:
                title = entry.get("title", "無標題")
                link = entry.get("link", "#")
                published = entry.get("published", entry.get("updated", entry.get("dc:date", entry.get("pubDate", None))))
                summary_raw = entry.get("summary", entry.get("description", ""))[:500]

                soup = BeautifulSoup(summary_raw, 'html.parser')
                summary = soup.get_text(separator=' ', strip=True)[:300]

                # 自動精準匹配（對所有搜尋都強制完整字串）
                if query_lower in title.lower() or query_lower in summary.lower():
                    dt = None
                    if published:
                        try:
                            dt = date_parser.parse(published)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=pytz.UTC)
                            dt = dt.astimezone(HKT)
                        except:
                            dt = None

                    all_articles.append({
                        "title": title,
                        "summary": summary,
                        "source": source["name"],
                        "published": dt,
                        "link": link,
                        "category": selected_group
                    })
        except:
            pass
    return all_articles

if st.button(search_button):
    if not query.strip():
        st.error("請輸入關鍵字" if interface_lang == "中文" else "Please enter keywords")
    else:
        st.info(loading_text)
        try:
            articles = fetch_rss_articles(selected_group, query)

            def parse_date(article):
                return article["published"] if article["published"] else datetime.datetime.min.replace(tzinfo=HKT)

            sorted_articles = sorted(articles, key=parse_date, reverse=True)

            st.session_state.search_results = sorted_articles

        except Exception as e:
            st.error(f"{error_generic}: {str(e)}")
        else:
            st.success(success_text)

# 顯示結果
if st.session_state.search_results is not None:
    st.subheader("搜尋結果" if interface_lang == "中文" else "Search Results")
    articles = st.session_state.search_results

    if not articles:
        st.warning(no_results)
    else:
        for article in articles:
            title = article.get('title', '無標題' if interface_lang == "中文" else 'No title')
            summary = article.get('summary', '')
            source = article.get('source', '未知' if interface_lang == "中文" else 'Unknown')
            category = article.get('category', '')
            published = article.get('published')
            pub_display = published.strftime("%Y-%m-%d %H:%M %Z") if published else '未知'
            link = article.get('link', '#')

            st.markdown(f"**{title}** ({category} - {source})")
            if summary:
                st.write(summary + "..." if len(summary) > 250 else summary)
            st.caption(pub_display)
            st.markdown(f"[閱讀全文 / Read full article]({link})")
            st.divider()