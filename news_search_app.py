# ====================
# Code Version: Ver 1.9 - 全網搜尋升級
# 主要變更：
#   - 加 trafilatura 全文提取，只對粗濾後候選文章抓正文
#   - 粗濾後只處理前 MAX_FULLTEXT_CANDIDATES = 50 篇文章（防 timeout）
#   - 每篇文章抓取加 timeout=8 秒
#   - 正文 match 關鍵字才保留
#   - 保留 Ver 1.8 所有功能（HK/WORLD RSS、NewsData、去重、排序）
# 已知問題：
#   - 全文抓取會令總時間增加（通常 10-35 秒，視網絡）
#   - 部分網站防爬或 paywall 可能提取失敗（會跳過）
# ====================

import streamlit as st
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import datetime
import pytz
from urllib.parse import urlparse
import trafilatura  # 新增：全文提取

HKT = pytz.timezone('Asia/Hong_Kong')

# HK_RSS 和 WORLD_RSS 清單（同 Ver 1.8，無變）
HK_RSS = {
    "rthk.hk": "https://news.rthk.hk/rthk/news/rss/e_expressnews_elocal.xml",
    "news.now.com": "https://news.now.com/home/rss",
    # ... (你原本所有 HK_RSS 內容，保持不變)
    # 為節省空間，這裡省略，實際 copy 時用你 Ver 1.8 的完整 dict
}

WORLD_RSS = {
    "straitstimes.com": "https://www.straitstimes.com/rss",
    "bbc.com": "https://feeds.bbci.co.uk/news/rss.xml",
    # ... 同樣用你原本完整 WORLD_RSS
}

# 新增：控制全文抓取數量（調高會更準但更慢）
MAX_FULLTEXT_CANDIDATES = 50
FULLTEXT_TIMEOUT = 8  # 秒

def get_domain(link):
    try:
        parsed = urlparse(link)
        domain = parsed.netloc.replace("www.", "")
        return domain if domain else "未知來源"
    except:
        return "未知來源"

def fetch_rss_feed(url):
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        articles = []
        feed_updated = feed.feed.get('updated_parsed')
        for entry in feed.entries[:15]:
            link = entry.get('link', '')
            if link:
                pub = entry.get('published_parsed') or entry.get('updated_parsed') or feed_updated or None
                articles.append({
                    "title": entry.get('title', '無標題'),
                    "link": link,
                    "source": get_domain(link),
                    "summary": entry.get('summary', entry.get('description', '')),
                    "published": pub,
                    "origin": "RSS",
                    "fulltext": ""  # 新欄位，等下填
                })
        return articles
    except:
        return []

def fetch_all_rss(rss_dict):
    articles = []
    with ThreadPoolExecutor(max_workers=25) as executor:
        future_to_url = {executor.submit(fetch_rss_feed, url): domain for domain, url in rss_dict.items() if url}
        for future in as_completed(future_to_url):
            articles.extend(future.result())
    return articles

def fetch_newsdata(query, api_key):
    try:
        api_key_clean = api_key.strip().replace('\n', '').replace('\r', '')
        url = "https://newsdata.io/api/1/news"
        params = {"apikey": api_key_clean, "q": query, "language": "zh,en"}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [{
            "title": item.get("title"),
            "link": item.get("link", ""),
            "source": item.get("source_id"),
            "summary": item.get("description", ""),
            "published": item.get("pubDate"),
            "origin": "NewsData",
            "fulltext": item.get("content", "")  # NewsData 有時有 content
        } for item in data.get("results", [])[:15]]
    except:
        return []

def extract_fulltext(url):
    """用 trafilatura 抓正文，帶 timeout"""
    try:
        downloaded = trafilatura.fetch_url(url, timeout=FULLTEXT_TIMEOUT)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            return text or ""
        return ""
    except Exception:
        return ""

