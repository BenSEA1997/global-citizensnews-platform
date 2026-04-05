import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單與配置 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# ==================== 工具函數 ====================
def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "")
    except: return "未知來源"

def clean_title_only(title):
    """移除標題中由 RSS 自動附加的媒體名稱 (通常在 ' - ' 之後)"""
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title.strip()

def is_relevant_strict(title, summary, query):
    if not query: return True
    q = query.lower().strip()
    return q in title.lower() or q in (summary or "").lower()

def is_relevant_loose(title, query):
    if not query: return True
    return query.lower().strip() in title.lower()

# ==================== API 邏輯 ====================
def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        return [{
            "title": e.get('title', '無標題'),
            "link": e.get('link', ''),
            "summary": e.get('summary', e.get('description', '')),
            "published": e.get('published_parsed'),
            "source_type": "Google"
        } for e in feed.entries if e.get('link')]
    except: return []

def fetch_gnews(query, start_date, end_date, lang, country, api_key):
    if not api_key: return [], 0
    try:
        params = {
            "token": api_key, "q": f'"{query}"', "lang": lang, "country": country,
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
                "link": a.get("url", ""),
                "summary": a.get("description", ""),
                "published": a.get("publishedAt"),
                "source_type": "GNews"
            })
        return articles, data.get("totalArticles", 0)
    except: return [], 0

# ==================== UI 與 核心邏輯 ====================
st.set_page_config(page_title="全球新聞搜尋平台 Ver 6.4.2", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("Ver 6.4.2 - 診斷增強版 | 移除摘要 | 整合來源行")

api_key = st.text_input("GNews API Key", type="password")
region = st.radio("選擇主要搜尋區域", ["1. 香港媒體", "2. 台灣/世界華文", "3. 英文全球", "4. 中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()

    if "中國大陸" in region: 
        current_white_list, gl, hl, ceid, g_l, g_c = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region: 
        current_white_list, gl, hl, ceid, g_l, g_c = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif "香港" in region: 
        current_white_list, gl, hl, ceid, g_l, g_c = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else: 
        current_white_list, gl, hl, ceid, g_l, g_c = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("深度搜尋中..."):
        def build_google_url(q, g, h, c, sd, ed, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            date_str = f"+after:{sd}+before:{ed}"
            return f"https://news.google.com/rss/search?q={quote(q)}{site_str}{date_str}&hl={h}&gl={g}&ceid={c}"

        # 1. 抓取
        raw_google_white = []
        white_list_list = list(current_white_list)
        for i in range(0, len(white_list_list), 10):
            batch = white_list_list[i:i+10]
            raw_google_white.extend(fetch_google_news(build_google_url(query, gl, hl, ceid, start_date, end_date, batch)))
        
        supplement_raw = fetch_google_news(build_google_url(query, gl, hl, ceid, start_date, end_date))
        gn_articles, gn_total = fetch_gnews(query, start_date, end_date, g_l, g_c, api_key)

        # 2. 分類與過濾
        final_core = []
        final_supplement = []
        seen_links = set()

        # A. 核心白名單
        all_potential_core = raw_google_white + [a for a in gn_articles if get_domain(a['link']) in current_white_list]
        for item in all_potential_core:
            if item['link'] not in seen_links:
                if is_relevant_strict(item['title'], item['summary'], query):
                    final_core.append(item)
                    seen_links.add(item['link'])

        # B. 補充層
        potential_supp = supplement_raw + [a for a in gn_articles if get_domain(a['link']) not in current_white_list]
        for item in potential_supp:
            if item['link'] not in seen_links:
                domain = get_domain(item['link'])
                if "香港" in region and (".tw" in domain or ".cn" in domain): continue
                if "台灣" in region and (".cn" in domain or ("hk" in domain and ".com.hk" not in domain)): continue
                if is_relevant_loose(item['title'], query):
                    final_supplement.append(item)
                    seen_links.add(item['link'])

        # C. 限制
        max_supp = int(len(final_core) * 0.55) if len(final_core) > 5 else 15
        final_supplement = final_supplement[:max_supp]

        # 3. 排序與時間處理
        unique_results = final_core + final_supplement
        
        # 轉換時間用於排序
        for item in unique_results:
            try:
                pub = item.get("published")
                if isinstance(pub, str): # GNews 格式
                    dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                else: # Google 格式
                    dt = datetime(*pub[:6], tzinfo=pytz.utc)
                item["dt_hkt"] = dt.astimezone(HKT)
            except:
                item["dt_hkt"] = datetime.now(HKT)

        unique_results.sort(key=lambda x: x["dt_hkt"], reverse=True)

        # 4. 顯示結果
        st.success(f"找到 {len(unique_results)} 則新聞")
        
        for news in unique_results:
            domain = get_domain(news['link'])
            is_white = "✅" if domain in current_white_list else "🌐"
            clean_t = clean_title_only(news['title'])
            time_str = news["dt_hkt"].strftime("%Y-%m-%d %H:%M")
            
            st.markdown(f"### {is_white} [{clean_t}]({news['link']})")
            # 整合行：來源媒體 | 日期時間 | 引擎
            st.caption(f"來源：{domain} | {time_str} HKT | 搜尋引擎：{news['source_type']}")
            st.divider()

        # 5. 診斷面板 (恢復命中計數)
        with st.expander("🔍 搜尋漏斗診斷"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Google 白名單抓取", len(raw_google_white))
            c2.metric("GNews API 總量", gn_total)
            c3.metric("最終顯示總數", len(unique_results))
            
            st.write(f"**白名單命中 (Core):** {len(final_core)}")
            st.write(f"**寬鬆補充 (Supplement):** {len(final_supplement)}")