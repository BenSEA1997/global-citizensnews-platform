import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import time
import pytz
from urllib.parse import urlparse, quote_plus
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import requests
from atproto import Client
import json

# ==================== 0. 核心配置 ====================
HKT = pytz.timezone('Asia/Hong_Kong')

def get_secret(key):
    return st.secrets.get(key)

api_key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")
serper_key = get_secret("SERPER_API_KEY")

# V15.7 強化 AI 診斷與路徑清洗邏輯（修復 404 報錯）
@st.cache_resource
def get_available_gemini_model(api_key):
    if not api_key:
        return "gemini-1.5-flash"
    try:
        genai.configure(api_key=api_key)
        # 取得所有支援 generateContent 的模型完整名稱
        model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 優先順序：最新別名 -> 2026新推薦 -> 標準 1.5 -> 穩定版
        priority_patterns = ["gemini-1.5-flash-latest", "gemini-flash-latest", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        
        for pattern in priority_patterns:
            for full_name in model_list:
                if pattern in full_name:
                    # 關鍵：使用 split('/')[-1] 剝離 models/ 前綴，避免雙重前綴導致 404
                    clean_name = full_name.split('/')[-1]
                    return clean_name
        
        # 最終保底邏輯
        if model_list:
            return model_list[0].split('/')[-1]
        return "gemini-1.5-flash"
    except Exception as e:
        return "gemini-1.5-flash"

available_model_path = get_available_gemini_model(api_key)

BSKY_HANDLE = "bennysea97.bsky.social"
BSKY_PASSWORD = "7inu-hoaz-vlda-alvq"

# 初始化 Session State (完整保留 V15.2 所有鍵值)
if 'news_results' not in st.session_state:
    st.session_state.news_results = None
if 'news_page' not in st.session_state:
    st.session_state.news_page = 0
if 'social_results' not in st.session_state:
    st.session_state.social_results = []
if 'social_page' not in st.session_state:
    st.session_state.social_page = 0
if 'last_social_params' not in st.session_state:
    st.session_state.last_social_params = None
if 'social_has_searched' not in st.session_state:
    st.session_state.social_has_searched = False
if 'last_news_params' not in st.session_state:
    st.session_state.last_news_params = None

# ==================== 1. 新聞核心引擎 (完整名單與邏輯) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}
CN_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "caixin.com", "chinanews.com.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

HK_BLACK_LIST = {
    "tw.news.yahoo.com", "yahoo.com.tw", "taisounds.com", "newtalk.tw", "udn.com", "storm.mg", "today.line.me", 
    "people.com.cn", "beijing.gov.cn", "cna.com.tw", "i-meihua.com", "ltn.com.tw", "msn.com", "setn.com", 
    "ctinews.com", "worldjournal.com", "cw.com.tw", "tdm.com.mo", "gvm.com.tw", "nownews.com", "youtube.com",
    "sinchew.com.my", "macaodaily.com", "threads.com", "chinatimes.com", "turnnewsapp.com", 
    "zh-yue.wikipedia.org", "big5.cctv.com", "zh.wikipedia.org"
}

def process_relative_date(date_str):
    now = datetime.now(HKT)
    s = date_str.lower()
    try:
        match = re.search(r'(\d+)', s)
        if not match: return None
        number = int(match.group(1))
        if 'min' in s: return now - timedelta(minutes=number)
        if 'hour' in s: return now - timedelta(hours=number)
        if 'day' in s: return now - timedelta(days=number)
        if 'week' in s: return now - timedelta(weeks=number)
        if 'month' in s: return now - timedelta(days=number*30)
    except: pass
    return None

def check_white(link, source_url, white_list):
    domains = []
    try: domains.append(urlparse(link).netloc.lower())
    except: pass
    if source_url:
        try: domains.append(urlparse(source_url).netloc.lower())
        except: pass
    for w in white_list:
        for d in domains:
            if w in d: return True
    return False

def check_black(link, source_url, region):
    if region != "香港媒體": return False
    check_strings = [str(link).lower()]
    if source_url: check_strings.append(str(source_url).lower())
    for b in HK_BLACK_LIST:
        for s in check_strings:
            if b in s: return True
    domains = []
    for s in check_strings:
        try: domains.append(urlparse(s).netloc)
        except: pass
    for d in domains:
        if d.endswith(('.tw', '.cn', '.sg', '.mo')): return True
        if '.tw.' in d or '.cn.' in d: return True
    return False

def parse_news_date(date_str):
    rel_dt = process_relative_date(date_str)
    if rel_dt: return rel_dt
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(tzinfo=HKT)
    except: 
        return datetime(2000, 1, 1, tzinfo=HKT)

def fetch_rss_news(url, start_hkt, end_hkt, white_list, region):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt_hkt = datetime.fromtimestamp(mktime(e.published_parsed)).replace(tzinfo=timezone.utc).astimezone(HKT)
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            link = e.get('link', '')
            source_url = e.get('source', {}).get('href', '')
            if check_black(link, source_url, region): continue
            articles.append({
                "title": e.get('title', '').rsplit(" - ", 1)[0], "link": link, 
                "source": e.get('source', {}).get('title', 'Google News RSS'), 
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"), 
                "raw_dt": dt_hkt,
                "is_white": check_white(link, source_url, white_list),
                "fetch_type": "rss"
            })
    except: pass
    return articles

def fetch_serper_combined(query, start_date, end_date, gl, hl, white_list, region):
    if not serper_key: return []
    all_results = []
    headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
    news_url = "https://google.serper.dev/news"
    search_q = f"{query} after:{start_date} before:{end_date + timedelta(days=1)}"
    for page in range(1, 9):
        payload = {"q": search_q, "gl": gl, "hl": hl, "page": page}
        try:
            res = requests.post(news_url, headers=headers, json=payload, timeout=10).json()
            items = res.get('news', [])
            if not items: break
            for i in items:
                link = i.get('link', '')
                if check_black(link, '', region): continue
                dt = parse_news_date(i.get('date', ''))
                all_results.append({
                    "title": i.get('title', ''), "link": link,
                    "source": i.get('source', 'Google Search'), "pub_str": dt.strftime("%Y-%m-%d %H:%M") if dt.year > 2000 else i.get('date', '歷史存檔'),
                    "raw_dt": dt,
                    "is_white": check_white(link, '', white_list),
                    "fetch_type": "serper_news"
                })
            time.sleep(0.5)
        except: break
    search_url = "https://google.serper.dev/search"
    payload_search = {"q": search_q, "gl": gl, "hl": hl, "page": 1}
    try:
        res = requests.post(search_url, headers=headers, json=payload_search, timeout=10).json()
        for i in res.get('organic', []):
            link = i.get('link', '')
            if check_black(link, '', region): continue
            all_results.append({
                "title": i.get('title', ''), "link": link,
                "source": "Google 網頁補充", "pub_str": "搜尋引擎索引",
                "raw_dt": datetime(2000, 1, 1, tzinfo=HKT),
                "is_white": check_white(link, '', white_list),
                "fetch_type": "supplement"
            })
    except: pass
    return all_results

# ==================== 2. 社交挖掘封裝 (恢復完整功能) ====================
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": f'query {{ search(input: {{key: "{query}", type: Article, first: 80}}) {{ edges {{ node {{ ... on Article {{ title shortHash summary author {{ displayName }} appreciationsReceivedTotal createdAt }} }} }} }} }}'}
    results = []
    try:
        response = requests.post(matters_api, json=query_json, timeout=12).json()
        edges = response.get('data', {}).get('search', {}).get('edges', [])
        for item in edges:
            n = item.get('node', {})
            if not n: continue
            dt = datetime.fromisoformat(n['createdAt'].replace('Z', '+00:00')).astimezone(HKT)
            results.append({
                "title": n.get('title', '無題'), "link": f"https://matters.town/a/{n['shortHash']}", 
                "author": n.get('author', {}).get('displayName', '未知作者'), 
                "likes": n.get('appreciationsReceivedTotal', 0), 
                "summary": n.get('summary', ''), 
                "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Matters", "raw_dt": dt
            })
    except: pass
    return results

def fetch_bluesky(query):
    results = []
    try:
        client = Client()
        client.login(BSKY_HANDLE, BSKY_PASSWORD)
        res = client.app.bsky.feed.search_posts(params={'q': query, 'limit': 80, 'sort': 'latest'}).posts
        for post in res:
            dt = datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00')).astimezone(HKT)
            results.append({
                "title": post.record.text[:80].replace('\n',' ') + "...", "link": f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}", 
                "author": post.author.display_name or post.author.handle, "likes": (post.like_count or 0), 
                "summary": post.record.text, "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Bluesky", "raw_dt": dt
            })
    except: pass
    return results

