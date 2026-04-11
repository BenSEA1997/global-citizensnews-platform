import streamlit as st
import feedparser
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
state_keys = ['news_results', 'news_page', 'social_results', 'social_page', 'last_social_params', 'social_has_searched', 'last_news_params']
for k in state_keys:
    if k not in st.session_state:
        st.session_state[k] = 0 if 'page' in k else ([] if 'results' in k else None)
 
# ==================== 1. 新聞引擎與黑白名單 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}
CN_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "caixin.com", "chinanews.com.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

# V14.1 嚴格黑名單 (含維基、央視、Threads 等)
HK_BLACK_LIST = {
    "tw.news.yahoo.com", "yahoo.com.tw", "taisounds.com", "newtalk.tw", "udn.com", 
    "storm.mg", "today.line.me", "people.com.cn", "beijing.gov.cn", "cna.com.tw", 
    "i-meihua.com", "ltn.com.tw", "msn.com", "setn.com", "ctinews.com", 
    "worldjournal.com", "cw.com.tw", "tdm.com.mo", "gvm.com.tw", "nownews.com", 
    "youtube.com", "sinchew.com.my", "macaodaily.com", "threads.net", "threads.com",
    "chinatimes.com", "turnnewsapp.com", "wikipedia.org", "cctv.com"
}
 
def check_white(link, source_url, white_list):
    domains = [urlparse(link).netloc.lower()]
    if source_url: domains.append(urlparse(source_url).netloc.lower())
    return any(any(w in d for d in domains) for w in white_list)

def check_black(link, source_url, region):
    if region != "香港媒體": return False
    domains = [urlparse(link).netloc.lower()]
    if source_url: domains.append(urlparse(source_url).netloc.lower())
    for d in domains:
        if any(b in d for b in HK_BLACK_LIST): return True
        if d.endswith(('.tw', '.cn', '.sg', '.mo')) or '.tw.' in d or '.cn.' in d: return True
    return False
 
def parse_news_date(date_str):
    if "前" in date_str or "ago" in date_str: return datetime.now(HKT)
    try: return datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(tzinfo=HKT)
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
                "source": e.get('source', {}).get('title', 'Google News RSS'), 
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
    
    # News Search
    for page in range(1, 9):
        try:
            res = requests.post("https://google.serper.dev/news", headers=headers, json={"q": search_q, "gl": gl, "hl": hl, "page": page}, timeout=10).json()
            items = res.get('news', [])
            if not items: break
            for i in items:
                if check_black(i.get('link', ''), '', region): continue
                all_results.append({
                    "title": i.get('title', ''), "link": i.get('link', ''),
                    "source": i.get('source', 'Google Search'), "pub_str": i.get('date', '歷史存檔'),
                    "raw_dt": parse_news_date(i.get('date', '')),
                    "is_white": check_white(i.get('link', ''), '', white_list), "fetch_type": "serper_news"
                })
            time.sleep(0.5)
        except: break
    # Supplement
    try:
        res = requests.post("https://google.serper.dev/search", headers=headers, json={"q": search_q, "gl": gl, "hl": hl}, timeout=10).json()
        for i in res.get('organic', []):
            if not check_black(i.get('link', ''), '', region):
                all_results.append({
                    "title": i.get('title', ''), "link": i.get('link', ''), "source": "Google 網頁補充", "pub_str": "搜尋引擎索引",
                    "raw_dt": datetime(2000, 1, 1, tzinfo=HKT), "is_white": check_white(i.get('link', ''), '', white_list), "fetch_type": "supplement"
                })
    except: pass
    return all_results
 
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": f'query {{ search(input: {{key: "{query}", type: Article, first: 80}}) {{ edges {{ node {{ ... on Article {{ title shortHash summary author {{ displayName }} appreciationsReceivedTotal createdAt }} }} }} }} }}'}
    results = []
    try:
        data = requests.post(matters_api, json=query_json, timeout=12).json()
        for item in data.get('data', {}).get('search', {}).get('edges', []):
            n = item.get('node', {})
            dt = datetime.fromisoformat(n['createdAt'].replace('Z', '+00:00')).astimezone(HKT)
            results.append({"title": n.get('title', '無題'), "link": f"https://matters.town/a/{n['shortHash']}", "author": n.get('author', {}).get('displayName', '未知'), "likes": n.get('appreciationsReceivedTotal', 0), "summary": n.get('summary', ''), "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Matters", "raw_dt": dt})
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
 
# ==================== 3. 主介面 ====================
st.set_page_config(page_title="全球 CitizensNews V14.1", layout="wide")
app_mode = st.sidebar.radio("請選擇模式：", ["新聞搜尋模式", "去中心化社交平台搜尋與分析"])
 
