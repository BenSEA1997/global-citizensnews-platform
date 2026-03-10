import streamlit as st
import requests
import re
import datetime
from xml.etree import ElementTree as ET
from urllib.parse import quote
from dateutil import parser
from bs4 import BeautifulSoup

st.set_page_config(page_title="全球即時新聞搜尋", page_icon="🌍", layout="wide")

# ===== 抓取新聞頁面 OpenGraph 圖片 =====
def extract_image_from_article(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")

        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]

    except:
        return None

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
    loading_text = "Fetching news..."
    no_results = "No news found. Try other keywords."
    success_text = "Search completed!"

else:

    page_title = "全球即時新聞搜尋"
    search_label = "搜尋地點或事件"
    search_placeholder = "例如：伊朗德黑蘭、李家超"
    search_button = "開始搜尋"
    loading_text = "正在抓取新聞..."
    no_results = "沒有找到新聞"
    success_text = "搜尋完成！"

st.title(page_title)

query = st.text_input(search_label, placeholder=search_placeholder)

if 'search_results' not in st.session_state:
    st.session_state.search_results = None


# ===== 搜尋 =====
if st.button(search_button):

    if not query:
        st.warning("Please enter keywords")

    else:

        st.info(loading_text)

        try:

            api_key = st.secrets["NEWS_API_KEY"]

            results = []

            precise_query = query

            if re.search(r'[\u4e00-\u9fff]', query):
                precise_query = f'"{query}"'

            # ===== NewsData API =====
            url_nd = f"https://newsdata.io/api/1/news?apikey={api_key}&q={quote(precise_query)}&language=zh,en&country={country_code}&size=10"

            r = requests.get(url_nd, timeout=15)

            if r.status_code == 200:

                data = r.json()

                for item in data.get("results", []):

                    img_url = item.get("image_url")

                    if not img_url:
                        img_url = extract_image_from_article(item.get("link"))

                    desc = item.get("description", "")

                    results.append({

                        "title": item.get("title"),
                        "description": desc,
                        "source": item.get("source_id"),
                        "date": item.get("pubDate"),
                        "link": item.get("link"),
                        "image": img_url
                    })


            # ===== Google News RSS =====
            google_query = quote(query)

            url_google = f"https://news.google.com/rss/search?q={google_query}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant"

            r = requests.get(url_google, timeout=15)

            if r.status_code == 200:

                root = ET.fromstring(r.content)

                for item in root.findall(".//item")[:10]:

                    title_raw = item.find("title").text
                    link = item.find("link").text
                    pub = item.find("pubDate").text
                    desc_raw = item.find("description").text

                    soup = BeautifulSoup(desc_raw, 'html.parser')
                    clean_desc = soup.get_text()

                    match = re.search(r' - (.+?)(?=\s*\(|$)', title_raw)

                    source = match.group(1) if match else "Google News"

                    title = re.sub(r' - .+$', '', title_raw)

                    img_url = extract_image_from_article(link)

                    results.append({

                        "title": title,
                        "description": clean_desc,
                        "source": source,
                        "date": pub,
                        "link": link,
                        "image": img_url
                    })


            # ===== 去重 =====
            unique = {r["link"]: r for r in results}.values()

            # ===== 時間排序 =====
            def parse_date(d):

                try:
                    return parser.parse(d)
                except:
                    return datetime.datetime.min

            sorted_results = sorted(unique, key=lambda x: parse_date(x["date"]), reverse=True)

            st.session_state.search_results = sorted_results

        except Exception as e:

            st.error(str(e))

        else:

            st.success(success_text)


# ===== 顯示結果 =====
if st.session_state.search_results:

    for article in st.session_state.search_results:

        col1, col2 = st.columns([1,5])

        with col1:

            if article["image"]:

                try:
                    st.image(article["image"], width="stretch")

                except:
                    st.image("https://via.placeholder.com/120?text=Image")

            else:

                st.image("https://via.placeholder.com/120?text=No+Image")

        with col2:

            st.markdown(f"### {article['title']}")

            if article["description"]:
                st.write(article["description"][:300])

            st.caption(f"{article['source']} | {article['date']}")

            st.markdown(f"[Read Full Article]({article['link']})")

        st.divider()