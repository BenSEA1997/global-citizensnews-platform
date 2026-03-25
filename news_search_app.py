# ====================
# Code Version: Ver 4.8 - 來源顯示最終加強版
# ====================

import streamlit as st
import feedparser
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, parse_qs, unquote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}

WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}

# 媒體名稱美化映射
SOURCE_MAP = {
    "mingpao.com": "明報",
    "hk01.com": "香港01",
    "scmp.com": "南華早報",
    "hket.com": "香港經濟日報",
    "hkej.com": "信報",
    "orientaldaily.on.cc": "東方日報",
    "stheadline.com": "星島日報",
    "rthk.hk": "香港電台",
    "news.gov.hk": "香港政府新聞網",
    "bbc.com": "BBC",
    "reuters.com": "路透社",
    "nytimes.com": "紐約時報",
    "ftchinese.com": "金融時報中文網",
    "aljazeera.com": "半島電視台",
}

def get_clean_source(title, link):
    # 1. 從標題尾巴提取（最常見有效方式）
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        if len(parts) == 2:
            source = parts[1].strip()
            if len(source) >= 2 and len(source) <= 25:
                return SOURCE_MAP.get(source.lower(), source)

    # 2. 從 Google 中轉連結解析真實來源
    try:
        if "news.google.com" in link:
            parsed = urlparse(link)
            params = parse_qs(parsed.query)
            if 'url' in params:
                real_url = unquote(params['url'][0])
                domain = urlparse(real_url).netloc.replace("www.", "")
                if domain:
                    return SOURCE_MAP.get(domain, domain)
    except:
        pass

    # 3. 最後 fallback 到 domain
    try:
        domain = urlparse(link).netloc.replace("www.", "").replace("news.google.com", "")
        if domain:
            return SOURCE_MAP.get(domain, domain)
    except:
        pass

    return "未知來源"

def clean_title(title):
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title.strip()

def clean_summary(text):
    if not text:
        return ""
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

def build_url(query, gl, hl, ceid, start_date=None, end_date=None, sites=None):
    q = query.replace(" ", "+")
    if sites:
        site_str = "+OR+".join(f"site:{s}" for s in sites)
        q = f"({q})+({site_str})"
    
    date_parts = []
    if start_date:
        date_parts.append(f"after:{start_date.strftime('%Y-%m-%d')}")
    if end_date:
        date_parts.append(f"before:{end_date.strftime('%Y-%m-%d')}")
    date_str = "+" + "+".join(date_parts) if date_parts else ""
    
    return f"https://news.google.com/rss/search?q={q}{date_str}&hl={hl}&gl={gl}&ceid={ceid}"

# ==================== UI ====================
st.set_page_config(page_title="全球公民新聞搜尋平台 - Ver 4.8", layout="wide")
st.title("🌐 全球公民新聞搜尋平台（Ver 4.8）")

region = st.radio("選擇搜尋區域", ["1. 香港媒體（優先白名單）", "2. 中國/台灣/世界華文媒體"], horizontal=True)
query = st.text_input("輸入關鍵字（英文可用 \"精確短語\" ）")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("開始日期（預設搜尋3天）", value=date.today() - timedelta(days=3))
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

    if not is_hk and any(c.isascii() and c.isalpha() for c in query):
        hl = "en"
        gl = "US"
        ceid = "US:en"

    with st.spinner("正在搜尋..."):
        batch_size = 8
        white_results = []
        for i in range(0, len(white_list), batch_size):
            batch = list(white_list)[i:i+batch_size]
            url = build_url(query, gl, hl, ceid, start_date, end_date, batch)
            white_results.extend(fetch_google_news(url))

        full_url = build_url(query, gl, hl, ceid, start_date, end_date)
        supplement = fetch_google_news(full_url)

        seen_links = {item["link"] for item in white_results}
        supplement = [item for item in supplement if item["link"] not in seen_links]

        all_results = white_results + supplement

        for item in all_results:
            item["title"] = clean_title(item["title"])
            item["source"] = get_clean_source(item["title"], item["link"])
            if item.get("published"):
                dt = datetime(*item["published"][:6])
                item["published_hkt"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")
            else:
                item["published_hkt"] = "未知時間"

        all_results.sort(key=lambda x: x.get("published", (0,)), reverse=True)

        st.success(f"找到 {len(all_results)} 則新聞")

        for news in all_results:
            st.markdown(f"### {news['title']}")
            st.caption(f"來源：{news['source']} | {news['published_hkt']}")
            st.write(news.get("summary", ""))
            st.markdown(f"[閱讀全文]({news['link']})")
            st.divider()