if "新聞搜尋" in app_mode:
    st.title("🌐 新聞搜尋模式 V14.1")
    region = st.radio("區域", ["香港媒體", "台灣/世界華文", "環球英文媒體", "中國大陸"], horizontal=True)
    query = st.text_input("關鍵字", placeholder="例如：李家超")
    c1, c2 = st.columns(2)
    start_date = c1.date_input("開始", value=date.today() - timedelta(days=2))
    end_date = c2.date_input("結束", value=date.today())
    enable_news_ai = st.toggle("🛡️ 開啟 AI 深度分析總結", value=False)
 
    if st.button("搜尋", type="primary"):
        with st.status("🔄 挖掘中...", expanded=True) as status:
            if not query: st.stop()
            mapping = {"香港媒體": (HK_WHITE_LIST, "hk", "zh-hk", "HK:zh-Hant"), "台灣/世界華文": (TW_WHITE_LIST, "tw", "zh-tw", "TW:zh-Hant"), "環球英文媒體": (ENGLISH_GLOBAL_LIST, "us", "en", "US:en"), "中國大陸": (CN_WHITE_LIST, "cn", "zh-cn", "CN:zh-Hans")}
            white_list, gl, hl, ceid = mapping[region]
            start_hkt, end_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time())), HKT.localize(datetime.combine(end_date, datetime.max.time()))
            rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}+after:{start_date}+before:{end_date + timedelta(days=1)}&hl={hl}&gl={gl.upper()}&ceid={ceid}"
            res_all = fetch_rss_news(rss_url, start_hkt, end_hkt, white_list, region) + fetch_serper_combined(query, start_date, end_date, gl, hl, white_list, region)
            unique = {a['link']: a for a in res_all}
            st.session_state.news_results = sorted(unique.values(), key=lambda x: x["raw_dt"], reverse=True)
            st.session_state.news_page, st.session_state.last_news_params = 0, (query, region, start_date, end_date)
            status.update(label=f"✅ 完成！共 {len(st.session_state.news_results)} 則", state="complete")
            st.rerun()
 
    if st.session_state.news_results is not None:
        res = st.session_state.news_results
        if res:
            st.success(f"📊 ✅白名單:{sum(1 for x in res if x['is_white'])} ｜ 🔴RSS:{sum(1 for x in res if x['fetch_type']=='rss')} ｜ 🔵Serper:{sum(1 for x in res if x['fetch_type']=='serper_news')} ｜ 🌐補充:{sum(1 for x in res if x['fetch_type']=='supplement')} ｜ 總計:{len(res)}")
            if enable_news_ai:
                ai_news_box = st.empty()
                with st.spinner("🤖 AI 分析中..."):
                    try:
                        model = genai.GenerativeModel(available_model_path)
                        safe = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
                        resp = model.generate_content(f"請分析以下報導趨勢及觀點：\n" + "\n".join([f"[{a['source']}] {a['title']}" for a in res[:25]]), safety_settings=safe)
                        ai_news_box.info(resp.text)
                    except Exception as e: ai_news_box.warning(f"⚠️ AI 分析不可用: {str(e)}")
            
            p_size = 30
            total_p = (len(res)-1)//p_size+1
            for n in res[st.session_state.news_page*p_size : (st.session_state.news_page+1)*p_size]:
                icon = "✅" if n['is_white'] else ("🔴" if n['fetch_type']=='rss' else ("🔵" if n['fetch_type']=='serper_news' else "🌐"))
                st.markdown(f"### {icon} [{n['title']}]({n['link']})")
                st.caption(f"{n['source']} | {n['pub_str']}")
                st.divider()
            
            c1, c2, _ = st.columns([1,1,4])
            if st.session_state.news_page > 0 and c1.button("⬅️ 上一頁"): st.session_state.news_page -= 1; st.rerun()
            if st.session_state.news_page < total_p-1 and c2.button("下一頁 ➡️"): st.session_state.news_page += 1; st.rerun()
 
else:
    st.title("🔵 社交平台深度分析")
    s_query = st.text_input("搜尋關鍵字")
    t_filter = st.selectbox("時間範圍", ["全部", "最近 24 小時", "最近 7 天"])
    s_order = st.selectbox("排序方式", ["🕒 最新發布", "🔥 互動次數"])
 
    if st.button("執行挖掘與 AI 分析", type="primary"):
        with st.status("🔄 搜尋中...", expanded=True) as status:
            raw = fetch_matters(s_query) + fetch_bluesky(s_query)
            now = datetime.now(HKT)
            filtered = [r for r in raw if not (t_filter == "最近 24 小時" and (now - r['raw_dt']) > timedelta(days=1)) and not (t_filter == "最近 7 天" and (now - r['raw_dt']) > timedelta(days=7))]
            st.session_state.social_results = sorted(filtered, key=lambda x: x['likes' if s_order == "🔥 互動次數" else 'raw_dt'], reverse=True)
            st.session_state.social_page, st.session_state.social_has_searched = 0, True
            status.update(label="✅ 完成", state="complete")
            st.rerun()
 
    if st.session_state.social_has_searched:
        res = st.session_state.social_results
        if res:
            ai_box = st.empty()
            with st.spinner("🤖 AI 分析中..."):
                try:
                    model = genai.GenerativeModel(available_model_path)
                    safe = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
                    response = model.generate_content(f"請分析討論趨勢及關鍵字：\n" + "\n".join([f"{d['title']}" for d in res[:20]]), safety_settings=safe)
                    ai_box.info(response.text)
                except Exception as e: ai_box.warning(f"⚠️ AI 暫時不可用 ({str(e)})")
            
            for item in res[st.session_state.social_page*30 : (st.session_state.social_page+1)*30]:
                st.markdown(f"### [{item['title']}]({item['link']})")
                st.caption(f"{item['author']} | {item['platform']} | ❤️ {item['likes']} | {item['published']}")
                st.write(item['summary'][:200] + "...")
                st.divider()
            cc1, cc2, _ = st.columns([1,1,4])
            if st.session_state.social_page > 0 and cc1.button("⬅️ 上一頁 "): st.session_state.social_page -= 1; st.rerun()
            if st.session_state.social_page < (len(res)-1)//30 and cc2.button(" 下一頁 ➡️"): st.session_state.social_page += 1; st.rerun()
