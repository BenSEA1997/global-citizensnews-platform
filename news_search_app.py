import streamlit as st
import requests
import re
import datetime
from xml.etree import ElementTree as ET
from urllib.parse import quote
from dateutil import parser
from bs4 import BeautifulSoup
import pytz

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

# ===== 地區選擇 =====
country_options = {
    "Global / 全球": "",
    "Hong Kong / 香港": "hk",
    "Taiwan / 台灣": "tw",
    "China / 大陸": "cn"
}
country_label = "Select Region / 選擇地區" if interface_lang == "English" else "選擇地區 / Select Region"
selected_country = st.selectbox(country_label, list(country_options.keys()), index=1)  # 預設香港
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
    x_tab_title = "X (Twitter) Results"
    x_no_results = "No X posts found."
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
    x_tab_title = "X (Twitter) 搜尋結果"
    x_no_results = "沒有找到相關 X 貼文"

st.title(page_title)
st.caption(search_tip)

# ===== 香港時區 =====
HKT = pytz.timezone('Asia/Hong_Kong')

# ===== 搜尋區塊 =====
query = st.text_input(search_label, placeholder=search_placeholder)

if 'news_results' not in st.session_state:
    st.session_state.news_results = None
if 'x_results' not in st.session_state:
    st.session_state.x_results = None

if st.button(search_button):
    if not query.strip():
        st.error("請輸入關鍵字" if interface_lang == "中文" else "Please enter keywords")
    else:
        st.info(loading_text)
        try:
            api_key = st.secrets["NEWS_API_KEY"]
            twitter_bearer = st.secrets.get("TWITTER_BEARER_TOKEN", None)

            results = []

            # 自動精準處理中文名字
            precise_query = query
            if re.search(r'[\u4e00-\u9fff]', query):
                precise_query = f'"{query}"'

            # NewsData.io 搜尋（移除 image=1，讓結果更多）
            url_nd = f"https://newsdata.io/api/1/news?apikey={api_key}&q={quote(precise_query)}&language=zh,en&country={country_code}&size=10"
            response_nd = requests.get(url_nd, timeout=15)
            if response_nd.status_code == 200:
                data = response_nd.json()
                for item in data.get("results", []):
                    desc = item.get("description") or item.get("content", "")[:300] or ""
                    results.append({
                        "title": item.get("title", ""),
                        "description": desc,
                        "source": item.get("source_id", "NewsData"),
                        "pubDate": item.get("pubDate"),
                        "link": item.get("link", "#"),
                        "type": "news"
                    })

            # Google News RSS 補充
            google_query = quote(query)
            url_google = f"https://news.google.com/rss/search?q={google_query}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant"
            response_google = requests.get(url_google, timeout=15)
            if response_google.status_code == 200:
                root = ET.fromstring(response_google.content)
                for item in root.findall(".//item")[:10]:
                    title_raw = item.find("title").text or ""
                    link = item.find("link").text or "#"
                    pub = item.find("pubDate").text or ""
                    desc_raw = item.find("description").text or ""

                    soup = BeautifulSoup(desc_raw, 'html.parser')
                    if soup.find_all('a'):
                        soup.find_all('a')[-1].decompose()
                    clean_desc = soup.get_text(separator=' ', strip=True)[:300]

                    match = re.search(r' - (.+?)(?=\s*\(|$)', title_raw)
                    source = match.group(1).strip() if match else "Google News"
                    title = re.sub(r' - .+$', '', title_raw).strip()

                    results.append({
                        "title": title,
                        "description": clean_desc,
                        "source": source,
                        "pubDate": pub,
                        "link": link,
                        "type": "news"
                    })

            # 去重 + 排序 + 轉香港時間
            unique_results = {r['link']: r for r in results if r.get('link') and r['link'] != "#"}.values()

            def parse_date_to_hkt(date_str):
                if not date_str:
                    return datetime.datetime.min.replace(tzinfo=HKT)
                try:
                    dt = parser.parse(date_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=pytz.UTC)
                    return dt.astimezone(HKT)
                except:
                    return datetime.datetime.min.replace(tzinfo=HKT)

            sorted_results = sorted(
                unique_results,
                key=lambda x: parse_date_to_hkt(x.get('pubDate', '')),
                reverse=True
            )

            for r in sorted_results:
                dt_hkt = parse_date_to_hkt(r['pubDate'])
                r['pubDate_display'] = dt_hkt.strftime("%Y-%m-%d %H:%M:%S %Z")

            st.session_state.news_results = sorted_results

            # X (Twitter) 真實搜尋
            x_results = []
            if twitter_bearer:
                headers = {
                    "Authorization": f"Bearer {twitter_bearer}"
                }
                params = {
                    "query": f"{query} lang:zh OR lang:en -is:retweet",  # 可調整過濾條件
                    "tweet.fields": "created_at,author_id,text,lang",
                    "user.fields": "username,name",
                    "expansions": "author_id",
                    "max_results": 10,
                    "sort_order": "recency"
                }
                url = "https://api.twitter.com/2/tweets/search/recent"
                response = requests.get(url, headers=headers, params=params, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                    for tweet in data.get("data", []):
                        user = users.get(tweet["author_id"], {})
                        created_at = tweet.get("created_at", "")
                        created_display = "未知"
                        if created_at:
                            try:
                                dt = parser.parse(created_at).astimezone(HKT)
                                created_display = dt.strftime("%Y-%m-%d %H:%M:%S %Z")
                            except:
                                pass
                        x_results.append({
                            "text": tweet.get("text", ""),
                            "user": f"@{user.get('username', 'unknown')}",
                            "name": user.get("name", ""),
                            "created_at": created_display,
                            "link": f"https://x.com/{user.get('username', 'unknown')}/status/{tweet['id']}"
                        })
                else:
                    st.warning(f"X API 錯誤 ({response.status_code}): {response.text}")
            else:
                st.warning("未設定 TWITTER_BEARER_TOKEN，請在 secrets 加入")

            st.session_state.x_results = x_results

        except requests.Timeout:
            st.error(error_timeout)
        except Exception as e:
            st.error(f"{error_generic}: {str(e)}")
        else:
            st.success(success_text)

# ===== 顯示新聞結果 =====
if st.session_state.news_results is not None:
    st.subheader("搜尋結果" if interface_lang == "中文" else "Search Results")
    articles = st.session_state.news_results

    if not articles:
        st.warning(no_results)
    else:
        for article in articles:
            title = article.get('title', '無標題' if interface_lang == "中文" else 'No title')
            desc = article.get('description', '')
            source = article.get('source', '未知' if interface_lang == "中文" else 'Unknown')
            pub = article.get('pubDate_display', '未知' if interface_lang == "中文" else 'Unknown')
            link = article.get('link', '#')

            st.markdown(f"**{title}**")
            if desc:
                st.write(desc + "..." if len(desc) > 250 else desc)
            st.caption(f"{source} | {pub}")
            st.markdown(f"[閱讀全文 / Read full article]({link})")
            st.divider()

# ===== 顯示 X 搜尋結果 =====
if st.session_state.x_results is not None:
    st.subheader(x_tab_title)
    x_posts = st.session_state.x_results

    if not x_posts:
        st.info(x_no_results)
    else:
        for post in x_posts:
            st.markdown(f"**{post['user']}** ({post['name']}) · {post['created_at']}")
            st.write(post['text'])
            st.markdown(f"[查看貼文 / View post]({post['link']})")
            st.divider()

st.caption("新聞來源：NewsData.io + Google News RSS | X 來源：Twitter API v2 | 時間已轉換為香港時區")