import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
import time
from time import mktime
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
state_keys = ['news_results', 'news_page', 'social_results', 'social_page', 'last_social_params', 'social_has_searched', 'last_news_params', 'serper_raw_count']
for k in state_keys:
    if k not in st.session_state:
        st.session_state[k] = 0 if 'page' in k or 'count' in k else ([] if 'results' in k else None)

# ==================== 1. 新聞核心引擎 (V13.5 優化) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}
CN_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "caixin.com", "chinanews.com.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

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

def parse_news_date(date_str):
    try:
        if "前" in date_str or "ago" in date_str: return datetime.now(HKT)
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(tzinfo=HKT)
    except: return datetime(2000, 1, 1, tzinfo=HKT)

def fetch_rss_news(url, start_hkt, end_hkt, white_list, region):
    articles = []
    exclusions = []
    if region == "香港媒體": exclusions = [".tw", ".mo", ".cn", "macau", "macao", "macaodaily", "taiwan"]
    elif region == "台灣/世界華文": exclusions = [".hk", ".mo", ".cn", "hongkong", "macau"]
    elif region == "中國大陸": exclusions = [".tw", ".hk", ".mo", "taiwan", "hongkong"]

    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt_hkt = datetime.fromtimestamp(mktime(e.published_parsed)).replace(tzinfo=timezone.utc).astimezone(HKT)
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            link = e.get('link', '')
            source_url = e.get('source', {}).get('href', '')
            source_title = e.get('source', {}).get('title', 'Google News RSS')
            is_white = check_white(link, source_url, white_list)
            if not is_white:
                domain = urlparse(link).netloc.lower()
                source_title_lower = source_title.lower()
                if any(ex in domain or ex in source_title_lower for ex in exclusions): continue
            articles.append({
                "title": e.get('title', '').rsplit(" - ", 1)[0], "link": link, 
                "source": source_title, "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"), 
                "raw_dt": dt_hkt, "is_white": is_white, "fetch_type": "rss"
            })
    except: pass
    return articles

def fetch_serper_combined(query, start_date, end_date, gl, hl, white_list):
    """V13.5: 完全採用 Lab Test 成功的 json payload 與分頁模式"""
    if not serper_key: return []
    all_results = []
    headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
    
    # 使用 Lab Test 證實有效的搜尋語法
    search_q = f"{query} after:{start_date}"
    
    # 1. 搜尋新聞 (翻 8 頁)
    news_url = "https://google.serper.dev/news"
    for page in range(1, 9):
        payload = {"q": search_q, "gl": gl, "hl": hl, "page": page}
        try:
            res = requests.post(news_url, headers=headers, json=payload, timeout=12).json()
            items = res.get('news', [])
            if not items: break
            for i in items:
                all_results.append({
                    "title": i.get('title', ''), "link": i.get('link', ''),
                    "source": i.get('source', 'Serper News'), "pub_str": i.get('date', '歷史存檔'),
                    "raw_dt": parse_news_date(i.get('date', '')),
                    "is_white": check_white(i.get('link', ''), '', white_list),
                    "fetch_type": "serper_news"
                })
            time.sleep(0.3) # 參考 Lab Test 的緩衝
        except: break

    # 2. 全網補充包
    search_url = "https://google.serper.dev/search"
    try:
        res = requests.post(search_url, headers=headers, json={"q": search_q, "gl": gl, "hl": hl}, timeout=12).json()
        for i in res.get('organic', []):
            all_results.append({
                "title": i.get('title', ''), "link": i.get('link', ''),
                "source": "Google 網頁補充", "pub_str": "搜尋引擎索引",
                "raw_dt": datetime(2000, 1, 1, tzinfo=HKT),
                "is_white": check_white(i.get('link', ''), '', white_list),
                "fetch_type": "supplement"
            })
    except: pass
    return all_results

