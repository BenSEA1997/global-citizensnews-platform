import streamlit as st
import feedparser
import requests
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

# 強制地區黑名單
HK_DOMAIN_BLACKLIST = ["hk01.com", "on.cc", "stheadline.com", "hket.com", "mingpao.com", "scmp.com", "rthk.hk", "news.now.com", "dotdotnews.com", "hkej.com", "bastillepost.com"]
TW_DOMAIN_BLACKLIST = ["ltn.com.tw", "chinatimes.com", "udn.com", "ettoday.net", "setn.com", "tvbs.com.tw"]

# ==================== 2. 工具函數 ====================
def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "").lower()
    except: return ""

def clean_summary(text):
    if not text: return ""
    return re.sub(r'<[^>]+>', ' ', text).replace('&nbsp;', ' ').strip()

def to_hkt_aware(dt_obj):
    if dt_obj.tzinfo is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj.astimezone(HKT)

def fetch_google_news(url, label, start_hkt, end_hkt, keywords):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt = datetime.fromtimestamp(mktime(e.published_parsed))
                dt_hkt = to_hkt_aware(dt)
            except: continue
            
            # 日期檢查
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            
            title = e.get('title', '')
            summary = clean_summary(e.get('summary', ''))
            full_text = (title + " " + summary).lower()
            
            # 【核心改進】AND 邏輯：標題+摘要必須包含所有關鍵字
            if not all(k.lower() in full_text for k in keywords): continue

            articles.append({
                "title": title.rsplit(" - ", 1)[0],
                "link": e.get('link', ''),
                "summary": summary,
                "published_dt": dt_hkt,
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "source": title.rsplit(" - ", 1)[-1] if " - " in title else "未知",
                "label": label,
                "domain": get_domain(e.get('link', ''))
            })
        return articles
    except: return []

# ==================== 3. Streamlit UI ====================
st.set_page_config(page_title="全球新聞搜尋器 V9.1", layout="wide")
st.title("🌐 全球新聞搜尋器 V9.1")
st.caption("修復日期語法 | 標題+摘要雙重過濾 | 解決白名單遺漏")

region = st.radio("主要搜尋區域", ["香港媒體", "台灣/世界華文", "英文全球", "中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超 託管")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("啟動深度搜尋", type="primary"):
    if not query: st.stop()
    
    # 預處理
    kw_list = query.strip().split()
    start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
    # 結束日期設為當天 23:59:59
    end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))
    
    # 區域映射
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

    with st.spinner("正在執行跨時區數據挖掘..."):
        # 構建 URL (模仿 Ver 6.3 穩定版)
        def build_url(q, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            base = f"https://news.google.com/rss/search?q={quote(q)}{site_str}"
            # 時間指令絕對不能編碼！
            time_params = f"+after:{start_date}+before:{end_date + timedelta(days=1)}"
            return f"{base}{time_params}&hl={hl}&gl={gl}&ceid={ceid}"

        # 1. 抓取白名單 (分組處理避免 URL 太長)
        raw_white = []
        wl_temp = list(white_list)
        for i in range(0, len(wl_temp), 10):
            url = build_url(query, wl_temp[i:i+10])
            raw_white.extend(fetch_google_news(url, "白名單", start_hkt, end_hkt, kw_list))
        
        # 2. 抓取補充包 (不限 Site)
        raw_supp = fetch_google_news(build_url(query), "補充包", start_hkt, end_hkt, kw_list)
        
        # 3. 過濾與混合
        final_core, final_supp, seen = [], [], set()
        
        for a in (raw_white + raw_supp):
            if a['link'] in seen: continue
            
            # A. 隔離黑名單
            if any(b_domain in a['domain'] for b_domain in blacklist): continue
            
            # B. 判斷白名單 (包含子網域判定，修復 NYT 遺漏)
            is_white = False
            for w_domain in white_list:
                if w_domain in a['link'] or w_domain in a['domain']:
                    is_white = True
                    break
            
            if is_white:
                final_core.append(a)
            else:
                # 補充包數量管理：不超過白名單的兩倍或基礎 20 則
                if len(final_supp) < max(20, len(final_core) * 2):
                    final_supp.append(a)
            
            seen.add(a['link'])

        # 4. 排序與顯示
        final_results = final_core + final_supp
        final_results.sort(key=lambda x: x["published_dt"], reverse=True)

        st.success(f"搜尋完成：核心白名單 {len(final_core)} 則 | 相關補充 {len(final_supp)} 則")
        
        for n in final_results:
            badge = "✅" if n in final_core else "🌐"
            st.markdown(f"### {badge} [{n['title']}]({n['link']})")
            st.caption(f"來源：**{n['source']}** | 時間：{n['pub_str']} | 網域：{n['domain']}")
            with st.expander("查看新聞摘要"):
                st.write(n['summary'])
            st.divider()

        # 5. 診斷面板 (回歸指標)
        with st.expander("🔍 Ver 9.1 深度診斷"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Google 原始總命中", len(raw_white) + len(raw_supp))
            c2.metric("白名單判定數", len(final_core))
            c3.metric("被排除雜訊數", (len(raw_white) + len(raw_supp)) - len(final_results))
            st.info(f"搜尋語法：`{query} after:{start_date} before:{end_date}`")