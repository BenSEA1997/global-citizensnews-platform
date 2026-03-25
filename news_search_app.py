# ====================
# Code Version: Ver 4.3 - Batch site: + 白名單強制優先 + 乾淨顯示
# ====================

import streamlit as st
import feedparser
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單 ====================
HK_WHITE_LIST = [
    "rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com",
    "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com",
    "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com",
    "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk",
    "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com",
    "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc",
    "hkej.com", "mingpao.com", "etnet.com.hk"
]

WORLD_WHITE_LIST = [
    "straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com",
    "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com",
    "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr",
    "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw",
    "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw",
    "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn",
    "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn",
    "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"
]

def get_domain(link):
    try:
        return urlparse(link).netloc.replace("www.", "")
    except:
        return "未知來源"

def clean_summary(text):
    if not text:
        return ""
    # 清除 Google 包裝的 HTML 標籤
    if '<a href' in text:
        text = text.split('<a href', 1)[0]
    if '<font color' in text:
        text = text.split('<font color', 1)[0]
    text = text.replace('<', ' ').replace('>', ' ').replace('&nbsp;', ' ').strip()
    return text

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
                    "published": entry.get('published_parsed')
                })
        return articles
    except Exception as e:
        st.error(f"Google News 拉取失敗: {e}")
        return []

def build_batch_urls(query, sites, gl, hl, ceid, start_date=None, end_date=None, batch_size=10):
    """把白名單分成多批，每批最多 batch_size 個 site:"""
    urls = []
    for i in range(0, len(sites), batch_size):
        batch = sites[i:i+batch_size]
        site_str = "+OR+".join(f"site:{s}" for s in batch)
        q = f"{query.replace(' ', '+')}+({site_str})"
        
        date_parts = []
        if start_date:
            date_parts.append(f"after:{start_date.strftime('%Y-%m-%d')}")
        if end_date:
            date_parts.append(f"before:{end_date.strftime('%Y-%m-%d')}")
        date_str = "+" + "+".join(date_parts) if date_parts else ""
        
        url = f"https://news.google.com/rss/search?q={q}{date_str}&hl={hl}&gl={gl}&ceid={ceid}"
        urls.append(url)
    return urls

# ==================== UI ====================
st.set_page_config(page_title="全球公民新聞搜尋平台 - Ver 4.3", layout="wide")
st.title("🌐 全球公民新聞搜尋平台（Ver 4.3）")

region = st.radio("選擇搜尋區域", ["1. 香港媒體（優先白名單）", "2. 中國/台灣/世界華文媒體"], horizontal=True)
query = st.text_input("輸入關鍵字")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("開始日期", value=date.today() - timedelta(days=7))
with col2:
    end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query:
        st.warning("請輸入關鍵字")
        st.stop()

    is_hk = "香港" in region
    white_list = HK_WHITE_LIST if is_hk else WORLD_WHITE_LIST
    gl = "HK" if is_hk else "TW"
    hl = "zh-HK" if is_hk else "zh-TW"
    ceid = "HK:zh-Hant" if is_hk else "TW:zh-Hant"

    with st.spinner("正在搜尋...（白名單優先 + Batch site）"):
        # 1. Batch site: 搜白名單（分批，避免 URL 過長）
        batch_urls = build_batch_urls(query, white_list, gl, hl, ceid, start_date, end_date, batch_size=8)
        white_results = []
        for url in batch_urls:
            white_results.extend(fetch_google_news(url))

        # 2. 全網補漏
        full_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl={hl}&gl={gl}&ceid={ceid}"
        if start_date:
            full_url += f"+after:{start_date.strftime('%Y-%m-%d')}"
        if end_date:
            full_url += f"+before:{end_date.strftime('%Y-%m-%d')}"
        supplement = fetch_google_news(full_url)

        # 3. 去重 + 白名單優先
        seen_links = {item["link"] for item in white_results}
        supplement = [item for item in supplement if item["link"] not in seen_links]

        # 合併：白名單永遠置前
        all_results = white_results + supplement

        # 加上時間與乾淨來源
        for item in all_results:
            domain = get_domain(item["link"])
            item["source"] = domain  # 暫時用 domain，之後可再美化
            if item["published"]:
                dt = datetime(*item["published"][:6])
                item["published_hkt"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")
            else:
                item["published_hkt"] = "未知時間"

        all_results.sort(key=lambda x: x.get("published", (0,)), reverse=True)

        st.success(f"找到 {len(all_results)} 筆新聞（白名單優先）")

        for news in all_results:
            clean_title = news["title"].split(" - ")[0] if " - " in news["title"] else news["title"]
            st.markdown(f"### {clean_title}")
            st.caption(f"來源：{news['source']} | {news['published_hkt']}")
            st.write(news["summary"])
            st.markdown(f"[閱讀全文]({news['link']})")
            st.divider()