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
 
# V14.2 對策：直接指定穩定模型名稱，解決 404 報錯
available_model_path = "gemini-1.5-flash"
if api_key:
    genai.configure(api_key=api_key)
 
BSKY_HANDLE = "bennysea97.bsky.social"
BSKY_PASSWORD = "7inu-hoaz-vlda-alvq"
 
# 初始化 Session State (還原 V14.0 完整狀態)
state_keys = ['news_results', 'news_page', 'social_results', 'social_page', 'last_social_params', 'social_has_searched', 'last_news_params']
for k in state_keys:
    if k not in st.session_state:
        st.session_state[k] = 0 if 'page' in k else ([] if 'results' in k else None)
 
# ==================== 1. 新聞引擎與黑白名單 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}
CN_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "caixin.com", "chinanews.com.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# V14.2 整合黑名單 (嚴格過濾)
HK_BLACK_LIST = {
    "tw.news.yahoo.com", "yahoo.com.tw", "taisounds.com", "newtalk.tw", "udn.com", 
    "storm.mg", "today.line.me", "people.com.cn", "beijing.gov.cn", "cna.com.tw", 
    "i-meihua.com", "ltn.com.tw", "msn.com", "setn.com", "ctinews.com", 
    "worldjournal.com", "cw.com.tw", "tdm.com.mo", "gvm.com.tw", "nownews.com", 
    "youtube.com", "sinchew.com.my", "macaodaily.com", "threads.net", "threads.com",
    "chinatimes.com", "turnnewsapp.com", "wikipedia.org", "zh.wikipedia.org", "zh-yue.wikipedia.org", "cctv.com"
}
 
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
    domains = []
    try: domains.append(urlparse(link).netloc.lower())
    except: pass
    if source_url:
        try: domains.append(urlparse(source_url).netloc.lower())
        except: pass
    for d in domains:
        for b in HK_BLACK_LIST:
            if b in d: return True
        if d.endswith(('.tw', '.cn', '.sg', '.mo', '.my')): return True
        if '.tw.' in d or '.cn.' in d: return True
    return False
 
def parse_news_date(date_str):
    try:
        if "前" in date_str or "ago" in date_str: return datetime.now(HKT)
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(tzinfo=HKT)
    except: return datetime(2000, 1, 1, tzinfo=HKT)
 
def fetch_rss_news(url, start_hkt, end_hkt, white_list, region):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try: dt_hkt = datetime.fromtimestamp(mktime(e.published_parsed)).replace(tzinfo=timezone.utc).astimezone(HKT)
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            link, source_url = e.get('link', ''), e.get('source', {}).get('href', '')
            if check_black(link, source_url, region): continue
            articles.append({
                "title": e.get('title', '').rsplit(" - ", 1)[0], "link": link, 
                "source": e.get('source', {}).get('title', 'Google News'), 
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"), "raw_dt": dt_hkt,
                "is_white": check_white(link, source_url, white_list), "fetch_type": "rss"
            })
    except: pass
    return articles
 
def fetch_serper_combined(query, start_date, end_date, gl, hl, white_list, region):
    if not serper_key: return []
    all_results = []
    headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
    search_q = f"{query} after:{start_date} before:{end_date + timedelta(days=1)}"
    
    # Serper News 抓取
    for page in range(1, 9):
        try:
            res = requests.post("https://google.serper.dev/news", headers=headers, json={"q": search_q, "gl": gl, "hl": hl, "page": page}, timeout=10).json()
            items = res.get('news', [])
            if not items: break
            for i in items:
                link = i.get('link', '')
                if check_black(link, '', region): continue
                all_results.append({
                    "title": i.get('title', ''), "link": link,
                    "source": i.get('source', 'Google Search'), 
                    "pub_str": i.get('date', '近期新聞'),
                    "raw_dt": parse_news_date(i.get('date', '')),
                    "is_white": check_white(link, '', white_list), "fetch_type": "serper_news"
                })
            time.sleep(0.5)
        except: break
 
    # Supplement 補充包
    try:
        res = requests.post("https://google.serper.dev/search", headers=headers, json={"q": search_q, "gl": gl, "hl": hl}, timeout=10).json()
        for i in res.get('organic', []):
            link = i.get('link', '')
            if check_black(link, '', region): continue
            # 修正：精確提取來源媒體名稱
            source_name = i.get('source')
            if not source_name:
                source_name = urlparse(link).netloc.replace('www.','')
            all_results.append({
                "title": i.get('title', ''), "link": link, 
                "source": source_name, 
                "pub_str": "Google 網頁索引",
                "raw_dt": datetime(2000, 1, 1, tzinfo=HKT),
                "is_white": check_white(link, '', white_list), "fetch_type": "supplement"
            })
    except: pass
    return all_results
 
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": f'query {{ search(input: {{key: "{query}", type: Article, first: 80}}) {{ edges {{ node {{ ... on Article {{ title shortHash summary author {{ displayName }} appreciationsReceivedTotal createdAt }} }} }} }} }}'}
    results = []
    try:
        res = requests.post(matters_api, json=query_json, timeout=12).json()
        edges = res.get('data', {}).get('search', {}).get('edges', [])
        for item in edges:
            n = item.get('node', {})
            dt = datetime.fromisoformat(n['createdAt'].replace('Z', '+00:00')).astimezone(HKT)
            results.append({
                "title": n.get('title', '無題'), "link": f"https://matters.town/a/{n['shortHash']}", 
                "author": n.get('author', {}).get('displayName', '未知'), "likes": n.get('appreciationsReceivedTotal', 0), 
                "summary": n.get('summary', ''), "published": dt.strftime("%Y-%m-%d %H:%M"), 
                "platform": "Matters", "raw_dt": dt
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
                "title": post.record.text[:80].replace('\n',' ') + "...", 
                "link": f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}", 
                "author": post.author.display_name or post.author.handle, 
                "likes": (post.like_count or 0), "summary": post.record.text, 
                "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Bluesky", "raw_dt": dt
            })
    except: pass
    return results
 
