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

# 初始化 Gemini 模型
available_model_path = "gemini-1.5-flash"
if api_key:
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        matched = [m for m in models if '1.5-flash' in m]
        available_model_path = matched[0] if matched else (models[0] if models else "gemini-1.5-flash")
    except: pass

# ==================== 1. 白名單與歸類判定 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk", "greenbean.media"}
NAME_WHITE_LIST = {"香港電台", "RTHK", "明報", "星島日報", "東網", "on.cc", "HK01", "香港01", "綠豆", "Green Bean", "Now 新聞", "有線新聞", "南華早報", "SCMP", "信報", "集誌社"}

def is_white_list(url, source_name):
    domain = urlparse(url).netloc.lower()
    if any(white in domain for white in HK_WHITE_LIST): return True
    if any(name.lower() in str(source_name).lower() for name in NAME_WHITE_LIST): return True
    return False

# ==================== 2. 數據挖掘引擎 ====================
def fetch_rss_news(url, start_hkt, end_hkt):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt_hkt = datetime.fromtimestamp(mktime(e.published_parsed)).replace(tzinfo=timezone.utc).astimezone(HKT)
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            articles.append({
                "title": e.get('title', '').rsplit(" - ", 1)[0],
                "link": e.get('link', ''),
                "source": e.get('source', {}).get('title', 'Google News'),
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "raw_origin": "rss"
            })
    except: pass
    return articles

def fetch_serper_data(query, start_date, end_date, gl, hl, progress_bar):
    if not serper_key: return []
    results = []
    headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
    search_q = f"{query} after:{start_date} before:{end_date + timedelta(days=1)}"
    
    for page in range(1, 9): # 呼叫 8 次分頁，深度挖掘
        progress_bar.progress(page * 10, text=f"正在挖掘分頁 {page}/8 ...")
        try:
            res = requests.post("https://google.serper.dev/news", headers=headers, 
                                data=json.dumps({"q": search_q, "gl": gl, "hl": hl, "num": 10, "page": page}), timeout=10).json()
            items = res.get('news', [])
            if not items: break
            for i in items:
                results.append({"title": i.get('title', ''), "link": i.get('link', ''), "source": i.get('source', 'Serper News'), "pub_str": i.get('date', '近期'), "raw_origin": "serper_news"})
        except: break

    try:
        res = requests.post("https://google.serper.dev/search", headers=headers, 
                            data=json.dumps({"q": search_q, "gl": gl, "hl": hl}), timeout=10).json()
        for i in res.get('organic', []):
            results.append({"title": i.get('title', ''), "link": i.get('link', ''), "source": "Google 補充包", "pub_str": "網頁索引", "raw_origin": "google_organic"})
    except: pass
    return results

# ==================== 3. UI 主介面 ====================
st.set_page_config(page_title="全球 CitizensNews V13.15", layout="wide")

if 'news_results' not in st.session_state: st.session_state.news_results = []
if 'diag_data' not in st.session_state: st.session_state.diag_data = {}
if 'last_news_params' not in st.session_state: st.session_state.last_news_params = None

# --- Sidebar ---
with st.sidebar:
    app_mode = st.radio("功能導航", [
        "新聞搜尋模式", 
        "去中心化社交平台 Matters, Bluesky 深度搜尋"
    ])
    st.divider()
    if "社交平台" in app_mode:
        st.write("Matters, Bluesky 是各地研究員、記者、專業人士，撰寫分析評論的去中心化社交平台。")

# --- 主頁面 ---
if app_mode == "新聞搜尋模式":
    st.title("🌐 新聞搜尋深度挖掘引擎 V13.15")
    
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
            prog = st.progress(0, text="啟動挖掘引擎...")
            
            mapping = {"香港媒體": ("hk", "zh-hk", "HK:zh-Hant"), "台灣/世界華文": ("tw", "zh-tw", "TW:zh-Hant"), "環球英文媒體": ("us", "en", "US:en"), "中國大陸": ("cn", "zh-cn", "CN:zh-Hans")}
            gl, hl, ceid = mapping[region]
            
            rss_data = fetch_rss_news(f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={hl}&gl={gl.upper()}&ceid={ceid}", 
                                      HKT.localize(datetime.combine(start_date, datetime.min.time())), 
                                      HKT.localize(datetime.combine(end_date, datetime.max.time())))
            
            serper_data = fetch_serper_data(query, start_date, end_date, gl, hl, prog)
            
            # 去重與分類邏輯
            all_raw = rss_data + serper_data
            unique_news = {}
            diag = {"white": 0, "serper": 0, "extra": 0}
            for item in all_raw:
                url = item['link']
                if is_white_list(url, item['source']): final_type = "white"
                elif item.get('raw_origin') == "google_organic": final_type = "extra"
                else: final_type = "serper"
                
                if url not in unique_news or (final_type == "white" and unique_news[url].get('type') != "white"):
                    unique_news[url] = {**item, "type": final_type}

            for info in unique_news.values(): diag[info['type']] += 1
            st.session_state.news_results = sorted(unique_news.values(), key=lambda x: (x.get("type") != "white", x.get("type") == "extra"))
            st.session_state.diag_data = diag
            st.session_state.last_news_params = news_params
            
            prog.empty()
            status.update(label="✅ 挖掘任務完成", state="complete")
            st.rerun()

    # --- 顯示結果 (分頁邏輯) ---
    if st.session_state.last_news_params == news_params:
        all_res = st.session_state.news_results
        if not all_res:
            st.error("❌ 關鍵字搜尋沒有結果")
        else:
            d = st.session_state.diag_data
            st.success(f"📊 診斷數據｜ ✅ 白名單：{d.get('white',0)} ｜ 🔹 Serper：{d.get('serper',0)} ｜ 🌍 補充包：{d.get('extra',0)} ｜ 📈 總計：{len(all_res)} 則")

            # AI 分析
            if enable_news_ai:
                st.subheader("✨ 新聞輿情 AI 深度分析")
                try:
                    model = genai.GenerativeModel(available_model_path)
                    context = "\n".join([f"[{n.get('source')}] {n.get('title')}" for n in all_res[:30]])
                    safe = {cat: HarmBlockThreshold.BLOCK_NONE for cat in [HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, HarmCategory.HARM_CATEGORY_HARASSMENT]}
                    resp = model.generate_content(f"請分析以下新聞趨勢：\n{context}", safety_settings=safe)
                    st.info(resp.text)
                except: st.warning("⚠️ AI 分析暫時不可用")

            # --- 30 則分頁器 ---
            items_per_page = 30
            total_pages = (len(all_res) - 1) // items_per_page + 1
            
            st.write("---")
            page_num = st.select_slider("請滑動選擇頁碼", options=range(1, total_pages + 1), value=1)
            
            start_idx = (page_num - 1) * items_per_page
            end_idx = start_idx + items_per_page
            current_page_res = all_res[start_idx:end_idx]

            st.caption(f"📍 正在顯示第 {page_num} 頁 (第 {start_idx+1} - {min(end_idx, len(all_res))} 則)")

            for n in current_page_res:
                n_type = n.get('type', 'extra')
                icon = "✅" if n_type == "white" else ("🔹" if n_type == "serper" else "🌍")
                st.markdown(f"### {icon} [{n.get('title')}]({n.get('link')})")
                st.caption(f"{n.get('source')} | {n.get('pub_str')}")
                st.divider()

            if total_pages > 1:
                st.center(f"第 {page_num} 頁 / 共 {total_pages} 頁")

else:
    st.title("🛡️ 社交平台深度搜尋")
    st.write("此處運行 Matters 與 Bluesky 的搜尋邏輯...")