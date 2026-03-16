import streamlit as st
import requests

def test_api():
    st.title("🛡️ 搜尋引擎：絕對路徑強制修正版")
    
    # 1. 強力清理 Secrets (移除所有換行與空格)
    try:
        # 使用 splitlines() 再 join 可以徹底移除所有平台的換行符
        k = "".join(st.secrets["GOOGLE_API_KEY"].split()).strip()
        c = "".join(st.secrets["CX_HK"].split()).strip()
        st.info(f"正在連線引擎 ID: `{c}`")
    except Exception as e:
        st.error(f"❌ 讀取 Secrets 失敗: {e}")
        st.stop()

    # 2. **完全手寫的完整 URL**
    base_url = "https://googleapis.com"
    
    # 使用字典傳參，讓 requests 自動處理編碼，這是最安全的方法
    params = {
        "key": k,
        "cx": c,
        "q": "香港",
        "num": 5
    }
    
    try:
        # 發出請求
        resp = requests.get(base_url, params=params, timeout=15)
        
        if resp.status_code == 200:
            st.success("✅ 連線成功！")
            st.json(resp.json().get("items", [])[:1])
        else:
            st.error(f"❌ 錯誤碼: {resp.status_code}")
            st.text_area("回應詳情 (若為404代表API路徑或類型錯了):", resp.text[:500])
    except Exception as e:
        st.error(f"⚠️ 連線異常: {e}")

if __name__ == "__main__":
    test_api()




