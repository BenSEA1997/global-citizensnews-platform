import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單 (保持原樣) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}

TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}

MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}

ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

def get_domain(link):
    try:
        return urlparse(link).netloc.replace("www.", "")
    except:
        return "未知來源"

def clean_title_and_source(title):
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return title.strip(), ""

def clean_summary(text):
    if not text:
        return ""
    if '<a href' in text:
        text = text.split('<a href', 1)[0]
    if '<font color' in text:
        text = text.split('<font color', 1)[0]
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&nbsp;', ' ').strip()
    return text

def is_relevant(title: str, summary: str, query: str) -> bool:
    if not query or not title:
        return True
    q_lower = query.lower().strip()
    title_lower = title.lower()
    summary_lower = (summary or "").lower()
    return q_lower in title_lower or q_lower in summary_lower

def filter_by_date(articles, start_date, end_date):
    if not start_date or not end_date:
        return articles
    filtered = []
    for item in articles:
        if item.get("published"):
            try:
                if isinstance(item["published"], str):
                    dt = datetime.fromisoformat(item["published"].replace("Z", "+00:00")).date()
                else:
                    dt = date(*item["published"][:3])
                if start_date <= dt <= end_date:
                    filtered.append(item)
            except:
                filtered.append(item)
        else:
            filtered.append(item)
    return filtered

def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        articles = []
        for entry in feed.entries:
            link = entry.get('link', '')
            if link:
                articles.append({
                    "title": entry.get('title', '無標題'),
                    "link": link,
                    "summary": clean_summary(entry.get('summary', entry.get('description', ''))),
                    "published": entry.get('published_parsed'),
                    "source_type": "Google"
                })
        return articles
    except Exception as e:
        st.error(f"Google News 拉取失敗: {e}")
        return []

def build_url(query, gl, hl, ceid, start_date=None, end_date=None, sites=None):
    q_clean = query.strip()
    q = q_clean.replace(" ", "+") if q_clean else ""
    if sites:
        site_str = "+OR+".join(f"site:{s}" for s in sites)
        q = f"({q})+({site_str})" if q else site_str
    date_parts = []
    if start_date:
        date_parts.append(f"after:{start_date.strftime('%Y-%m-%d')}")
    if end_date:
        date_parts.append(f"before:{end_date.strftime('%Y-%m-%d')}")
    date_str = "+" + "+".join(date_parts) if date_parts else ""
    return f"https://news.google.com/rss/search?q={q}{date_str}&hl={hl}&gl={gl}&ceid={ceid}"

GNEWS_API_URL = "https://gnews.io/api/v4/search"

def fetch_gnews(query, start_date, end_date, lang, country, api_key, max_articles=60):
    try:
        params = {
            "token": api_key,
            "q": query,
            "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "lang": lang,
            "country": country,
            "max": max_articles,
            "sortby": "publishedAt"
        }
        response = requests.get(GNEWS_API_URL, params=params, timeout=25)
        data = response.json()
        articles = []
        for article in data.get("articles", []):
            articles.append({
                "title": article.get("title", "無標題"),
                "link": article.get("url", ""), 
                "summary": article.get("description", ""),
                "published": article.get("publishedAt"),
                "source_type": "GNews"
            })
        return articles, data.get("totalArticles", 0)
    except Exception as e:
        st.error(f"GNews 拉取失敗: {e}")
        return [], 0

