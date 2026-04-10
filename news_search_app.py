import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import urlparse, quote_plus
import google.generativeai as genai
import requests
from atproto import Client
# 【AI 修正 1】加入安全設定類別引用
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==================== 0. 核心配置 ====================
HKT = pytz.timezone('Asia/Hong_Kong')

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    BSKY_HANDLE = "bennysea97.bsky.social"
    BSKY_PASSWORD = "7inu-hoaz-vlda-alvq"
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("❌ Secrets 設定錯誤。")
    st.stop()

if 'social_results' not in st.session_state:
    st.session_state.social_results = []
if 'social_page' not in st.session_state:
    st.session_state.social_page = 0

# ==================== 1. 新聞媒體與邏輯 (回歸 10.1 核心) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}
CN_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "caixin.com", "chinanews.com.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "").lower()
    except: return ""

def to_hkt_aware(dt_obj):
    if dt_obj.tzinfo is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj.astimezone(HKT)

def is_flexible_relevant(entry, query):
    title = entry.get('title', '').lower()
    summary = entry.get('summary', '').lower()
    query_clean = query.replace('"', '').replace("'", "").lower()
    kws = [kw for kw in re.findall(r'\w+', query_clean) if len(kw) > 1]
    if not kws: return True
    if any(kw in title for kw in kws): return True
    synonyms = {"李家超": ["特首", "行政長官", "john lee"], "特首": ["李家超"]}
    for main_kw, syns in synonyms.items():
        if main_kw in query_clean and any(s in title for s in syns): return True
    if any(kw in summary for kw in kws): return True
    return False

def fetch_google_news(url, start_hkt, end_hkt, query, white_list):
    articles = []
    diag = {"raw_count": 0, "filtered_count": 0}
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        diag["raw_count"] = len(feed.entries)
        for e in feed.entries:
            try: dt_hkt = to_hkt_aware(datetime.fromtimestamp(mktime(e.published_parsed)))
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            
            if not is_flexible_relevant(e, query):
                diag["filtered_count"] += 1
                continue
            
            clean_title = e.get('title', '').rsplit(" - ", 1)[0]
            raw_source = e.get('source', {})
            real_domain = get_domain(raw_source.get('href', raw_source.get('url', '')))
            source_title = raw_source.get('title', '未知來源')
            is_white = real_domain in white_list
            
            articles.append({
                "title": clean_title, "link": e.get('link', ''), 
                "real_domain": real_domain, "source": source_title, 
                "published_dt": dt_hkt, "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "is_white": is_white
            })
        return articles, diag
    except: return [], diag

# ==================== 2. 社交平台 (封存不動) ====================
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": f'query {{ search(input: {{key: "{query}", type: Article, first: 80}}) {{ edges {{ node {{ ... on Article {{ title shortHash summary author {{ displayName }} appreciationsReceivedTotal createdAt }} }} }} }} }}'}
    results = []
    try:
        response = requests.post(matters_api, json=query_json, timeout=12)
        data = response.json()['data']['search']['edges']
        for item in data:
            n = item['node']
            dt = datetime.fromisoformat(n['createdAt'].replace('Z', '+00:00')).astimezone(HKT)
            results.append({"title": n['title'], "link": f"https://matters.town/a/{n['shortHash']}", "author": n['author']['displayName'], "likes": n['appreciationsReceivedTotal'], "summary": n['summary'], "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Matters", "raw_dt": dt})
    except: pass
    return results

