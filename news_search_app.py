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

# ==================== 1. 新聞搜尋過濾邏輯 (修正版) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}
CN_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "caixin.com", "chinanews.com.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "").lower()
    except: return ""

def to_hkt_aware(dt_obj):
    if dt_obj.tzinfo is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj.astimezone(HKT)

# 修正：精確檢查標題是否含有關鍵字
def is_strictly_relevant(title, query):
    # 移除引號後的乾淨關鍵字清單
    query_clean = query.replace('"', '').replace("'", "")
    kws = [kw.lower() for kw in re.findall(r'\w+', query_clean) if len(kw) > 1]
    title_lower = title.lower()
    # 只要標題中包含其中一個核心關鍵字，即視為通過
    return any(kw in title_lower for kw in kws)

def fetch_google_news(url, start_hkt, end_hkt, query):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try: dt_hkt = to_hkt_aware(datetime.fromtimestamp(mktime(e.published_parsed)))
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            
            clean_title = e.get('title', '').rsplit(" - ", 1)[0]
            
            # --- 立即糾正：執行強制過濾 ---
            if not is_strictly_relevant(clean_title, query):
                continue
            
            raw_source = e.get('source', {})
            real_domain = get_domain(raw_source.get('href', raw_source.get('url', '')))
            source_title = raw_source.get('title', '未知來源')
            articles.append({"title": clean_title, "link": e.get('link', ''), "real_domain": real_domain, "source": source_title, "published_dt": dt_hkt, "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M")})
        return articles
    except: return []

# ==================== 2. 社交平台邏輯 (封存不變) ====================
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

# ==================== 3. 主介面 UI (優化新聞，封存社交) ====================
st.set_page_config(page_title="全球 CitizensNews V11.9", layout="wide")

with st.sidebar:
    st.title("⚙️ 搜尋功能選項")
    app_mode = st.radio("模式：", ["新聞搜尋", "去中心社交平台搜尋與AI觀點分析"])
    st.divider()

if app_mode == "新聞搜尋":
    st.title("🌐 新聞搜尋引擎 V10.3")
    region = st.radio("區域", ["香港媒體", "台灣/世界華文", "英文全球", "中國大陸"], horizontal=True)
    query = st.text_input("關鍵字", placeholder="例如：垃圾徵費")
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

        all_res, seen = [], set()
        p_bar = st.progress(0)
        # 使用雙引號強制 Google 執行精確匹配
        q_google = f'"{query}"'
        sites_str = quote_plus(" OR ".join([f"site:{s}" for s in white_list]))
        url = f"https://news.google.com/rss/search?q={quote_plus(q_google)}+({sites_str})+after:{start_date}+before:{end_date + timedelta(days=1)}&hl={hl}&gl={gl}&ceid={ceid}"
        
        raw = fetch_google_news(url, start_hkt, end_hkt, query)
        for a in raw:
            if a['link'] not in seen:
                all_res.append(a); seen.add(a['link'])
        p_bar.progress(100)
        
        all_res.sort(key=lambda x: x["published_dt"], reverse=True)
        st.success(f"找到 {len(all_res)} 則高相關新聞")
        for n in all_res:
            st.markdown(f"### ✅ [{n['title']}]({n['link']})")
            st.caption(f"來源：{n['source']} | 時間：{n['pub_str']}")
            st.divider()

else:
    # 🔴 社交平台頁面：完全保留 Ver 11.8 版權，不作修改
    st.title("🔵 去中心社交平台搜尋與AI觀點分析")
    col_input, col_time, col_sort = st.columns([2, 1, 1])
    with col_input: social_query = st.text_input("關鍵字", key="s_input")
    with col_time: time_filter = st.selectbox("時間範圍", ["全部", "最近 24 小時", "最近 7 天"])
    with col_sort: sort_order = st.selectbox("排序方式", ["🕒 最新發布", "🔥 互動次數"])

    if st.button("執行挖掘與分析", type="primary"):
        p_bar_soc = st.progress(0)
        st.write("🔍 正在進行深度檢索...")
        p_bar_soc.progress(30)
        m_results = fetch_matters(social_query)
        p_bar_soc.progress(60)
        b_results = fetch_bluesky(social_query)
        p_bar_soc.progress(100)
        raw_all = m_results + b_results
        now = datetime.now(HKT)
        filtered = [r for r in raw_all if not (time_filter == "最近 24 小時" and (now - r['raw_dt']) > timedelta(days=1)) and not (time_filter == "最近 7 天" and (now - r['raw_dt']) > timedelta(days=7))]
        if sort_order == "🔥 互動次數": st.session_state.social_results = sorted(filtered, key=lambda x: x['likes'], reverse=True)
        else: st.session_state.social_results = sorted(filtered, key=lambda x: x['raw_dt'], reverse=True)
        st.session_state.social_page = 0
        st.success(f"搜尋完成，共找到 {len(filtered)} 則動態。")

    if st.session_state.social_results:
        results = st.session_state.social_results
        items_per_page = 20
        total_pages = (len(results) - 1) // items_per_page + 1
        curr_data = results[st.session_state.social_page * items_per_page : (st.session_state.social_page + 1) * items_per_page]
        if curr_data:
            st.subheader("✨ Gemini AI 觀點回覆")
            context = "\n".join([f"[{d['platform']}] {d['title']}: {d['summary'][:80]}" for d in curr_data[:12]])
            try:
                model = genai.GenerativeModel('models/gemini-2.0-flash')
                prompt = f"你是 CitizensNews AI。請根據以下內容回覆問題：'{social_query}'。\n{context}"
                response = model.generate_content(prompt)
                st.info(f"{response.text}")
            except: st.warning("AI 額度限制中。")
        st.divider()
        for item in curr_data:
            with st.container():
                st.markdown(f"### [{'✍️' if item['platform']=='Matters' else '🦋'}] [{item['title']}]({item['link']})")
                st.caption(f"平台: {item['platform']} | 作者: {item['author']} | 日期: {item['published']} | ❤️ {item['likes']}")
                st.write(item['summary'][:300])
                st.divider()
        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.session_state.social_page > 0:
                if st.button("⬅️ 上一頁"): 
                    st.session_state.social_page -= 1
                    st.rerun()
        with p2: st.write(f"第 {st.session_state.social_page + 1} 頁 / 共 {total_pages} 頁")
        with p3:
            if (st.session_state.social_page + 1) < total_pages:
                if st.button("下一頁 ➡️"):
                    st.session_state.social_page += 1
                    st.rerun()