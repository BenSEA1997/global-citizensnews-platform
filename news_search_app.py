import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import urlparse, quote_plus

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 專業清單配置 (回歸最穩定的網域比對) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "aljazeera.com", "bbc.com", "nytimes.com", "wsj.com", "cnn.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# 【Ver 9.5 新增】全球輻射白名單（所有優質來源聯集，只在後端使用）
ALL_REPUTABLE_DOMAINS = HK_WHITE_LIST | TAIWAN_WORLD_WHITE_LIST | MAINLAND_CHINA_WHITE_LIST | ENGLISH_GLOBAL_LIST

HK_DOMAIN_BLACKLIST = ["hk01.com", "on.cc", "stheadline.com", "hket.com", "mingpao.com", "scmp.com", "rthk.hk", "news.now.com", "dotdotnews.com", "hkej.com", "bastillepost.com"]
TW_DOMAIN_BLACKLIST = ["ltn.com.tw", "chinatimes.com", "udn.com", "ettoday.net", "setn.com", "tvbs.com.tw", "yahoo.com"]

# ==================== 2. 工具函數 ====================
def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "").lower()
    except: return ""

def to_hkt_aware(dt_obj):
    if dt_obj.tzinfo is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj.astimezone(HKT)

def clean_summary(text):
    if not text: return ""
    return re.sub(r'<[^>]+>', ' ', text).replace('&nbsp;', ' ').strip()

def fetch_google_news(url, label_fallback, start_hkt, end_hkt, keywords):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt = datetime.fromtimestamp(mktime(e.published_parsed))
                dt_hkt = to_hkt_aware(dt)
            except: continue
            
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            
            raw_source = e.get('source', {})
            real_source_url = raw_source.get('href', raw_source.get('url', ''))
            real_domain = get_domain(real_source_url)
            source_title = raw_source.get('title', '未知來源')
            
            raw_title = e.get('title', '')
            clean_title = raw_title.rsplit(" - ", 1)[0]
            summary = clean_summary(e.get('summary', ''))
            full_content = (clean_title + " " + summary).lower()
            
            if not all(k.lower() in full_content for k in keywords): continue

            articles.append({
                "title": clean_title,
                "link": e.get('link', ''),
                "real_domain": real_domain,
                "source": source_title,
                "published_dt": dt_hkt,
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "label": label_fallback
            })
        return articles
    except: return []

# 【Ver 9.5 新增】時間範圍拆分函數（解決舊聞數量極少問題）
def split_date_ranges(start_date, end_date, max_days=45):
    ranges = []
    current = start_date
    while current <= end_date:
        chunk_end = min(current + timedelta(days=max_days - 1), end_date)
        ranges.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return ranges

# ==================== 3. UI 介面（完全保留 V9.4 原版面，一字不改） ====================
st.set_page_config(page_title="全球新聞搜尋器 V9.4", layout="wide")
st.title("🌐 全球新聞搜尋器 V9.4")
st.caption("重啟 Site 引擎 | 底層真實網域解析 | 恢復大數據抓取")

region = st.radio("搜尋區域", ["香港媒體", "台灣/世界華文", "英文全球", "中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超 託管")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("執行搜尋", type="primary"):
    if not query: st.stop()
    
    kw_list = query.strip().split()
    start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
    end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))
    
    blacklist = []
    if "香港" in region:
        white_list, gl, hl, ceid = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant"
        blacklist = TW_DOMAIN_BLACKLIST
    elif "台灣" in region:
        white_list, gl, hl, ceid = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant"
        blacklist = HK_DOMAIN_BLACKLIST
    elif "英文" in region:
        white_list, gl, hl, ceid = ENGLISH_GLOBAL_LIST, "US", "en", "US:en"
    else:
        white_list, gl, hl, ceid = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans"

    with st.spinner("啟動深度挖掘引擎 (預計需時 5-10 秒)..."):
        # URL 構建器 (Ver 9.5 版)
        def build_url(q, sites=None, chunk_start=None, chunk_end=None
