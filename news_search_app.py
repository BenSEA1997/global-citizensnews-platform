import streamlit as st
import feedparser
from datetime import datetime, date, timedelta, timezone
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
state_keys = ['news_results', 'news_page', 'social_results', 'social_page', 'last_social_params', 'social_has_searched', 'last_news_params', 'diag_data']
for k in state_keys:
    if k not in st.session_state:
        st.session_state[k] = 0 if 'page' in k else ({} if k == 'diag_data' else ([] if 'results' in k else None))

# ==================== 1. 新聞引擎與歸類邏輯 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk", "greenbean.media"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}
CN_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "caixin.com", "chinanews.com.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

def get_domain(link):
    try:
        domain = urlparse(link).netloc.lower()
        if domain.startswith("www."): domain = domain[4:]
        return domain
    except: return ""

def fetch_rss_news(url, start_hkt, end_hkt, white_list):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt_hkt = datetime.fromtimestamp(mktime(e.published_parsed)).replace(tzinfo=timezone.utc).astimezone(HKT)
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            link = e.get('link', '')
            articles.append({
                "title": e.get('title', '').rsplit(" - ", 1)[0], "link": link, 
                "source": e.get('source', {}).get('title', 'Google News'), 
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"), 
                "raw_type": "rss"
            })
    except: pass
    return articles

def fetch_serper_combined(query, start_date, end_date, gl, hl):
    if not serper_key: return []
    combined = []
    headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
    search_q = f"{query} after:{start_date} before:{end_date + timedelta(days=1)}"
    
    # 1. Serper News (8頁)
    for page in range(1, 9):
        try:
            res = requests.post("https://google.serper.dev/news", headers=headers, 
                                data=json.dumps({"q": search_q, "gl": gl, "hl": hl, "num": 10, "page": page}), timeout=10).json()
            items = res.get('news', [])
            if not items: break
            for i in items:
                combined.append({
                    "title": i.get('title', ''), "link": i.get('link', ''),
                    "source": i.get('source', 'Serper News'), "pub_str": i.get('date', '近期'),
                    "raw_type": "serper"
                })
        except: break

    # 2. Google Organic (補充包)
    try:
        res = requests.post("https://google.serper.dev/search", headers=headers, 
                            data=json.dumps({"q": search_q, "gl": gl, "hl": hl}), timeout=10).json()
        for i in res.get('organic', []):
            combined.append({
                "title": i.get('title', ''), "link": i.get('link', ''),
                "source": "Google 補充包", "pub_str": "搜尋索引",
                "raw_type": "extra"
            })
    except: pass
    return combined

# ==================== 2. 主介面 UI ====================
st.set_page_config(page_title="全球 CitizensNews V13.4", layout="wide")

if "新聞搜尋模式" in st.sidebar.radio("模式", ["新聞搜尋模式", "去中心化社交平台 Matters, Bluesky搜尋與分析"], label_visibility="collapsed"):
    st.title("🌐 新聞搜尋深度挖掘引擎 V13.4")
    region = st.radio("區域", ["香港媒體", "台灣/世界華文", "環球英文媒體", "中國大陸"], horizontal=True)
    query = st.text_input("關鍵字", placeholder="例如：李家超")
    
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("開始", value=date.today() - timedelta(days=2))
    with col2: end_date = st.date_input("結束", value=date.today())
    
    enable_news_ai = st.toggle("🛡️ 開啟 AI 深度分析總結", value=False)
    news_params = (query, region, start_date, end_date)

    if st.button("執行新聞挖掘與分析", type="primary"):
        with st.status("正在挖掘資料中 ...", expanded=True) as status:
            if not query: st.stop()
            mapping = {"香港媒體": (HK_WHITE_LIST, "hk", "zh-hk", "HK:zh-Hant"), "台灣/世界華文": (TW_WHITE_LIST, "tw", "zh-tw", "TW:zh-Hant"), "環球英文媒體": (ENGLISH_GLOBAL_LIST, "us", "en", "US:en"), "中國大陸": (CN_WHITE_LIST, "cn", "zh-cn", "CN:zh-Hans")}
            white_list, gl, hl, ceid = mapping[region]
            
            # 抓取
            rss_res = fetch_rss_news(f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={hl}&gl={gl.upper()}&ceid={ceid}", 
                                     HKT.localize(datetime.combine(start_date, datetime.min.time())), 
                                     HKT.localize(datetime.combine(end_date, datetime.max.time())), white_list)
            serper_res = fetch_serper_combined(query, start_date, end_date, gl, hl)
            
            # 核心修正：統一去重與重新標籤
            unique = {}
            diag = {"white": 0, "serper": 0, "extra": 0}
            
            for item in (rss_res + serper_res):
                url = item['link']
                domain = get_domain(url)
                
                # 決定最終身份 (白名單優先)
                if domain in white_list:
                    final_type = "white"
                else:
                    final_type = "serper" if item['raw_type'] in ["serper", "rss"] else "extra"
                
                # 如果 URL 重複，保留白名單身份
                if url not in unique or (final_type == "white" and unique[url]['final_type'] != "white"):
                    unique[url] = {**item, "final_type": final_type}

            # 統計數據
            for info in unique.values(): diag[info['final_type']] += 1
            
            st.session_state.news_results = sorted(unique.values(), key=lambda x: (x["final_type"] != "white", x["final_type"] == "extra"))
            st.session_state.diag_data = diag
            st.session_state.news_page = 0
            st.session_state.last_news_params = news_params
            status.update(label="✅ 挖掘完成！", state="complete")
            st.rerun()

    if st.session_state.news_results and st.session_state.last_news_params == news_params:
        d = st.session_state.diag_data
        st.success(f"📊 **診斷數據測試**｜ ✅ 白名單：{d['white']} 則 ｜ 🔹 Serper：{d['serper']} 則 ｜ 🌍 補充包：{d['extra']} 則 ｜ 📈 總數：{sum(d.values())} 則")

        if enable_news_ai:
            st.subheader("✨ 新聞輿情 AI 深度分析")
            try:
                model = genai.GenerativeModel(available_model_path)
                context = "\n".join([f"[{n['source']}] {n['title']}" for n in st.session_state.news_results[:30]])
                resp = model.generate_content(f"請分析以下新聞趨勢：\n{context}")
                st.info(resp.text)
            except: st.warning("AI 分析暫時不可用")

        res = st.session_state.news_results
        curr_data = res[st.session_state.news_page*30 : (st.session_state.news_page+1)*30]
        for n in curr_data:
            icon = "✅" if n['final_type'] == "white" else ("🔹" if n['final_type'] == "serper" else "🌍")
            st.markdown(f"### {icon} [{n['title']}]({n['link']})")
            st.caption(f"{n['source']} | {n['pub_str']}")
            st.divider()
        
        tp = (len(res)-1)//30+1
        c1, c2, _ = st.columns([1,1,4])
        if st.session_state.news_page > 0 and c1.button("⬅️ 上一頁"): st.session_state.news_page -= 1; st.rerun()
        if st.session_state.news_page < tp-1 and c2.button("下一頁 ➡️"): st.session_state.news_page += 1; st.rerun()