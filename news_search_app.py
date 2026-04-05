import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單與配置 (保持您的專業清單) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
# ... (其他白名單維持您的定義)
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# ==================== 工具函數 ====================
def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "")
    except: return "未知來源"

def clean_summary(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    return text.replace('&nbsp;', ' ').strip()

def is_relevant_strict(title, summary, query):
    """核心白名單使用：嚴格檢查標題與摘要"""
    if not query: return True
    q = query.lower().strip()
    return q in title.lower() or q in (summary or "").lower()

def is_relevant_loose(title, query):
    """補充層使用：標題命中即可"""
    if not query: return True
    return query.lower().strip() in title.lower()

# ==================== API 邏輯 ====================
def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        return [{
            "title": e.get('title', '無標題'),
            "link": e.get('link', ''),
            "summary": clean_summary(e.get('summary', e.get('description', ''))),
            "published": e.get('published_parsed'),
            "source_type": "Google"
        } for e in feed.entries if e.get('link')]
    except: return []

def fetch_gnews(query, start_date, end_date, lang, country, api_key):
    try:
        # Ver 6.3 修正：中英雙語強化 (針對知名人物)
        search_q = query
        if "李家超" in query: search_q = '李家超 OR "John Lee"'
        elif "特朗普" in query or "川普" in query: search_q = 'Trump OR 特朗普 OR 川普'
        
        params = {
            "token": api_key, "q": search_q, "lang": lang, "country": country,
            "from": start_date.strftime("%Y-%m-%dT00:00:00Z"), # Ver 6.3 修正時間格式
            "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "max": 100, "sortby": "publishedAt"
        }
        resp = requests.get("https://gnews.io/api/v4/search", params=params, timeout=20)
        data = resp.json()
        articles = []
        for a in data.get("articles", []):
            articles.append({
                "title": a.get("title", "無標題"),
                "link": a.get("url", ""),
                "summary": a.get("description", ""),
                "published": a.get("publishedAt"),
                "source_type": "GNews"
            })
        return articles, data.get("totalArticles", 0)
    except: return [], 0

# ==================== UI 與 核心邏輯 ====================
st.set_page_config(page_title="全球新聞搜尋平台 Ver 6.3", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("Ver 6.3 - 專業新聞工作者版 (白名單優先 + 智能補充)")

api_key = st.text_input("GNews API Key", type="password")
region = st.radio("選擇主要搜尋區域", ["1. 香港媒體", "2. 台灣/世界華文", "3. 英文全球", "4. 中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()

    # 區域映射
    if "中國大陸" in region: white_list, gl, hl, ceid, g_l, g_c = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region: white_list, gl, hl, ceid, g_l, g_c = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif "香港" in region: white_list, gl, hl, ceid, g_l, g_c = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else: white_list, gl, hl, ceid, g_l, g_c = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("深度搜尋中..."):
        # 1. Google RSS 雙重抓取 (相關性 + 時間)
        def build_google_url(q, g, h, c, sd, ed, sites=None, sort=""):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            date_str = f"+after:{sd}+before:{ed}"
            return f"https://news.google.com/rss/search?q={quote(q)}{site_str}{date_str}&hl={h}&gl={g}&ceid={c}{sort}"

        raw_google = []
        # 抓取核心白名單 (Scoring=r 相關性優先)
        batch_size = 10
        for i in range(0, len(white_list), batch_size):
            batch = list(white_list)[i:i+batch_size]
            raw_google.extend(fetch_google_news(build_google_url(query, gl, hl, ceid, start_date, end_date, batch)))
        
        # 抓取補充包 (不限 Site)
        supplement_raw = fetch_google_news(build_google_url(query, gl, hl, ceid, start_date, end_date))
        
        # 2. GNews 抓取
        gn_articles, gn_total = fetch_gnews(query, start_date, end_date, g_l, g_c, api_key)

        # 3. 處理與分類 (漏斗邏輯)
        final_core = []
        final_supplement = []
        seen_links = set()

        # A. 處理核心白名單 (Google + Gnews 中符合白名單的)
        all_potential_core = raw_google + [a for a in gn_articles if get_domain(a['link']) in white_list]
        for item in all_potential_core:
            if item['link'] not in seen_links:
                if is_relevant_strict(item['title'], item['summary'], query):
                    final_core.append(item)
                    seen_links.add(item['link'])

        # B. 處理補充層 (非白名單，但標題命中的)
        potential_supp = supplement_raw + [a for a in gn_articles if get_domain(a['link']) not in white_list]
        for item in potential_supp:
            if item['link'] not in seen_links:
                if is_relevant_loose(item['title'], query):
                    final_supplement.append(item)
                    seen_links.add(item['link'])

        # C. 動態配額限制 (Supplement 不超過總數 35%)
        max_supp_count = int(len(final_core) * 0.55) # 約佔總比例 35%
        final_supplement = final_supplement[:max_supp_count] if len(final_core) > 5 else final_supplement[:15]

        # 4. 排序與顯示
        unique_results = final_core + final_supplement
        unique_results.sort(key=lambda x: str(x.get("published", "")), reverse=True)

        st.success(f"找到 {len(unique_results)} 則新聞 (核心: {len(final_core)} | 補充: {len(final_supplement)})")
        
        for news in unique_results:
            domain = get_domain(news['link'])
            is_white = "✅" if domain in white_list else "🌐"
            st.markdown(f"### {is_white} [{news['title']}]({news['link']})")
            st.caption(f"來源：{domain} ({news['source_type']})")
            st.write(news.get("summary", ""))
            st.divider()

        # Ver 6.3 漏斗診斷面板
        with st.expander("🔍 Ver 6.3 搜尋漏斗診斷"):
            c1, c2, c3 = st.columns(3)
            c1.metric("原始抓取 (Google)", len(raw_google) + len(supplement_raw))
            c2.metric("GNews API 總計", gn_total)
            c3.metric("最終顯示", len(unique_results))
            st.write(f"白名單命中: {len(final_core)} | 寬鬆補充: {len(final_supplement)}")
            if gn_total == 0: st.error("警告：GNews 回傳為 0，請檢查 Key 狀態或日期格式。")