# ==================== 3. 主介面 UI ====================
st.set_page_config(page_title="全球 CitizensNews V14.2", layout="wide")
 
with st.sidebar:
    st.markdown("### 🌐 功能選單")
    app_mode = st.radio("請選擇模式：", ["新聞搜尋模式", "去中心化社交平台 Matters, Bluesky搜尋與分析"])
    if "去中心化社交平台" in app_mode:
        st.info("ℹ️ Matters, Bluesky是來自各地研究員、記者、評論員等，撰寫評論和分析的去中心化社交平台")
 
if "新聞搜尋" in app_mode:
    st.title("🌐 新聞搜尋模式 V14.2")
    region = st.radio("區域", ["香港媒體", "台灣/世界華文", "環球英文媒體", "中國大陸"], horizontal=True)
    query = st.text_input("關鍵字", placeholder="例如：李家超")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("開始", value=date.today() - timedelta(days=2))
    with col2: end_date = st.date_input("結束", value=date.today())
    enable_news_ai = st.toggle("🛡️ 開啟 AI 深度分析總結 (分析本次搜尋結果)", value=False)
 
    if st.button("搜尋", type="primary"):
        with st.status("🔄 正在搜尋中 ...", expanded=True) as status:
            if not query: st.stop()
            mapping = {"香港媒體": (HK_WHITE_LIST, "hk", "zh-hk", "HK:zh-Hant"), "台灣/世界華文": (TW_WHITE_LIST, "tw", "zh-tw", "TW:zh-Hant"), "環球英文媒體": (ENGLISH_GLOBAL_LIST, "us", "en", "US:en"), "中國大陸": (CN_WHITE_LIST, "cn", "zh-cn", "CN:zh-Hans")}
            white_list, gl, hl, ceid = mapping[region]
            start_hkt, end_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time())), HKT.localize(datetime.combine(end_date, datetime.max.time()))
            
            rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}+after:{start_date}+before:{end_date + timedelta(days=1)}&hl={hl}&gl={gl.upper()}&ceid={ceid}"
            articles = fetch_rss_news(rss_url, start_hkt, end_hkt, white_list, region) + fetch_serper_combined(query, start_date, end_date, gl, hl, white_list, region)
            
            unique = {a['link']: a for a in articles}
            st.session_state.news_results = sorted(unique.values(), key=lambda x: x["raw_dt"], reverse=True)
            st.session_state.news_page, st.session_state.last_news_params = 0, (query, region, start_date, end_date)
            status.update(label=f"✅ 挖掘完成！共獲取 {len(st.session_state.news_results)} 則結果", state="complete")
            st.rerun()
 
    if st.session_state.news_results is not None:
        res = st.session_state.news_results
        if not res: st.warning("⚠️ 此關鍵字沒有搜到相關新聞")
        else:
            st.success(f"📊 **資料源診斷**：✅白名單: **{sum(1 for x in res if x['is_white'])}** ｜ 🔴RSS: **{sum(1 for x in res if x['fetch_type']=='rss')}** ｜ 🔵Serper: **{sum(1 for x in res if x['fetch_type']=='serper_news')}** ｜ 🌐補充: **{sum(1 for x in res if x['fetch_type']=='supplement')}** ｜ 總數: **{len(res)}**")
 
            if enable_news_ai:
                st.subheader("✨ 新聞輿情 AI 深度分析")
                ai_news_box = st.empty()
                with st.spinner("🤖 AI正在閱讀資料和分析中..."):
                    try:
                        model = genai.GenerativeModel(available_model_path)
                        safe = [{"category": f"HARM_CATEGORY_{cat}", "threshold": "BLOCK_NONE"} for cat in ["HATE_SPEECH", "SEXUALLY_EXPLICIT", "DANGEROUS_CONTENT", "HARASSMENT"]]
                        resp = model.generate_content(f"請分析以下新聞報導的主要趨勢、各方觀點對比及核心事件整理：\n" + "\n".join([f"[{a['source']}] {a['title']}" for a in res[:25]]), safety_settings=safe)
                        ai_news_box.info(resp.text)
                    except Exception as e: ai_news_box.warning(f"⚠️ 新聞 AI 分析失效: {str(e)}")
 
            p_size = 30
            total_pages = (len(res)-1)//p_size+1
            curr_data = res[st.session_state.news_page*p_size : (st.session_state.news_page+1)*p_size]
            
            for n in curr_data:
                icon = "✅" if n['is_white'] else ("🔴" if n['fetch_type']=='rss' else ("🔵" if n['fetch_type']=='serper_news' else "🌐"))
                st.markdown(f"### {icon} [{n['title']}]({n['link']})")
                st.caption(f"{n['source']} | {n['pub_str']}")
                st.divider()
            
            # 還原：頁底分頁資訊
            st.write(f"顯示第 {st.session_state.news_page*p_size + 1}-{min((st.session_state.news_page+1)*p_size, len(res))} 則新聞 (第 {st.session_state.news_page+1} 頁 / 共 {total_pages} 頁，總數 {len(res)} 則)")
            c1, c2, _ = st.columns([1,1,4])
            if st.session_state.news_page > 0 and c1.button("⬅️ 上一頁"): st.session_state.news_page -= 1; st.rerun()
            if st.session_state.news_page < total_pages-1 and c2.button("下一頁 ➡️"): st.session_state.news_page += 1; st.rerun()
 
