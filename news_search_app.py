import streamlit as st
import feedparser
import datetime
from dateutil import parser as date_parser
import pytz

st.set_page_config(page_title="全球新聞搜尋", page_icon="🌍", layout="wide")

# 香港時區
HKT = pytz.timezone('Asia/Hong_Kong')

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
    page_title = "Global News Search"
    search_label = "Search keywords"
    search_placeholder = "e.g. Tehran Iran, Li Ka-shing"
    search_button = "Search"
    loading_text = "Fetching news..."
    no_results = "No news found. Try other keywords."
    error_generic = "An error occurred"
    success_text = "Search completed!"
    search_tip = "Tip: Use quotes for exact phrases e.g. \"Li Ka-shing\""
    source_filter_label = "Source Category"
    hk_sources = "Hong Kong"
    tw_sources = "Taiwan"
    cn_sources = "China Mainland"
    world_chinese = "World Chinese"
    world_english = "World English"
else:
    page_title = "全球新聞搜尋"
    search_label = "搜尋關鍵字"
    search_placeholder = "例如：伊朗德黑蘭、李家超"
    search_button = "開始搜尋"
    loading_text = "正在抓取新聞..."
    no_results = "沒有找到新聞，請試其他關鍵字"
    error_generic = "發生錯誤"
    success_text = "✅ 搜尋完成！"
    search_tip = "提示：人名或專有名詞建議用引號包住，例如 \"李家超\" 或 \"伊朗核協議\""
    source_filter_label = "來源分類"
    hk_sources = "香港"
    tw_sources = "台灣"
    cn_sources = "中國大陸"
    world_chinese = "世界華文"
    world_english = "世界英文"

st.title(page_title)
st.caption(search_tip)