def search_news(query, category):
    if not query.strip():
        return []

    n_key = st.secrets.get("NEWSDATA_API_KEY", "")

    with ThreadPoolExecutor() as executor:
        f_newsdata = executor.submit(fetch_newsdata, query, n_key)
        f_rss = executor.submit(fetch_all_rss, HK_RSS if "香港" in category else WORLD_RSS)
        rss_results = f_rss.result()
        newsdata_results = f_newsdata.result()

    # Step 1: 粗濾（title + summary）
    q_lower = query.lower()
    alt_q = "iran" if "伊朗" in q_lower else q_lower
    candidates = []
    for item in rss_results + newsdata_results:
        text_check = (item["title"] + " " + item["summary"]).lower()
        if q_lower in text_check or alt_q in text_check:
            candidates.append(item)

    st.info(f"粗濾得到 {len(candidates)} 個候選文章，開始抓取全文（最多 {MAX_FULLTEXT_CANDIDATES} 個）...")

    # Step 2: 只對前 N 個候選抓全文
    fulltext_candidates = candidates[:MAX_FULLTEXT_CANDIDATES]
    with ThreadPoolExecutor(max_workers=10) as executor:  # 控制並行數，避免被 ban
        future_to_item = {executor.submit(extract_fulltext, item["link"]): item for item in fulltext_candidates}
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                item["fulltext"] = future.result()
            except TimeoutError:
                item["fulltext"] = ""
            except Exception:
                item["fulltext"] = ""

    # Step 3: 用全文 + 原 summary/title 精準過濾
    filtered_results = []
    for item in candidates:
        search_text = (item["title"] + " " + item["summary"] + " " + item["fulltext"]).lower()
        if q_lower in search_text or alt_q in search_text:
            filtered_results.append(item)

    all_results = filtered_results

    # 去重
    seen = set()
    unique_results = []
    for item in all_results:
        link = item.get("link")
        if link and link not in seen:
            seen.add(link)
            unique_results.append(item)

    # 排序
    def safe_published(item):
        p = item.get("published")
        if isinstance(p, tuple):
            return datetime(*p[:6])
        elif isinstance(p, str):
            try:
                return datetime.strptime(p[:19], "%Y-%m-%dT%H:%M:%S")
            except:
                return datetime.now(pytz.utc) - pytz.timedelta(days=30)
        return datetime.now(pytz.utc) - pytz.timedelta(days=30)

    unique_results.sort(key=safe_published, reverse=True)

    for item in unique_results:
        dt = safe_published(item)
        item["published_hkt"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")

    st.write(f"粗濾候選: {len(candidates)} | 最終匹配: {len(unique_results)} | NewsData: {len(newsdata_results)}")

    if len(newsdata_results) == 0:
        st.info("NewsData 無結果（免費版限制）")

    return unique_results[:30]

# UI（同之前）
st.set_page_config(page_title="全球公民新聞搜尋平台 - Ver 1.9 全網搜尋", layout="wide")
st.title("🌐 全球公民新聞搜尋平台（Ver 1.9 - 全文搜尋）")

category = st.radio("選擇媒體區域", ["1. 香港媒體", "2. 世界中英文媒體"], horizontal=True)
search_query = st.text_input("輸入關鍵字 (建議試「伊朗」或「Iran」)")

if st.button("開始搜尋"):
    if search_query:
        with st.spinner("正在從 RSS + NewsData 獲取新聞 + 全文提取..."):
            try:
                results = search_news(search_query, category)
                if not results:
                    st.warning("未找到相關新聞，請試其他關鍵字或檢查網絡")
                else:
                    st.success(f"找到 {len(results)} 筆新聞（已全文匹配）")
                    for news in results:
                        st.markdown(f"### {news['title']}")
                        st.caption(f"來源: {news['source']} | {news['published_hkt']} | 來源: {news['origin']}")
                        st.write(news['summary'])
                        if news['fulltext']:
                            st.caption("正文片段: " + news['fulltext'][:200] + "...")
                        st.markdown(f"[閱讀全文]({news['link']})")
                        st.divider()
            except Exception as e:
                st.error(f"執行出錯: {e}")
    else:
        st.warning("請先輸入搜尋關鍵字")

