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

# ==================== 0. 核心配置與 AI 初始化 ====================
HKT = pytz.timezone('Asia/Hong_Kong')

# 憑據配置
GEMINI_API_KEY = "AIzaSyC3BObPwMWoulIw2tVdf-mnuvzH6bDFOSI"
BSKY_HANDLE = "bennysea97.bsky.social"
BSKY_PASSWORD = "7inu-hoaz-vlda-alvq"

# 初始化 Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# ==================== 1. 傳統新聞 Ver 10.3 核心邏輯 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}
CN_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "caixin.com", "chinanews.com.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "nbcnews.com", "abcnews.go.com", "usatoday.com", "dailymail.co.uk", "mirror.co.uk", "sky.com", "telegraph.co.uk", "economist.com"}

HK_SUPP_KEYWORDS = ["香港", "HK", "Hong Kong", "港聞", "港"]
SYNONYM_DICT = {"中山": ["中山陵", "中山紀念館", "中山市", "孫中山"], "習近平": ["習主席", "習總書記"], "李家超": ["特首", "John Lee"]}

def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "").lower()
    except: return ""

def to_hkt_aware(dt_obj):
    if dt_obj.tzinfo is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj.astimezone(HKT)

def clean_summary(text):
    if not text: return ""
    return re.sub(r'<[^>]+>', ' ', text).replace('&nbsp;', ' ').strip()

def split_date_ranges(start_date, end_date, interval_days=30):
    ranges = []
    curr = start_date
    while curr <= end_date:
        nxt = min(curr + timedelta(days=interval_days), end_date)
        ranges.append((curr, nxt))
        curr = nxt + timedelta(days=1)
    return ranges

def fetch_google_news(url, start_hkt, end_hkt, keywords, is_supp=False):
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
            full_content = (clean_title + " " + clean_summary(e.get('summary', ''))).lower()
            match_all = True
            for k in keywords:
                if not (k.lower() in full_content or any(s.lower() in full_content for s in SYNONYM_DICT.get(k, []))):
                    match_all = False; break
            if not match_all: continue
            articles.append({"title": clean_title, "link": e.get('link', ''), "real_domain": real_domain, "source": source_title, "published_dt": dt_hkt, "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M")})
        return articles
    except: return []