# ==================== UI ====================
st.set_page_config(page_title="全球新聞搜尋平台", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("🔧 Ver 6.9 - 90天前強制顯示所有 Gnews + 近期放鬆篩選")

api_key = st.text_input("GNews API Key", type="password", help="輸入你的 GNews Essential Plan API Key")

region_options = ["1. 香港媒體（優先白名單）", "2. 台灣/世界華文媒體", "3. 英文全球媒體", "4. 中國大陸媒體（簡體中文）"]
region = st.radio("選擇主要搜尋區域", region_options, horizontal=True)

use_hybrid = st.checkbox("✅ 啟用合併搜尋測試模式（90 天分界測試）", value=False)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超、衞志樑、Trump、特朗普")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2:
    end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query:
        st.warning("請輸入關鍵字")
        st.stop()

    if "中國大陸" in region:
        white_list, gl, hl, ceid, g_lang, g_country = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region:
        white_list, gl, hl, ceid, g_lang, g_country = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif "香港" in region:
        white_list, gl, hl, ceid, g_lang, g_country = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else:
        white_list, gl, hl, ceid, g_lang, g_country = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("正在搜尋..."):
        all_results = []
        google_raw, gnews_raw, gnews_total = 0, 0, 0
        is_hybrid_mode = use_hybrid
        is_old_news = (end_date - start_date).days > 90

        if is_old_news:
            gnews_articles, gnews_total = fetch_gnews(query, start_date, end_date, g_lang, g_country, api_key)
            gnews_raw = len(gnews_articles)
            all_results.extend(gnews_articles)

            batch_size = 8
            for i in range(0, len(white_list), batch_size):
                batch = list(white_list)[i:i+batch_size]
                url = build_url(query, gl, hl, ceid, start_date, end_date, batch)
                batch_results = fetch_google_news(url)
                google_raw += len(batch_results)
                all_results.extend(batch_results)
        else:
            batch_size = 8
            for i in range(0, len(white_list), batch_size):
                batch = list(white_list)[i:i+batch_size]
                url = build_url(query, gl, hl, ceid, start_date, end_date, batch)
                batch_results = fetch_google_news(url)
                google_raw += len(batch_results)
                all_results.extend(batch_results)

            if "香港媒體" in region or "英文全球" in region:
                full_url = build_url(query, gl, hl, ceid, start_date, end_date)
                supplement = fetch_google_news(full_url)
                google_raw += len(supplement)
                all_results.extend(supplement)

            if is_hybrid_mode:
                gnews_articles, gnews_total = fetch_gnews(query, start_date, end_date, g_lang, g_country, api_key)
                gnews_raw = len(gnews_articles)
                seen = {item.get("link") for item in all_results if item.get("link")}
                for article in gnews_articles:
                    if article.get("link") not in seen:
                        all_results.append(article)

        if not is_old_news:
            unique_results = filter_by_date(all_results, start_date, end_date)
            unique_results = [item for item in unique_results if is_relevant(item.get("title", ""), item.get("summary", ""), query)]
        else:
            seen = set()
            unique_results = []
            for item in all_results:
                link = item.get("link", "")
                if link and link not in seen:
                    seen.add(link)
                    unique_results.append(item)

        for item in unique_results:
            clean_title, source_from_title = clean_title_and_source(item.get("title", ""))
            item["title"] = clean_title
            base_source = source_from_title or get_domain(item.get("link", ""))
            item["source"] = f"{base_source} (GNews)" if item.get("source_type") == "GNews" else f"{base_source} (Google)"
            try:
                if isinstance(item.get("published"), str):
                    dt = datetime.fromisoformat(item["published"].replace("Z", "+00:00"))
                else:
                    dt = datetime(*item["published"][:6])
                item["published_hkt"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")
            except:
                item["published_hkt"] = "未知時間"

        unique_results.sort(key=lambda x: x.get("published", ""), reverse=True)
        st.success(f"找到 {len(unique_results)} 則相關新聞 | {'合併搜尋模式' if is_hybrid_mode else '標準模式'}")

        for news in unique_results:
            st.markdown(f"### [{news.get('title', '無標題')}]({news.get('link', '#')})")
            st.caption(f"來源：{news.get('source', '未知')} | {news.get('published_hkt', '未知時間')}")
            st.write(news.get("summary", ""))
            st.divider()

        st.subheader("🔍 詳細搜尋診斷面板")
        st.write("### Google RSS")
        st.write(f"Raw 抓取總數: **{google_raw}** 則")
        st.write("### GNews")
        st.write(f"Raw 返回總數: **{gnews_raw}** 則")
        st.write(f"API totalArticles: **{gnews_total}**")
        st.write("### 最終結果")
        st.write(f"顯示數量: **{len(unique_results)}**")


