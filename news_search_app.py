import streamlit as st
import feedparser
import requests
import re
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單配置 (維持不變) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "economist.com", "telegraph.co.uk", "usatoday.com", "ft.com", "theguardian.com", "washingtonpost.com", "bloomberg.com", "afp.com", "apnews.com", "reuters.com", "ftchinese.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "caijing.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "chinadaily.com.cn", "qstheory.cn", "xinhuanet.com", "people.com.cn", "aljazeera.com", "bbc.com"}
# ... (其他名單省略以節省空間，請維持您原本的設定)

# ==================== 工具函數 ====================
def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "")
    except: return "未知來源"

def clean_title_and_source(title):
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return title.strip(), ""

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
        articles = []
        for e in feed.entries:
            if e.get('link'):
                articles.append({
                    "title": e.get('title', '無標題'),
                    "link": e.get('link', ''),
                    "summary": e.get('summary', e.get('description', '')),
                    "published": e.get('published_parsed'),
                    "source_type": "Google"
                })
        return articles
    except: return []

def fetch_gnews(query, start_date, end_date, lang, country, api_key):
    try:
        search_q = f'"{query}"' # 強制精確匹配
        params = {
            "token": api_key, "q": search_q, "lang": lang, "country": country,
            "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "max": 100, "sortby": "publishedAt"
        }
        resp = requests.get("https://gnews.io/api/v4/search", params=params, timeout=20)
        data = resp.json()
        return [{
            "title": a.get("title", "無標題"),
            "link": a.get("url", ""),
            "summary": a.get("description", ""),
            "published": a.get("publishedAt"),
            "source_type": "GNews"
        } for a in data.get("articles", [])], data.get("totalArticles", 0)
    except: return [], 0

# ==================== UI 與 核心邏輯 ====================
st.set_page_config(page_title="全球新聞搜尋平台 Ver 6.4", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("Ver 6.4 - 格式修復與地區過濾強化版")

api_key = st.text_input("GNews API Key", type="password")
region_opt = ["1. 香港媒體", "2. 台灣/世界華文", "3. 英文全球", "4. 中國大陸"]
region = st.radio("選擇主要搜尋區域", region_opt, horizontal=True)
query = st.text_input("輸入關鍵字")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()

    # 區域設定
    is_hk = "香港" in region
    is_tw = "台灣" in region
    if "中國大陸" in region: white_list, gl, hl, ceid, g_l, g_c = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", "zh", "cn"
    elif "英文" in region: white_list, gl, hl, ceid, g_l, g_c = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "en", "us"
    elif is_hk: white_list, gl, hl, ceid, g_l, g_c = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", "zh", "hk"
    else: white_list, gl, hl, ceid, g_l, g_c = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", "zh", "tw"

    with st.spinner("深度搜尋中..."):
        def build_google_url(q, g, h, c, sd, ed, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            return f"https://news.google.com/rss/search?q={quote(q)}{site_str}+after:{sd}+before:{ed}&hl={h}&gl={g}&ceid={c}"

        # 1. 抓取
        raw_google_white = []
        batch_size = 10
        for i in range(0, len(white_list), batch_size):
            batch = list(white_list)[i:i+batch_size]
            raw_google_white.extend(fetch_google_news(build_google_url(query, gl, hl, ceid, start_date, end_date, batch)))
        
        supplement_raw = fetch_google_news(build_google_url(query, gl, hl, ceid, start_date, end_date))
        gn_articles, gn_total = fetch_gnews(query, start_date, end_date, g_l, g_c, api_key)

        # 2. 處理分類與地區過濾
        final_core = []
        final_supplement = []
        seen_links = set()

        # A. 核心層
        for item in raw_google_white + [a for a in gn_articles if get_domain(a['link']) in white_list]:
            if item['link'] not in seen_links:
                if is_relevant_strict(item['title'], item['summary'], query):
                    final_core.append(item)
                    seen_links.add(item['link'])

        # B. 補充層 (Ver 6.4 強化地區過濾)
        for item in supplement_raw + [a for a in gn_articles if get_domain(a['link']) not in white_list]:
            domain = get_domain(item['link'])
            # 排除邏輯：香港引擎排除 .tw，台灣引擎排除 .hk (非白名單情況下)
            if is_hk and domain.endswith(".tw"): continue
            if is_tw and (domain.endswith(".hk") or "news.gov.hk" in domain): continue
            
            if item['link'] not in seen_links:
                if is_relevant_loose(item['title'], query):
                    final_supplement.append(item)
                    seen_links.add(item['link'])

        # C. 配額限制
        final_supplement = final_supplement[:int(len(final_core)*0.55)] if len(final_core)>5 else final_supplement[:15]

        # 3. 排序與顯示 (恢復原始時間格式)
        all_res = final_core + final_supplement
        
        # 轉換時間用於排序
        for item in all_res:
            try:
                if isinstance(item['published'], str):
                    dt = datetime.fromisoformat(item['published'].replace("Z", "+00:00"))
                else:
                    dt = datetime(*item['published'][:6])
                item['dt_obj'] = dt.astimezone(HKT)
            except:
                item['dt_obj'] = datetime.min.replace(tzinfo=HKT)

        all_res.sort(key=lambda x: x['dt_obj'], reverse=True)

        # 4. 渲染界面
        st.success(f"找到 {len(all_res)} 則新聞 (核心: {len(final_core)} | 補充: {len(final_supplement)})")
        
        for news in all_res:
            clean_t, src_t = clean_title_and_source(news['title'])
            domain = get_domain(news['link'])
            # 優先使用標題解析出的媒體名，若無則用 domain
            final_src_name = src_t or domain
            time_str = news['dt_obj'].strftime("%Y-%m-%d %H:%M")
            
            # 顯示格式：標題 (超連結)
            st.markdown(f"### [{clean_t}]({news['link']})")
            # 來源行：媒體名稱 | 日期時間 (無 Summary)
            st.caption(f"{final_src_name} | {time_str}")
            st.divider()

        # 診斷面板
        with st.expander("🔍 Ver 6.4 搜尋漏斗診斷"):
            st.write(f"Google 原始抓取: {len(raw_google_white) + len(supplement_raw)} | GNews API 總計: {gn_total}")
            st.write(f"白名單命中: {len(final_core)} | 寬鬆補充: {len(final_supplement)}")