# ==================== 2. 去中心化社交平台抓取邏輯 ====================
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": """query { search(input: {key: \"""" + query + """\", type: Article, first: 20}) { edges { node { ... on Article { title shortHash summary author { displayName } appreciationsReceivedTotal createdAt } } } } } """}
    results = []
    try:
        response = requests.post(matters_api, json=query_json, timeout=10)
        data = response.json()['data']['search']['edges']
        for item in data:
            n = item['node']
            results.append({"title": n['title'], "link": f"https://matters.town/a/{n['shortHash']}", "author": n['author']['displayName'], "likes": n['appreciationsReceivedTotal'], "summary": n['summary'], "published": n['createdAt'][:10], "platform": "Matters"})
    except: pass
    return results

def fetch_bluesky(query):
    results = []
    try:
        client = Client()
        client.login(BSKY_HANDLE, BSKY_PASSWORD)
        response = client.app.bsky.feed.search_posts(params={'q': query, 'limit': 20, 'sort': 'top'})
        for post in response.posts:
            results.append({"title": post.record.text[:50].replace('\n',' ') + "...", "link": f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}", "author": post.author.display_name or post.author.handle, "likes": post.like_count or 0, "summary": post.record.text, "published": post.record.created_at[:10], "platform": "Bluesky"})
    except: pass
    return results

# ==================== 3. 主介面切換與 UI ====================
st.set_page_config(page_title="全球 CitizensNews 平台 V11.0", layout="wide")

with st.sidebar:
    st.title("🛠 控制面板")
    app_mode = st.radio("選擇模式：", ["🔘 傳統新聞 (V10.3)", "🔵 去中心化社交平台觀點 (New)"])
    st.divider()
    st.caption("Ver 11.0 | 雙引擎驅動")

# --- 模式 A：傳統新聞搜尋 ---
if app_mode == "🔘 傳統新聞 (V10.3)":
    st.title("🌐 傳統新聞搜尋引擎 V10.3")
    region = st.radio("搜尋區域", ["香港媒體", "台灣/世界華文", "英文全球", "中國大陸"], horizontal=True)
    query = st.text_input("輸入關鍵字", placeholder="例如：鄭麗文 中山")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
    with col2: end_date = st.date_input("結束日期", value=date.today())

    if st.button("執行搜尋", type="primary"):
        if not query: st.stop()
        kw_list = query.strip().split()
        start_hkt, end_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time())), HKT.localize(datetime.combine(end_date, datetime.max.time()))
        tld_target, is_china = "", False
        if "香港" in region: white_list, gl, hl, ceid, tld_target = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", ".hk"
        elif "台灣" in region: white_list, gl, hl, ceid, tld_target = TW_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", ".tw"
        elif "英文" in region: white_list, gl, hl, ceid, tld_target = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", ".com"
        else: white_list, gl, hl, ceid, is_china = CN_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans", True

        date_chunks = split_date_ranges(start_date, end_date)
        all_raw_white, all_raw_supp = [], []
        p_bar = st.progress(0)
        for idx, (s_d, e_d) in enumerate(date_chunks):
            q_str = " ".join(kw_list)
            def get_url(sites=None):
                s_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
                return f"https://news.google.com/rss/search?q={quote_plus(q_str)}{s_str}+after:{s_d}+before:{e_d + timedelta(days=1)}&hl={hl}&gl={gl}&ceid={ceid}"
            all_raw_white.extend(fetch_google_news(get_url(list(white_list)), start_hkt, end_hkt, kw_list))
            all_raw_supp.extend(fetch_google_news(get_url(), start_hkt, end_hkt, kw_list, is_supp=True))
            p_bar.progress((idx + 1) / len(date_chunks))

        final_res, seen = [], set()
        c_w, c_s = 0, 0
        for a in (all_raw_white + all_raw_supp):
            if a['title'] in seen: continue
            label = ""
            if any(w in a['real_domain'] for w in white_list): label, c_w = "✅ 核心白名單", c_w + 1
            elif (tld_target and a['real_domain'].endswith(tld_target)) or is_china or any(sk in a['source'] for sk in HK_SUPP_KEYWORDS): label, c_s = "🌐 區域補充包", c_s + 1
            if label: a['final_label'] = label; final_res.append(a); seen.add(a['title'])

        final_res.sort(key=lambda x: x["published_dt"], reverse=True)
        st.success(f"找到 {len(final_res)} 則新聞")
        for n in final_res:
            st.markdown(f"### {n['final_label'][0]} [{n['title']}]({n['link']})")
            st.markdown(f"**來源：**{n['source']} | **時間：**{n['pub_str']}")
            st.divider()

# --- 模式 B：去中心化社交平台 ---
else:
    st.title("🔵 去中心化社交平台觀點挖掘")
    social_query = st.text_input("輸入社交關鍵字", placeholder="例如：李家超 房屋政策")
    if st.button("執行觀點挖掘", type="primary"):
        if not social_query: st.stop()
        with st.spinner("正在抓取 Matters & Bluesky 觀點..."):
            all_social = fetch_matters(social_query) + fetch_bluesky(social_query)
        
        if not all_social: st.warning("未找到相關討論。")
        else:
            # AI Lab 總結
            st.subheader("✨ Gemini AI Lab 觀點總結")
            context = "\n".join([f"[{d['platform']}] {d['title']}: {d['summary'][:120]}" for d in all_social[:15]])
            try:
                res = ai_model.generate_content(f"分析以下社群觀點並用繁體中文回覆：1.總結核心意見 2.是否有獨特視角 3.討論情緒。內容：\n{context}")
                st.info(res.text)
            except: st.error("AI 服務暫時無法連接。")

            # 列表顯示
            st.divider()
            for item in all_social:
                icon = "✍️" if item['platform'] == "Matters" else "🦋"
                with st.container():
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.markdown(f"### {icon} [{item['title']}]({item['link']})")
                        st.caption(f"作者: {item['author']} | 平台: {item['platform']} | 日期: {item['published']}")
                        st.write(item['summary'])
                    with c2: st.metric("❤️ 互動", item['likes'])
                    st.divider()