# ==================== 3. 主介面 UI ====================
st.set_page_config(page_title="全球 CitizensNews V15.7", layout="wide")

with st.sidebar:
    st.markdown("### 🌐 功能選單")
    app_mode = st.radio("請選擇模式：", ["新聞搜尋模式", "去中心化社交平台 Matters, Bluesky搜尋與分析"])
    if "去中心化社交平台" in app_mode:
        st.info("ℹ️ Matters, Bluesky是去中心化平台，適合尋找深度評論")

if "新聞搜尋" in app_mode:
    st.title("🌐 新聞搜尋模式 V15.7")
    region = st.radio("區域", ["香港媒體", "台灣/世界華文", "環球英文媒體", "中國大陸"], horizontal=True)
    query = st.text_input("關鍵字", placeholder="例如：香港經濟")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("開始", value=date.today() - timedelta(days=2))
    with col2: end_date = st.date_input("結束", value=date.today())
    enable_news_ai = st.toggle("🛡️ 開啟 AI 深度分析總結", value=False)
    news_params = (query, region, start_date, end_date)

    if st.button("搜尋", type="primary"):
        with st.status("🔄 正在搜尋中 ...", expanded=True) as status:
            if not query: st.stop()
            start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
            end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))
            mapping = {"香港媒體": (HK_WHITE_LIST, "hk", "zh-hk", "HK:zh-Hant"), "台灣/世界華文": (TW_WHITE_LIST, "tw", "zh-tw", "TW:zh-Hant"), "環球英文媒體": (ENGLISH_GLOBAL_LIST, "us", "en", "US:en"), "中國大陸": (CN_WHITE_LIST, "cn", "zh-cn", "CN:zh-Hans")}
            white_list, gl, hl, ceid = mapping[region]
            
            rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}+after:{start_date}+before:{end_date + timedelta(days=1)}&hl={hl}&gl={gl.upper()}&ceid={ceid}"
            articles_rss = fetch_rss_news(rss_url, start_hkt, end_hkt, white_list, region)
            articles_ext = fetch_serper_combined(query, start_date, end_date, gl, hl, white_list, region)
            
            unique = {}
            for a in (articles_rss + articles_ext):
                if a['link'] not in unique: unique[a['link']] = a
            
            st.session_state.news_results = sorted(unique.values(), key=lambda x: x["raw_dt"], reverse=True)
            st.session_state.news_page = 0
            st.session_state.last_news_params = news_params
            status.update(label=f"✅ 挖掘完成！共獲取 {len(st.session_state.news_results)} 則結果", state="complete")
            st.rerun()

    if st.session_state.news_results is not None and st.session_state.last_news_params == news_params:
        res = st.session_state.news_results
        if not res: st.warning("⚠️ 此關鍵字沒有搜尋到新聞")
        else:
            # 完整恢復 V15.2 的診斷統計 Success Box
            w_c = sum(1 for x in res if x.get('is_white'))
            r_c = sum(1 for x in res if x.get('fetch_type') == 'rss')
            s_c = sum(1 for x in res if x.get('fetch_type') == 'serper_news')
            b_c = sum(1 for x in res if x.get('fetch_type') == 'supplement')
            st.success(f"📊 **資料源診斷**：✅白名單: **{w_c}** | 🔴RSS新聞: **{r_c}** | 🔵Serper: **{s_c}** | 🌐網頁補充: **{b_c}** | 總計: **{len(res)}**")

            if enable_news_ai:
                st.subheader("✨ 新聞輿情 AI 深度分析")
                ai_news_box = st.empty()
                with st.spinner(f"🤖 AI正在分析中... (使用模型 ID: {available_model_path})"):
                    try:
                        model = genai.GenerativeModel(available_model_path)
                        context = "\n".join([f"[{a['source']}] {a['title']}" for a in res[:25]])
                        safe = {cat: HarmBlockThreshold.BLOCK_NONE for cat in [HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, HarmCategory.HARM_CATEGORY_HARASSMENT]}
                        resp = model.generate_content(f"請分析以下新聞報導的主要趨勢、各方觀點對比及核心事件整理：\n{context}", safety_settings=safe)
                        ai_news_box.info(resp.text)
                    except Exception as e: 
                        ai_news_box.warning(f"⚠️ AI 失效: {str(e)}")

            total_pages = (len(res)-1)//30+1
            start_idx = st.session_state.news_page * 30
            end_idx = min(start_idx + 30, len(res))
            curr_data = res[start_idx:end_idx]
            
            for n in curr_data:
                icon = "✅" if n['is_white'] else ("🔴" if n['fetch_type']=='rss' else ("🔵" if n['fetch_type']=='serper_news' else "🌐"))
                st.markdown(f"### {icon} [{n['title']}]({n['link']})")
                st.caption(f"{n['source']} | {n['pub_str']}")
                st.divider()
            
            st.write(f"顯示第 {start_idx + 1}-{end_idx} 則新聞 (第 {st.session_state.news_page+1} 頁 / 共 {total_pages} 頁)")
            c1, c2, _ = st.columns([1,1,4])
            if st.session_state.news_page > 0 and c1.button("⬅️ 上一頁"): st.session_state.news_page -= 1; st.rerun()
            if st.session_state.news_page < total_pages-1 and c2.button("下一頁 ➡️"): st.session_state.news_page += 1; st.rerun()

