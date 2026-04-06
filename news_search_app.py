import streamlit as st
import feedparser
import re
from datetime import datetime, date, timedelta, timezone
from time import mktime
import pytz
from urllib.parse import quote

HKT = pytz.timezone('Asia/Hong_Kong')

# ==================== 1. 媒體白名單與黑名單 (強化隔離) ====================
HK_WHITE_LIST = {"rthk.hk", "news.now.com", "metroradio.com.hk", "i-cable.com", "881903.com", "news.tvb.com", "epochtimes.com", "inmediahk.net", "orangenews.hk", "lionrockdaily.com", "hongkongfp.com", "skypost.hk", "pulsehknews.com", "thecollectivehk.com", "ifeng.com", "chinadailyhk.com", "thestandard.com.hk", "hk01.com", "hkcd.com.hk", "takungpao.com", "wenweipo.com", "bastillepost.com", "am730.com.hk", "hket.com", "hk.on.cc", "stheadline.com", "scmp.com", "news.gov.hk", "orientaldaily.on.cc", "hkej.com", "mingpao.com", "etnet.com.hk"}
TAIWAN_WORLD_WHITE_LIST = {"straitstimes.com", "dailymail.co.uk", "economist.com", "telegraph.co.uk", "ft.com", "theguardian.com", "bloomberg.com", "apnews.com", "reuters.com", "rfi.fr", "dw.com", "zh.cn.nikkei.com", "m.cn.nytimes.com", "ttv.com.tw", "ctv.com.tw", "ctinews.com", "tvbs.com.tw", "ftvnews.com.tw", "setn.com", "ctee.com.tw", "cna.com.tw", "ettoday.net", "nownews.com", "chinatimes.com", "ltn.com.tw", "udn.com", "aljazeera.com", "bbc.com"}
MAINLAND_CHINA_WHITE_LIST = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "globaltimes.cn", "thepaper.cn", "yicai.com", "21jingji.com", "caixin.com", "chinanews.com.cn", "qstheory.cn", "news.cn", "gov.cn", "cctv.com"}
ENGLISH_GLOBAL_LIST = {"bbc.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com", "theguardian.com", "washingtonpost.com", "nytimes.com", "wsj.com", "cnn.com", "usatoday.com"}

# 用於地區隔離的關鍵域名（排除用）
HK_DOMAINS = ["hk01.com", "on.cc", "stheadline.com", "hket.com", "mingpao.com", "scmp.com", "rthk.hk"]
TW_DOMAINS = ["ltn.com.tw", "chinatimes.com", "udn.com", "ettoday.net", "setn.com", "tvbs.com.tw"]

# ==================== 2. 工具函數 ====================
def to_hkt_aware(dt_obj):
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj.astimezone(HKT)

def fetch_google_news(url, label, start_hkt, end_hkt):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        for e in feed.entries:
            try:
                dt = datetime.fromtimestamp(mktime(e.published_parsed))
                dt_hkt = to_hkt_aware(dt)
            except: continue
            
            # 嚴格日期過濾
            if not (start_hkt <= dt_hkt <= end_hkt): continue
                
            raw_title = e.get('title', '')
            media_name = raw_title.rsplit(" - ", 1)[-1] if " - " in raw_title else "未知"
            pure_title = raw_title.rsplit(" - ", 1)[0] if " - " in raw_title else raw_title

            articles.append({
                "pure_title": pure_title,
                "link": e.get('link', ''),
                "published_dt": dt_hkt,
                "pub_time_str": dt_hkt.strftime("%Y-%m-%d %H:%M HKT"),
                "media_name": media_name,
                "source_type": label
            })
        return articles
    except: return []

# ==================== 3. UI 介面 ====================
st.set_page_config(page_title="全球新聞搜尋器 V9.0", layout="wide")
st.title("🌐 全球新聞搜尋器 V9.0")
st.caption("全面回歸 Google RSS | 修復雙關鍵字 | 強化地區隔離 | 移除 GNews")

