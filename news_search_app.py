import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import urlparse, quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 媒體白名單 (嚴格對齊) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com", "cntv.cn", "cgtn.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# ==================== 2. 工具函數 ====================
def to_hkt_aware(dt_obj):
    """將時間轉換為香港時區 (HKT)"""
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj.astimezone(HKT)

def clean_summary(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    return text.replace('&nbsp;', ' ').strip()

def is_relevant(title, summary, query):
    """標題或摘要命中即可"""
    if not query: return True
    q = query.lower().strip()
    return q in title.lower() or q in (summary or "").lower()

# ==================== 3. 搜尋引擎核心 ====================
def fetch_google_news(url, source_type_label, start_hkt, end_hkt):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            if not e.get('link'): continue
            
            # 時間解析與嚴格過濾
            try:
                dt = datetime.fromtimestamp(mktime(e.published_parsed))
                dt_hkt = to_hkt_aware(dt)
            except:
                continue # 若無法解析時間則捨棄
            
            if not (start_hkt <= dt_hkt <= end_hkt):
                continue # 強制日期過濾，踢出舊新聞
                
            # 解析標題與媒體名稱 (Google 通常格式為 "標題 - 媒體名稱")
            raw_title = e.get('title', '')
            if " - " in raw_title:
                parts = raw_title.rsplit(" - ", 1)
                pure_title = parts[0]
                media_name = parts[1]
            else:
                pure_title = raw_title
                media_name = "未知來源"

            articles.append({
                "pure_title": pure_title,
                "link": e.get('link', ''),
                "summary": clean_summary(e.get('summary', e.get('description', ''))),
                "published_dt": dt_hkt,
                "pub_time_str": dt_hkt.strftime("%Y-%m-%d %H:%M HKT"),
                "media_name": media_name,
                "source_type": source_type_label
            })
        return articles
    except: return []

def fetch_gnews(query, start_date, end_date, lang, country, api_key, start_hkt, end_hkt):
    if not api_key: return [], 0
    try:
        # 取消雙引號，改用寬鬆比對以支援繁體中文分詞
        params = {
            "token": api_key, "q": query, "lang": lang, "country": country,
            "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "max": 100
        }
        resp = requests.get("https://gnews.io/api/v4/search", params=params, timeout=15)
        data = resp.json()
        articles = []
        
        for a in data.get("articles", []):
            try:
                # Gnews 時間格式: 2021-03-22T08:26:02Z
                dt = datetime.strptime(a.get("publishedAt"), "%Y-%m-%dT%H:%M:%SZ")
                dt_hkt = to_hkt_aware(dt)
            except:
                continue
                
            if not (start_hkt <= dt_hkt <= end_hkt):
                continue # 強制日期過濾
                
            articles.append({
                "pure_title": a.get("title", ""),
                "link": a.get("url", ""),
                "summary": a.get("description", ""),
                "published_dt": dt_hkt,
                "pub_time_str": dt_hkt.strftime("%Y-%m-%d %H:%M HKT"),
                "media_name": a.get("source", {}).get("name", "未知來源"),
                "source_type": "GNews"
            })
        return articles, data.get("totalArticles", 0)
    except: return [], 0

# ==================== 4. UI 介面 ====================
st.set_page_config(page_title="全球新聞搜尋平台 Ver 8.0", layout="wide")
st.title("🌐 全球新聞搜尋平台 Ver 8.0")
st.caption("90日引擎智能切換 | 嚴格日期過濾 | 顯示介面優化 | 精準白名單")

api_key = st.text_input("GNews API Key", type="password")
region = st.radio("選擇主要搜尋區域", ["1. 香港媒體", "2. 台灣/世界華文", "3. 英文全球", "4. 中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()

    # 建立精確的 HKT 邊界時間，用於強制過濾
    start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
    end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))

    # 判斷是否為 90 日內新聞 (決定主力引擎)
    days_diff = (date.today() - start_date).days
    is_recent = days_diff <= 90

    # 區域映射
    if "中國大陸" in region: white_list, gl, hl, ceid, g_l, g_c = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region: white_list, gl, hl, ceid, g_l, g_c = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif "香港" in region: white_list, gl, hl, ceid, g_l, g_c = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else: white_list, gl, hl, ceid, g_l, g_c = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("正在執行精準搜尋與智能分配引擎..."):
        def build_google_url(q, g, h, c, sd, ed, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            return f"https://news.google.com/rss/search?q={quote(q)}{site_str}+after:{sd}+before:{ed + timedelta(days=1)}&hl={h}&gl={g}&ceid={c}"

        # 1. 抓取 Google 白名單 (直接打上 Core 標籤)
        raw_google_white = []
        batch_size = 15
        wl_list = list(white_list)
        for i in range(0, len(wl_list), batch_size):
            url = build_google_url(query, gl, hl, ceid, start_date, end_date, wl_list[i:i+batch_size])
            raw_google_white.extend(fetch_google_news(url, "Google 白名單 (Core)", start_hkt, end_hkt))
        
        # 2. 抓取 Google 補充包 (打上 Supplement 標籤)
        url_supp = build_google_url(query, gl, hl, ceid, start_date, end_date)
        supplement_raw = fetch_google_news(url_supp, "Google 補充包", start_hkt, end_hkt)
        
        # 3. 抓取 GNews
        gn_articles, gn_total = fetch_gnews(query, start_date, end_date, g_l, g_c, api_key, start_hkt, end_hkt)

        # ==================== 過濾與清洗 ====================
        tw_blacklist = ["ettoday", "ltn.com.tw", "chinatimes", "udn.com", "setn.com", "tvbs", "ftvnews", "nownews"]
        hk_blacklist = ["hk01", "on.cc", "scmp", "rthk", "hkej", "mingpao", "tvb"]

        def filter_articles(articles_list):
            valid, seen = [], set()
            for item in articles_list:
                # 排除重複
                if item['pure_title'] in seen or item['link'] in seen: continue
                
                # 地區黑名單過濾
                is_excluded = False
                if "香港" in region and any(k in item['link'].lower() or k in item['media_name'].lower() for k in tw_blacklist): is_excluded = True
                elif "台灣" in region and any(k in item['link'].lower() or k in item['media_name'].lower() for k in hk_blacklist): is_excluded = True
                if is_excluded: continue

                # 相關性校驗 (維持標題或摘要命中)
                if is_relevant(item['pure_title'], item['summary'], query):
                    valid.append(item)
                    seen.add(item['pure_title'])
            return valid

        valid_core = filter_articles(raw_google_white)
        valid_supp = filter_articles(supplement_raw)
        valid_gn = filter_articles(gn_articles)

        # ==================== 90 日引擎權重分配 ====================
        # 目標顯示數量約 100 篇
        final_results = []
        if is_recent:
            # 90日以內：Google 主力 (Core 優先, 補給次之), GNews 補充
            final_core = valid_core[:60]
            final_supp = valid_supp[:20]
            final_gn = valid_gn[:20]
            main_engine = "Google News RSS"
        else:
            # 90日以上：GNews 主力, Google 補充 (但仍保留高價值 Core)
            final_gn = valid_gn[:60]
            final_core = valid_core[:30]
            final_supp = valid_supp[:10]
            main_engine = "GNews API"
        
        final_results = final_core + final_supp + final_gn
        
        # 強制按 HKT 時間由最新到最舊排序
        final_results.sort(key=lambda x: x["published_dt"], reverse=True)

        # ==================== 5. 輸出顯示 ====================
        st.success(f"找到 {len(final_results)} 則新聞 (主力引擎: {main_engine})")
        
        for news in final_results:
            source_tag = "✅" if "Core" in news['source_type'] else ("🚀" if "GNews" in news['source_type'] else "🌐")
            # 第一行：標題與連結
            st.markdown(f"### {source_tag} [{news['pure_title']}]({news['link']})")
            # 第二行：媒體名稱、類型、香港時間 (移除摘要)
            st.caption(f"來源：**{news['media_name']}** | 類型：{news['source_type']} | 時間：{news['pub_time_str']}")
            st.divider()

        # ==================== 6. 診斷面板 ====================
        with st.expander("🔍 搜尋漏斗診斷 (Ver 8.0)"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("時間判定", "≤90日" if is_recent else ">90日")
            c2.metric("Google 白名單(Core) 抓取", len(raw_google_white))
            c3.metric("GNews API 總返回量", gn_total)
            c4.metric("最終顯示總數", len(final_results))
            
            st.write(f"實際顯示分佈 -> 白名單: {len(final_core)} | 寬鬆補充: {len(final_supp)} | GNews: {len(final_gn)}")