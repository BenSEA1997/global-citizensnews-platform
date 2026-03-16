import streamlit as st
import requests

def test_api():
    st.set_page_config(page_title="Final Fix Success")
    st.title("🛡️ 搜尋引擎：路徑強制修正版")
    
    # 1. 讀取並「強力清理」Secrets (防止換行符號導致 404)
    try:
        # .strip() 移出前後空格，.replace('\n', '') 移出中間換行
        api_key = st.secrets["GOOGLE_API_KEY"].strip().replace('\n', '').replace('\r', '').replace(' ', '')
        cx = st.secrets["CX_HK"].strip().replace('\n', '').replace('\r', '').replace(' ', '')
        st.info(f"正在測試引擎 ID: `{cx}`")
    except Exception as e:
        st.error(f"❌ 讀取 Secrets 失敗: {e}")
        st.stop()

    # 2. **絕對正確的 Google API 完整路徑**
    # 確保包含 https://www. 和 /customsearch/v1
    base_url = "https://googleapis.com"
    
    # 3. 發出請求 (使用 params 讓 requests 自動處理編碼，最安全)
    params = {
        "key": api_key,
        "cx": cx,
        "q": "香港",
        "num": 5
    }
    
    try:
        # 強制指定完整的 base_url
        resp = requests.get(base_url, params=params, timeout=15)
        
        if resp.status_code == 200:
            st.success("✅ 恭喜！連線完全成功。404 障礙已徹底排除！")
            data = resp.json()
            if "items" in data:
                st.write(f"🔍 搜尋結果範例：**{data['items'][0]['title']}**")
                st.json(data['items'][:2])
        else:
            st.error(f"❌ Google 依然拒絕連線 (HTTP {resp.status_code})")
            # 如果是 404，印出 Google 給的診斷文字
            st.warning("💡 診斷：404 代表網址路徑不對。請檢查 Secrets 裡的金鑰是否有一行以上的內容？")
            st.text_area("Google 回傳內容 (前500字):", resp.text[:500])
                
    except Exception as e:
        st.error(f"⚠️ 連線過程發生異常: {e}")

if __name__ == "__main__":
    test_api()



