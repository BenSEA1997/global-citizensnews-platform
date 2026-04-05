import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 媒體名稱對應表 ====================
MEDIA_NAME_MAP = {
    "rthk.hk": "香港電台", "news.now.com": "Now新聞", "news.tvb.com": "無綫新聞",
    "i-cable.com": "有線新聞", "hk01.com": "香港01", "on.cc": "東網",
    "stheadline.com": "星島日報", "scmp.com": "南華早報", "mingpao.com": "明報",
    "hket.com": "經濟日報", "hkej.com": "信報", "881903.com": "商台新聞"
}

# ==================== 白名單配置 ====================
HK_WHITE_LIST = set(MEDIA_NAME_MAP.keys()) | {"metroradio.com.hk", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "news.gov.hk", "orientaldaily.on.cc", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# ==================== 工具函數 ====================
def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "")
    except: return "未知來源"

def get_clean_media_name(item):
    """獲取漂亮媒體名稱"""
    domain = get_domain(item['link'])
    if domain in MEDIA_NAME_MAP:
        return MEDIA_NAME_MAP[domain]
    
    # 嘗試從標題提取
    full_title = item.get('title', '')
    if " - " in full_title:
        return full_title.rsplit(" - ", 1)[1].strip()
    return domain

def clean_title(full_title):
    if " - " in full_title:
        return full_title.rsplit(" - ", 1)[0].strip()
    return full_title.strip()

# ==================== API 邏輯 ====================
def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        return [{"title": e.get('title', ''), "link": e.get('link', ''), "published": e.get('published_parsed'), "source_type": "Google"} for e in feed.entries if e.get('link')]
    except: return []

# ==================== UI 與 核心邏輯 ====================
st.set_page_config(page_title="全球新聞搜尋平台 Ver 6.7", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("Ver 6.7 - 解決截圖中出現的不相關新聞問題")

api_key = st.text_input("GNews API Key", type="password")
region = st.radio("選擇主要搜尋區域", ["1. 香港媒體", "2. 台灣/世界華文", "3. 英文全球", "4. 中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()

    if "中國大陸" in region: white_list, gl, hl, ceid = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans"
    elif "英文" in region: white_list, gl, hl, ceid = ENGLISH_GLOBAL_LIST, "US", "en", "US:en"
    elif "香港" in region: white_list, gl, hl, ceid = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant"
    else: white_list, gl, hl, ceid = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant"

    with st.spinner("正在進行精準過濾..."):
        def build_url(q, g, h, c, sd, ed, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            return f"https://news.google.com/rss/search?q={quote(f'({q})')}{site_str}+after:{sd}+before:{ed + timedelta(days=1)}&hl={h}&gl={g}&ceid={c}"

        # 1. 抓取
        raw_google_white = []
        wl_list = list(white_list)
        for i in range(0, len(wl_list), 10):
            raw_google_white.extend(fetch_google_news(build_url(query, gl, hl, ceid, start_date, end_date, wl_list[i:i+10])))
        
        # 2. 處理與二次校驗
        final_core, final_supp, seen_links = [], [], set()

        for item in raw_google_white:
            if item['link'] in seen_links: continue
            
            # --- 關鍵修正：再次檢查標題是否真的含有關鍵字 ---
            display_t = clean_title(item['title'])
            if query.lower() not in display_t.lower(): 
                continue 
            
            # 時間過濾
            try:
                dt = datetime(*item['published'][:6], tzinfo=pytz.utc).astimezone(HKT)
                if not (start_date <= dt.date() <= end_date): continue
                
                item.update({
                    "display_title": display_t,
                    "display_media": get_clean_media_name(item),
                    "hkt": dt,
                    "is_core": True
                })
                final_core.append(item)
                seen_links.add(item['link'])
            except: continue

        # 3. 排序與顯示
        final_core.sort(key=lambda x: x['hkt'], reverse=True)

        st.success(f"找到 {len(final_core)} 則相關新聞")
        for news in final_core:
            time_str = news["hkt"].strftime("%Y-%m-%d %H:%M")
            st.markdown(f"### ✅ [{news['display_title']}]({news['link']})")
            st.caption(f"來源：{news['display_media']} | {time_str} HKT")
            st.divider()

        with st.expander("🔍 搜尋漏斗診斷 (Ver 6.7)"):
            st.write(f"Google 原始回傳: {len(raw_google_white)}")
            st.write(f"關鍵字校驗後: {len(final_core)}")