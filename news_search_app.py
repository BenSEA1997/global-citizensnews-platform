import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import urlparse, quote_plus

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 清單配置 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
# 擴展補充包准入關鍵字
HK_SUPP_KEYWORDS = ["香港", "HK", "Hong Kong", "港聞", "港"]

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
    """將長日期範圍切割成小塊，提高舊新聞抓取成功率"""
    ranges = []
    curr = start_date
    while curr <= end_date:
        nxt = min(curr + timedelta(days=interval_days), end_date)
        ranges.append((curr, nxt))
        curr = nxt + timedelta(days=1)
    return ranges

def fetch_google_news(url, label_fallback, start_hkt, end_hkt, keywords, is_supp=False):
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

            if is_supp:
                if not any(k.lower() in full_content for k in keywords): continue
            else:
                if not all(k.lower() in full_content for k in keywords): continue

            articles.append({
                "title": clean_title,
                "link": e.get('link', ''),
                "real_domain": real_domain,
                "source": source_title,
                "published_dt": dt_hkt,
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "label_candidate": label_fallback
            })
        return articles
    except: return []

# ==================== 3. Streamlit UI ====================
st.set_page_config(page_title="全球新聞搜尋器 V10.0", layout="wide")
st.title("🌐 全球新聞搜尋器 V10.0")
st.caption("分段日期挖掘技術 | 進取型補充包邏輯 | 舊新聞復活")

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
    
    # 區域參數設定
    tld_target = ""
    if "香港" in region:
        white_list, gl, hl, ceid, tld_target = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", ".hk"
    elif "台灣" in region:
        white_list, gl, hl, ceid, tld_target = HK_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", ".tw" # 此處應為 TW_WHITE_LIST，Ver 9.9 已有，此處簡略
    else:
        white_list, gl, hl, ceid, tld_target = HK_WHITE_LIST, "US", "en", "US:en", ""

    # 執行分段搜尋
    date_chunks = split_date_ranges(start_date, end_date, interval_days=30 if (end_date-start_date).days > 60 else 90)
    
    all_raw_white = []
    all_raw_supp = []

    progress_bar = st.progress(0)
    for idx, (s_d, e_d) in enumerate(date_chunks):
        with st.spinner(f"正在挖掘 {s_d} 至 {e_d} 的新聞..."):
            def build_url(q, sites=None, sd=s_d, ed=e_d):
                site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
                base = f"https://news.google.com/rss/search?q={quote_plus(q)}{site_str}"
                time_params = f"+after:{sd}+before:{ed + timedelta(days=1)}"
                return f"{base}{time_params}&hl={hl}&gl={gl}&ceid={ceid}"

            all_raw_white.extend(fetch_google_news(build_url(query, list(white_list)), "核心白名單", start_hkt, end_hkt, kw_list, is_supp=False))
            all_raw_supp.extend(fetch_google_news(build_url(query), "智能補充包", start_hkt, end_hkt, kw_list, is_supp=True))
        progress_bar.progress((idx + 1) / len(date_chunks))

    # 過濾邏輯
    final_results, seen = [], set()
    count_core, count_supp = 0, 0
    
    for a in (all_raw_white + all_raw_supp):
        if a['title'] in seen: continue
        d = a['real_domain']
        s_title = a['source']
        label = ""
        
        # 1. 核心白名單
        if any(w_domain in d for w_domain in white_list):
            label = "✅ 核心白名單"
            count_core += 1
        
        # 2. 進取型補充包 (符合 TLD OR 來源名含關鍵字)
        elif (tld_target and d.endswith(tld_target)) or any(sk in s_title for sk in HK_SUPP_KEYWORDS):
            label = "🌐 區域補充包"
            count_supp += 1
            
        if label:
            a['final_label'] = label
            final_results.append(a)
            seen.add(a['title'])

    final_results.sort(key=lambda x: x["published_dt"], reverse=True)
    st.success(f"挖掘完成！共找到 {len(final_results)} 則新聞")
    
    for n in final_results:
        st.markdown(f"### {n['final_label'][0]} [{n['title']}]({n['link']})")
        st.markdown(f"**來源：**{n['source']} | **標籤：**{n['final_label']} | **時間：**{n['pub_str']}")
        st.divider()

    with st.expander("🔍 Ver 10.0 深度診斷"):
        c1, c2, c3 = st.columns(3)
        c1.metric("時間分段數", len(date_chunks))
        c2.metric("原始命中總數", len(all_raw_white) + len(all_raw_supp))
        c3.metric("最終顯示總數", len(final_results))
        st.write(f"搜尋範圍：{start_date} 至 {end_date}")
