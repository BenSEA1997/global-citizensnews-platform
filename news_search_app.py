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

# ==================== 工具函數 ====================
def expand_query_for_region(query: str, region: str) -> str:
    q = query.strip()
    if "台灣/世界華文" in region and "特朗普" in q:
        return f"({q} OR 川普)"
    if "香港" in region and "川普" in q:
        return f"({q} OR 特朗普)"
    return q

def clean_google_link(link):
    try:
        if "news.google.com" in link:
            if "/rss/articles/" in link or "url=" in link:
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
    if '<a href' in text:
        text = text.split('<a href', 1)[0]
    if '<font color' in text:
        text = text.split('<font color', 1)[0]
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&nbsp;', ' ').strip()
    return text

def is_relevant(title: str, summary: str, query: str, strict_mode: bool = True) -> bool:
    if not query or not title:
        return True
    q_lower = query.lower().strip()
    title_lower = title.lower()
    summary_lower = (summary or "").lower()
    if q_lower in title_lower:
        return True
    if not strict_mode and q_lower in summary_lower:
        return True
    if not strict_mode:
        query_words = [word for word in q_lower.split() if len(word) > 1]
        if query_words and all(any(w in title_lower or w in summary_lower for w in query_words)):
            return True
    return False

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

def is_in_whitelist(link, whitelist):
    if not link or not whitelist:
        return True
    domain = get_domain(link)
    return any(domain.endswith(site) or site in domain for site in whitelist)

def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        return feed.entries
    except Exception as e:
        st.error(f"Google News 拉取失敗: {e}")
        return []

def build_url(query, gl, hl, ceid, start_date=None, end_date=None, sites=None):
    q_clean = query.strip()
    q = q_clean.replace(" ", "+") if q_clean else ""   # 移除強制 exact phrase
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
        return data.get("articles", []), data.get("totalArticles", 0)
    except Exception as e:
        st.error(f"GNews 拉取失敗: {e}")
        return [], 0

