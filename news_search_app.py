import streamlit as st
import requests
from urllib.parse import quote
import feedparser

# =========================
# CONFIG
# =========================
NEWSDATA_API_KEY = "YOUR_NEWSDATA_API_KEY"

st.set_page_config(
    page_title="Global Citizens News",
    page_icon="📰",
    layout="wide"
)

st.title("🌍 Global Citizens News Search")

st.write("Search news from NewsData.io and Google News")

# =========================
# SEARCH BAR
# =========================
query = st.text_input("Enter keyword")

# =========================
# NEWSDATA.IO SEARCH
# =========================
def search_newsdata(query):

    url = "https://newsdata.io/api/1/news"

    params = {
        "apikey": NEWSDATA_API_KEY,
        "q": query,
        "language": "en"
    }

    response = requests.get(url, params=params)

    articles = []

    if response.status_code == 200:

        data = response.json()

        if "results" in data:

            for item in data["results"]:

                articles.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "image": item.get("image_url"),
                    "source": item.get("source_id"),
                    "date": item.get("pubDate")
                })

    return articles


# =========================
# GOOGLE NEWS SEARCH
# =========================
def search_google(query):

    google_query = quote(query)

    url = f"https://news.google.com/rss/search?q={google_query}"

    feed = feedparser.parse(url)

    articles = []

    for entry in feed.entries:

        articles.append({
            "title": entry.title,
            "link": entry.link,
            "image": None,
            "source": entry.source.title if "source" in entry else "Google News",
            "date": entry.published
        })

    return articles


# =========================
# SHOW RESULTS
# =========================
if st.button("Search"):

    if query == "":
        st.warning("Please enter a keyword")

    else:

        st.subheader("NewsData.io Results")

        newsdata_articles = search_newsdata(query)

        for a in newsdata_articles:

            col1, col2 = st.columns([1,3])

            with col1:
                if a["image"]:
                    st.image(a["image"], use_column_width=True)

            with col2:
                st.markdown(f"### [{a['title']}]({a['link']})")
                st.write(f"Source: {a['source']}")
                st.write(a["date"])

            st.divider()

        st.subheader("Google News Results")

        google_articles = search_google(query)

        for a in google_articles:

            st.markdown(f"### [{a['title']}]({a['link']})")
            st.write(f"Source: {a['source']}")
            st.write(a["date"])

            st.divider()