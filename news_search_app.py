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
def extract_source_and_clean_title(full_title):
    """從標題末尾提取媒體名稱"""
    if " - " in full_title:
        parts = full_title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return full_title.strip(), "未知媒體"

def is_relevant_strict(title, query):
    if not query: return True
    return query.lower().strip() in title.lower()

# ==================== API 邏輯 ====================
def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        results = []
        for e in feed.entries:
            clean_t, media_n = extract_source_and_clean_title(e.get('title', ''))
            results.append({
                "title": clean_t,
                "media": media_n,
                "link": e.get('link', ''),
                "published": e.get('published_parsed'),
                "source_type": "Google"
            })
        return results
    except: return []

def fetch_gnews(query, start_date, end_date, lang, country, api_key):
    if not api_key: return [], 0
    try:
        search_q = query
        if "李家超" in query: search_q = '李家超 OR "John Lee"'
        elif "特朗普" in query or "川普" in query: search_q = 'Trump OR 特朗普 OR 川普'
        
        params = {
            "token": api_key, "q": search_q, "lang": lang, "country": country,
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
                "media": a.get("source", {}).get("name", "未知媒體"),
                "link": a.get("url", ""),
                "published": a.get("publishedAt"),
                "source_type": "GNews"
            })
        return articles, data.get("totalArticles", 0)
    except: return [], 0

# ==================== UI 與 核心邏輯 ====================
st.set_page_config(page_title="全球新聞搜尋平台 Ver 6.5", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("Ver 6.5 - 回復 6.3 搜尋量 | 強效地區過濾 | 極簡 UI")

api_key = st.text_input("GNews API Key", type="password")
region = st.radio("選擇主要搜尋區域", ["1. 香港媒體", "2. 台灣/世界華文", "3. 英文全球", "4. 中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()

    if "中國大陸" in region: 
        white_list, gl, hl, ceid, g_l, g_c = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region: 
        white_list, gl, hl, ceid, g_l, g_c = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif "香港" in region: 
        white_list, gl, hl, ceid, g_l, g_c = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else: 
        white_list, gl, hl, ceid, g_l, g_c = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("正在搜尋並過濾新聞..."):
        def build_url(q, g, h, c, sd, ed, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            date_str = f"+after:{sd}+before:{ed + timedelta(days=1)}" # 擴展一天確保涵蓋
            return f"https://news.google.com/rss/search?q={quote(q)}{site_str}{date_str}&hl={h}&gl={g}&ceid={c}"

        # 1. 抓取 (回歸 6.3 邏輯)
        raw_google_white = []
        for i in range(0, len(white_list), 10):
            batch = list(white_list)[i:i+10]
            raw_google_white.extend(fetch_google_news(build_url(query, gl, hl, ceid, start_date, end_date, batch)))
        
        supplement_raw = fetch_google_news(build_url(query, gl, hl, ceid, start_date, end_date))
        gn_articles, gn_total = fetch_gnews(query, start_date, end_date, g_l, g_c, api_key)

        # 2. 處理與強效過濾
        final_core = []
        final_supplement = []
        seen_links = set()

        # 強效地區排除清單 (解決地區失效問題)
        def is_wrong_region(media_name):
            if "香港" in region:
                return any(x in media_name for x in ["ETtoday", "自由時報", "中時", "聯合報", "TVBS", "三立", "網易", "新浪"])
            if "台灣" in region:
                return any(x in media_name for x in ["香港01", "東網", "文匯", "大公", "RTHK", "觀察者網"])
            return False

        # A. 核心處理
        for item in (raw_google_white + [a for a in gn_articles if a['media'] in white_list]):
            if item['link'] not in seen_links:
                # 恢復 6.3 的寬容日期邏輯，只要標題包含關鍵字且由 Google URL 過濾出
                if is_relevant_strict(item['title'], query):
                    final_core.append(item)
                    seen_links.add(item['link'])

        # B. 補充處理
        for item in (supplement_raw + gn_articles):
            if item['link'] not in seen_links:
                # 地區強效排除
                if is_wrong_region(item['media']): continue
                
                if is_relevant_strict(item['title'], query):
                    final_supplement.append(item)
                    seen_links.add(item['link'])

        # C. 限制數量與排序
        max_supp = int(len(final_core) * 0.55) if len(final_core) > 5 else 20
        final_supplement = final_supplement[:max_supp]
        
        unique_results = final_core + final_supplement
        
        # 統一時間格式供排序 (修正 GNews vs Google 時間)
        for x in unique_results:
            try:
                if isinstance(x['published'], str):
                    dt = datetime.fromisoformat(x['published'].replace("Z", "+00:00")).astimezone(HKT)
                else:
                    dt = datetime(*x['published'][:6], tzinfo=pytz.utc).astimezone(HKT)
                x['hkt_str'] = dt.strftime("%Y-%m-%d %H:%M")
                x['dt_obj'] = dt
            except:
                x['hkt_str'] = "未知時間"
                x['dt_obj'] = datetime.min.replace(tzinfo=pytz.utc)

        unique_results.sort(key=lambda x: x['dt_obj'], reverse=True)

        # 4. 顯示結果
        st.success(f"找到 {len(unique_results)} 則新聞")
        for news in unique_results:
            is_white = "✅" if news in final_core else "🌐"
            st.markdown(f"### {is_white} [{news['title']}]({news['link']})")
            st.caption(f"來源：{news['media']} | {news['hkt_str']} HKT")
            st.divider()

        # 5. 診斷面版
        with st.expander("🔍 搜尋漏斗診斷 (Ver 6.5)"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Google 原始抓取", len(raw_google_white) + len(supplement_raw))
            c2.metric("GNews API 總量", gn_total)
            c3.metric("最終顯示總數", len(unique_results))
            st.write(f"**白名單命中 (Core):** {len(final_core)}")
            st.write(f"**寬鬆補充 (Supplement):** {len(final_supplement)}")