import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 媒體白名單 (嚴格對齊) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# ==================== 2. 工具函數 ====================
def get_domain_from_url(url):
    """修正白名單判定：從原始網址或來源描述中提取"""
    try:
        # 如果是 Google RSS 的跳轉連結，這一步可能不準確，需要配合標題末尾的來源
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except: return ""

def clean_summary(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    return text.replace('&nbsp;', ' ').strip()

def is_relevant(title, summary, query):
    """回復 Ver 6.3/6.4 邏輯：標題或摘要命中即可"""
    if not query: return True
    q = query.lower().strip()
    return q in title.lower() or q in (summary or "").lower()

# ==================== 3. 搜尋引擎核心 ====================
def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        return [{
            "title": e.get('title', ''),
            "link": e.get('link', ''),
            "summary": clean_summary(e.get('summary', e.get('description', ''))),
            "published": e.get('published_parsed'),
            "source_type": "Google"
        } for e in feed.entries if e.get('link')]
    except: return []

def fetch_gnews(query, start_date, end_date, lang, country, api_key):
    if not api_key: return [], 0
    try:
        params = {
            "token": api_key, "q": f'"{query}"', "lang": lang, "country": country,
            "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "max": 100
        }
        resp = requests.get("https://gnews.io/api/v4/search", params=params, timeout=15)
        data = resp.json()
        articles = []
        for a in data.get("articles", []):
            articles.append({
                "title": a.get("title", ""),
                "link": a.get("url", ""),
                "summary": a.get("description", ""),
                "published": a.get("publishedAt"),
                "source": a.get("source", {}).get("name", ""),
                "domain": urlparse(a.get("url", "")).netloc.replace("www.", ""),
                "source_type": "GNews"
            })
        return articles, data.get("totalArticles", 0)
    except: return [], 0

# ==================== 4. UI 介面 ====================
st.set_page_config(page_title="全球新聞搜尋平台 Ver 7.0", layout="wide")
st.title("🌐 全球新聞搜尋平台 Ver 7.0")
st.caption("回復搜尋量 | 修正白名單失效 | 強化地區過濾")

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

    with st.spinner("正在搜尋大量新聞來源..."):
        # 建立 Google RSS URL
        def build_google_url(q, g, h, c, sd, ed, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            return f"https://news.google.com/rss/search?q={quote(q)}{site_str}+after:{sd}+before:{ed + timedelta(days=1)}&hl={h}&gl={g}&ceid={c}"

        # 1. 抓取 Google (核心白名單 + 補充包)
        raw_google_white = []
        batch_size = 15
        wl_list = list(white_list)
        for i in range(0, len(wl_list), batch_size):
            raw_google_white.extend(fetch_google_news(build_google_url(query, gl, hl, ceid, start_date, end_date, wl_list[i:i+batch_size])))
        
        supplement_raw = fetch_google_news(build_google_url(query, gl, hl, ceid, start_date, end_date))
        
        # 2. 抓取 GNews
        gn_articles, gn_total = fetch_gnews(query, start_date, end_date, g_l, g_c, api_key)

        # 3. 混合處理與過濾 (Ver 7.0 修正過濾邏輯)
        final_core, final_supplement, seen_links = [], [], set()

        # 預定義地區排除關鍵字
        tw_blacklist = ["ettoday", "ltn.com.tw", "chinatimes", "udn.com", "setn.com", "tvbs", "ftvnews", "nownews"]
        hk_blacklist = ["hk01.com", "on.cc", "scmp.com", "rthk", "hkej", "mingpao", "tvb.com"]

        all_candidates = raw_google_white + gn_articles + supplement_raw

        for item in all_candidates:
            if item['link'] in seen_links: continue
            
            # 獲取標題中的媒體名稱 (Google RSS 標題通常是 "標題 - 媒體")
            media_name = ""
            if " - " in item['title']:
                parts = item['title'].rsplit(" - ", 1)
                item['pure_title'] = parts[0]
                media_name = parts[1]
            else:
                item['pure_title'] = item['title']
                media_name = item.get('source', '未知來源')

            # 提取網域進行白名單比對
            domain = get_domain_from_url(item['link'])
            
            # 強效地區過濾 (防止 Engine 滲透)
            is_excluded = False
            if "香港" in region:
                if any(k in item['link'].lower() or k in media_name.lower() for k in tw_blacklist): is_excluded = True
            elif "台灣" in region:
                if any(k in item['link'].lower() or k in media_name.lower() for k in hk_blacklist): is_excluded = True

            if is_excluded: continue

            # 相關性校驗 (回復 Ver 6.3 廣度：標題或摘要含有關鍵字)
            if is_relevant(item['pure_title'], item['summary'], query):
                # 白名單判定 (修正失效問題)
                is_white = False
                if any(ws in domain for ws in white_list) or any(ws in item['link'] for ws in white_list):
                    is_white = True
                
                if is_white:
                    final_core.append(item)
                else:
                    final_supplement.append(item)
                seen_links.add(item['link'])

        # 4. 數量控制：回復豐富度，Supplement 顯示更多
        # 按照討論，需顯示接近三分一整體數量，這裡我們保留更多補充包
        max_supplement = 100 if len(final_core) < 10 else len(final_core) * 2
        final_supplement = final_supplement[:max_supplement]
        
        results = final_core + final_supplement
        # 按時間排序
        results.sort(key=lambda x: str(x.get("published", "")), reverse=True)

        # 5. 輸出顯示
        st.success(f"找到 {len(results)} 則新聞 (白名單: {len(final_core)} | 補充: {len(final_supplement)})")
        
        for news in results:
            source_tag = "✅" if news in final_core else "🌐"
            st.markdown(f"### {source_tag} [{news['pure_title']}]({news['link']})")
            # 顯示來源與時間
            pub_time = news.get("published", "時間未知")
            st.caption(f"來源：{get_domain_from_url(news['link'])} | 類型：{news['source_type']} | 時間：{pub_time}")
            st.write(news['summary'][:200] + "...")
            st.divider()

        # 6. 診斷面板
        with st.expander("🔍 搜尋漏斗診斷 (Ver 7.0)"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Google 原始抓取", len(raw_google_white) + len(supplement_raw))
            c2.metric("GNews API 總量", gn_total)
            c3.metric("最終顯示總數", len(results))
            st.write(f"白名單命中 (Core): {len(final_core)}")
            st.write(f"寬鬆補充 (Supplement): {len(final_supplement)}")