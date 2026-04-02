import streamlit as st
import feedparser
import requests
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, parse_qs
import re

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}

TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}

MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}

ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# ==================== 譯名自動擴展 ====================
def expand_query_for_region(query: str, region: str) -> str:
    q = query.strip()
    if "台灣/世界華文" in region:
        if "特朗普" in q and "川普" not in q:
            return f"({q} OR 川普)"
        if "川普" in q and "特朗普" not in q:
            return f"({q} OR 特朗普)"
    elif "香港" in region:
        if "川普" in q and "特朗普" not in q:
            return f"({q} OR 特朗普)"
    return q

# ==================== 加強清理 Google 長連結 ====================
def clean_google_link(link):
    try:
        if "news.google.com" in link:
            if "/rss/articles/" in link or "url=" in link:
                parsed = urlparse(link)
                query_params = parse_qs(parsed.query)
                real_url = query_params.get("url", [link])[0]
                return real_url
        return link
    except:
        return link

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
    return q_lower in title.lower() or q_lower in (summary or "").lower()

def filter_by_date(articles, start_date, end_date):
    if not start_date or not end_date:
        return articles
    filtered = []
    for item in articles:
        if item.get("published"):
            try:
                if isinstance(item["published"], str):
                    dt = datetime.fromisoformat(item["published"].replace("Z", "+00:00"))
                else:
                    dt = datetime(*item["published"][:6])
                if start_date <= dt.date() <= end_date:
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
                clean_link = clean_google_link(link)
                articles.append({
                    "title": entry.get('title', '無標題'),
                    "link": clean_link,
                    "summary": clean_summary(entry.get('summary', entry.get('description', ''))),
                    "published": entry.get('published_parsed')
                })
        return articles
    except Exception as e:
        st.error(f"Google News 拉取失敗: {e}")
        return []

def build_url(query, gl, hl, ceid, start_date=None, end_date=None, sites=None):
    q_clean = query.strip()
    q = f"%22{q_clean.replace(' ', '+')}%22" if q_clean else ""
    if sites:
        site_str = "+OR+".join(f"site:{s}" for s in sites)
        q = f"({q})+({site_str})" if q else site_str
    date_parts = []
    if start_date:
        date_parts.append(f"after:{start_date.strftime('%Y-%m-%d')}")
    if end_date:
        date_parts.append(f"before:{end_date.strftime('%Y-%m-%d')}")
    if start_date and end_date and (end_date - start_date).days <= 60:
        date_parts.append(f"when:{(end_date - start_date).days + 2}d")
    date_str = "+" + "+".join(date_parts) if date_parts else ""
    return f"https://news.google.com/rss/search?q={q}{date_str}&hl={hl}&gl={gl}&ceid={ceid}"

GNEWS_API_URL = "https://gnews.io/api/v4/search"

def fetch_gnews(query, start_date, end_date, lang, country, api_key, max_articles=60):
    try:
        params = {
            "token": api_key,
            "q": query,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "lang": lang,
            "country": country,
            "max": max_articles,
            "sortby": "publishedAt",
            "in": "title,description"
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
                "source": article.get("source", {}).get("name", "GNews")
            })
        return articles
    except Exception as e:
        st.error(f"GNews 拉取失敗: {e}")
        return []