# ===== 白名單 RSS 清單（全部保留，按你提供的清單整理） =====
rss_sources = {
    "香港": [
        {"name": "香港電台 (RTHK)", "rss": "https://news.rthk.hk/rthk/ch/rss.htm"},
        {"name": "政府新聞網", "rss": "https://www.news.gov.hk/chi/rss.xml"},
        {"name": "明報", "rss": "https://news.mingpao.com/php/rss.php"},
        {"name": "南華早報 (SCMP)", "rss": "https://www.scmp.com/rss/91/feed"},
        {"name": "星島日報", "rss": "https://www.singtao.com/rss"},
        {"name": "東方日報", "rss": "https://orientaldaily.on.cc/rss/news.xml"},
        {"name": "信報", "rss": "https://www.hkej.com/rss"},
        {"name": "經濟日報", "rss": "https://www.hket.com/rss"},
        {"name": "am730", "rss": "https://www.am730.com.hk/rss"},
        {"name": "巴士的報", "rss": "https://www.bastillepost.com/rss"},
        {"name": "文匯報", "rss": "https://www.wenweipo.com/rss"},
        {"name": "大公報", "rss": "https://www.takungpao.com/rss"},
        {"name": "商報", "rss": "https://www.hkcd.com.hk/rss"},
        {"name": "香港01", "rss": "https://www.hk01.com/rss"},
        {"name": "Now 新聞", "rss": "https://news.now.com/home/rss"},
        {"name": "有線新聞", "rss": "https://www.i-cable.com/rss"},
        {"name": "無線新聞 (TVB)", "rss": "https://news.tvb.com/rss"},
        {"name": "英文虎報 (The Standard)", "rss": "https://www.thestandard.com.hk/rss"},
        {"name": "China Daily HK", "rss": "https://www.chinadailyhk.com/rss"},
        {"name": "香港自由新聞 (HKFP)", "rss": "https://hongkongfp.com/feed/"},
        {"name": "香港仔", "rss": "https://lionrockdaily.com/feed/"},
        {"name": "橙新聞", "rss": "https://orangenews.hk/rss"},
        {"name": "獨立媒體 (InMediaHK)", "rss": "https://www.inmediahk.net/rss"},
        {"name": "大紀元", "rss": "https://www.epochtimes.com/gb/rss.htm"},
    ],
    "台灣": [
        {"name": "聯合報", "rss": "https://udn.com/rssfeed/news/2/7225?ch=news"},
        {"name": "自由時報", "rss": "https://news.ltn.com.tw/rss"},
        {"name": "中國時報", "rss": "https://www.chinatimes.com/realtimenews/?chdtv=rss"},
        {"name": "NOWnews", "rss": "https://www.nownews.com/rss"},
        {"name": "ETtoday", "rss": "https://www.ettoday.net/news/newslist.rss"},
        {"name": "中央社", "rss": "https://www.cna.com.tw/rss"},
        {"name": "經濟日報", "rss": "https://money.udn.com/rssfeed/5591/1001?ch=news"},
        {"name": "工商時報", "rss": "https://ctee.com.tw/rss"},
        {"name": "三立新聞", "rss": "https://www.setn.com/rss.aspx?PageGroupID=1"},
        {"name": "民視新聞", "rss": "https://www.ftvnews.com.tw/rss"},
        {"name": "TVBS 新聞", "rss": "https://news.tvbs.com.tw/rss"},
        {"name": "中天新聞", "rss": "https://www.ctitv.com.tw/rss"},
        {"name": "關鍵評論網", "rss": "https://www.thenewslens.com/rss"},
        {"name": "報導者", "rss": "https://www.twreporter.org/rss"},
    ],
    "中國大陸": [
        {"name": "人民日報", "rss": "http://paper.people.com.cn/rmrb/rss.xml"},
        {"name": "新華社", "rss": "http://www.xinhuanet.com/english/rss.xml"},
        {"name": "央視 / CGTN", "rss": "https://news.cctv.com/rss/index.xml"},
        {"name": "求是", "rss": "http://www.qstheory.cn/rss"},
        {"name": "中國日報", "rss": "https://www.chinadaily.com.cn/rss/china_rss.xml"},
        {"name": "環球時報", "rss": "https://www.globaltimes.cn/rss.xml"},
        {"name": "澎湃新聞", "rss": "https://www.thepaper.cn/rss"},
        {"name": "財新網", "rss": "https://www.caixin.com/rss"},
        {"name": "界面新聞", "rss": "https://www.jiemian.com/rss"},
        {"name": "21世紀經濟報導", "rss": "https://www.21jingji.com/rss"},
        {"name": "第一財經", "rss": "https://www.yicai.com/rss"},
    ],
    "世界華文": [
        {"name": "聯合早報", "rss": "https://www.zaobao.com.sg/rss"},
        {"name": "星洲網", "rss": "https://www.sinchew.com.my/rss"},
        {"name": "BBC 中文", "rss": "https://feeds.bbci.co.uk/zhongwen/trad/rss.xml"},
        {"name": "紐約時報中文", "rss": "https://cn.nytimes.com/rss"},
        {"name": "華爾街日報中文", "rss": "https://cn.wsj.com/zh-hant/rss"},
        {"name": "德國之聲中文", "rss": "https://rss.dw.com/rdf/rss-chi-all"},
        {"name": "法廣中文", "rss": "https://www.rfi.fr/cn/rss"},
        {"name": "SBS 中文", "rss": "https://www.sbs.com.au/language/chinese/feed"},
        {"name": "ABC 中文", "rss": "https://www.abc.net.au/news/chinese/feed"},
    ],
    "世界英文": [
        {"name": "Reuters", "rss": "https://www.reuters.com/rss"},
        {"name": "AP News", "rss": "https://apnews.com/index.rss"},
        {"name": "AFP", "rss": "https://www.afp.com/en/rss-feeds"},
        {"name": "Bloomberg", "rss": "https://www.bloomberg.com/feed"},
        {"name": "The New York Times", "rss": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"},
        {"name": "The Washington Post", "rss": "https://www.washingtonpost.com/rss"},
        {"name": "The Guardian", "rss": "https://www.theguardian.com/rss"},
        {"name": "Financial Times", "rss": "https://www.ft.com/rss"},
        {"name": "BBC News", "rss": "https://feeds.bbci.co.uk/news/rss.xml"},
        {"name": "Al Jazeera English", "rss": "https://www.aljazeera.com/xml/rss/all.xml"},
    ]
}

# ===== 來源分類過濾（刪除「全部來源」） =====
source_category = st.selectbox(
    "來源分類",
    [hk_sources, tw_sources, cn_sources, world_chinese, world_english]
)

# 決定要讀哪一組
category_map = {
    hk_sources: "香港",
    tw_sources: "台灣",
    cn_sources: "中國大陸",
    world_chinese: "世界華文",
    world_english: "世界英文"
}
selected_group = category_map[source_category]

# ===== 搜尋區塊 =====
query = st.text_input(search_label, placeholder=search_placeholder)

if 'search_results' not in st.session_state:
    st.session_state.search_results = None

@st.cache_data(ttl=600)  # 快取 10 分鐘
def fetch_rss_articles(selected_group, query):
    all_articles = []
    for source in rss_sources[selected_group]:
        try:
            feed = feedparser.parse(source["rss"])
            for entry in feed.entries:
                title = entry.get("title", "無標題")
                link = entry.get("link", "#")
                published = entry.get("published", entry.get("updated", None))
                summary = entry.get("summary", entry.get("description", ""))[:300]

                if query.lower() in title.lower() or query.lower() in summary.lower():
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
            pass  # 跳過失效 RSS
    return all_articles

if st.button(search_button):
    if not query.strip():
        st.error("請輸入關鍵字" if interface_lang == "中文" else "Please enter keywords")
    else:
        st.info(loading_text)
        try:
            articles = fetch_rss_articles(selected_group, query)

            # 排序（最新在上）
            def parse_date(article):
                return article["published"] if article["published"] else datetime.datetime.min.replace(tzinfo=HKT)

            sorted_articles = sorted(articles, key=parse_date, reverse=True)

            st.session_state.search_results = sorted_articles

        except Exception as e:
            st.error(f"{error_generic}: {str(e)}")
        else:
            st.success(success_text)

# ===== 顯示結果 =====
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