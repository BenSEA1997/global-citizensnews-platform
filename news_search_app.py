import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import urlparse, quote_plus
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import requests
from atproto import Client

# ==================== 0. 核心配置 ====================
HKT = pytz.timezone('Asia/Hong_Kong')

def get_gemini_key():
    for name in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
        if name in st.secrets: return st.secrets[name]
    return None

api_key = get_gemini_key()
available_model_path = "gemini-1.5-flash"

if api_key:
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        matched = [m for m in models if '1.5-flash' in m]
        available_model_path = matched[0] if matched else (models[0] if models else "gemini-1.5-flash")
    except: pass

BSKY_HANDLE = "bennysea97.bsky.social"
BSKY_PASSWORD = "7inu-hoaz-vlda-alvq"

# 初始化 Session State
state_defaults = {
    'news_results': [], 'news_page': 0, 
    'social_results': [], 'social_page': 0,
    'last_social_params': None, 'social_has_searched': False
}
for key, val in state_defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# ==================== 1. 新聞邏輯 ====================
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
    kws = [kw for kw in re.findall(r'\w+', query.lower()) if len(kw) > 1]
    return not kws or any(kw in title for kw in kws)

def fetch_google_news(url, start_hkt, end_hkt, query, white_list):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try: dt_hkt = to_hkt_aware(datetime.fromtimestamp(mktime(e.published_parsed)))
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt) or not is_flexible_relevant(e, query): continue
            real_domain = get_domain(e.get('source', {}).get('href', e.get('link', '')))
            articles.append({
                "title": e.get('title', '').rsplit(" - ", 1)[0], "link": e.get('link', ''), 
                "source": e.get('source', {}).get('title', '未知來源'), 
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"), "is_white": real_domain in white_list
            })
        return articles
    except: return []

