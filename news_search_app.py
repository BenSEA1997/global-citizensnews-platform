import streamlit as st
import requests

def test_api():
    st.set_page_config(page_title="Hardcoded URL Test")
    st.title("🕵️ 終極連線診斷 (硬核路徑修正版)")
    
    # 1. 讀取並強力清理 Secrets
    try:
        # 強制移除所有換行、空格、以及可能存在的引號
        api_key = st.secrets["GOOGLE_API_KEY"].replace('\n', '').replace(' ', '').strip()
        cx = st.secrets["CX_HK"].replace('\n', '').replace(' ', '').strip()
        st.info(f"正在測試引擎 ID: `{cx}`")
    except Exception as e:
        st.error(f"❌ 讀取 Secrets 失敗: {e}")
        st.stop()

    # 2. **完全硬編碼的完整路徑**
    # 確保結尾沒有斜槓，且路徑包含 /customsearch/v1
    base_url = "https://googleapis.com"
    
    # 手動拼湊測試網址 (隱藏部分金鑰以保護隱私)
    display_url = f"{base_url}?key=AIza...&cx={cx}&q=香港"
    st.write(f"正在請求網址: `{display_url}`")
    
    # 3. 發出請求 (使用 params 確保編碼正確)
    try:
        params = {
            "key": api_key,
            "cx": cx,
            "q": "香港"
        }
        resp = requests.get(base_url, params=params, timeout=15)
        
        # 4. 結果判定
        if resp.status_code == 200:
            st.success("✅ 恭喜！連線完全成功。404 已經被徹底擊敗！")
            data = resp.json()
            if "items" in data:
                st.write(f"搜尋結果範例: **{data['items'][0]['title']}**")
                st.json(data['items'][:1])
        else:
            st.error(f"❌ Google 依然拒絕請求 (HTTP {resp.status_code})")
            # 顯示 Google 回傳的原始內容，抓出真正的報錯網頁
            st.text_area("Google 回傳的原始 HTML 內容 (前 500 字):", resp.text[:500])
            
            if resp.status_code == 404:
                st.warning("💡 診斷：404 代表網址路徑不對。請檢查 Google Cloud 是否有特殊的 API 端點限制。")
                
    except Exception as e:
        st.error(f"⚠️ 連線過程發生系統崩潰: {e}")

if __name__ == "__main__":
    test_api()





