import streamlit as st
import requests

def test_api():
    st.set_page_config(page_title="Final Fix Success")
    st.title("🚀 終極連線診斷 (換行符號修正版)")
    
    # 1. 讀取並強力清理 Secrets
    try:
        # 強制移除換行符號與前後空格
        api_key = st.secrets["GOOGLE_API_KEY"].replace('\n', '').strip()
        cx = st.secrets["CX_HK"].replace('\n', '').strip()
        st.info(f"正在連線引擎: `{cx}`")
    except Exception as e:
        st.error(f"❌ 讀取 Secrets 失敗: {e}")
        st.stop()

    # 2. 正確的完整 API 網址
    api_url = "https://googleapis.com"
    
    params = {
        "key": api_key,
        "cx": cx,
        "q": "香港",
        "num": 3
    }
    
    # 3. 發出請求
    try:
        resp = requests.get(api_url, params=params, timeout=15)
        
        if resp.status_code == 200:
            st.success("✅ 恭喜！連線成功！404 障礙已排除。")
            data = resp.json()
            if "items" in data:
                st.write(f"成功抓取新聞：**{data['items'][0]['title']}**")
                st.json(data['items'][0])
        else:
            st.error(f"❌ 請求失敗 (HTTP {resp.status_code})")
            st.json(resp.json())
                
    except Exception as e:
        st.error(f"⚠️ 連線異常: {e}")

if __name__ == "__main__":
    test_api()






