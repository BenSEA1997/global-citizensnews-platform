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
    
    for page in range(1, 9):
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
st.set_page_config(page_title="全球 CitizensNews V13.9", layout="wide")

# 初始化 Session State
state_keys = ['news_results', 'diag_data', 'last_news_params']
for k in state_keys:
    if k not in st.session_state:
        st.session_state[k] = [] if 'results' in k else ({} if 'diag' in k else None)

# --- Sidebar: 模式切換與平台介紹 ---
with st.sidebar:
    st.title("🚀 CitizensNews")
    app_mode = st.radio("功能導航", ["新聞搜尋模式", "去中心化社交平台搜尋"])
    st.divider()
    if "社交平台" in app_mode:
        st.markdown("### 📚 平台介紹")
        st.info("**Matters**: 基於 Web3 的去中心化寫作社區，強調創作自由與內容永存。")
        st.info("**Bluesky**: 由 Twitter 創辦人發起的去中心化社交網絡，採用 AT 協議。")
    else:
        st.markdown("🔍 **新聞搜尋系統**：整合 Google RSS, Serper 深度挖掘與白名單過濾機制。")

# --- 主頁面 ---
if app_mode == "新聞搜尋模式":
    st.title("🌐 新聞搜尋深度挖掘引擎 V13.9")
    
    # 地區選擇移至標題下方
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
            
            rss_data = fetch_rss_news(f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={hl}&gl={gl.upper()}&ceid={ceid}", 
                                      HKT.localize(datetime.combine(start_date, datetime.min.time())), 
                                      HKT.localize(datetime.combine(end_date, datetime.max.time())))
            
            serper_data = fetch_serper_data(query, start_date, end_date, gl, hl, prog)
            
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
            
            prog.progress(100, text="挖掘完成！")
            time.sleep(0.5)
            prog.empty()
            status.update(label="✅ 挖掘任務已完成", state="complete")
            st.rerun()

    if st.session_state.last_news_params == news_params:
        res = st.session_state.news_results
        if not res:
            st.error("❌ 關鍵字搜尋沒有結果")
        else:
            d = st.session_state.diag_data
            st.success(f"📊 **診斷數據測試**｜ ✅ 白名單：{d.get('white', 0)} 則 ｜ 🔹 Serper：{d.get('serper', 0)} 則 ｜ 🌍 補充包：{d.get('extra', 0)} 則 ｜ 📈 總數：{len(res)} 則")

            if enable_news_ai:
                st.subheader("✨ 新聞輿情 AI 深度分析")
                try:
                    model = genai.GenerativeModel(available_model_path)
                    context = "\n".join([f"[{n.get('source')}] {n.get('title')}" for n in res[:30]])
                    safe = {cat: HarmBlockThreshold.BLOCK_NONE for cat in [HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, HarmCategory.HARM_CATEGORY_HARASSMENT]}
                    resp = model.generate_content(f"分析以下新聞趨勢：\n{context}", safety_settings=safe)
                    st.info(resp.text)
                except: st.warning("⚠️ AI 分析暫時不可用")

            for n in res:
                n_type = n.get('type', 'extra')
                icon = "✅" if n_type == "white" else ("🔹" if n_type == "serper" else "🌍")
                st.markdown(f"### {icon} [{n.get('title', '無標題')}]({n.get('link', '#')})")
                st.caption(f"{n.get('source', '未知來源')} | {n.get('pub_str', '未知時間')}")
                st.divider()

else:
    # 社交平台搜尋模式 (維持原有邏輯)
    st.title("🔵 社交平台深度搜尋")
    st.write("此處為 Matters 與 Bluesky 搜尋界面...")
    # (此處省略社交平台具體實作，與 V13.2 保持一致)