# ==================== 2. 社交挖掘 ====================
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": f'query {{ search(input: {{key: "{query}", type: Article, first: 80}}) {{ edges {{ node {{ ... on Article {{ title shortHash summary author {{ displayName }} appreciationsReceivedTotal createdAt }} }} }} }} }}'}
    results = []
    try:
        res = requests.post(matters_api, json=query_json, timeout=12).json()['data']['search']['edges']
        for item in res:
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
        res = client.app.bsky.feed.search_posts(params={'q': query, 'limit': 80, 'sort': 'latest'}).posts
        for post in res:
            dt = datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00')).astimezone(HKT)
            results.append({"title": post.record.text[:80].replace('\n',' ') + "...", "link": f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}", "author": post.author.display_name or post.author.handle, "likes": (post.like_count or 0), "summary": post.record.text, "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Bluesky", "raw_dt": dt})
    except: pass
    return results

# ==================== 3. 主介面 UI (V12.8) ====================
st.set_page_config(page_title="全球 CitizensNews V12.8", layout="wide")

with st.sidebar:
    st.markdown("### 🌐 功能選單")
    st.info("**去中心化社交平台 Matters, Bluesky搜尋與分析**\n\n內容來自各地專業人士、記者、研究員等深度評論和觀點。")
    app_mode = st.radio("請選擇模式：", ["新聞搜尋模式", "去中心化社交平台 Matters, Bluesky搜尋與分析"])

if "新聞搜尋" in app_mode:
    st.title("🌐 新聞搜尋引擎 V12.4")
    region = st.radio("區域", ["香港媒體", "台灣/世界華文", "環球英文媒體", "中國大陸"], horizontal=True)
    query = st.text_input("請輸入新聞關鍵字", placeholder="例如：聯合國")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=2))
    with col2: end_date = st.date_input("結束日期", value=date.today())

    if st.button("執行新聞搜尋", type="primary"):
        with st.status("🔍 正在檢索新聞庫...", expanded=True) as status:
            if not query: st.stop()
            start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
            end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))
            mapping = {"香港媒體": (HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant"), "台灣/世界華文": (TW_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant"), "環球英文媒體": (ENGLISH_GLOBAL_LIST, "US", "en", "US:en"), "中國大陸": (CN_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans")}
            white_list, gl, hl, ceid = mapping[region]
            url = f"https://news.google.com/rss/search?q={quote_plus(query)}+after:{start_date}+before:{end_date + timedelta(days=1)}&hl={hl}&gl={gl}&ceid={ceid}"
            articles = fetch_google_news(url, start_hkt, end_hkt, query, white_list)
            seen = set()
            st.session_state.news_results = sorted([a for a in articles if a['link'] not in seen and not seen.add(a['link'])], key=lambda x: x["is_white"], reverse=True)
            st.session_state.news_page = 0
            status.update(label="✅ 搜尋完成！", state="complete")
            st.rerun()

    if st.session_state.news_results:
        res = st.session_state.news_results
        core_count = len([a for a in res if a['is_white']])
        st.success(f"📊 搜尋統計：核心媒體 **{core_count}** 則 | 補充媒體 **{len(res)-core_count}** 則")
        total_pages = (len(res) - 1) // 30 + 1
        curr_page_data = res[st.session_state.news_page*30 : (st.session_state.news_page+1)*30]
        for n in curr_page_data:
            icon = "✅" if n['is_white'] else "🌐"
            st.markdown(f"### {icon} [{n['title']}]({n['link']})")
            st.caption(f"{n['source']} | {n['pub_str']}")
            st.divider()
        st.write(f"第 {st.session_state.news_page + 1} / {total_pages} 頁 (共 {len(res)} 則)")
        c1, c2, _ = st.columns([1, 1, 4])
        if st.session_state.news_page > 0 and c1.button("⬅️ 上一頁"): st.session_state.news_page -= 1; st.rerun()
        if st.session_state.news_page < total_pages - 1 and c2.button("下一頁 ➡️"): st.session_state.news_page += 1; st.rerun()

else:
    st.title("🔵 社交平台深度搜尋與分析")
    col_i, col_t, col_s = st.columns([2, 1, 1])
    with col_i: s_query = st.text_input("搜尋關鍵字", key="s_input")
    with col_t: t_filter = st.selectbox("時間範圍", ["全部", "最近 24 小時", "最近 7 天"])
    with col_s: s_order = st.selectbox("排序方式", ["🕒 最新發布", "🔥 互動次數"])

    current_params = (s_query, t_filter, s_order)

    if st.button("執行挖掘與 AI 分析", type="primary"):
        with st.status("📡 正在挖掘數據...", expanded=True) as status:
            raw = fetch_matters(s_query) + fetch_bluesky(s_query)
            now = datetime.now(HKT)
            filtered = [r for r in raw if not (t_filter == "最近 24 小時" and (now - r['raw_dt']) > timedelta(days=1)) and not (t_filter == "最近 7 天" and (now - r['raw_dt']) > timedelta(days=7))]
            st.session_state.social_results = sorted(filtered, key=lambda x: (x['likes'] if s_order=="🔥 互動次數" else x['raw_dt']), reverse=True)
            st.session_state.social_page = 0
            st.session_state.last_social_params = current_params
            st.session_state.social_has_searched = True
            status.update(label="✅ 挖掘完成，正在生成分析...", state="complete")
            st.rerun()

    if st.session_state.social_has_searched and st.session_state.last_social_params == current_params:
        res = st.session_state.social_results
        
        if not res:
            st.warning("⚠️ 沒有搜尋到此關鍵字貼文。")
        else:
            # AI 趨勢分析區塊 (回歸視覺提示)
            st.subheader("✨ AI 趨勢分析")
            ai_box = st.empty() # 創建一個空容器
            ai_box.info("🤖 AI 正在閱讀文章並撰寫總結，請稍候...") # 先放提示
            
            try:
                model = genai.GenerativeModel(available_model_path)
                context = "\n".join([f"{d['title']}" for d in res[:15]])
                safe = {cat: HarmBlockThreshold.BLOCK_NONE for cat in [HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, HarmCategory.HARM_CATEGORY_HARASSMENT]}
                response = model.generate_content(f"請總結社交平台討論趨勢：\n{context}", safety_settings=safe)
                ai_box.info(response.text) # AI 完成後，替換掉「正在閱讀」提示
            except: 
                ai_box.warning("⚠️ AI 分析暫時不可用")

            total_p = (len(res) - 1) // 30 + 1
            curr_p_data = res[st.session_state.social_page*30 : (st.session_state.social_page+1)*30]
            for item in curr_p_data:
                st.markdown(f"### [{item['title']}]({item['link']})")
                st.caption(f"作者: {item['author']} | 平台: **{item['platform']}** | ❤️ {item['likes']} | {item['published']}")
                st.write(item['summary'][:200] + "...")
                st.divider()

            st.write(f"第 {st.session_state.social_page + 1} / {total_p} 頁 (共 {len(res)} 則)")
            cc1, cc2, _ = st.columns([1, 1, 4])
            if st.session_state.social_page > 0 and cc1.button("⬅️ 上一頁"): st.session_state.social_page -= 1; st.rerun()
            if st.session_state.social_page < total_p - 1 and cc2.button(" 下一頁 ➡️"): st.session_state.social_page += 1; st.rerun()
    elif st.session_state.social_has_searched:
        st.info("💡 選項已更改，請按下紅色「執行挖掘與 AI 分析」按鈕以獲取新結果。")