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

# 【Ver 9.5 新增】全球輻射白名單（所有優質來源聯集，只在後端使用，不影響 UI）
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
            
            # 【核心修復】從 RSS 底層提取真實來源與網域
            raw_source = e.get('source', {})
            real_source_url = raw_source.get('href', raw_source.get('url', ''))
            real_domain = get_domain(real_source_url)
            source_title = raw_source.get('title', '未知來源')
            
            # 處理標題與摘要
            raw_title = e.get('title', '')
            clean_title = raw_title.rsplit(" - ", 1)[0]
            summary = clean_summary(e.get('summary', ''))
            full_content = (clean_title + " " + summary).lower()
            
            # AND 邏輯判定
            if not all(k.lower() in full_content for k in keywords): continue

            articles.append({
                "title": clean_title,
                "link": e.get('link', ''), # 提供給使用者點擊的連結
                "real_domain": real_domain, # 留給後端做白名單比對的真實網域
                "source": source_title,
                "published_dt": dt_hkt,
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "label": label_fallback
            })
        return articles
    except: return []

# 【Ver 9.5 新增】時間範圍拆分函數（只在後端使用，解決舊聞數量極少問題）
def split_date_ranges(start_date, end_date, max_days=45):
    ranges = []
    current = start_date
    while current <= end_date:
        chunk_end = min(current + timedelta(days=max_days - 1), end_date)
        ranges.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return ranges

# ==================== 3. UI 介面 ====================
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
        blacklist = []  # Ver 9.5 後端補全，防止未定義錯誤（不影響 UI）
    else:
        white_list, gl, hl, ceid = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans"
        blacklist = []  # Ver 9.5 後端補全，防止未定義錯誤（不影響 UI）
    
    with st.spinner("啟動深度挖掘引擎 (預計需時 5-10 秒)..."):
        # URL 構建器 (Ver 9.5 支援時間拆分 + quote_plus)
        def build_url(q, sites=None, chunk_start=None, chunk_end=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            base = f"https://news.google.com/rss/search?q={quote_plus(q)}{site_str}"
            # 使用拆分區間或原始日期
            after_d = chunk_start if chunk_start is not None else start_date
            before_d = (chunk_end if chunk_end is not None else end_date) + timedelta(days=1)
            time_params = f"+after:{after_d}+before:{before_d}"
            return f"{base}{time_params}&hl={hl}&gl={gl}&ceid={ceid}"

        # 【Ver 9.5 新增】時間範圍自動拆分（>45 天就拆，解決舊聞極少）
        date_ranges = [(start_date, end_date)]
        if (end_date - start_date).days > 45:
            date_ranges = split_date_ranges(start_date, end_date, max_days=45)

        raw_white = []
        raw_supp = []
        
        for c_start, c_end in date_ranges:
            # 1. 單次抓取全部白名單（取代原本10個一批）
            white_url = build_url(query, list(white_list), c_start, c_end)
            raw_white.extend(fetch_google_news(white_url, "核心白名單", start_hkt, end_hkt, kw_list))
            
            # 2. 抓取補充包
            supp_url = build_url(query, None, c_start, c_end)
            raw_supp.extend(fetch_google_news(supp_url, "智能補充包", start_hkt, end_hkt, kw_list))
        
        # 3. 精準網域過濾與標籤判定（Ver 9.5 新增全球輻射過濾，解決地區滲入）
        final_core, final_supp, seen = [], [], set()
        
        for a in (raw_white + raw_supp):
            # 防止重複
            if a['title'] in seen: continue
            
            # A. 絕對黑名單防護
            if any(b_domain in a['real_domain'] for b_domain in blacklist): continue
            
            # B. 重新判定白名單 (利用提取出的真實網域)
            is_white = any(w_domain in a['real_domain'] for w_domain in white_list)
            
            if is_white:
                a['label'] = "核心白名單"
                final_core.append(a)
            else:
                # 【Ver 9.5 核心優化】只保留全球優質輻射來源（其他地區直接排除）
                if any(w_domain in a['real_domain'] for w_domain in ALL_REPUTABLE_DOMAINS):
                    a['label'] = "智能補充包"
                    final_supp.append(a)
                # else: 隨機其他地區新聞 → 直接丟棄
            
            seen.add(a['title'])

        # 4. 排序與顯示（以下完全保留 9.4 原樣，一字不改）
        results = final_core + final_supp
        results.sort(key=lambda x: x["published_dt"], reverse=True)

        st.success(f"找到 {len(results)} 則新聞 (白名單: {len(final_core)} | 補充: {len(final_supp)})")
        
        for n in results:
            badge = "✅" if n['label'] == "核心白名單" else "🌐"
            st.markdown(f"### {badge} [{n['title']}]({n['link']})")
            st.markdown(f"**來源：**{n['source']} | **標籤：**{n['label']} | **時間：**{n['pub_str']}")
            st.divider()

        # 5. 診斷面板（完全保留 9.4 原樣，只更新版本號）
        with st.expander("🔍 Ver 9.5 深度診斷"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Google 原始命中", len(raw_white) + len(raw_supp))
            c2.metric("最終顯示總數", len(results))
            c3.metric("過濾排除雜訊", (len(raw_white) + len(raw_supp)) - len(results))
            st.write(f"當前搜尋關鍵字: {kw_list}")

