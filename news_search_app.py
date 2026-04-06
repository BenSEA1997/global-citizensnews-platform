import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import urlparse, quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 專業清單配置 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "aljazeera.com", "bbc.com", "nytimes.com", "wsj.com", "cnn.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

HK_DOMAIN_BLACKLIST = ["hk01.com", "on.cc", "stheadline.com", "hket.com", "mingpao.com", "scmp.com", "rthk.hk", "news.now.com", "dotdotnews.com", "hkej.com", "bastillepost.com"]
TW_DOMAIN_BLACKLIST = ["ltn.com.tw", "chinatimes.com", "udn.com", "ettoday.net", "setn.com", "tvbs.com.tw"]

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

def fetch_google_news(url, label, start_hkt, end_hkt, keywords):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt = datetime.fromtimestamp(mktime(e.published_parsed))
                dt_hkt = to_hkt_aware(dt)
            except: continue
            
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            
            title = e.get('title', '')
            summary = clean_summary(e.get('summary', ''))
            # 雖然不顯示摘要，但後端仍用來做 AND 邏輯判定
            full_text = (title + " " + summary).lower()
            
            if not all(k.lower() in full_text for k in keywords): continue

            articles.append({
                "title": title.rsplit(" - ", 1)[0],
                "link": e.get('link', ''),
                "published_dt": dt_hkt,
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "source": title.rsplit(" - ", 1)[-1] if " - " in title else "未知",
                "label": label,
                "domain": get_domain(e.get('link', ''))
            })
        return articles
    except: return []

# ==================== 3. UI 介面 ====================
st.set_page_config(page_title="全球新聞搜尋器 V9.2", layout="wide")
st.title("🌐 全球新聞搜尋器 V9.2")
st.caption("穩定日期語法 | 核心/補充標籤回歸 | 刪除摘要顯示")

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

    with st.spinner("數據挖掘中..."):
        def build_url(q, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            base = f"https://news.google.com/rss/search?q={quote(q)}{site_str}"
            time_params = f"+after:{start_date}+before:{end_date + timedelta(days=1)}"
            return f"{base}{time_params}&hl={hl}&gl={gl}&ceid={ceid}"

        # 1. 抓取
        raw_white = []
        wl_temp = list(white_list)
        for i in range(0, len(wl_temp), 10):
            raw_white.extend(fetch_google_news(build_url(query, wl_temp[i:i+10]), "核心白名單", start_hkt, end_hkt, kw_list))
        
        raw_supp = fetch_google_news(build_url(query), "智能補充包", start_hkt, end_hkt, kw_list)
        
        # 2. 過濾與標籤判定
        final_core, final_supp, seen = [], [], set()
        
        for a in (raw_white + raw_supp):
            if a['link'] in seen: continue
            if any(b_domain in a['domain'] for b_domain in blacklist): continue
            
            # 重新判定白名單 (修復遺漏邏輯)
            is_white = False
            for w_domain in white_list:
                if w_domain in a['link'] or w_domain in a['domain']:
                    is_white = True
                    break
            
            if is_white:
                a['label'] = "核心白名單"
                final_core.append(a)
            else:
                if len(final_supp) < max(20, len(final_core) * 2):
                    a['label'] = "智能補充包"
                    final_supp.append(a)
            seen.add(a['link'])

        # 3. 排序
        results = final_core + final_supp
        results.sort(key=lambda x: x["published_dt"], reverse=True)

        st.success(f"找到 {len(results)} 則新聞 (白名單: {len(final_core)} | 補充: {len(final_supp)})")
        
        # 4. 顯示結果 (極簡化格式)
        for n in results:
            badge = "✅" if n['label'] == "核心白名單" else "🌐"
            st.markdown(f"### {badge} [{n['title']}]({n['link']})")
            # 恢復您要求的資訊行，刪除網域與摘要
            st.markdown(f"**來源：**{n['source']} | **標籤：**{n['label']} | **時間：**{n['pub_str']}")
            st.divider()

        # 5. 診斷面板
        with st.expander("🔍 Ver 9.2 深度診斷"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Google 原始命中", len(raw_white) + len(raw_supp))
            c2.metric("最終顯示總數", len(results))
            c3.metric("過濾排除雜訊", (len(raw_white) + len(raw_supp)) - len(results))
            st.write(f"當