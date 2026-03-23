# ====================
# Code Version: Ver 4.0 - Google News RSS + 白名單優先 + 全網補漏
# 香港模式：先 30+ HK 白名單 → 再 gl=HK 全網補漏
# 大中華模式：先 40+ World 白名單 → 再 gl=TW 全網補漏
# 去重 + 日期預設 7 天 + HKT 顯示
# ====================

import streamlit as st
import feedparser
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 你之前定好的白名單 (直接用 keys) ====================
HK_WHITE_LIST = [
    "rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com",
    "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com",
    "hongkongfp.com", "skypost.hk", "thechasernews.co.uk", "pulsehknews.com", "thecollectivehk.com",
    "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk",
    "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com",
    "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "stepaper.stheadline.com",
    "eastweek.stheadline.com", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"
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

def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        articles = []
        for entry in feed.entries:
            link = entry.get('link', '')
            if link:
                pub = entry.get('published_parsed')
                articles.append({
                    "title": entry.get('title', '無標題'),
                    "link": link,
                    "source": get_domain(link),
                    "summary": entry.get('summary', ''),
                    "published": pub
                })
        return articles
    except:
        return []

def build_url(query, gl, hl, ceid, start_date=None, end_date=None, sites=None):
    q = query.replace(" ", "+")
    if sites:
        site_str = " OR ".join(f"site:{s}" for s in sites)
        q = f"({q}) ({site_str})"
    
    date_str = ""
    if start_date:
        date_str += f" after:{start_date.strftime('%Y-%m-%d')}"
    if end_date:
        date_str += f" before:{end_date.strftime('%Y-%m-%d')}"
    
    return f"https://news.google.com/rss/search?q={q}{date_str}&hl={hl}&gl={gl}&ceid={ceid}"

# ==================== UI ====================
st.set_page_config(page_title="全球公民新聞搜尋平台 - Ver 4.0", layout="wide")
st.title("🌐 全球公民新聞搜尋平台（Ver 4.0）")

region = st.radio("選擇搜尋區域", ["1. 香港媒體（優先白名單）", "2. 中國/台灣/世界華文媒體"], horizontal=True)
query = st.text_input("輸入關鍵字（例如：伊朗、樓市、國安法）")

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

    with st.spinner("正在搜尋...（白名單優先）"):
        # 1. 先跑白名單（精準）
        white_url = build_url(query, gl, hl, ceid, start_date, end_date, white_list)
        white_results = fetch_google_news(white_url)
        
        # 2. 再跑全網補漏
        full_url = build_url(query, gl, hl, ceid, start_date, end_date)  # 無 site:
        full_results = fetch_google_news(full_url)
        
        # 去重
        seen = {item["link"] for item in white_results}
        supplement = [item for item in full_results if item["link"] not in seen]
        
        all_results = white_results + supplement
        
        # 轉 HKT + 排序
        for item in all_results:
            if item["published"]:
                dt = datetime(*item["published"][:6])
                item["published_hkt"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")
            else:
                item["published_hkt"] = "未知時間"
        
        all_results.sort(key=lambda x: x.get("published", (0,)), reverse=True)

        st.success(f"找到 {len(all_results)} 筆新聞（白名單優先）")
        
        for news in all_results:
            st.markdown(f"### {news['title']}")
            st.caption(f"來源：{news['source']} | {news['published_hkt']}")
            st.write(news['summary'][:300] + "..." if len(news['summary']) > 300 else news['summary'])
            st.markdown(f"[閱讀全文]({news['link']})")
            st.divider()

