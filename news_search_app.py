import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import urlparse, quote_plus

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 配置與清單 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "news.cn", "gov.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

HK_SUPP_KEYWORDS = ["香港", "HK", "Hong Kong", "港聞", "港", "商報", "文匯", "大公"]
ENGLISH_TLD_ALLOWED = {".com", ".org", ".net", ".edu", ".gov", ".uk", ".us", ".au", ".ca"}

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

def split_date_ranges(start_date, end_date, interval_days=30):
    ranges = []
    curr = start_date
    while curr <= end_date:
        nxt = min(curr + timedelta(days=interval_days), end_date)
        ranges.append((curr, nxt))
        curr = nxt + timedelta(days=1)
    return ranges

def fetch_google_news(url, start_hkt, end_hkt, keywords, is_supp=False):
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

            # 關鍵字過濾邏輯
            if is_supp:
                if not any(k.lower() in full_content for k in keywords): continue
            else:
                if not all(k.lower() in full_content for k in keywords): continue

            articles.append({
                "title": clean_title, "link": e.get('link', ''), "real_domain": real_domain,
                "source": source_title, "published_dt": dt_hkt, "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M")
            })
        return articles
    except: return []

# ==================== 3. 介面與搜尋邏輯 ====================
st.set_page_config(page_title="全球新聞搜尋器 V10.2", layout="wide")
st.title("🌐 全球新聞搜尋器 V10.2")

region = st.radio("搜尋區域", ["香港媒體", "台灣/世界華文", "英文全球", "中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("執行搜尋", type="primary"):
    if not query: st.stop()
    kw_list = query.strip().split()
    start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
    end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))
    
    # 區域參數與白名單對齊
    tld_target = ""
    is_china_mode = False
    
    if "香港" in region:
        white_list, gl, hl, ceid, tld_target = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", ".hk"
    elif "台灣" in region:
        white_list, gl, hl, ceid, tld_target = TW_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", ".tw"
    elif "英文" in region:
        white_list, gl, hl, ceid, tld_target = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "GLOBAL_EN"
    else: # 中國大陸 (改為 SG 繞過 CN 接口限制)
        white_list, gl, hl, ceid, tld_target = MAINLAND_CHINA_WHITE_LIST, "SG", "zh-CN", "SG:zh-Hans", ".cn"
        is_china_mode = True

    date_chunks = split_date_ranges(start_date, end_date, interval_days=30 if (end_date-start_date).days > 60 else 90)
    all_raw_white, all_raw_supp = [], []

    p_bar = st.progress(0)
    for idx, (s_d, e_d) in enumerate(date_chunks):
        def build_url(q, sites=None, sd=s_d, ed=e_d):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            return f"https://news.google.com/rss/search?q={quote_plus(q)}{site_str}+after:{sd}+before:{ed + timedelta(days=1)}&hl={hl}&gl={gl}&ceid={ceid}"
        
        all_raw_white.extend(fetch_google_news(build_url(query, list(white_list)), start_hkt, end_hkt, kw_list))
        all_raw_supp.extend(fetch_google_news(build_url(query), start_hkt, end_hkt, kw_list, is_supp=True))
        p_bar.progress((idx + 1) / len(date_chunks))

    final_results, seen = [], set()
    count_white, count_supp = 0, 0
    
    for a in (all_raw_white + all_raw_supp):
        if a['title'] in seen: continue
        d, s_title = a['real_domain'], a['source']
        label = ""
        
        # A. 核心白名單判定
        if any(w_domain in d for w_domain in white_list):
            if tld_target == "GLOBAL_EN" and ".hk" in d: continue # 英文模式排除 .hk 核心
            label, count_white = "✅ 核心白名單", count_white + 1
        
        # B. 區域補充包判定
        else:
            if is_china_mode:
                if d.endswith(".cn") or any(md in d for md in MAINLAND_CHINA_WHITE_LIST):
                    label, count_supp = "🌐 區域補充包", count_supp + 1
            elif tld_target == "GLOBAL_EN":
                if any(d.endswith(ext) for ext in ENGLISH_TLD_ALLOWED) and not any(bad in d for bad in [".hk", ".tw", ".cn"]):
                    label, count_supp = "🌐 區域補充包", count_supp + 1
            elif tld_target and d.endswith(tld_target):
                label, count_supp = "🌐 區域補充包", count_supp + 1
            elif any(sk in s_title for sk in HK_SUPP_KEYWORDS) and "香港" in region:
                label, count_supp = "🌐 區域補充包", count_supp + 1
            
        if label:
            a['final_label'] = label
            final_results.append(a)
            seen.add(a['title'])

    final_results.sort(key=lambda x: x["published_dt"], reverse=True)
    st.success(f"找到 {len(final_results)} 則新聞")
    
    for n in final_results:
        st.markdown(f"### {n['final_label'][0]} [{n['title']}]({n['link']})")
        st.markdown(f"**來源：**{n['source']} | **時間：**{n['pub_str']}")
        st.divider()

    with st.expander("🔍 Ver 10.2 深度診斷"):
        raw_total = len(all_raw_white) + len(all_raw_supp)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Google 原始命中", raw_total)
        c2.metric("✅ 白名單命中", count_white)
        c3.metric("🌐 補充包命中", count_supp)
        c4.metric("❌ 濾除雜訊", raw_total - len(final_results))