else:
    # ==================== 社交平台搜尋模式 (長度完全恢復) ====================
    st.title("🔵 社交平台深度搜尋與分析 V15.7")
    col_i, col_t, col_s = st.columns([2, 1, 1])
    with col_i: s_query = st.text_input("搜尋關鍵字")
    with col_t: t_filter = st.selectbox("時間範圍", ["全部", "最近 24 小時", "最近 7 天"])
    with col_s: s_order = st.selectbox("排序方式", ["🕒 最新發布", "🔥 互動次數"])
    cur_s_params = (s_query, t_filter, s_order)

    if st.button("執行挖掘與 AI 分析", type="primary"):
        with st.status("🔄 正在搜尋中 ..."):
            raw = fetch_matters(s_query) + fetch_bluesky(s_query)
            now = datetime.now(HKT)
            filtered = [r for r in raw if not (t_filter == "最近 24 小時" and (now - r['raw_dt']) > timedelta(days=1)) and not (t_filter == "最近 7 天" and (now - r['raw_dt']) > timedelta(days=7))]
            st.session_state.social_results = sorted(filtered, key=lambda x: x['likes' if s_order == "🔥 互動次數" else 'raw_dt'], reverse=True)
            st.session_state.social_page = 0
            st.session_state.last_social_params = cur_s_params
            st.session_state.social_has_searched = True
            st.rerun()

    if st.session_state.social_has_searched and st.session_state.last_social_params == cur_s_params:
        res = st.session_state.social_results
        if not res: st.warning("⚠️ 沒有貼文結果")
        else:
            st.subheader("✨ AI 趨勢分析")
            ai_box = st.empty()
            with st.spinner("🤖 AI 正在深入分析貼文內容..."):
                try:
                    model = genai.GenerativeModel(available_model_path)
                    context = "\n".join([f"{d['title']}" for d in res[:15]])
                    safe = {cat: HarmBlockThreshold.BLOCK_NONE for cat in [HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, HarmCategory.HARM_CATEGORY_HARASSMENT]}
                    response = model.generate_content(f"分析社交討論趨勢及核心議題：\n{context}", safety_settings=safe)
                    ai_box.info(response.text)
                except Exception as e: ai_box.warning(f"⚠️ AI 失效: {str(e)}")
            
            tp = (len(res)-1)//30+1
            s_idx = st.session_state.social_page * 30
            e_idx = min(s_idx + 30, len(res))
            for item in res[s_idx:e_idx]:
                st.markdown(f"### [{item['title']}]({item['link']})")
                st.caption(f"作者: {item['author']} | 平台: **{item['platform']}** | ❤️ {item['likes']} | {item['published']}")
                st.write(item['summary'][:200] + "...")
                st.divider()
            
            st.write(f"顯示第 {s_idx + 1}-{e_idx} 則貼文 (第 {st.session_state.social_page+1} 頁 / 共 {tp} 頁)")
            cc1, cc2, _ = st.columns([1,1,4])
            if st.session_state.social_page > 0 and cc1.button("⬅️ 上一頁 "): st.session_state.social_page -= 1; st.rerun()
            if st.session_state.social_page < tp-1 and cc2.button(" 下一頁 ➡️"): st.session_state.social_page += 1; st.rerun()
