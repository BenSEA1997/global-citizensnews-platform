import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單配置 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# ==================== 工具函數 ====================
def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "")
    except: return "未知來源"

def extract_source_and_clean_title(full_title):
    if " - " in full_title:
        parts = full_title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return full_title.strip(), "未知媒體"

def is_wrong_region(media_name, region_choice, link):
    """強效地區排除"""
    domain = get_domain(link)
    if "香港" in region_choice:
        # 排除台灣常見媒體關鍵字
        tw_keywords = ["ETtoday", "自由時報", "中時", "聯合報", "TVBS", "三立", "NOWnews", "ttv.com.tw", "ltn.com.tw"]
        return any(k in media_name or k in domain for k in tw_keywords)
    if "台灣" in region_choice:
        # 排除香港常見媒體關鍵字
        hk_keywords = ["香港01", "東網", "文匯", "大公", "RTHK", "hk01.com", "on.cc"]
        return any(k in media_name or k in domain for k in hk_keywords)
    return False

# ==================== API 邏輯 ====================
def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        return [{
            "title": e.get('title', '無標題'),
            "link": e.get('link', ''),
            "published": e.get('published_parsed'),
            "source_type": "Google"
        } for e in feed.entries if e.get('link')]
    except: return []

def fetch_gnews(query, start_date, end_date, lang, country, api_key):
    if not api_key: return [], 0
    try:
        # 修正：不要在搜尋詞外加多餘引號，除非使用者輸入
        search_q = query
        params = {
            "token": api_key, "q": search_q, "lang": lang, "country": country,
            "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "max": 100, "sortby": "publishedAt"
        }
        resp = requests.get("https://gnews.io/api/v4/search", params=params, timeout=20)
        data = resp.json()
        articles = []
        for a in data.get("articles", []):
            articles.append({
                "title": a.get("title", "無標題"),
                "media": a.get("source", {}).get("name", "未知媒體"),
                "link": a.get("url", ""),
                "published": a.get("publishedAt"),
                "source_type": "GNews"
            })
        return articles, data.get("totalArticles", 0)
    except: return [], 0

# ==================== UI 與 核心邏輯 ====================
st.set_page_config(page_title="全球新聞搜尋平台 Ver 6.6", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("Ver 6.6 - 解決舊新聞與地區滲透問題")

api_key = st.text_input("GNews API Key", type="password")
region = st.radio("選擇主要搜尋區域", ["1. 香港媒體", "2. 台灣/世界華文", "3. 英文全球", "4. 中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()

    if "中國大陸" in region: 
        white_list, gl, hl, ceid, g_l, g_c = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region: 
        white_list, gl, hl, ceid, g_l, g_c = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif "香港" in region: 
        white_list, gl, hl, ceid, g_l, g_c = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else: 
        white_list, gl, hl, ceid, g_l, g_c = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("深度搜尋與精準過濾中..."):
        def build_url(q, g, h, c, sd, ed, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            # 優化日期格式
            date_str = f"+after:{sd.isoformat()}+before:{(ed + timedelta(days=1)).isoformat()}"
            return f"https://news.google.com/rss/search?q={quote(q)}{site_str}{date_str}&hl={h}&gl={g}&ceid={c}"

        # 1. 抓取
        raw_google_white = []
        for i in range(0, len(white_list), 10):
            batch = list(white_list)[i:i+10]
            raw_google_white.extend(fetch_google_news(build_url(query, gl, hl, ceid, start_date, end_date, batch)))
        
        supplement_raw = fetch_google_news(build_url(query, gl, hl, ceid, start_date, end_date))
        gn_articles, gn_total = fetch_gnews(query, start_date, end_date, g_l, g_c, api_key)

        # 2. 精準過濾
        final_core = []
        final_supplement = []
        seen_links = set()

        all_candidates = raw_google_white + gn_articles + supplement_raw

        for item in all_candidates:
            if item['link'] in seen_links: continue
            
            # --- 核心：強製時間檢查 (解決舊新聞問題) ---
            try:
                pub = item.get("published")
                if isinstance(pub, str): 
                    dt = datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(HKT)
                else: 
                    dt = datetime(*pub[:6], tzinfo=pytz.utc).astimezone(HKT)
                
                # 嚴格限制在使用者選擇的範圍內
                if not (start_date <= dt.date() <= end_date):
                    continue
                item['hkt_dt'] = dt
            except: continue

            # --- 核心：提取媒體與標題 ---
            clean_t, media_n = extract_source_and_clean_title(item['title'])
            if item['source_type'] == "GNews": media_n = item['media'] # GNews 有獨立媒體欄位
            
            # --- 核心：地區排除 ---
            if is_wrong_region(media_n, region, item['link']): continue

            # --- 核心：分類 ---
            domain = get_domain(item['link'])
            is_in_white = domain in white_list or any(w in media_n.lower() for w in ["rthk", "now news", "tvb", "scmp"])
            
            if is_in_white:
                item.update({"display_title": clean_t, "display_media": media_n, "is_core": True})
                final_core.append(item)
                seen_links.add(item['link'])
            elif query.lower() in clean_t.lower(): # 補充包必須標題含有關鍵字
                item.update({"display_title": clean_t, "display_media": media_n, "is_core": False})
                final_supplement.append(item)
                seen_links.add(item['link'])

        # 3. 配額與排序
        max_supp = max(15, int(len(final_core) * 0.6))
        final_supplement = final_supplement[:max_supp]
        
        unique_results = final_core + final_supplement
        unique_results.sort(key=lambda x: x['hkt_dt'], reverse=True)

        # 4. 顯示
        st.success(f"找到 {len(unique_results)} 則新聞 (Core: {len(final_core)} | Supp: {len(final_supplement)})")
        for news in unique_results:
            is_white = "✅" if news["is_core"] else "🌐"
            time_str = news["hkt_dt"].strftime("%Y-%m-%d %H:%M")
            st.markdown(f"### {is_white} [{news['display_title']}]({news['link']})")
            st.caption(f"來源：{news['display_media']} | {time_str} HKT")
            st.divider()

        with st.expander("🔍 搜尋漏斗診斷 (Ver 6.6)"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Google 原始抓取", len(raw_google_white) + len(supplement_raw))
            c2.metric("GNews API 總量", gn_total)
            c3.metric("最終通過過濾", len(unique_results))