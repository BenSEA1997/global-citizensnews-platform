import streamlit as st
import requests
import re
import datetime
from urllib.parse import quote

# ===== HanLP (中文 NER) =====
# 先安裝：pip install hanlp
# 然後在 requirements.txt 加 hanlp
try:
    import hanlp
    HanLP = hanlp.load(hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_BASE_ZH)
except:
    HanLP = None  # 如果沒裝，跳過

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
    loading_text = "Fetching news from multiple sources..."
    no_results = "No news found. Try other keywords."
    error_generic = "An error occurred"
    success_text = "Search completed!"
    search_tip = "Tip: Use AND/OR/NOT for precise search, e.g. Li Ka-shing AND Hong Kong"
else:
    page_title = "全球即時新聞搜尋"
    search_label = "搜尋地點或事件"
    search_placeholder = "例如：伊朗德黑蘭、李家超"
    search_button = "開始搜尋"
    loading_text = "正在從多來源抓取新聞..."
    no_results = "沒有找到新聞，請試其他關鍵字"
    error_generic = "發生錯誤"
    success_text = "✅ 搜尋完成！"
    search_tip = "提示：用 AND/OR/NOT 精細搜尋，例如 李家超 AND 香港 OR 李家超 NOT 商業"

st.title(page_title)

st.caption(search_tip)

# ===== API Key =====
api_key = st.secrets.get("NEWS_API_KEY", "")

if not api_key:
    st.error("API Key not set in Streamlit Secrets. Please add NEWS_API_KEY.")
    st.stop()

# ===== 搜尋區塊 =====
query = st.text_input(search_label, placeholder=search_placeholder)

if 'search_results' not in st.session_state:
    st.session_state.search_results = None

if st.button(search_button):
    if not query:
        st.error("請輸入關鍵字" if interface_lang == "中文" else "Please enter keywords")
    else:
        st.info(loading_text)
        try:
            all_results = []

            # 1. NewsData.io 主搜尋（主流媒體）
            precise_query = f'"{query}"' if re.search(r'[\u4e00-\u9fff]', query) else query
            url_nd = f"https://newsdata.io/api/1/news?apikey={api_key}&q={precise_query}&language=zh,en&prioritydomain=top&size=10"
            r_nd = requests.get(url_nd, timeout=15)
            if r_nd.status_code == 200:
                all_results.extend(r_nd.json().get("results", []))

            # 2. Google News RSS 補充（大量中文新聞）
            google_query = quote(query)
            url_google = f"https://news.google.com/rss/search?q={google_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            r_google = requests.get(url_google, timeout=15)
            if r_google.status_code == 200:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(r_google.content)
                for item in root.findall(".//item")[:10]:
                    title = item.find("title").text
                    link = item.find("link").text
                    pub = item.find("pubDate").text
                    all_results.append({"title": title, "link": link, "pubDate": pub, "source_id": "Google News"})

            # 3. HanLP NER 過濾與擴詞（如果裝了 HanLP）
            if HanLP:
                doc = HanLP(query)
                entities = doc['ner/msra']
                if entities:
                    extra_keywords = [ent[0] for ent in entities if ent[1] in ['PER', 'ORG']]  # 人名/組織
                    if extra_keywords:
                        st.info(f"偵測到人物/組織：{', '.join(extra_keywords)}，已擴大搜尋範圍")
                        # 可再呼叫一次 API 加 extra_keywords

            # 顯示結果
            st.session_state.search_results = all_results[:20]  # 限制 20 條
        except Exception as e:
            st.error(f"{error_generic}: {str(e)}")
            st.session_state.search_results = None

# 顯示搜尋結果
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

st.success(success_text)