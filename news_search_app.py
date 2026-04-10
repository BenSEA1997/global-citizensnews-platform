import streamlit as st
import feedparser
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import urlparse, quote_plus
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import requests
import json
import time

# ==================== 0. 核心配置 ====================
HKT = pytz.timezone('Asia/Hong_Kong')

def get_secret(key):
    return st.secrets.get(key)

api_key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")
serper_key = get_secret("SERPER_API_KEY")

# 初始化 Gemini
available_model_path = "gemini-1.5-flash"
if api_key:
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        matched = [m for m in models if '1.5-flash' in m]
        available_model_path = matched[0] if matched else (models[0] if models else "gemini-1.5-flash")
    except: pass

# ==================== 1. 白名單 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk", "greenbean.media"}
NAME_WHITE_LIST = {"香港電台", "RTHK", "明報", "星島日報", "東網", "on.cc", "HK01", "香港01", "綠豆", "Green Bean", "Now 新聞", "有線新聞", "南華早報", "SCMP", "信報", "集誌社"}

def is_white_list(url, source_name):
    domain = urlparse(url).netloc.lower()
    if any(white in domain for white in HK_WHITE_LIST): return True
    if any(name.lower() in str(source_name).lower() for name in NAME_WHITE_LIST): return True
    return False

# ==================== 2. 引擎 (抓取 8 頁) ====================
def fetch_rss_news(url, start_hkt, end_hkt):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt_hkt = datetime.fromtimestamp(mktime(e.published_parsed)).replace(tzinfo=timezone.utc).astimezone(HKT)
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            articles.append({"title": e.get('title', '').rsplit(" - ", 1)[0], "link": e.get('link', ''), "source": e.get('source', {}).get('title', 'Google News'), "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"), "raw_origin": "rss"})
    except: pass
    return articles

def fetch_serper_data(query, start_date, end_date, gl, hl, progress_bar):
    if not serper_key: return []
    results = []
    headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
    search_q = f"{query} after:{start_date} before:{end_date + timedelta(days=1)}"
    for page in range(1, 9):
        progress_bar.progress(page * 10, text=f"正在挖掘資料中 ... ({page}/8)")
        try:
            res = requests.post("https://google.serper.dev/news", headers=headers, data=json.dumps({"q": search_q, "gl": gl, "hl": hl, "num": 10, "page": page}), timeout=10).json()
            items = res.get('news', [])
            if not items: break
            for i in items:
                results.append({"title": i.get('title', ''), "link": i.get('link', ''), "source": i.get('source', 'Serper News'), "pub_str": i.get('date', '近期'), "raw_origin": "serper_news"})
        except: break
    return results

# ==================== 3. UI 主介面 ====================
st.set_page_config(page_title="全球 CitizensNews V13.17", layout="wide")

# 初始化 Session State
if 'news_results' not in st.session_state: st.session_state.news_results = []
if 'diag_data' not in st.session_state: st.session_state.diag_data = {}
if 'last_news_params' not in st.session_state: st.session_state.last_news_params = None
if 'current_page' not in st.session_state: st.session_state.current_page = 1

with st.sidebar:
    app_mode = st.radio("功能導航", ["新聞搜尋模式", "去中心化社交平台 Matters, Bluesky 深度搜尋"])
    st.divider()
    if "社交平台" in app_mode:
        st.write("Matters, Bluesky 是各地研究員、記者、專業人士，撰寫分析評論的去中心化社交平台。")

if app_mode == "新聞搜尋模式":
    st.title("🌐 新聞搜尋深度挖掘引擎 V13.17")
    region = st.radio("請選擇搜尋區域", ["香港媒體", "台灣/世界華文", "環球英文媒體", "中國大陸"], horizontal=True)
    query = st.text_input("關鍵字", placeholder="例如：李家超")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("開始", value=date.today() - timedelta(days=2))
    with col2: end_date = st.date_input("結束", value=date.today())
    enable_news_ai = st.toggle("🛡️ 開啟 AI 深度分析總結", value=False)
    news_params = (query, region, start_date, end_date)

    if st.button("執行新聞挖掘與分析", type="primary"):
        with st.status("正在挖掘資料中 ...", expanded=True) as status:
            if not query: st.warning("請輸入關鍵字"); st.stop()
            prog = st.progress(0, text="準備啟動引擎...")
            mapping = {"香港媒體": ("hk", "zh-hk", "HK:zh-Hant"), "台灣/世界華文": ("tw", "zh-tw", "TW:zh-Hant"), "環球英文媒體": ("us", "en", "US:en"), "中國大陸": ("cn", "zh-cn", "CN:zh-Hans")}
            gl, hl, ceid = mapping[region]
            
            rss_data = fetch_rss_news(f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={hl}&gl={gl.upper()}&ceid={ceid}", HKT.localize(datetime.combine(start_date, datetime.min.time())), HKT.localize(datetime.combine(end_date, datetime.max.time())))
            serper_data = fetch_serper_data(query, start_date, end_date, gl, hl, prog)
            
            unique_news = {}
            for item in rss_data + serper_data:
                url = item['link']
                final_type = "white" if is_white_list(url, item['source']) else "serper"
                if url not in unique_news or (final_type == "white" and unique_news[url].get('type') != "white"):
                    unique_news[url] = {**item, "type": final_type}

            st.session_state.news_results = sorted(unique_news.values(), key=lambda x: (x.get("type") != "white"))
            st.session_state.last_news_params = news_params
            st.session_state.current_page = 1 # 每次新搜尋重置回第一頁
            prog.empty()
            status.update(label="✅ 挖掘完成", state="complete")
            st.rerun()

    if st.session_state.last_news_params == news_params:
        all_res = st.session_state.news_results
        if not all_res:
            st.error("❌ 關鍵字搜尋沒有結果")
        else:
            items_per_page = 30
            total_pages = (len(all_res) - 1) // items_per_page + 1
            
            # --- 分頁內容呈現 ---
            curr_p = st.session_state.current_page
            start_idx = (curr_p - 1) * items_per_page
            current_page_res = all_res[start_idx : start_idx + items_per_page]

            st.write(f"📊 總計：{len(all_res)} 則新聞 ｜ 當前顯示第 {curr_p} / {total_pages} 頁")
            st.divider()

            for n in current_page_res:
                icon = "✅" if n.get('type') == "white" else "🔹"
                st.markdown(f"### {icon} [{n.get('title')}]({n.get('link')})")
                st.caption(f"{n.get('source')} | {n.get('pub_str')}")
                st.divider()

            # --- 底部翻頁按鈕 ---
            btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
            
            with btn_col1:
                if curr_p > 1:
                    if st.button("⬅️ 上一頁"):
                        st.session_state.current_page -= 1
                        st.rerun()
            
            with btn_col2:
                st.markdown(f"<p style='text-align: center; color: gray;'>第 {curr_p} 頁 / 共 {total_pages} 頁</p>", unsafe_allow_html=True)
            
            with btn_col3:
                if curr_p < total_pages:
                    if st.button("下一頁 ➡️"):
                        st.session_state.current_page += 1
                        st.rerun()

else:
    st.title("🛡️ 社交平台深度搜尋")
    st.write("運行中...")