# ==================== UI ====================
st.set_page_config(page_title="全球新聞搜尋平台", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("🔧 Ver 5.8 - 合併搜尋測試模式")

api_key = st.text_input("GNews API Key", type="password", help="輸入你的 GNews Essential Plan API Key")

region_options = [
    "1. 香港媒體（優先白名單）",
    "2. 台灣/世界華文媒體",
    "3. 英文全球媒體",
    "4. 中國大陸媒體（簡體中文）",
    "5. 合併搜尋（Google + GNews） - **測試模式**"
]
region = st.radio("選擇搜尋區域", region_options, horizontal=True)

query = st.text_input("輸入關鍵字", placeholder="例如：Trump、特朗普、川普、李家超")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2:
    end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query:
        st.warning("請輸入關鍵字")
        st.stop()

    is_hybrid = "合併搜尋" in region
    is_hk = "香港" in region
    is_mainland = "中國大陸" in region
    is_taiwan_world = "台灣/世界華文" in region
    is_english_global = "英文全球" in region

    if is_hybrid and not (is_hk or is_mainland or is_taiwan_world or is_english_global):
        st.error("⚠️ 使用合併搜尋時，請同時選擇一個地區模式（1-4）")
        st.stop()

    # 決定白名單與參數
    if is_mainland:
        white_list = MAINLAND_CHINA_WHITE_LIST
        gl, hl, ceid = "CN", "zh-CN", "CN:zh-Hans"
        gnews_lang, gnews_country = "zh", "cn"
    elif is_english_global:
        white_list = ENGLISH_GLOBAL_LIST
        gl, hl, ceid = "US", "en", "US:en"
        gnews_lang, gnews_country = "en", "us"
    elif is_hk:
        white_list = HK_WHITE_LIST
        gl, hl, ceid = "HK", "zh-HK", "HK:zh-Hant"
        gnews_lang, gnews_country = "zh", "hk"
    else:  # 台灣/世界華文
        white_list = TAIWAN_WORLD_WHITE_LIST
        gl, hl, ceid = "TW", "zh-TW", "TW:zh-Hant"
        gnews_lang, gnews_country = "zh", "tw"

    expanded_query = expand_query_for_region(query, region)

    with st.spinner("正在執行合併搜尋..."):
        all_results = []
        google_count = 0
        gnews_count = 0

        days_diff = (end_date - start_date).days

        # ==================== Google RSS ====================
        if white_list:
            batch_size = 4 if days_diff > 60 else 6   # 超過60天用少量 Google
            white_results = []
            for i in range(0, len(white_list), batch_size):
                batch = list(white_list)[i:i+batch_size]
                url = build_url(expanded_query, gl, hl, ceid, start_date, end_date, batch)
                batch_results = fetch_google_news(url)
                white_results.extend(batch_results)

            all_results.extend(white_results)
            google_count += len(white_results)

            # 超過60天只補少量 supplement
            if days_diff <= 60 or (days_diff > 60 and len(white_results) < 10):  # 若 Google 太少才補
                full_url = build_url(expanded_query, gl, hl, ceid, start_date, end_date)
                supplement = fetch_google_news(full_url)
                all_results.extend(supplement)
                google_count += len(supplement)

        # ==================== GNews 強力補漏 ====================
        gnews_results = fetch_gnews(expanded_query, start_date, end_date, gnews_lang, gnews_country, api_key, max_articles=60)
        all_results.extend(gnews_results)
        gnews_count += len(gnews_results)

        # ==================== 去重 + 過濾 ====================
        seen_links = set()
        unique_results = []
        for item in all_results:
            link = item.get("link", "")
            if link and link not in seen_links:
                seen_links.add(link)
                unique_results.append(item)

        unique_results = filter_by_date(unique_results, start_date, end_date)
        unique_results = [item for item in unique_results if is_relevant(item.get("title", ""), item.get("summary", ""), query)]

        # 最終處理
        for item in unique_results:
            item["link"] = clean_google_link(item.get("link", ""))
            clean_title, source_from_title = clean_title_and_source(item.get("title", ""))
            item["title"] = clean_title
            item["source"] = source_from_title or item.get("source", get_domain(item.get("link", "")))

            try:
                if isinstance(item["published"], str):
                    dt = datetime.fromisoformat(item["published"].replace("Z", "+00:00"))
                else:
                    dt = datetime(*item["published"][:6])
                item["published_hkt"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")
            except:
                item["published_hkt"] = "未知時間"

        unique_results.sort(key=lambda x: x.get("published", ""), reverse=True)

        # 顯示測試資訊
        mode_text = f"合併搜尋測試模式（{'≤60天 Google優先' if days_diff <= 60 else '>60天 GNews優先'}）"
        st.success(f"找到 {len(unique_results)} 則新聞 | {mode_text} | Google: {google_count} | GNews: {gnews_count}")

        for news in unique_results:
            title = news.get('title', '無標題')
            link = news.get('link', '#')
            st.markdown(f"### [{title}]({link})")
            st.caption(f"來源：{news.get('source', '未知')} | {news.get('published_hkt', '未知時間')}")
            st.write(news.get("summary", ""))
            st.divider()