def fetch_bluesky(query):
    results = []
    try:
        client = Client()
        client.login(BSKY_HANDLE, BSKY_PASSWORD)
        response = client.app.bsky.feed.search_posts(params={'q': query, 'limit': 80, 'sort': 'latest'})
        for post in response.posts:
            dt = datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00')).astimezone(HKT)
            results.append({"title": post.record.text[:60].replace('\n',' ') + "...", "link": f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}", "author": post.author.display_name or post.author.handle, "likes": (post.like_count or 0) + (post.repost_count or 0), "summary": post.record.text, "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Bluesky", "raw_dt": dt})
    except: pass
    return results

# ==================== 3. 主介面 UI (優化顯示方式) ====================
st.set_page_config(page_title="全球 CitizensNews V12.4", layout="wide")

with st.sidebar:
    st.title("⚙️ 功能選項")
    app_mode = st.radio("模式：", ["新聞搜尋", "去中心社交分析"])

if app_mode == "新聞搜尋":
    st.title("🌐 新聞搜尋引擎 V12.4 (穩定版)")
    region = st.radio("區域", ["香港媒體", "台灣/世界華文", "英文全球", "中國大陸"], horizontal=True)
    query = st.text_input("關鍵字", placeholder="例如：李家超")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=2))
    with col2: end_date = st.date_input("結束日期", value=date.today())

    if st.button("執行新聞搜尋", type="primary"):
        if not query: st.stop()
        start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
        end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))
        
        if "香港" in region: white_list, gl, hl, ceid = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant"
        elif "台灣" in region: white_list, gl, hl, ceid = TW_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant"
        elif "英文" in region: white_list, gl, hl, ceid = ENGLISH_GLOBAL_LIST, "US", "en", "US:en"
        else: white_list, gl, hl, ceid = CN_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans"

        url = f"https://news.google.com/rss/search?q={quote_plus(query)}+after:{start_date}+before:{end_date + timedelta(days=1)}&hl={hl}&gl={gl}&ceid={ceid}"
        
        with st.spinner("正在進行檢索..."):
            all_articles, diag = fetch_google_news(url, start_hkt, end_hkt, query, white_list)

        seen = set()
        unique_articles = sorted([a for a in all_articles if a['link'] not in seen and not seen.add(a['link'])], 
                                key=lambda x: x["published_dt"], reverse=True)

        white_count = len([a for a in unique_articles if a['is_white']])
        extra_count = len(unique_articles) - white_count
        
        st.success(f"🔍 搜尋完成：核心媒體 {white_count} 則，補充包 {extra_count} 則")

        for n in unique_articles:
            icon = "✅" if n['is_white'] else "📦"
            label = "核心來源" if n['is_white'] else "補充來源"
            
            st.markdown(f"### {icon} [{n['title']}]({n['link']})")
            st.caption(f"{label}：{n['source']} | 時間：{n['pub_str']}")
            st.divider()

        st.divider()
        st.subheader("🛠️ 技術診斷資訊")
        st.json({
            "搜尋關鍵字": query, 
            "引擎地區": region,
            "原始抓取總數": diag["raw_count"], 
            "雜訊剔除數": diag["filtered_count"], 
            "最終顯示數": len(unique_articles),
            "API URL": url
        })

else:
    st.title("🔵 去中心社交平台搜尋與AI分析")
    col_input, col_time, col_sort = st.columns([2, 1, 1])
    with col_input: social_query = st.text_input("關鍵字", key="s_input")
    with col_time: time_filter = st.selectbox("時間範圍", ["全部", "最近 24 小時", "最近 7 天"])
    with col_sort: sort_order = st.selectbox("排序方式", ["🕒 最新發布", "🔥 互動次數"])

    if st.button("執行挖掘與分析", type="primary"):
        m_results = fetch_matters(social_query)
        b_results = fetch_bluesky(social_query)
        raw_all = m_results + b_results
        now = datetime.now(HKT)
        filtered = [r for r in raw_all if not (time_filter == "最近 24 小時" and (now - r['raw_dt']) > timedelta(days=1)) and not (time_filter == "最近 7 天" and (now - r['raw_dt']) > timedelta(days=7))]
        st.session_state.social_results = sorted(filtered, key=lambda x: (x['likes'] if sort_order=="🔥 互動次數" else x['raw_dt']), reverse=True)
        st.session_state.social_page = 0
        st.rerun()

    if st.session_state.social_results:
        results = st.session_state.social_results
        curr_data = results[st.session_state.social_page*20 : (st.session_state.social_page+1)*20]
        if curr_data:
            st.subheader("✨ AI 總結觀點")
            try:
                # 【AI 修正 2】強制解除安全限制 (BLOCK_NONE)
                # 維持你習慣的 gemini-1.5-pro 增加穩定度 (或改回 models/gemini-2.0-flash)
                model = genai.GenerativeModel('gemini-1.5-pro')
                
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                
                context = "\n".join([f"{d['title']}" for d in curr_data[:10]])
                # 傳入安全設定
                response = model.generate_content(
                    f"請分析討論趨勢：\n{context}",
                    safety_settings=safety_settings
                )
                st.info(response.text)
            except Exception as ai_err: 
                # 這裡顯示具體錯誤，不再只顯示「AI 限制」
                st.warning(f"AI 目前受限：{str(ai_err)}")

        for item in curr_data:
            st.markdown(f"### [{'✍️' if item['platform']=='Matters' else '🦋'}] [{item['title']}]({item['link']})")
            st.caption(f"作者: {item['author']} | 日期: {item['published']} | ❤️ {item['likes']}")
            st.write(item['summary'][:200])
            st.divider()