# ===== Google News RSS =====
google_query = quote(query)

url_google = f"https://news.google.com/rss/search?q={google_query}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant"

r = requests.get(url_google,timeout=15)

if r.status_code == 200:

    root = ET.fromstring(r.content)

    for item in root.findall(".//item")[:10]:

        title_raw = item.find("title").text

        link = item.find("link").text

        pub = item.find("pubDate").text

        desc_raw = item.find("description").text

        soup = BeautifulSoup(desc_raw,"html.parser")

        # 抓 RSS 圖片
        img_tag = soup.find("img")

        if img_tag and img_tag.get("src"):
            img_url = img_tag["src"]
        else:
            img_url = None

        clean_desc = soup.get_text()

        match = re.search(r' - (.+?)(?=\s*\(|$)', title_raw)

        source = match.group(1) if match else "Google News"

        title = re.sub(r' - .+$','',title_raw)

        results.append({

            "title":title,
            "desc":clean_desc,
            "source":source,
            "date":pub,
            "link":link,
            "image":img_url
        })