region = st.radio("選擇搜尋區域", ["香港媒體", "台灣/世界華文", "英文全球", "中國大陸"], horizontal=True)
query = st.text_input("輸入關鍵字 (多個關鍵字請用空格分開)", placeholder="例如：李家超 託管")

col1, col2 = st.columns(2)
with col1: start_date = st.date_input("開始日期", value=date.today() - timedelta(days=3))
with col2: end_date = st.date_input("結束日期", value=date.today())

if st.button("開始搜尋", type="primary"):
    if not query: st.stop()

    start_hkt = HKT.localize(datetime.combine(start_date, datetime.min.time()))
    end_hkt = HKT.localize(datetime.combine(end_date, datetime.max.time()))

    # 區域配置與排除邏輯
    exclude_query = ""
    if "香港" in region:
        white_list, gl, hl, ceid = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant"
        exclude_query = " " + " ".join([f"-site:{d}" for d in TW_DOMAINS])
    elif "台灣" in region:
        white_list, gl, hl, ceid = TAIWAN_WORLD_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant"
        exclude_query = " " + " ".join([f"-site:{d}" for d in HK_DOMAINS])
    elif "英文" in region:
        white_list, gl, hl, ceid = ENGLISH_GLOBAL_LIST, "US", "en", "US:en"
    else:
        white_list, gl, hl, ceid = MAINLAND_CHINA_WHITE_LIST, "CN", "zh-CN", "CN:zh-Hans"

    # 多關鍵字處理：將空格轉為 + 確保 Google News 執行 AND 搜尋
    processed_query = query.strip().replace(" ", "+")

    with st.spinner("正在執行多重深度搜尋..."):
        def build_url(q, ex_q, sites=None):
            site_str = f"+({'+OR+'.join(f'site:{s}' for s in sites)})" if sites else ""
            # 加入 after 和 before 語法
            base = f"https://news.google.com/rss/search?q={quote(q)}{site_str}{quote(ex_q)}"
            date_filter = f"+after:{start_date}+before:{end_date + timedelta(days=1)}"
            return f"{base}{quote(date_filter)}&hl={hl}&gl={gl}&ceid={ceid}"

        # 1. 白名單 (Core) - 批次抓取
        all_core = []
        wl_list = list(white_list)
        for i in range(0, len(wl_list), 15):
            url = build_url(processed_query, exclude_query, wl_list[i:i+15])
            all_core.extend(fetch_google_news(url, "白名單", start_hkt, end_hkt))
        
        # 2. 廣泛補充包 (Supplement)
        url_supp = build_url(processed_query, exclude_query)
        all_supp = fetch_google_news(url_supp, "補充包", start_hkt, end_hkt)

        # ==================== 清洗與去重 ====================
        final_results, seen = [], set()
        
        # 優先合併白名單
        for a in all_core:
            if a['link'] not in seen:
                final_results.append(a)
                seen.add(a['link'])
        
        # 填充補充包 (最多補到總數的三分一或設定上限)
        supp_count = 0
        max_supp = max(40, len(final_results) // 2) # 提高補充包比例
        for a in all_supp:
            if a['link'] not in seen and supp_count < max_supp:
                final_results.append(a)
                seen.add(a['link'])
                supp_count += 1
        
        # 按時間排序
        final_results.sort(key=lambda x: x["published_dt"], reverse=True)

        # ==================== 輸出 ====================
        st.success(f"搜尋完成：找到 {len(final_results)} 則相關新聞")
        
        for news in final_results:
            icon = "✅" if news['source_type'] == "白名單" else "🌐"
            st.markdown(f"### {icon} [{news['pure_title']}]({news['link']})")
            st.caption(f"來源：**{news['media_name']}** | 類別：{news['source_type']} | 時間：{news['pub_time_str']}")
            st.divider()

        with st.expander("🔍 搜尋診斷 (V9.0)"):
            st.write(f"關鍵字處理: `{processed_query}`")
            st.write(f"白名單總數: {len(all_core)} | 補充包總數: {len(all_supp)}")
            st.write(f"排除字串: `{exclude_query}`")