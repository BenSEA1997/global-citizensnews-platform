# ====================
# Code Version: Ver 1.8
# 主要變更：
#   - 完整包含 HK_RSS 和 WORLD_RSS 清單（無任何省略）
#   - 保留 Ver 1.7 的所有修復（去重防 crash、中英匹配、domain source、時間 fallback）
#   - 無新功能，只確保字典定義完整，避免 not defined 錯誤
# 已知問題/待優化：
#   - 中文搜尋結果較少（可加更多 OR 關鍵字變體）
#   - NewsData 免費版常 0（建議升級）
# ====================

import streamlit as st
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import pytz
from urllib.parse import urlparse

HKT = pytz.timezone('Asia/Hong_Kong')

# HK RSS 清單（完整，無省略）
HK_RSS = {
    "rthk.hk": "https://news.rthk.hk/rthk/news/rss/e_expressnews_elocal.xml",
    "news.now.com": "https://news.now.com/home/rss",
    "metroradio.com.hk": "https://www.metroradio.com.hk/rss/news.xml",
    "i-cable.com": "https://www.i-cable.com/rss/news",
    "881903.com": "https://www.881903.com/rss/news.xml",
    "news.tvb.com": "https://news.tvb.com/rss",
    "epochtimes.com": "https://www.epochtimes.com.tw/rss",
    "inmediahk.net": "https://www.inmediahk.net/feed",
    "orangenews.hk": "https://www.orangenews.hk/rss",
    "lionrockdaily.com": "https://lionrockdaily.com/feed",
    "hongkongfp.com": "https://hongkongfp.com/feed/",
    "skypost.hk": "https://skypost.hk/rss",
    "thechasernews.co.uk": "https://thechasernews.co.uk/feed",
    "pulsehknews.com": "https://pulsehknews.com/feed",
    "thecollectivehk.com": "https://thecollectivehk.com/feed",
    "ifeng.com": "https://news.ifeng.com/rss",
    "chinadailyhk.com": "https://www.chinadailyhk.com/rss",
    "thestandard.com.hk": "https://www.thestandard.com.hk/newsfeed/latest/news.xml",
    "hk01.com": "https://rsshub.app/hk01/hot",
    "hkcd.com.hk": "https://www.hkcd.com.hk/rss",
    "takungpao.com": "https://www.takungpao.com/rss",
    "wenweipo.com": "https://www.wenweipo.com/rss",
    "bastillepost.com": "https://www.bastillepost.com/hongkong/feed",
    "am730.com.hk": "https://www.am730.com.hk/rss",
    "hket.com": "https://www.hket.com/rss",
    "hk.on.cc": "http://news.on.cc/ncnews/rss/loc_news.xml",
    "stheadline.com": "https://hd.stheadline.com/rss/news/daily/",
    "scmp.com": "https://www.scmp.com/rss/91/feed",
    "isd.gov.hk": None,
    "news.gov.hk": "https://www.news.gov.hk/eng/common/html/ticker.rss.xml",
    "stepaper.stheadline.com": "https://stepaper.stheadline.com/rss",
    "eastweek.stheadline.com": "https://eastweek.stheadline.com/rss",
    "orientaldaily.on.cc": "https://orientaldaily.on.cc/rss/news.xml",
    "hkej.com": "https://www.hkej.com/rss",
    "mingpao.com": "https://news.mingpao.com/php/rss.php",
    "etnet.com.hk": "https://rsshub.app/etnet/news",
    "infocast.com.hk": None
}

# World RSS 清單（完整，無省略）
WORLD_RSS = {
    "straitstimes.com": "https://www.straitstimes.com/rss",
    "dailymail.co.uk": "https://www.dailymail.co.uk/articles.rss",
    "mirror.co.uk": "https://www.mirror.co.uk/rss.xml",
    "sky.com": "https://news.sky.com/feeds/rss/home.xml",
    "economist.com": "https://www.economist.com/rss",
    "telegraph.co.uk": "https://www.telegraph.co.uk/rss.xml",
    "usatoday.com": "https://rssfeeds.usatoday.com/usatoday-NewsTopStories",
    "ft.com": "https://www.ft.com/rss/home",
    "theguardian.com": "https://www.theguardian.com/world/rss",
    "washingtonpost.com": "https://feeds.washingtonpost.com/rss/world",
    "bloomberg.com": "https://feeds.bloomberg.com/news/rss",
    "afp.com": "https://www.afp.com/en/rss",
    "apnews.com": "https://apnews.com/rss",
    "reuters.com": "https://feeds.reuters.com/reuters/worldNews",
    "ftchinese.com": "https://www.ftchinese.com/rss",
    "rfi.fr": "https://www.rfi.fr/tw/rss",
    "dw.com": "https://rss.dw.com/rdf/rss-chi-all",
    "zh.cn.nikkei.com": "https://www.nikkei.com/rss",
    "m.cn.nytimes.com": "https://cn.nytimes.com/rss.xml",
    "ttv.com.tw": "https://www.ttv.com.tw/rss",
    "ctv.com.tw": "https://www.ctv.com.tw/rss",
    "ctinews.com": "https://www.ctinews.com/rss",
    "tvbs.com.tw": "https://news.tvbs.com.tw/rss",
    "ftvnews.com.tw": "https://www.ftvnews.com.tw/rss",
    "setn.com": "https://www.setn.com/rss.aspx?PageGroupID=1",
    "ctee.com.tw": "https://www.ctee.com.tw/rss",
    "cna.com.tw": "https://www.cna.com.tw/rss",
    "ettoday.net": "https://www.ettoday.net/news/focus/rss.xml",
    "nownews.com": "https://www.nownews.com/rss",
    "chinatimes.com": "https://www.chinatimes.com/rss/realtimenews",
    "ltn.com.tw": "https://news.ltn.com.tw/rss/",
    "udn.com": "https://udn.com/rssfeed/news/2/7225",
    "caijing.com.cn": "https://www.caijing.com.cn/rss",
    "globaltimes.cn": "https://www.globaltimes.cn/rss",
    "thepaper.cn": "https://www.thepaper.cn/rss",
    "yicai.com": "https://www.yicai.com/rss",
    "21jingji.com": "https://www.21jingji.com/rss",
    "caixin.com": "https://www.caixin.com/rss",
    "chinanews.com.cn": "https://www.chinanews.com/rss",
    "chinadaily.com.cn": "https://www.chinadaily.com.cn/rss",
    "qstheory.cn": "https://www.qstheory.cn/rss",
    "xinhuanet.com": "http://www.xinhuanet.com/english/rss/worldrss.xml",
    "people.com.cn": "http://english.people.com.cn/rss",
    "aljazeera.com": "https://www.aljazeera.com/xml/rss/all.xml",
    "bbc.com": "https://feeds.bbci.co.uk/news/rss.xml",
    "news.sky.com": "https://news.sky.com/feeds/rss/home.xml"
}

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

    # 中英匹配
    q_lower = query.lower()
    alt_q = "iran" if "伊朗" in q_lower else q_lower
    filtered_rss = [
        item for item in rss_results
        if q_lower in item["title"].lower() or q_lower in item["summary"].lower() or alt_q in item["title"].lower() or alt_q in item["summary"].lower()
    ]

    all_results = filtered_rss + newsdata_results

    # 去重（安全版）
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
        unique_results = all_results[:50]

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

