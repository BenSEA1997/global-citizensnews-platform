import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 媒體名稱判定清單 (解決加密連結問題) ====================
# 使用媒體在 Google News 顯示的名稱進行比對
HK_NAME_WHITE_LIST = ["RTHK", "香港電台", "Now 新聞", "點新聞", "巴士的報", "星島日報", "東網", "on.cc", "文匯報", "大公報", "香港01", "HK01", "明報", "信報", "南華早報", "SCMP", "無線新聞", "TVB News", "經濟日報", "hket", "阿思達克", "雅虎香港", "Yahoo", "橙新聞", "獨立媒體", "香港政府新聞網"]
TW_NAME_WHITE_LIST = ["中央通訊社", "CNA", "自由時報", "中時新聞網", "聯合新聞網", "udn", "ETtoday", "TVBS", "三立新聞", "風傳媒", "關鍵評論網", "中廣新聞網", "華視", "民視", "台視"]
ENGLISH_NAME_WHITE_LIST = ["Reuters", "BBC", "AP News", "Bloomberg", "Financial Times", "FT", "The Guardian", "Washington Post", "New York Times", "NYT", "Wall Street Journal", "WSJ", "CNN", "ABC News", "NBC News", "Sky News"]

# 地區黑名單 (名稱包含即剔除)
HK_NAME_BLACKLIST = ["RTHK", "香港電台", "Now 新聞", "點新聞", "巴士的報", "星島", "文匯", "大公", "香港01", "HK01", "明報", "信報", "南華早報", "SCMP", "無線新聞", "TVB", "經濟日報", "hket", "雅虎香港", "Yahoo", "橙新聞", "獨立媒體", "香港政府新聞"]
TW_NAME_BLACKLIST = ["中央通訊社", "CNA", "自由時報", "中時新聞網", "聯合新聞網", "udn", "ETtoday", "TVBS", "三立新聞", "風傳媒", "關鍵評論", "中廣新聞", "華視", "民視", "台視"]

# ==================== 2. 工具函數 ====================
def to_hkt_aware(dt_obj):
    if dt_obj.tzinfo is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj.astimezone(HKT)

def clean_summary(text):
    if not text: return ""
    return re.sub(r'<[^>]+>', ' ', text).replace('&nbsp;', ' ').strip()

def fetch_google_news(url, start_hkt, end_hkt, keywords):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt = datetime.fromtimestamp(mktime(e.published_parsed))
                dt_hkt = to_hkt_aware(dt)
            except: continue
            
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            
            full_title = e.get('title', '')
            # 拆分標題與來源 (Google News 標準格式: 標題 - 來源)
            parts = full_title.rsplit(" - ", 1)
            main_title = parts[0] if len(parts) > 1 else full_title
            source_name = parts[1] if len(parts) > 1 else "未知來源"
            
            summary = clean_summary(e.get('summary', ''))
            full_content = (main_title + " " + summary).lower()
            
            # 多關鍵字 AND 邏輯判定
            if not all(k.lower() in full_content for k in keywords): continue

            articles.append({
                "title": main_title,
                "link": e.get('link', ''),
                "published_dt": dt_hkt,
                "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "source": source_name
            })
        return articles
    except: return []

# ==================== 3. Streamlit UI ====================
st.set_page_config(page_title="全球新聞搜尋器 V9.3", layout="wide")
st.title("🌐 全球新聞搜尋器 V9.3")
st.caption("名稱判定機制 | 恢復 Ver 6.3 日期穩定性 | 移除摘要")

region = st.radio("主要搜尋區域", ["香港媒體", "台灣/世界華文", "英文全球", "中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字", placeholder="例如：李家超 託管")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("執行搜尋", type="primary"):
    if not query: st.stop()
    
    kw_list = query.strip().split()
    start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
    end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))
    
    # 根據區域選擇判定名單與黑名單
    whitelist_names = []
    blacklist_names = []
    
    if "香港" in region:
        whitelist_names, gl, hl, ceid = HK_NAME_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant"
        blacklist_names = TW_NAME_BLACKLIST
    elif "台灣" in region:
        whitelist_names, gl, hl, ceid = TW_NAME_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant"
        blacklist_names = HK_NAME_BLACKLIST
    elif "英文" in region:
        whitelist_names, gl, hl, ceid = ENGLISH_NAME_WHITE_LIST, "US", "en", "US:en"
        blacklist_names = []
    else:
        whitelist_names, gl, hl, ceid = [], "CN", "zh-CN", "CN:zh-Hans" # 中國內地主要靠 Google 原始相關性

    with st.spinner("正在精準匹配數據..."):
        # 構建 URL (Ver 6.3 原始拼接法，確保舊新聞搜尋力)
        def build_url(q):
            base_q = quote(q)
            # 時間參數嚴禁 quote，否則搜尋會變成 0
            time_str = f"+after:{start_date}+before:{end_date + timedelta(days=1)}"
            return f"https://news.google.com/rss/search?q={base_q}{time_str}&hl={hl}&gl={gl}&ceid={ceid}"

        # 1. 抓取 (不再分批，直接全抓，後端處理)
        raw_results = fetch_google_news(build_url(query), start_hkt, end_hkt, kw_list)
        
        # 2. 邏輯判定 (核心白名單 vs 智能補充包)
        final_core, final_supp = [], []
        seen = set()
        
        for a in raw_results:
            if a['link'] in seen: continue
            
            # A. 隔離黑名單 (名稱比對)
            if any(b_name.lower() in a['source'].lower() for b_name in blacklist_names):
                continue
            
            # B. 判定白名單 (名稱比對)
            is_white = False
            for w_name in whitelist_names:
                if w_name.lower() in a['source'].lower():
                    is_white = True
                    break
            
            if is_white:
                a['label'] = "核心白名單"
                final_core.append(a)
            else:
                a['label'] = "智能補充包"
                final_supp.append(a)
            
            seen.add(a['link'])

        # 3. 混合與排序
        total_results = final_core + final_supp
        total_results.sort(key=lambda x: x["published_dt"], reverse=True)

        st.success(f"找到 {len(total_results)} 則新聞 (白名單: {len(final_core)} | 補充: {len(final_supp)})")
        
        # 4. 顯示結果 (極簡化格式)
        for n in total_results:
            badge = "✅" if n['label'] == "核心白名單" else "🌐"
            st.markdown(f"### {badge} [{n['title']}]({n['link']})")
            st.markdown(f"**來源：**{n['source']} | **標籤：**{n['label']} | **時間：**{n['pub_str']}")
            st.divider()

        # 5. 診斷面板
        with st.expander("🔍 Ver 9.3 深度診斷"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Google 原始命中", len(raw_results))
            c2.metric("白名單判定數", len(final_core))
            c3.metric("黑名單排除數", len(raw_results) - len(total_results))
            st.info(f"搜尋語法：`{query} after:{start_date} before:{end_date}`")

