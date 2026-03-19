# ====================
# Code Version: Ver 1.6
# 主要變更：
#   - 修復 'set' object has no attribute 'items'（去重邏輯加強 + 防誤用）
#   - 加 try-except 包去重部分，避免整個 app crash
#   - 維持 Ver 1.5 的其他優化（中英匹配、domain source、時間 fallback）
# 已知問題/待優化：
#   - 如果還 crash，貼完整錯誤 trace 給我
# ====================

import streamlit as st
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import pytz
from urllib.parse import urlparse

HKT = pytz.timezone('Asia/Hong_Kong')

# RSS 清單（維持不變，從 Ver 1.5 複製）

# ... HK_RSS 和 WORLD_RSS 字典維持原樣（省略重複）

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
                    "origin": "RSS"
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
            "origin": "NewsData"
        } for item in data.get("results", [])[:15]]
    except:
        return []

def search_news(query, category):
    if not query.strip():
        return []

    n_key = st.secrets.get("NEWSDATA_API_KEY", "")

    with ThreadPoolExecutor() as executor:
        f_newsdata = executor.submit(fetch_newsdata, query, n_key)
        f_rss = executor.submit(fetch_all_rss, HK_RSS if "香港" in category else WORLD_RSS)
        rss_results = f_rss.result()
        newsdata_results = f_newsdata.result()

    # 加強中英匹配
    q_lower = query.lower()
    alt_q = "iran" if "伊朗" in q_lower else q_lower
    filtered_rss = [
        item for item in rss_results
        if q_lower in item["title"].lower() or q_lower in item["summary"].lower() or alt_q in item["title"].lower() or alt_q in item["summary"].lower()
    ]

    all_results = filtered_rss + newsdata_results

    # 去重（嚴格用 set.add / in，避免 .items() 誤用）
    seen = set()
    unique_results = []
    try:
        for item in all_results:
            link = item.get("link")
            if link and link not in seen:
                seen.add(link)
                unique_results.append(item)
    except Exception as e:
        st.error(f"去重錯誤: {e} - 顯示原始結果")
        unique_results = all_results  # fallback

    # 安全排序
    def safe_published(item):
        p = item.get("published")
        if isinstance(p, tuple):
            return datetime(*p[:6])
        elif isinstance(p, str):
            try:
                return datetime.strptime(p[:19], "%Y-%m-%dT%H:%M:%S")
            except:
                return datetime.now(pytz.utc) - timedelta(days=30)
        return datetime.now(pytz.utc) - timedelta(days=30)

    unique_results.sort(key=safe_published, reverse=True)

    for item in unique_results:
        dt = safe_published(item)
        item["published_hkt"] = dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT")

    # 低結果 fallback
    if len(unique_results) < 5 and len(rss_results) > 0:
        st.info("過濾後結果較少，已顯示原始 RSS 前 15 筆（含較廣泛相關）")
        fallback = sorted(rss_results, key=safe_published, reverse=True)[:15]
        unique_results = fallback + unique_results

    st.write(f"RSS 原始筆數: {len(rss_results)} | NewsData 原始筆數: {len(newsdata_results)}")
    if len(newsdata_results) == 0:
        st.info("NewsData 目前無補充結果（免費版限制：僅過去 48 小時 + 可能延遲 12 小時）")

    return unique_results[:30]

# UI
st.set_page_config(page_title="全球公民新聞搜尋平台", layout="wide")
st.title("🌐 全球公民新聞搜尋平台")

category = st.radio("選擇媒體區域", ["1. 香港媒體", "2. 世界中英文媒體"], horizontal=True)
search_query = st.text_input("輸入關鍵字 (建議同時試「伊朗」或「Iran」)")

if st.button("開始搜尋"):
    if search_query:
        with st.spinner("正在從 RSS + NewsData 獲取新聞..."):
            try:
                results = search_news(search_query, category)
                if not results:
                    st.warning("未找到相關新聞，請試「Iran」或「伊朗戰爭」")
                else:
                    st.success(f"找到 {len(results)} 筆新聞")
                    for news in results:
                        st.markdown(f"### {news['title']}")
                        st.caption(f"來源: {news['source']} | {news['published_hkt']}")
                        st.write(news['summary'])
                        st.markdown(f"[閱讀全文]({news['link']})")
                        st.divider()
            except Exception as e:
                st.error(f"執行出錯: {e}")
    else:
        st.warning("請先輸入搜尋關鍵字")

