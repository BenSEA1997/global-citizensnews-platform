# ====================
# Code Version: Ver 4.5 - 精確匹配 + 語言智能切換 + 減少側欄干擾
# ====================

import streamlit as st
import feedparser
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse

HKT = pytz.timezone('Asia/Hong_Kong')

# 白名單
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}

WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}

def get_domain(link):
    try:
        return urlparse(link).netloc.replace("www.", "")
    except:
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
st.set_page_config(page_title="全球公民新聞搜尋平台 - Ver 4.5", layout="wide")
st.title("🌐 全球公民新聞搜尋平台（Ver 4.5）")

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

    # 如果是 World Engine 且關鍵字是英文，強制切英文模式
    if not is_hk and any(c.isascii() and c.isalpha() for c in query):
        hl = "en"
        gl = "US"
        ceid = "US:en"

    with st.spinner("正在搜尋..."):
        # Batch 白名單搜尋
        batch_size = 8
        white_results = []
        for i in range(0, len(white_list), batch_size):
            batch = list(white_list)[i:i+batch_size]
            url = build_url(query, gl, hl, ceid, start_date, end_date, batch)
            white_results.extend(fetch_google_news(url))

        # 全網補漏
        full_url = build_url(query, gl, hl, ceid, start_date, end_date)
        supplement = fetch_google_news(full_url)

        # 去重
        seen_links = {item["link"] for item in white_results}
        supplement = [item for item in supplement if item["link"] not in seen_links]

        all_results = white_results + supplement

        # 處理顯示
        for item in all_results:
            item["title"] = clean_title(item["title"])
            item["source"] = get_domain(item["link"])
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