else:
    # ==================== 社交分析模式 (完全還原 V14.0) ====================
    st.title("🔵 社交平台深度搜尋與分析")
    col_i, col_t, col_s = st.columns([2, 1, 1])
    with col_i: s_query = st.text_input("搜尋關鍵字")
    with col_t: t_filter = st.selectbox("時間範圍", ["全部", "最近 24 小時", "最近 7 天"])
    with col_s: s_order = st.selectbox("排序方式", ["🕒 最新發布", "🔥 互動次數"])
 
    if st.button("執行挖掘與 AI 分析", type="primary"):
        with st.status("🔄 正在搜尋中 ...", expanded=True) as status:
            raw = fetch_matters(s_query) + fetch_bluesky(s_query)
            now = datetime.now(HKT)
            # 時間篩選邏輯
            filtered = [r for r in raw if not (t_filter == "最近 24 小時" and (now - r['raw_dt']) > timedelta(days=1)) and not (t_filter == "最近 7 天" and (now - r['raw_dt']) > timedelta(days=7))]
            # 排序邏輯
            st.session_state.social_results = sorted(filtered, key=lambda x: x['likes' if s_order == "🔥 互動次數" else 'raw_dt'], reverse=True)
            st.session_state.social_page, st.session_state.social_has_searched = 0, True
            status.update(label="✅ 挖掘完成", state="complete")
            st.rerun()
 
    if st.session_state.social_has_searched:
        res = st.session_state.social_results
        if not res: st.warning("⚠️ 沒有搜尋到相關貼文")
        else:
            st.subheader("✨ AI 趨勢分析")
            ai_box = st.empty()
            with st.spinner("🤖 AI正在分析中..."):
                try:
                    model = genai.GenerativeModel(available_model_path)
                    safe = [{"category": f"HARM_CATEGORY_{cat}", "threshold": "BLOCK_NONE"} for cat in ["HATE_SPEECH", "SEXUALLY_EXPLICIT", "DANGEROUS_CONTENT", "HARASSMENT"]]
                    resp = model.generate_content(f"請分析以下社交媒體動態的主要討論趨勢、情感傾向及核心關鍵字：\n" + "\n".join([f"{d['title']}" for d in res[:15]]), safety_settings=safe)
                    ai_box.info(resp.text)
                except Exception as e: ai_box.warning(f"⚠️ AI 分析暫時不可用 ({str(e)})")
            
            p_size = 30
            total_pages = (len(res)-1)//p_size+1
            for item in res[st.session_state.social_page*p_size : (st.session_state.social_page+1)*p_size]:
                st.markdown(f"### [{item['title']}]({item['link']})")
                st.caption(f"作者: {item['author']} | 平台: **{item['platform']}** | ❤️ {item['likes']} | {item['published']}")
                st.write(item['summary'][:250] + "...") # 還原 250 字摘要
                st.divider()
            
            # 還原：社交頁底分頁資訊
            st.write(f"顯示第 {st.session_state.social_page*p_size + 1}-{min((st.session_state.social_page+1)*p_size, len(res))} 則貼文 (第 {st.session_state.social_page+1} 頁 / 共 {total_pages} 頁)")
            cc1, cc2, _ = st.columns([1,1,4])
            if st.session_state.social_page > 0 and cc1.button("⬅️ 上一頁 "): st.session_state.social_page -= 1; st.rerun()
            if st.session_state.social_page < total_pages-1 and cc2.button(" 下一頁 ➡️"): st.session_state.social_page += 1; st.rerun()
