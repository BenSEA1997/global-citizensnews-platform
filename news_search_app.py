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

# ==================== 0. 核心配置 (自動偵測模型版) ====================
HKT = pytz.timezone('Asia/Hong_Kong')

def get_gemini_key():
    for key_name in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
        if key_name in st.secrets: return st.secrets[key_name]
    return None

api_key = get_gemini_key()
available_model = None

if api_key:
    try:
        genai.configure(api_key=api_key)
        # 🧪 自動偵測可用模型
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                # 優先順序：1.5-flash -> 1.5-pro -> 1.0-pro -> 隨便一個支援的模型
                if 'gemini-1.5-flash' in m.name: 
                    available_model = m.name
                    break
                elif 'gemini-1.5-pro' in m.name:
                    available_model = m.name
        
        # 如果沒找到 flash，就拿清單中第一個可用的
        if not available_model:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if models: available_model = models[0]
            
    except Exception as e:
        st.error(f"❌ Gemini 配置失敗：{str(e)}")
        st.stop()
else:
    st.error("❌ 找不到 API Key。")
    st.stop()

BSKY_HANDLE = "bennysea97.bsky.social"
BSKY_PASSWORD = "7inu-hoaz-vlda-alvq"

if 'social_results' not in st.session_state: st.session_state.social_results = []
if 'social_page' not in st.session_state: st.session_state.social_page = 0

# ==================== 1. 新聞媒體工具 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TW_WHITE_LIST = {"ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com"}

def get_domain(link):
    try: return urlparse(link).netloc.replace("www.", "").lower()
    except: return ""

def to_hkt_aware(dt_obj):
    if dt_obj.tzinfo is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj.astimezone(HKT)

def fetch_google_news(url, start_hkt, end_hkt, query, white_list):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try: dt_hkt = to_hkt_aware(datetime.fromtimestamp(mktime(e.published_parsed)))
            except: continue
            if not (start_hkt <= dt_hkt <= end_hkt): continue
            clean_title = e.get('title', '').rsplit(" - ", 1)[0]
            raw_source = e.get('source', {})
            real_domain = get_domain(raw_source.get('href', raw_source.get('url', '')))
            articles.append({
                "title": clean_title, "link": e.get('link', ''), 
                "source": raw_source.get('title', '未知來源'), 
                "published_dt": dt_hkt, "pub_str": dt_hkt.strftime("%Y-%m-%d %H:%M"),
                "is_white": real_domain in white_list
            })
        return articles
    except: return []

# ==================== 2. 社交挖掘 ====================
def fetch_matters(query):
    matters_api = "https://server.matters.news/graphql"
    query_json = {"query": f'query {{ search(input: {{key: "{query}", type: Article, first: 40}}) {{ edges {{ node {{ ... on Article {{ title shortHash summary author {{ displayName }} appreciationsReceivedTotal createdAt }} }} }} }} }}'}
    results = []
    try:
        response = requests.post(matters_api, json=query_json, timeout=10)
        data = response.json()['data']['search']['edges']
        for item in data:
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
        response = client.app.bsky.feed.search_posts(params={'q': query, 'limit': 40, 'sort': 'latest'})
        for post in response.posts:
            dt = datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00')).astimezone(HKT)
            results.append({"title": post.record.text[:60].replace('\n',' ') + "...", "link": f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}", "author": post.author.display_name or post.author.handle, "likes": (post.like_count or 0), "summary": post.record.text, "published": dt.strftime("%Y-%m-%d %H:%M"), "platform": "Bluesky", "raw_dt": dt})
    except: pass
    return results

# ==================== 3. 主 UI ====================
st.set_page_config(page_title="全球 CitizensNews V12.4", layout="wide")

with st.sidebar:
    st.title("⚙️ 功能選項")
    app_mode = st.radio("模式：", ["新聞搜尋", "去中心社交分析"])
    if available_model:
        st.caption(f"🤖 AI 模型已就緒: {available_model.split('/')[-1]}")

if app_mode == "新聞搜尋":
    st.title("🌐 新聞搜尋引擎 V12.4")
    query = st.text_input("關鍵字")
    if st.button("搜尋新聞") and query:
        start_hkt = HKT.localize(datetime.combine(date.today() - timedelta(days=2), datetime.min.time()))
        end_hkt = HKT.localize(datetime.combine(date.today(), datetime.max.time()))
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=zh-HK&gl=HK&ceid=HK:zh-Hant"
        articles = fetch_google_news(url, start_hkt, end_hkt, query, HK_WHITE_LIST)
        for n in sorted(articles, key=lambda x: x["published_dt"], reverse=True):
            st.markdown(f"### {'✅' if n['is_white'] else '📦'} [{n['title']}]({n['link']})")
            st.caption(f"{n['source']} | {n['pub_str']}")

else:
    st.title("🔵 社交平台 AI 分析")
    social_query = st.text_input("分析主題")
    if st.button("執行分析") and social_query:
        raw_all = fetch_matters(social_query) + fetch_bluesky(social_query)
        st.session_state.social_results = sorted(raw_all, key=lambda x: x['raw_dt'], reverse=True)
        st.rerun()

    if st.session_state.social_results:
        curr_data = st.session_state.social_results[:20]
        st.subheader("✨ AI 總結觀點")
        if available_model:
            try:
                model = genai.GenerativeModel(available_model)
                context = "\n".join([f"{d['title']}" for d in curr_data[:10]])
                response = model.generate_content(
                    f"請分析以下趨勢並總結：\n{context}",
                    safety_settings={cat: HarmBlockThreshold.BLOCK_NONE for cat in HarmCategory}
                )
                st.info(response.text)
            except Exception as e:
                st.warning(f"AI 生成失敗：{str(e)}")
        else:
            st.error("此 API Key 目前不支援任何 Gemini 生成模型。")

        for item in curr_data:
            st.markdown(f"### [{'✍️' if item['platform']=='Matters' else '🦋'}] [{item['title']}]({item['link']})")
            st.caption(f"{item['author']} | ❤️ {item['likes']} | {item['published']}")
            st.write(item['summary'][:200])
            st.divider()