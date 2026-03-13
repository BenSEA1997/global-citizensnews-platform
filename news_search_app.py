import streamlit as st
import feedparser
import datetime
from dateutil import parser as date_parser
import pytz
from urllib.parse import quote

st.set_page_config(page_title="全球即時新聞搜尋", page_icon="🌍", layout="wide")

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
    loading_text = "Fetching news..."
    no_results = "No news found. Try other keywords."
    error_timeout = "Connection timed out. Check network or VPN."
    error_generic = "An error occurred"
    success_text = "Search completed!"
    search_tip = "Tip: For names or exact phrases, use quotes e.g. \"Li Ka-shing\""
    source_filter_label = "Source Category"
    all_sources = "All Sources"
    hk_sources = "Hong Kong"
    tw_sources = "Taiwan"
    cn_sources = "China Mainland"
    world_chinese = "World Chinese"
    world_english = "World English"
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
    search_tip = "提示：人名或專有名詞建議用引號包住，例如 \"李家超\" 或 \"伊朗核協議\""
    source_filter_label = "來源分類"
    all_sources = "全部來源"
    hk_sources = "香港"
    tw_sources = "台灣"
    cn_sources = "中國大陸"
    world_chinese = "世界華文"
    world_english = "世界英文"

st.title(page_title)
st.caption(search_tip)

# ===== 白名單 RSS 清單（已整理域名 + RSS 連結） =====
# 注意：部分 RSS 需透過 rss.app 或官方產生，若官方無 RSS 則用 rss.app 替代連結（你可自行替換）

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
        {"name": "香港01", "rss": "https://www.hk01.com/rss"},
        {"name": "Now 新聞", "rss": "https://news.now.com/home/rss"},
        {"name": "香港自由新聞 (HKFP)", "rss": "https://hongkongfp.com/feed/"},
    ],
    "台灣": [
        {"name": "聯合報", "rss": "https://udn.com/rssfeed/news/2/7225?ch=news"},
        {"name": "自由時報", "rss": "https://news.ltn.com.tw/rss"},
        {"name": "中國時報", "rss": "https://www.chinatimes.com/realtimenews/?chdtv=rss"},
        {"name": "中央社", "rss": "https://www.cna.com.tw/rss"},
        {"name": "ETtoday", "rss": "https://www.ettoday.net/news/newslist.rss"},
        {"name": "關鍵評論網", "rss": "https://www.thenewslens.com/rss"},
        {"name": "報導者", "rss": "https://www.twreporter.org/rss"},
    ],
    "中國大陸": [
        {"name": "人民日報", "rss": "http://paper.people.com.cn/rmrb/rss.xml"},
        {"name": "新華社", "rss": "http://www.xinhuanet.com/english/rss.xml"},
        {"name": "中國日報", "rss": "https://www.chinadaily.com.cn/rss/china_rss.xml"},
        {"name": "環球時報", "rss": "https://www.globaltimes.cn/rss.xml"},
        {"name": "澎湃新聞", "rss": "https://www.thepaper.cn/rss"},
        {"name": "財新網", "rss": "https://www.caixin.com/rss"},
    ],
    "世界華文": [
        {"name": "聯合早報", "rss": "https://www.zaobao.com.sg/rss"},
        {"name": "星洲網", "rss": "https://www.sinchew.com.my/rss"},
        {"name": "BBC 中文", "rss": "https://feeds.bbci.co.uk/zhongwen/trad/rss.xml"},
        {"name": "紐約時報中文", "rss": "https://cn.nytimes.com/rss"},
        {"name": "華爾街日報中文", "rss": "https://cn.wsj.com/zh-hant/rss"},
        {"name": "德國之聲中文", "rss": "https://rss.dw.com/rdf/rss-chi-all"},
        {"name": "法廣中文", "rss": "https://www.rfi.fr/cn/rss"},
    ],
    "世界英文": [
        {"name": "Reuters", "rss": "https://www.reuters.com/rss"},
        {"name": "AP News", "rss": "https://apnews.com/index.rss"},
        {"name": "BBC News", "rss": "https://feeds.bbci.co.uk/news/rss.xml"},
        {"name": "The Guardian", "rss": "https://www.theguardian.com/rss"},
        {"name": "NYTimes", "rss": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"},
        {"name": "Washington Post", "rss": "https://www.washingtonpost.com/rss"},
        {"name": "Financial Times", "rss": "https://www.ft.com/rss"},
        {"name": "Al Jazeera", "rss": "https://www.aljazeera.com/xml/rss/all.xml"},
    ]
}

st.caption("新聞來源：已精選港中台及世界主流媒體 RSS | 時間已轉換為香港時區")

# ===== 來源分類過濾 =====
source_category = st.selectbox(
    source_filter_label,
    [all_sources, hk_sources, tw_sources, cn_sources, world_chinese, world_english]
)

# 根據選擇決定要讀哪些 RSS
selected_groups = []
if source_category == all_sources:
    selected_groups = list(rss_sources.keys())
elif source_category == hk_sources:
    selected_groups = ["香港"]
elif source_category == tw_sources:
    selected_groups = ["台灣"]
elif source_category == cn_sources:
    selected_groups = ["中國大陸"]
elif source_category == world_chinese:
    selected_groups = ["世界華文"]
elif source_category == world_english:
    selected_groups = ["世界英文"]

# ===== 搜尋區塊 =====
query = st.text_input(search_label, placeholder=search_placeholder)

if 'search_results' not in st.session_state:
    st.session_state.search_results = None

if st.button(search_button):
    if not query.strip():
        st.error("請輸入關鍵字" if interface_lang == "中文" else "Please enter keywords")
    else:
        st.info(loading_text)
        try:
            all_articles = []

            # 只讀取選中的分類 RSS
            for group in selected_groups:
                for source in rss_sources[group]:
                    try:
                        feed = feedparser.parse(source["rss"])
                        for entry in feed.entries:
                            title = entry.get("title", "無標題")
                            link = entry.get("link", "#")
                            published = entry.get("published", entry.get("updated", None))
                            summary = entry.get("summary", entry.get("description", ""))[:300]

                            # 簡單關鍵字過濾（可加強）
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
                                    "category": group
                                })
                    except Exception as e:
                        st.warning(f"來源 {source['name']} 讀取失敗：{str(e)}")

            # 排序（最新在上）
            def parse_date(article):
                return article["published"] if article["published"] else datetime.datetime.min.replace(tzinfo=HKT)

            sorted_articles = sorted(all_articles, key=parse_date, reverse=True)

            # 儲存結果
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
            st.caption(f"{pub_display}")
            st.markdown(f"[閱讀全文 / Read full article]({link})")
            st.divider()