import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 媒體名稱對應表 (依指令優化顯示) ====================
MEDIA_NAME_MAP = {
    "rthk.hk": "香港電台", "news.now.com": "Now新聞", "news.tvb.com": "無綫新聞",
    "i-cable.com": "有線新聞", "hk01.com": "香港01", "on.cc": "東網",
    "stheadline.com": "星島日報", "scmp.com": "南華早報", "mingpao.com": "明報",
    "hket.com": "經濟日報", "hkej.com": "信報", "881903.com": "商台新聞",
    "am730.com.hk": "am730", "bastillepost.com": "巴士的報", "wenweipo.com": "文匯報",
    "takungpao.com": "大公報", "hkcd.com.hk": "香港商報"
}

# ==================== 2. 白名單配置 (保持專業清單) ====================
HK_WHITE_LIST = set(MEDIA_NAME_MAP.keys()) | {"metroradio.com.hk", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "news.gov.hk", "orientaldaily.on.cc", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# ==================== 3. 工具函數 (依討論邏輯開發) ====================
def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "")
    except: return "未知來源"

def get_clean_media_name(item):
    domain = get_domain(item['link'])
    if domain in MEDIA_NAME_MAP: return MEDIA_NAME_MAP[domain]
    if item.get('source_type') == "GNews" and item.get('media'): return item['media']
    full_title = item.get('title', '')
    if " - " in full_title: return full_title.rsplit(" - ", 1)[1].strip()
    return domain

def clean_title(full_title):
    if " - " in full_title: return full_title.rsplit(" - ", 1)[0].strip()
    return full_title.strip()

def is_wrong_region(media_n, domain, region_choice):
    """強效地區排除邏輯"""
    if "香港" in region_choice:
        tw_k = ["ETtoday", "自由時報", "中時", "聯合報", "TVBS", "三立", "NOWnews", "ltn.com.tw", "udn.com"]
        return any(k in media_n or k in domain for k in tw_k)
    if "台灣" in region_choice:
        hk_k = ["香港01", "東網", "文匯", "大公", "RTHK", "hk01.com", "on.cc"]
        return any(k in media_n or k in domain for k in hk_k)
    return False

# ==================== 4. 抓取邏輯 ====================
def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        return [{"title": e.get('title', ''), "link": e.get('link', ''), "published": e.get('published_parsed'), "source_type": "Google"} for e in feed.entries if e.get('link')]
    except: return []

def fetch_gnews(query, start_date, end_date, lang, country, api_key):
    if not api_key: return [], 0
    try:
        params = {"token": api_key, "q": query, "lang": lang, "country": country, "from": start_date.strftime("%Y-%m-%dT00:00:00Z"), "to": end_date.strftime("%Y-%m-%dT23:59:59Z"), "max": 100, "sortby": "publishedAt"}
        resp = requests.get("https://gnews.io/api/v4/search", params=params, timeout=20)
        data = resp.json()
        articles = [{"title": a.get("title", ""), "media": a.get("source", {}).get("name", ""), "link": a.get("url", ""), "published": a.get("publishedAt"), "source_type": "GNews"} for a in data.get("articles", [])]
        return articles, data.get("totalArticles", 0)
    except: return [], 0

# ==================== 5. 主程式 ====================
st.set_page_config(page_title="全球新聞搜尋平台 Ver 6.9", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("Ver 6.9 - 指令嚴格執行版 (標題校驗 + 完整診斷)")

api_key = st.text_input("GNews API Key", type="password")
region = st.radio("選擇主要搜尋區域", ["1. 香港媒體", "2. 台灣/世界華文", "3. 英文全球", "4. 中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()

    # 映射配置
    if "中國大陸" in region: white_list, gl, hl, ceid, glang, gcount = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region: white_list, gl, hl, ceid, glang, gcount = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif "香港" in region: white_list, gl, hl, ceid, glang, gcount = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else: white_list, gl, hl, ceid, glang, gcount = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("按照指令深度檢索中..."):
        def build_url(q, g, h, c, sd, ed, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            return f"https://news.google.com/rss/search?q={quote(f'({q})')}{site_str}+after:{sd}+before:{ed + timedelta(days=1)}&hl={h}&gl={g}&ceid={c}"

        # A. 抓取
        raw_google_white = []
        wl_list = list(white_list)
        for i in range(0, len(wl_list), 10):
            raw_google_white.extend(fetch_google_news(build_url(query, gl, hl, ceid, start_date, end_date, wl_list[i:i+10])))
        
        supplement_raw = fetch_google_news(build_url(query, gl, hl, ceid, start_date, end_date))
        gn_articles, gn_total = fetch_gnews(query, start_date, end_date, glang, gcount, api_key)

        # B. 依指令執行過濾
        final_core, final_supp, seen_links = [], [], set()
        all_candidates = raw_google_white + gn_articles + supplement_raw

        for item in all_candidates:
            if item['link'] in seen_links: continue
            
            # 1. 標題關鍵字強制校驗
            disp_t = clean_title(item['title'])
            if query.lower() not in disp_t.lower(): continue

            # 2. 地區強效排除
            domain = get_domain(item['link'])
            media_n = get_clean_media_name(item)
            if is_wrong_region(media_n, domain, region): continue

            # 3. 嚴格時間校驗
            try:
                pub = item.get("published")
                if isinstance(pub, str): dt = datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(HKT)
                else: dt = datetime(*pub[:6], tzinfo=pytz.utc).astimezone(HKT)
                
                if not (start_date <= dt.date() <= end_date): continue
                
                item.update({"display_title": disp_t, "display_media": media_n, "hkt": dt})
                
                # 4. 分類歸檔
                if domain in white_list or (item['source_type'] == "GNews" and item['media'] in white_list):
                    final_core.append(item)
                else:
                    final_supp.append(item)
                seen_links.add(item['link'])
            except: continue

        # C. 顯示與排序
        final_supp = final_supp[:30] # 調整補充包限額
        results = final_core + final_supp
        results.sort(key=lambda x: x['hkt'], reverse=True)

        st.success(f"找到 {len(results)} 則新聞 (Core: {len(final_core)} | Supp: {len(final_supp)})")
        for n in results:
            icon = "✅" if n in final_core else "🌐"
            st.markdown(f"### {icon} [{n['display_title']}]({n['link']})")
            st.caption(f"來源：{n['display_media']} | {n['hkt'].strftime('%Y-%m-%d %H:%M')} HKT")
            st.divider()

        # D. 完整診斷面板 (嚴格遵守指令顯示)
        with st.expander("🔍 搜尋漏斗診斷 (Ver 6.9)"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Google 原始抓取", len(raw_google_white) + len(supplement_raw))
            c2.metric("GNews API 總量", gn_total)
            c3.metric("最終通過數目", len(results))
            st.write(f"**白名單命中 (Core):** {len(final_core)}")
            st.write(f"**寬鬆補充 (Supplement):** {len(final_supp)}")