# ==================== UI ====================
st.set_page_config(page_title="全球新聞搜尋平台", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("🔧 Ver 6.0 - 加入完整搜尋診斷面板 + 修正大部分 0 結果問題")

api_key = st.text_input("GNews API Key", type="password", help="輸入你的 GNews Essential Plan API Key")

region_options = [
    "1. 香港媒體（優先白名單）",
    "2. 台灣/世界華文媒體",
    "3. 英文全球媒體",
    "4. 中國大陸媒體（簡體中文）"
]
region = st.radio("選擇主要搜尋區域", region_options, horizontal=True)

use_hybrid = st.checkbox("✅ 啟用合併搜尋測試模式（Google + GNews，測試舊新聞補充）", value=False)

query = st.text_input("輸入關鍵字", placeholder="例如：衞志樑、李家超、Trump、特朗普")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2:
    end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query:
        st.warning("請輸入關鍵字")
        st.stop()

    is_hk = "香港" in region
    is_mainland = "中國大陸" in region
    is_taiwan_world = "台灣/世界華文" in region
    is_english_global = "英文全球" in region

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
    else:
        white_list = TAIWAN_WORLD_WHITE_LIST
        gl, hl, ceid = "TW", "zh-TW", "TW:zh-Hant"
        gnews_lang, gnews_country = "zh", "tw"

    expanded_query = expand_query_for_region(query, region)
    days_diff = (end_date - start_date).days
    is_hybrid_mode = use_hybrid

    with st.spinner("正在搜尋並收集診斷數據..."):
        all_results = []
        google_raw_count = 0
        google_whitelist_count = 0
        gnews_raw_count = 0
        gnews_total = 0
        google_urls = []

        # Google RSS
        if white_list:
            batch_size = 4 if (is_hybrid_mode and days_diff > 60) else 6
            for i in range(0, len(white_list), batch_size):
                batch = list(white_list)[i:i+batch_size]
                url = build_url(expanded_query, gl, hl, ceid, start_date, end_date, batch)
                google_urls.append(url)
                entries = fetch_google_news(url)
                google_raw_count += len(entries)
                batch_results = []
                for entry in entries:
                    link = entry.get('link', '')
                    if link:
                        clean_link = clean_google_link(link)
                        batch_results.append({
                            "title": entry.get('title', '無標題'),
                            "link": clean_link,
                            "summary": clean_summary(entry.get('summary', entry.get('description', ''))),
                            "published": entry.get('published_parsed')
                        })
                batch_results = [item for item in batch_results if is_in_whitelist(item.get("link", ""), white_list)]
                google_whitelist_count += len(batch_results)
                all_results.extend(batch_results)

        # GNews
        if is_hybrid_mode:
            gnews_articles, gnews_total = fetch_gnews(expanded_query, start_date, end_date, gnews_lang, gnews_country, api_key)
            gnews_raw_count = len(gnews_articles)
            seen_links = {item.get("link") for item in all_results}
            gnews_results = []
            for article in gnews_articles:
                link = article.get("url", "")
                if link and link not in seen_links:
                    gnews_results.append({
                        "title": article.get("title", "無標題"),
                        "link": link,
                        "summary": article.get("description", ""),
                        "published": article.get("publishedAt"),
                        "source": article.get("source", {}).get("name", "GNews")
                    })
            all_results.extend(gnews_results)

        # 最終過濾
        seen_links = set()
        unique_results = [item for item in all_results if item.get("link") and item["link"] not in seen_links]

        unique_results = filter_by_date(unique_results, start_date, end_date)

        strict_results = [item for item in unique_results if is_relevant(item.get("title", ""), item.get("summary", ""), query, strict_mode=True)]
        final_results = strict_results
        if len(strict_results) < 12:
            final_results = [item for item in unique_results if is_relevant(item.get("title", ""), item.get("summary", ""), query, strict_mode=False)]

        # 顯示處理
        for item in final_results:
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

        final_results.sort(key=lambda x: x.get("published", ""), reverse=True)

        # 顯示結果
        mode = "合併搜尋測試模式" if is_hybrid_mode else "標準模式"
        st.success(f"找到 {len(final_results)} 則相關新聞 | {mode}")

        for news in final_results:
            title = news.get('title', '無標題')
            link = news.get('link', '#')
            st.markdown(f"### [{title}]({link})")
            st.caption(f"來源：{news.get('source', '未知')} | {news.get('published_hkt', '未知時間')}")
            st.write(news.get("summary", ""))
            st.divider()

        # ==================== 詳細診斷面板 ====================
        with st.expander("🔍 詳細搜尋診斷面板（點擊展開查看呼叫情況與 0 結果原因）", expanded=True):
            st.subheader("Google RSS 呼叫情況")
            st.write(f"Raw 抓取總數: **{google_raw_count}** 則")
            st.write(f"白名單過濾後: **{google_whitelist_count}** 則")
            if google_urls:
                st.write("最後一次呼叫的完整 URL（可直接複製到瀏覽器測試）:")
                st.code(google_urls[-1])

            st.subheader("GNews 呼叫情況")
            st.write(f"Raw 返回總數: **{gnews_raw_count}** 則")
            st.write(f"API totalArticles: **{gnews_total}**")

            st.subheader("過濾流程統計")
            st.write(f"合併後總文章: {len(all_results)}")
            st.write(f"去重 + 日期過濾後: {len(unique_results)}")
            st.write(f"嚴格相關性過濾後: {len(strict_results)}")
            st.write(f"**最終顯示數量: {len(final_results)}**")

            if len(final_results) == 0:
                st.error("🔴 目前為 0 結果，可能原因如下：")
                if google_raw_count == 0 and gnews_raw_count == 0:
                    st.write("• Google 和 GNews 都沒有抓到任何文章（最常見：query 建構問題）")
                elif google_whitelist_count == 0 and google_raw_count > 0:
                    st.write("• Google 有抓到文章，但全部被白名單過濾掉")
                elif len(strict_results) == 0:
                    st.write("• 文章被相關性過濾全部濾掉")
                st.info("建議：展開上方 URL 到瀏覽器查看 Google 是否真的有結果")
