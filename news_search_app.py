# Code Version: Ver 5.1 - 修正長連結、日期預設、HK 來源混雜、build_url 錯誤
# ====================

import streamlit as st
import feedparser
import requests
from datetime import datetime, date, timedelta
import pytz
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 白名單 ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}

# ... (其他白名單保持不變，為了節省篇幅這裡省略，你可以從 Ver 5.0 複製過來)

# ==================== 清理 Google RSS 長連結 ====================
def clean_google_link(link):
    """清理 Google News RSS 的長追蹤連結，提取真實文章 URL"""
    try:
        if "news.google.com" in link and "url=" in link:
            parsed = urlparse(link)
            query_params = parse_qs(parsed.query)
            real_url = query_params.get("url", [link])[0]
            return real_url
        return link
    except:
        return link

# ==================== GNews 函數（保持不變） ====================
GNEWS_API_URL = "https://gnews.io/api/v4/search"

def fetch_gnews(query, start_date, end_date, lang, country, api_key, max_articles=25):
    try:
        params = {
            "token": api_key,
            "q": query,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "lang": lang,
            "country": country,
            "max": max_articles,
            "sortby": "publishedAt"
        }
        response = requests.get(GNEWS_API_URL, params=params, timeout=15)
        data = response.json()
        articles = []
        for article in data.get("articles", []):
            articles.append({
                "title": article.get("title", "無標題"),
                "link": article.get("url", ""),
                "summary": article.get("description", "") or "",
                "published": article.get("publishedAt"),
                "source": article.get("source", {}).get("name", "GNews")
            })
        return articles
    except Exception as e:
        st.error(f"GNews 拉取失敗: {e}")
        return []

# ==================== 其他函數 ====================
def get_domain(link):
    try:
        return urlparse(link).netloc.replace("www.", "")
    except:
        return "未知來源"

def clean_title_and_source(title):
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return title.strip(), ""

def clean_summary(text):
    if not text:
        return ""
    text = text.replace('<', ' ').replace('>', ' ').replace('&nbsp;', ' ').strip()
    return text

def is_relevant(title: str, summary: str, query: str) -> bool:
    if not query or not title:
        return True
    q_lower = query.lower().strip()
    return q_lower in title.lower() or q_lower in (summary or "").lower()

def filter_by_date(articles, start_date, end_date):
    if not start_date or not end_date:
        return articles
    filtered = []
    for item in articles:
        if item.get("published"):
            try:
                if isinstance(item["published"], str):
                    dt = datetime.fromisoformat(item["published"].replace("Z", "+00:00"))
                else:
                    dt = datetime(*item["published"][:6])
                if start_date <= dt.date() <= end_date:
                    filtered.append(item)
            except:
                filtered.append(item)
        else:
            filtered.append(item)
    return filtered

def fetch_google_news(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        articles = []
        for entry in feed.entries:
            link = entry.get('link', '')
            if link:
                clean_link = clean_google_link(link)   # ← 新增清理長連結
                articles.append({
                    "title": entry.get('title', '無標題'),
                    "link": clean_link,
                    "summary": clean_summary(entry.get('summary', entry.get('description', ''))),
                    "published": entry.get('published_parsed')
                })
        return articles
    except Exception as e:
        st.error(f"Google News 拉取失敗: {e}")
        return []

def build_url(query, gl, hl, ceid, start_date=None, end_date=None, sites=None):
    q_clean = query.strip()
    if q_clean:
        phrase = q_clean.replace(" ", "+")
        q = f"%22{phrase}%22"
    else:
        q = ""
    
    if sites:
        site_str = "+OR+".join(f"site:{s}" for s in sites)
        q = f"({q})+({site_str})" if q else site_str
    
    date_parts = []
    if start_date:
        date_parts.append(f"after:{start_date.strftime('%Y-%m-%d')}")
    if end_date:
        date_parts.append(f"before:{end_date.strftime('%Y-%m-%d')}")
    
    if start_date and end_date:
        days_diff = (end_date - start_date).days
        if days_diff <= 60:
            date_parts.append(f"when:{days_diff + 2}d")
    
    date_str = "+" + "+".join(date_parts) if date_parts else ""
    return f"https://news.google.com/rss/search?q={q}{date_str}&hl={hl}&gl={gl}&ceid={ceid}"

# ==================== UI ====================
st.set_page_config(page_title="全球新聞搜尋平台", layout="wide")
st.title("🌐 全球新聞搜尋平台")
st.caption("🔧 Ver 5.1 - 修正長連結、日期預設、HK 來源混雜")

api_key = st.text_input("GNews API Key", type="password", help="輸入你的 GNews Essential Plan API Key")

region_options = [
    "1. 香港媒體（優先白名單）", 
    "2. 台灣/世界華文媒體", 
    "3. 英文全球媒體",
    "4. 中國大陸媒體（簡體中文）",
    "5. Google + GNews 合併搜尋（智能日期切換）"
]
region = st.radio("選擇搜尋區域", region_options, horizontal=True)

query = st.text_input("輸入關鍵字", placeholder="例如：鄭習會、李家超")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))  # ← 改回預設 3 天
with col2:
    end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query:
        st.warning("請輸入關鍵字")
        st.stop()

    # === 修正：先定義所有參數 ===
    if "合併搜尋" in region:
        is_hybrid = True
        # 混合模式不依賴單一 white_list
        gl = hl = ceid = None
    else:
        is_hybrid = False
        is_hk = "香港" in region
        is_mainland = "中國大陸" in region
        is_english_global = "英文全球" in region

        if is_mainland:
            white_list = MAINLAND_CHINA_WHITE_LIST
            gl, hl, ceid = "CN", "zh-CN", "CN:zh-Hans"
        elif is_english_global:
            white_list = ENGLISH_GLOBAL_LIST
            gl, hl, ceid = "US", "en", "US:en"
        elif is_hk:
            white_list = HK_WHITE_LIST
            gl, hl, ceid = "HK", "zh-HK", "HK:zh-Hant"
        else:
            white_list = TAIWAN_WORLD_WHITE_LIST
            gl, hl, ceid = "TW", "zh-TW", "TW:zh-Hant"

    with st.spinner("正在搜尋..."):
        all_results = []

        # Google RSS 部分
        if not is_hybrid or (is_hybrid and (end_date - start_date).days <= 60):
            # ... (保持原本的 batch + supplement 邏輯，你可以從 Ver 5.0 複製這部分)

        # GNews 部分（略，保持不變）

        # 後續處理：清理連結 + 過濾 + 顯示
        for item in all_results:
            item["link"] = clean_google_link(item.get("link", ""))

        # ... (其餘顯示邏輯保持不變)

        st.success(f"找到 {len(all_results)} 則相關新聞")
        for news in all_results:
            st.markdown(f"### {news.get('title')}")
            st.caption(f"來源：{news.get('source')} | {news.get('published_hkt', '未知時間')}")
            st.write(news.get("summary", ""))
            st.markdown(f"[閱讀全文]({news.get('link', '#')})")
            st.divider()