# ==================== 2. 社交挖掘封裝 ====================
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": f'query {{ search(input: {{key: "{query}", type: Article, first: 80}}) {{ edges {{ node {{ ... on Article {{ title shortHash summary author {{ displayName }} appreciationsReceivedTotal createdAt }} }} }} }} }}'}
    results = []
    try:
        response = requests.post(matters_api, json=query_json, timeout=12); data = response.json()
        edges = data.get('data', {}).get('search', {}).get('edges', [])
        for item in edges:
            n = item.get('node', {})
            if not n: continue
            dt = datetime.fromisoformat(n['createdAt'].replace('Z', '+00:00')).astimezone(HKT)
            results.append({
                "title": n.get('title', '無題'), "link": f"https://matters.town/a/{n['shortHash']}", 
                "author": n.get('author', {}).get('displayName', '未知作者'), 
                "likes": n.get('appreciationsReceivedTotal', 0), "summary": n.get('summary', ''), 
                "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Matters", "raw_dt": dt
            })
    except: pass
    return results

def fetch_bluesky(query):
    results = []
    try:
        client = Client(); client.login(BSKY_HANDLE, BSKY_PASSWORD)
        res = client.app.bsky.feed.search_posts(params={'q': query, 'limit': 80, 'sort': 'latest'}).posts
        for post in res:
            dt = datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00')).astimezone(HKT)
            results.append({
                "title": post.record.text[:80].replace('\n',' ') + "...", 
                "link": f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}", 
                "author": post.author.display_name or post.author.handle, 
                "likes": (post.like_count or 0), "summary": post.record.text, 
                "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Bluesky", "raw_dt": dt
            })
    except: pass
    return results

# ==================== 3. 主介面 UI ====================
st.set_page_config(page_title="全球 CitizensNews V13.5", layout="wide")

with st.sidebar:
    st.markdown("### 🌐 功能選單")
    app_mode = st.radio("請選擇模式：", ["新聞搜尋模式", "去中心化社交平台 Matters, Bluesky搜尋與分析"])

if "新聞搜尋" in app_mode:
    st.title("🌐 新聞搜尋模式 V13.5")
    if not serper_key: st.warning("⚠️ 系統未偵測到 `SERPER_API_KEY`。")
        
    region = st.radio("區域", ["香港媒體", "台灣/世界華文", "環球英文媒體", "中國大陸"], horizontal=True)
    query = st.text_input("關鍵字", placeholder="例如：李家超")
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
            
            # 抓取 RSS
            rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}+after:{start_date}+before:{end_date + timedelta(days=1)}&hl={hl}&gl={gl.upper()}&ceid={ceid}"
            articles_rss = fetch_rss_news(rss_url, start_hkt, end_hkt, white_list, region)
            
            # 抓取 Serper (Lab Test 版)
            articles_ext = fetch_serper_combined(query, start_date, end_date, gl, hl, white_list)
            st.session_state.serper_raw_count = len(articles_ext)
            
            # 去重複並優先保留來源資訊
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
        if not res: st.warning("⚠️ 此關鍵字沒有搜到相關新聞")
        else:
            white_count = sum(1 for x in res if x.get('is_white'))
            rss_count = sum(1 for x in res if x.get('fetch_type') == 'rss')
            serper_count = sum(1 for x in res if x.get('fetch_type') == 'serper_news')
            supp_count = sum(1 for x in res if x.get('fetch_type') == 'supplement')
            st.success(f"📊 **資料源診斷**：白名單: **{white_count}** ｜ RSS: **{rss_count}** (🔴) ｜ Serper: **{serper_count}** (🔼) (原始抓取:{st.session_state.serper_raw_count}) ｜ 補充包: **{supp_count}** (🌐) ｜ 總數: **{len(res)}**")

            if enable_news_ai:
                st.subheader("✨ 新聞輿情 AI 深度分析")
                ai_news_box = st.empty()
                with st.spinner("🤖 AI分析中..."):
                    try:
                        model = genai.GenerativeModel(available_model_path)
                        context = "\n".join([f"[{a['source']}] {a['title']}" for a in res[:25]])
                        safe = {cat: HarmBlockThreshold.BLOCK_NONE for cat in [HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, HarmCategory.HARM_CATEGORY_HARASSMENT]}
                        resp = model.generate_content(f"分析新聞：\n{context}", safety_settings=safe); ai_news_box.info(resp.text)
                    except: pass

            total_pages = (len(res)-1)//30+1
            start_idx = st.session_state.news_page * 30
            end_idx = min(start_idx + 30, len(res))
            curr_data = res[start_idx : end_idx]
            
            for n in curr_data:
                # V13.5 Icon: ✅ (白名單), 🔴 (RSS), 🔼 (Serper), 🌐 (補充)
                if n['is_white']: icon = "✅"
                elif n.get('fetch_type') == 'rss': icon = "🔴"
                elif n.get('fetch_type') == 'serper_news': icon = "🔼"
                elif n.get('fetch_type') == 'supplement': icon = "🌐"
                else: icon = "☑️"
                
                st.markdown(f"### {icon} [{n['title']}]({n['link']})")
                st.caption(f"{n['source']} | {n['pub_str']}")
                st.divider()
                
            st.write(f"顯示第 {start_idx + 1}-{end_idx} 則新聞 (第 {st.session_state.news_page+1} 頁 / 共 {total_pages} 頁)")
            c1, c2, _ = st.columns([1,1,4])
            if st.session_state.news_page > 0 and c1.button("⬅️ 上一頁"): st.session_state.news_page -= 1; st.rerun()
            if st.session_state.news_page < total_pages-1 and c2.button("下一頁 ➡️"): st.session_state.news_page += 1; st.rerun()

