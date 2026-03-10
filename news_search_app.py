import streamlit as st
import requests
import re
import datetime
from xml.etree import ElementTree as ET
from urllib.parse import quote
from dateutil import parser
from bs4 import BeautifulSoup

st.set_page_config(page_title="全球即時新聞搜尋", page_icon="🌍", layout="wide")

# ===== 抓取新聞頁面圖片 =====
def extract_image_from_article(url):

    try:

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9"
        }

        r = requests.get(url, headers=headers, timeout=8)

        soup = BeautifulSoup(r.text, "html.parser")

        og = soup.find("meta", property="og:image")

        if og and og.get("content"):
            return og["content"]

        # 如果沒有 og:image，再找文章第一張圖片
        img = soup.find("img")

        if img and img.get("src"):
            return img["src"]

    except:
        return None

    return None


# ===== 取得 Google News 真實新聞網址 =====
def get_real_news_url(google_link):

    try:

        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(google_link, headers=headers, timeout=5, allow_redirects=True)

        return r.url

    except:

        return google_link


# ===== 右上角語言切換 =====
col1, col2 = st.columns([8,1])

with col2:

    interface_lang = st.selectbox(
        "Language",
        ["English","中文"],
        label_visibility="collapsed"
    )


# ===== 地區選擇 =====
country_options = {

    "Global / 全球":"",
    "Hong Kong / 香港":"hk",
    "Taiwan / 台灣":"tw",
    "China / 大陸":"cn"

}

selected_country = st.selectbox(
    "Select Region / 選擇地區",
    list(country_options.keys()),
    index=1
)

country_code = country_options[selected_country]


# ===== 文字 =====
if interface_lang == "English":

    title = "Global Real-time News Search"
    search_button = "Search"

else:

    title = "全球即時新聞搜尋"
    search_button = "開始搜尋"


st.title(title)

query = st.text_input("Search / 搜尋")

if "search_results" not in st.session_state:

    st.session_state.search_results = None


# ===== 搜尋 =====
if st.button(search_button):

    if not query:

        st.warning("請輸入關鍵字")

    else:

        st.info("正在抓取新聞...")

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

                for item in data.get("results",[]):

                    link = item.get("link")

                    img_url = item.get("image_url")

                    if not img_url:

                        img_url = extract_image_from_article(link)

                    results.append({

                        "title":item.get("title"),
                        "desc":item.get("description"),
                        "source":item.get("source_id"),
                        "date":item.get("pubDate"),
                        "link":link,
                        "image":img_url
                    })


            # ===== Google News RSS =====
            google_query = quote(query)

            url_google = f"https://news.google.com/rss/search?q={google_query}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant"

            r = requests.get(url_google,timeout=15)

            if r.status_code == 200:

                root = ET.fromstring(r.content)

                for item in root.findall(".//item")[:10]:

                    title_raw = item.find("title").text

                    link = item.find("link").text

                    pub = item.find("pubDate").text

                    desc_raw = item.find("description").text

                    # 取得真正新聞網址
                    real_link = get_real_news_url(link)

                    soup = BeautifulSoup(desc_raw,'html.parser')

                    clean_desc = soup.get_text()

                    match = re.search(r' - (.+?)(?=\s*\(|$)', title_raw)

                    source = match.group(1) if match else "Google News"

                    title = re.sub(r' - .+$','',title_raw)

                    img_url = extract_image_from_article(real_link)

                    results.append({

                        "title":title,
                        "desc":clean_desc,
                        "source":source,
                        "date":pub,
                        "link":real_link,
                        "image":img_url
                    })


            # ===== 去重 =====
            unique = {r["link"]:r for r in results}.values()


            # ===== 排序 =====
            def parse_date(d):

                try:

                    return parser.parse(d)

                except:

                    return datetime.datetime.min


            sorted_results = sorted(unique,key=lambda x:parse_date(x["date"]),reverse=True)

            st.session_state.search_results = sorted_results

        except Exception as e:

            st.error(str(e))

        else:

            st.success("搜尋完成")


# ===== 顯示結果 =====
if st.session_state.search_results:

    for article in st.session_state.search_results:

        col1,col2 = st.columns([1,5])

        with col1:

            if article["image"]:

                try:

                    st.image(article["image"], width="stretch")

                except:

                    st.image("https://via.placeholder.com/120")

            else:

                st.image("https://via.placeholder.com/120?text=No+Image")

        with col2:

            st.markdown(f"### {article['title']}")

            if article["desc"]:

                st.write(article["desc"][:300])

            st.caption(f"{article['source']} | {article['date']}")

            st.markdown(f"[Read Full Article]({article['link']})")

        st.divider()