def fetch_google_news(query, cx, api_key, lr=None):
    """
    修正點：使用完整的官方 API 路徑 /customsearch/v1
    並對金鑰進行嚴格的 .strip() 與換行符清理
    """
    try:
        # 修正後的完整 URL（官方文件指定）
        url = "https://www.googleapis.com/customsearch/v1"
       
        params = {
            "key": api_key.strip().replace('\n', '').replace('\r', ''),
            "cx": cx.strip().replace('\n', '').replace('\r', ''),
            "q": query,
            "dateRestrict": "m1",          # 過去 1 個月 ≈ 30 天，官方支援
            "num": 10,
            "hl": "zh-Hant"
        }
        if lr:
            params["lr"] = lr
       
        resp = requests.get(url, params=params, timeout=15)
        
        # 增加 debug 資訊（上線後可移除）
        if resp.status_code != 200:
            st.error(f"Google API 回應 {resp.status_code}：{resp.text[:300]}...")
            return []
           
        data = resp.json()
        articles = []
        for item in data.get("items", []):
            link = item.get("link", "").lower()
            tier = 1
            for key, val in MEDIA_TIERS.items():
                if key in link:
                    tier = val
                    break
            articles.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "source": item.get("displayLink", ""),
                "summary": item.get("snippet", ""),
                "published": None,
                "tier": tier,
                "origin": "Google"
            })
        return articles
    except Exception as e:
        st.error(f"Google 搜尋異常：{str(e)}")
        return []



