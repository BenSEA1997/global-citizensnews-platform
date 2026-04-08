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

# ==================== 1. 傳統新聞邏輯 (保持 V10.3) ====================
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

def split_date_ranges(start_date, end_date, interval_days=30):
    ranges = []
    curr = start_date
    while curr <= end_date:
        nxt = min(curr + timedelta(days=interval_days), end_date)
        ranges.append((curr, nxt))
        curr = nxt + timedelta(days=1)
    return ranges

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

# ==================== 2. 社交平台邏輯 ====================
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": f'query {{ search(input: {{key: "{query}", type: Article, first: 80}}) {{ edges {{ node {{ ... on Article {{ title shortHash summary author {{ displayName }} appreciationsReceivedTotal createdAt }} }} }} }} }}'}
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

# ==================== 3. 主介面 UI ====================
st.set_page_config(page_title="全球 CitizensNews V11.7", layout="wide")

with st.sidebar:
    st.title("🛠 控制面板")
    app_mode = st.radio("選擇模式：", ["🔘 傳統新聞搜尋", "🔵 社交觀點分析"])
    st.divider()

if app_mode == "🔘 傳統新聞搜尋":
    st.title("🌐 傳統新聞搜尋引擎 V10.3")
    region = st.radio("搜尋區域", ["香港媒體", "台灣/世界華文", "英文全球", "中國大陸"], horizontal=True)
    query = st.text_input("輸入關鍵字", placeholder="例如：房屋政策")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
    with col2: end_date = st.date_input("結束日期", value=date.today())

    if st.button("執行新聞搜尋", type="primary"):
        if not query: st.stop()
        kw_list = query.strip().split()
        start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
        end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))
        
        if "香港" in region: white_list, gl, hl, ceid = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant"
        elif "台灣" in region: white_list, gl, hl, ceid = TW_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant"
        elif "英文" in region: white_list, gl, hl, ceid = ENGLISH_GLOBAL_LIST, "US", "en", "US:en"
        else: white_list, gl, hl, ceid = CN_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans"

        date_chunks = split_date_ranges(start_date, end_date)
        all_res, seen = [], set()
        p_bar = st.progress(0)
        for idx, (s_d, e_d) in enumerate(date_chunks):
            q_str = quote_plus(" ".join(kw_list))
            sites_str = quote_plus(" OR ".join([f"site:{s}" for s in white_list]))
            url = f"https://news.google.com/rss/search?q={q_str}+({sites_str})+after:{s_d}+before:{e_d + timedelta(days=1)}&hl={hl}&gl={gl}&ceid={ceid}"
            raw = fetch_google_news(url, start_hkt, end_hkt, kw_list)
            for a in raw:
                if a['link'] not in seen:
                    a['final_label'] = "✅ 核心媒體"
                    all_res.append(a); seen.add(a['link'])
            p_bar.progress((idx + 1) / len(date_chunks))
        all_res.sort(key=lambda x: x["published_dt"], reverse=True)
        st.success(f"找到 {len(all_res)} 則新聞")
        for n in all_res:
            st.markdown(f"### ✅ [{n['title']}]({n['link']})")
            st.caption(f"來源：{n['source']} | 時間：{n['pub_str']}")
            st.divider()

else:
    st.title("🔵 社交平台觀點挖掘 (Matters / Bluesky)")
    col_input, col_time, col_sort = st.columns([2, 1, 1])
    with col_input:
        social_query = st.text_input("輸入社交關鍵字", key="s_input")
    with col_time:
        time_filter = st.selectbox("時間範圍", ["全部", "最近 24 小時", "最近 7 天"])
    with col_sort:
        sort_order = st.selectbox("排序方式", ["🕒 最新發布", "🔥 互動次數"])

    if st.button("執行觀點挖掘", type="primary"):
        with st.spinner("抓取社交大數據..."):
            raw_all = fetch_matters(social_query) + fetch_bluesky(social_query)
            if sort_order == "🔥 互動次數":
                st.session_state.social_results = sorted(raw_all, key=lambda x: x['likes'], reverse=True)
            else:
                st.session_state.social_results = sorted(raw_all, key=lambda x: x['published'], reverse=True)
            st.session_state.social_page = 0

    if st.session_state.social_results:
        results = st.session_state.social_results
        curr_data = results[st.session_state.social_page*20 : (st.session_state.social_page+1)*20]

        # --- AI 總結區塊 (Ver 11.7：額度優化與 Flash 優先) ---
        if curr_data:
            st.subheader("✨ Gemini AI 調查報告")
            # 優化 Token：只取前 10 則最重要的內容，且每則只取 80 字，降低 TPM 壓力
            context = "\n".join([f"[{d['platform']}] {d['title']}: {d['summary'][:80]}" for d in curr_data[:10]])
            
            # 模型選擇：優先使用 Flash (額度較高)，避開容易 429 的 Pro 系列
            models_to_try = [
                'models/gemini-2.0-flash', 
                'models/gemini-flash-latest',
                'models/gemini-2.5-flash-lite'
            ]
            ai_success = False
            last_err = ""

            for m_name in models_to_try:
                try:
                    model = genai.GenerativeModel(m_name)
                    response = model.generate_content(f"請用繁體中文分析以下社群內容並總結核心意見：\n{context}", 
                                                   generation_config={"max_output_tokens": 500})
                    st.info(f"**分析模型：{m_name.split('/')[-1]}**\n\n{response.text}")
                    ai_success = True
                    break
                except Exception as e:
                    last_err = str(e)
                    continue
            
            if not ai_success:
                if "429" in last_err:
                    st.warning("⚠️ Google API 額度已達上限（每分鐘或每日次數限制）。請等候約 30 秒後再試，或更換關鍵字減少 Token 負擔。")
                else:
                    st.error(f"AI 總結暫時不可用。錯誤：{last_err}")

        st.divider()
        for item in curr_data:
            with st.container():
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"### [{'✍️' if item['platform']=='Matters' else '🦋'}] [{item['title']}]({item['link']})")
                    st.caption(f"{item['platform']} | 作者: {item['author']}")
                    st.write(item['summary'][:250])
                with c2:
                    st.metric("❤️ 互動", item['likes'])
                st.divider()

        # 分頁控制
        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.session_state.social_page > 0:
                if st.button("⬅️ 上一頁"): 
                    st.session_state.social_page -= 1
                    st.rerun()
        with p3:
            if (st.session_state.social_page + 1) * 20 < len(results):
                if st.button("下一頁 ➡️"):
                    st.session_state.social_page += 1
                    st.rerun()