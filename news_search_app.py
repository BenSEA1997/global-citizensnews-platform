import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import urlparse, quote_plus

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 專業清單配置 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "aljazeera.com", "bbc.com", "nytimes.com", "wsj.com", "cnn.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

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
st.set_page_config(page_title="全球新聞搜尋器 V9.9", layout="wide")
st.title("🌐 全球新聞搜尋器 V9.9")
st.caption("WiseNews 網域鎖定架構 | 三層混合過濾 | 完整診斷面板")

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
    
    tld_target = ""
    if "香港" in region:
        white_list, gl, hl, ceid, tld_target = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", ".hk"
    elif "台灣" in region:
        white_list, gl, hl, ceid, tld_target = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", ".tw"
    elif "英文" in region:
        white_list, gl, hl, ceid = ENGLISH_GLOBAL_LIST, "US", "en", "US:en"
    else:
        white_list, gl, hl, ceid = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans"

    with st.spinner("WiseNews 邏輯挖掘中..."):
        def build_url(q, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            base = f"https://news.google.com/rss/search?q={quote_plus(q)}{site_str}"
            time_params = f"+after:{start_date}+before:{end_date + timedelta(days=1)}"
            return f"{base}{time_params}&hl={hl}&gl={gl}&ceid={ceid}"

        raw_white = fetch_google_news(build_url(query, list(white_list)), "核心白名單", start_hkt, end_hkt, kw_list, is_supp=False)
        raw_supp = fetch_google_news(build_url(query), "智能補充包", start_hkt, end_hkt, kw_list, is_supp=True)
        
        final_results, seen = [], set()
        count_core, count_supp, count_intl = 0, 0, 0
        
        for a in (raw_white + raw_supp):
            if a['title'] in seen: continue
            d = a['real_domain']
            label = ""
            
            if any(w_domain in d for w_domain in white_list):
                label = "✅ 核心白名單"
                count_core += 1
            elif tld_target and d.endswith(tld_target):
                label = "🌐 區域補充包"
                count_supp += 1
            elif any(e_domain in d for e_domain in ENGLISH_GLOBAL_LIST):
                label = "🌍 國際補充"
                count_intl += 1
            
            if label:
                a['final_label'] = label
                final_results.append(a)
                seen.add(a['title'])

        final_results.sort(key=lambda x: x["published_dt"], reverse=True)
        st.success(f"找到 {len(final_results)} 則新聞")
        
        for n in final_results:
            st.markdown(f"### {n['final_label'][0]} [{n['title']}]({n['link']})")
            st.markdown(f"**來源：**{n['source']} | **標籤：**{n['final_label']} | **時間：**{n['pub_str']}")
            st.divider()

        # ==================== 4. 診斷面板 (Ver 9.9 回歸) ====================
        with st.expander("🔍 Ver 9.9 深度診斷"):
            raw_total = len(raw_white) + len(raw_supp)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Google 原始命中", raw_total)
            c2.metric("核心白名單數", count_core)
            c3.metric("區域補充包數", count_supp)
            c4.metric("過濾排除雜訊", raw_total - len(final_results))
            
            st.info(f"**搜尋策略：** 鎖定 {tld_target if tld_target else '國際網域'} + 核心白名單")
