import streamlit as st
import requests
import re
import datetime
from xml.etree import ElementTree as ET
from urllib.parse import quote
from dateutil import parser
from bs4 import BeautifulSoup
import pytz
import json  # 新增，用來解析 X API 回傳

st.set_page_config(page_title="全球即時新聞搜尋", page_icon="🌍", layout="wide")

# 語言切換、地區選擇、文字設定（保持原樣，略過重複貼）
# ... (你的語言切換、地區、文字設定代碼保持不變) ...

st.title(page_title)
st.caption(search_tip)

# 香港時區
HKT = pytz.timezone('Asia/Hong_Kong')

# 搜尋區塊
query = st.text_input(search_label, placeholder=search_placeholder)

if 'news_results' not in st.session_state:
    st.session_state.news_results = None
if 'x_results' not in st.session_state:
    st.session_state.x_results = None

if st.button(search_button):
    if not query.strip():
        st.error("請輸入關鍵字" if interface_lang == "中文" else "Please enter keywords")
    else:
        st.info(loading_text)
        try:
            api_key = st.secrets["NEWS_API_KEY"]
            twitter_bearer = st.secrets.get("TWITTER_BEARER_TOKEN", None)

            # ── NewsData.io + Google News ── (保持原樣，略過重複)
            # ... (你的 NewsData.io 和 Google News 搜尋邏輯保持不變) ...

            # 去重 + 排序 + 轉香港時間（保持原樣）
            # ... (你的 unique_results、parse_date_to_hkt、sorted_news 邏輯保持不變) ...

            st.session_state.news_results = sorted_news

            # ── 真實 X (Twitter) 搜尋 ──
            x_results = []
            if twitter_bearer:
                headers = {
                    "Authorization": f"Bearer {twitter_bearer}"
                }
                params = {
                    "query": f"{query} lang:zh OR lang:en -is:retweet",  # 搜中文/英文，排除轉推
                    "tweet.fields": "created_at,author_id,text,lang",
                    "user.fields": "username,name",
                    "expansions": "author_id",
                    "max_results": 10,  # 最多 10 則（免費額度允許）
                    "sort_order": "recency"  # 最新在上
                }
                url = "https://api.twitter.com/2/tweets/search/recent"
                response = requests.get(url, headers=headers, params=params, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                    for tweet in data.get("data", []):
                        user = users.get(tweet["author_id"], {})
                        created_at = tweet.get("created_at", "")
                        if created_at:
                            dt = parser.parse(created_at).astimezone(HKT)
                            created_display = dt.strftime("%Y-%m-%d %H:%M:%S %Z")
                        else:
                            created_display = "未知"
                        x_results.append({
                            "text": tweet.get("text", ""),
                            "user": f"@{user.get('username', 'unknown')}",
                            "name": user.get("name", ""),
                            "created_at": created_display,
                            "link": f"https://x.com/{user.get('username', 'unknown')}/status/{tweet['id']}"
                        })
                else:
                    st.warning(f"X API 錯誤 ({response.status_code}): {response.text}")
            else:
                st.warning("未設定 TWITTER_BEARER_TOKEN，請在 secrets 加入")

            st.session_state.x_results = x_results

        except requests.Timeout:
            st.error(error_timeout)
        except Exception as e:
            st.error(f"{error_generic}: {str(e)}")
        else:
            st.success(success_text)

# ===== 顯示新聞結果 =====
# (保持原樣，略過重複貼)

# ===== X 搜尋結果 =====
if st.session_state.x_results is not None:
    st.subheader("X (Twitter) 搜尋結果" if interface_lang == "中文" else "X (Twitter) Results")
    x_posts = st.session_state.x_results

    if not x_posts:
        st.info("沒有找到相關 X 貼文" if interface_lang == "中文" else "No X posts found.")
    else:
        for post in x_posts:
            st.markdown(f"**{post['user']}** ({post['name']}) · {post['created_at']}")
            st.write(post['text'])
            st.markdown(f"[查看貼文 / View post]({post['link']})")
            st.divider()