else:
    # ==================== 社交分析模式 (維持穩定邏輯) ====================
    st.title("🔵 社交平台深度搜尋與分析")
    col_i, col_t, col_s = st.columns([2, 1, 1])
    with col_i: s_query = st.text_input("搜尋關鍵字", key="s_input")
    with col_t: t_filter = st.selectbox("時間範圍", ["全部", "最近 24 小時", "最近 7 天"])
    with col_s: s_order = st.selectbox("排序方式", ["🕒 最新發布", "🔥 互動次數"])
    cur_s_params = (s_query, t_filter, s_order)

    if st.button("執行挖掘與 AI 分析", type="primary"):
        with st.status("🔄 正在搜尋中 ...", expanded=True) as status:
            raw = fetch_matters(s_query) + fetch_bluesky(s_query); now = datetime.now(HKT)
            filtered = [r for r in raw if not (t_filter == "最近 24 小時" and (now - r['raw_dt']) > timedelta(days=1)) and not (t_filter == "最近 7 天" and (now - r['raw_dt']) > timedelta(days=7))]
            st.session_state.social_results = sorted(filtered, key=lambda x: (x['likes'] if s_order == "🔥 互動次數" else x['raw_dt']), reverse=True)
            st.session_state.social_page = 0; st.session_state.last_social_params = cur_s_params; st.session_state.social_has_searched = True
            status.update(label="✅ 挖掘完成", state="complete"); st.rerun()

    if st.session_state.social_has_searched and st.session_state.last_social_params == cur_s_params:
        res = st.session_state.social_results
        if not res: st.warning("⚠️ 沒有搜尋到貼文。")
        else:
            ai_box = st.empty()
            with st.spinner("🤖 AI分析中..."):
                try:
                    model = genai.GenerativeModel(available_model_path)
                    context = "\n".join([f"{d['title']}" for d in res[:15]])
                    safe = {cat: HarmBlockThreshold.BLOCK_NONE for cat in [HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, HarmCategory.HARM_CATEGORY_HARASSMENT]}
                    response = model.generate_content(f"分析趨勢：\n{context}", safety_settings=safe); ai_box.info(response.text)
                except: pass
            
            start_idx = st.session_state.social_page * 30; end_idx = min(start_idx + 30, len(res))
            for item in res[start_idx : end_idx]:
                st.markdown(f"### [{item['title']}]({item['link']})")
                st.caption(f"作者: {item['author']} | 平台: **{item['platform']}** | ❤️ {item['likes']} | {item['published']}")
                st.write(item['summary'][:200] + "..."); st.divider()
            cc1, cc2, _ = st.columns([1,1,4])
            if st.session_state.social_page > 0 and cc1.button("⬅️ 上一頁 "): st.session_state.social_page -= 1; st.rerun()
            if st.session_state.social_page < (len(res)-1)//30 and cc2.button(" 下一頁 ➡️"): st.session_state.social_page += 1; st.rerun()
