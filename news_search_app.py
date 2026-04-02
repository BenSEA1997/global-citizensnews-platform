import streamlit as st
import feedparser
import requests
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, parse_qs

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

# ==================== 加強清理 Google RSS 長連結 ====================
def clean_google_link(link):
    try:
        if not link:
            return link
        if "news.google.com" in link:
            # 處理新版 Google RSS /rss/articles/ 格式
            if "/rss/articles/" in link:
                # 嘗試從 URL 中提取真實連結（常見於新版 feed）
                if "url=" in link:
                    parsed = urlparse(link)
                    query_params = parse_qs(parsed.query)
                    real_url = query_params.get("url", [link])[0]
                    return real_url
                # 如果還是 Google 轉址，保留原始但標記（後續可再處理）
                return link
            # 舊版清理
            if "url=" in link:
                parsed = urlparse(link)
                query_params = parse_qs(parsed.query)
                return query_params.get("url", [link])[0]
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
    return text.replace('<', ' ').replace('>', ' ').replace('&nbsp;', ' ').strip()

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
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0 (compatible; NewsApp/1.0)'})
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

    if sites and len(sites) > 0:
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

def fetch_gnews(query, start_date, end_date, lang, country, api_key, max_articles=50):
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
        response = requests.get(GNEWS_API_URL, params=params, timeout=20)
        data = response.json()
        if data.get("totalArticles", 0) == 0:
            st.info(f"GNews 此次沒有結果（總數: 0）")
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
st.caption("🔧 Ver 5.6 - 加強 Google RSS 長連結清理 + 修復合併模式 0 結果")

api_key = st.text_input("GNews API Key", type="password", help="輸入你的 GNews Essential Plan API Key")

region_options = [
    "1. 香港媒體（優先白名單）",
    "2. 台灣/世界華文媒體",
    "3. 英文全球媒體",
    "4. 中國大陸媒體（簡體中文）",
    "5. Google + GNews 合併搜尋（智能日期切換）"
]
region = st.radio("選擇搜尋區域", region_options, horizontal=True)

query = st.text_input("輸入關鍵字", placeholder="例如：Trump、特朗普、川普、油價")

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

    # 決定白名單與 Google 參數
    if is_mainland:
        white_list = MAINLAND_CHINA_WHITE_LIST
        gl, hl, ceid = "CN", "zh-CN", "CN:zh-Hans"
    elif is_english_global:
        white_list = ENGLISH_GLOBAL_LIST
        gl, hl, ceid = "US", "en", "US:en"
    elif is_hk:
        white_list = HK_WHITE_LIST
        gl, hl, ceid = "HK", "zh-HK", "HK:zh-Hant"
    else:  # 台灣/世界華文 或 合併模式預設
        white_list = TAIWAN_WORLD_WHITE_LIST
        gl, hl, ceid = "TW", "zh-TW", "TW:zh-Hant"

    expanded_query = expand_query_for_region(query, region)

    with st.spinner("正在搜尋並過濾..."):
        all_results = []

        # Google RSS（白名單 + 補充）
        if white_list:
            batch_size = 4   # 進一步縮小，避免 query 過長被截斷
            white_results = []
            for i in range(0, len(white_list), batch_size):
                batch = list(white_list)[i:i+batch_size]
                url = build_url(expanded_query, gl, hl, ceid, start_date, end_date, batch)
                batch_results = fetch_google_news(url)
                white_results.extend(batch_results)

            all_results.extend(white_results)

            # 合併模式下補充一次全域搜尋（但仍過濾地區）
            if is_hybrid:
                full_url = build_url(expanded_query, gl, hl, ceid, start_date, end_date)
                supplement = fetch_google_news(full_url)
                all_results.extend(supplement)

        # GNews（合併模式或超過60天）
        if is_hybrid or (end_date - start_date).days > 60:
            if is_mainland:
                gnews_lang, gnews_country = "zh", "cn"
            elif is_hk:
                gnews_lang, gnews_country = "zh", "hk"
            elif is_taiwan_world:
                gnews_lang, gnews_country = "zh", "tw"
            elif is_english_global:
                gnews_lang, gnews_country = "en", "us"
            else:
                gnews_lang, gnews_country = "zh", "hk"

            gnews_results = fetch_gnews(expanded_query, start_date, end_date, gnews_lang, gnews_country, api_key)
            all_results.extend(gnews_results)

        # 去重 + 過濾
        seen_links = set()
        unique_results = []
        for item in all_results:
            link = item.get("link", "")
            if link and link not in seen_links:
                seen_links.add(link)
                unique_results.append(item)

        unique_results = filter_by_date(unique_results, start_date, end_date)
        unique_results = [item for item in unique_results if is_relevant(item.get("title", ""), item.get("summary", ""), query)]

        # 最終清理連結 + 顯示處理
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

        st.success(f"找到 {len(unique_results)} 則相關新聞")

        for news in unique_results:
            title = news.get('title', '無標題')
            link = news.get('link', '#')
            # 乾淨的標題可點擊連結（不再有任何多餘文字）
            st.markdown(f"### [{title}]({link})")
            st.caption(f"來源：{news.get('source', '未知')} | {news.get('published_hkt', '未知時間')}")
            st.write(news.get("summary", ""))
            st.divider()