import streamlit as st
import requests

def test_api():
    st.title("🕵️ 終極連線診斷 (API Key 2 測試)")
    
    # 讀取 Secrets
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
        cx = st.secrets["CX_HK"]
        st.write(f"正在使用引擎 ID: {cx}")
    except Exception as e:
        st.error(f"無法讀取 Secrets 設定: {e}")
        return

    # 發出最純粹的測試請求
    url = "https://googleapis.com"
    params = {"key": api_key, "cx": cx, "q": "test"}
    
    resp = requests.get(url, params=params)
    
    if resp.status_code == 200:
        st.success("✅ 恭喜！連線完全成功。API key 2 已經生效！")
        data = resp.json()
        if "items" in data:
            st.write(f"成功搜到結果，第一則為：{data['items'][0]['title']}")
            st.json(data['items'][:2]) # 顯示前兩則確認
    else:
        st.error(f"❌ 連線失敗 (HTTP 錯誤碼: {resp.status_code})")
        st.json(resp.json()) # 顯示詳細原因

if __name__ == "__main__":
    test_api()




