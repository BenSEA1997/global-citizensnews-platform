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

# ==================== 0. 核心配置與 AI 初始化 ====================
HKT = pytz.timezone('Asia/Hong_Kong')

# 憑據配置
GEMINI_API_KEY = "AIzaSyC3BObPwMWoulIw2tVdf-mnuvzH6bDFOSI"
BSKY_HANDLE = "bennysea97.bsky.social"
BSKY_PASSWORD = "7inu-hoaz-vlda-alvq"

# 初始化 Gemini AI (修正 404 錯誤)
try:
    genai.configure(api_key=GEMINI_API_KEY)
    # 明確指定版本模型
    ai_model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"AI 初始化失敗: {e}")

# 初始化 Session State
if 'social_results' not in st.session_state:
    st.session_state.social_results = []
if 'social_page' not in st.session_state:
    st.session_state.social_page = 0

# ==================== 1. 傳統新聞邏輯 (封裝) ====================
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

def fetch_google_news(url, start_hkt, end_hkt, keywords):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try: dt_hkt = to_hkt_aware(datetime.fromtimestamp(mktime(e.published_parsed)))
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            raw_source = e.get('source', {})
            real_domain = get_domain(raw_source.get('href', raw_source.get('url', '')))
            source_title = raw_source.get('title', '未知來源')
            clean_title = e.get('title', '').rsplit(" - ", 1)[0]
            articles.append({"title": clean_title, "link": e.get('link', ''), "real_domain": real_domain, "source": source_title, "published_dt": dt_hkt, "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M")})
        return articles
    except: return []

# ==================== 2. 去中心化社交平台邏輯 ====================
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": """query { search(input: {key: \"""" + query + """\", type: Article, first: 80}) { edges { node { ... on Article { title shortHash summary author { displayName } appreciationsReceivedTotal createdAt } } } } } """}
    results = []
    try:
        response = requests.post(matters_api, json=query_json, timeout=10)
        data = response.json()['data']['search']['edges']
        for item in data:
            n = item['node']
            results.append({"title": n['title'], "link": f"https://matters.town/a/{n['shortHash']}", "author": n['author']['displayName'], "likes": n['appreciationsReceivedTotal'], "summary": n['summary'], "published": n['createdAt'], "platform": "Matters"})
    except: pass
    return results

def fetch_bluesky(query):
    results = []
    try:
        client = Client()
        client.login(BSKY_HANDLE, BSKY_PASSWORD)
        response = client.app.bsky.feed.search_posts(params={'q': query, 'limit': 80, 'sort': 'latest'})
        for post in response.posts:
            results.append({"title": post.record.text[:60].replace('\n',' ') + "...", "link": f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}", "author": post.author.display_name or post.author.handle, "likes": (post.like_count or 0) + (post.repost_count or 0), "summary": post.record.text, "published": post.record.created_at, "platform": "Bluesky"})
    except: pass
    return results

# ==================== 3. UI 邏輯 ====================
st.set_page_config(page_title="全球 CitizensNews 平台 V11.2", layout="wide")

with st.sidebar:
    st.title("🛠 控制面板")
    app_mode = st.radio("選擇模式：", ["🔘 傳統新聞 (V10.3)", "🔵 去中心化社交平台觀點 (New)"])
    st.divider()

if app_mode == "🔘 傳統新聞 (V10.3)":
    st.title("🌐 傳統新聞搜尋引擎 V10.3")
    # ... 原有 10.3 UI 邏輯 ...
    query = st.text_input("輸入關鍵字 (傳統新聞)")
    if st.button("執行新聞搜尋"): st.write("請依照 V10.3 流程操作")

else:
    st.title("🔵 去中心化社交平台觀點挖掘")
    
    col_input, col_time, col_sort = st.columns([2, 1, 1])
    with col_input:
        social_query = st.text_input("輸入社交關鍵字", placeholder="例如：房屋政策 評論", key="social_input")
    with col_time:
        time_filter = st.selectbox("時間範圍", ["全部", "最近 24 小時", "最近 7 天"])
    with col_sort:
        sort_order = st.selectbox("排序方式", ["🕒 最新發布", "🔥 互動次數 (高到低)"])

    if st.button("執行觀點挖掘", type="primary"):
        if not social_query: st.stop()
        with st.spinner("正在抓取大數據..."):
            raw_all = fetch_matters(social_query) + fetch_bluesky(social_query)
            
            # 1. 先執行時間過濾
            now = datetime.now(timezone.utc)
            filtered = []
            for r in raw_all:
                try:
                    pub_time = datetime.fromisoformat(r['published'].replace('Z', '+00:00'))
                    if time_filter == "最近 24 小時" and (now - pub_time) > timedelta(days=1): continue
                    if time_filter == "最近 7 天" and (now - pub_time) > timedelta(days=7): continue
                    filtered.append(r)
                except: filtered.append(r)

            # 2. 再執行排序
            if sort_order == "🕒 最新發布":
                st.session_state.social_results = sorted(filtered, key=lambda x: x['published'], reverse=True)
            else:
                st.session_state.social_results = sorted(filtered, key=lambda x: x['likes'], reverse=True)
            
            st.session_state.social_page = 0 

    if st.session_state.social_results:
        results = st.session_state.social_results
        items_per_page = 20
        total_pages = (len(results) - 1) // items_per_page + 1
        curr_data = results[st.session_state.social_page * items_per_page : (st.session_state.social_page + 1) * items_per_page]

        if curr_data:
            st.subheader("✨ Gemini AI Lab 觀點總結")
            # 傳送內容給 AI 時，如果是互動排序，AI 抓到的會是最具影響力的言論
            context = "\n".join([f"[{d['platform']}] {d['title']}: {d['summary'][:150]}" for d in curr_data[:15]])
            try:
                # 修正後的 AI 呼叫指令
                response = ai_model.generate_content(f"你是一位資深調查記者，請分析以下社群觀點，並以繁體中文總結：1.核心主流意見 2.值得注意的少數派異議 3.整體社群情緒。內容：\n{context}")
                st.info(response.text)
            except Exception as e:
                st.error(f"AI 總結失敗 (已修正 404，若仍失敗請檢查 API Key)：{str(e)}")

            st.divider()
            for item in curr_data:
                icon = "✍️" if item['platform'] == "Matters" else "🦋"
                with st.container():
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.markdown(f"### {icon} [{item['title']}]({item['link']})")
                        st.caption(f"作者: {item['author']} | 平台: {item['platform']} | 時間: {item['published'][:16].replace('T', ' ')}")
                        st.write(item['summary'])
                    with c2: st.metric("❤️ 互動", item['likes'])
                    st.divider()

            p1, p2, p3 = st.columns([1, 2, 1])
            with p1:
                if st.session_state.social_page > 0:
                    if st.button("⬅️ 上一頁"): 
                        st.session_state.social_page -= 1
                        st.rerun()
            with p2: st.write(f"第 {st.session_state.social_page + 1} 頁 / 共 {total_pages} 頁")
            with p3:
                if (st.session_state.social_page + 1) * items_per_page < len(results):
                    if st.button("下一頁 ➡️"):
                        st.session_state.social_page += 1
                        st.rerun()