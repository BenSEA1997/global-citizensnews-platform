import streamlit as st
import requests

def test_api():
    st.title("🕵️ 最終連線診斷 (修正 URL 版)")
    
    # 1. 從 Secrets 讀取 (請確保 Secrets 中有這三個變數)
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
        cx = st.secrets["CX_HK"]
        st.info(f"使用引擎 ID: {cx}")
    except Exception as e:
        st.error(f"❌ 無法讀取 Secrets: {e}")
        st.stop()

    # 2. **修正後的完整 Google API 網址** (必須包含 /customsearch/v1)
    url = "https://googleapis.com"
    params = {
        "key": api_key,
        "cx": cx,
        "q": "香港", # 使用一個穩定的測試關鍵字
        "num": 5
    }
    
    # 3. 發出請求
    try:
        resp = requests.get(url, params=params, timeout=10)
        
        # 檢查 HTTP 狀態碼
        if resp.status_code == 200:
            data = resp.json()
            st.success("✅ 恭喜！連線成功，API Key 2 與 CX ID 完全匹配！")
            
            if "items" in data:
                st.write(f"🔍 搜尋結果範例：{data['items'][0]['title']}")
                st.json(data['items'][:2]) # 顯示前兩則資料
            else:
                st.warning("⚠️ 連線成功，但該引擎內找不到『香港』相關內容，請檢查 PSE 白名單。")
        else:
            st.error(f"❌ Google 拒絕請求 (HTTP 錯誤碼: {resp.status_code})")
            # 嘗試顯示 Google 的錯誤原因，若不是 JSON 則顯示純文字
            try:
                st.json(resp.json())
            except:
                st.text(f"原始回應內容: {resp.text[:500]}")
                
    except Exception as e:
        st.error(f"⚠️ 連線過程發生異常: {e}")

if __name__ == "__main__":
    test_api()




