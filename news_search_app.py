import streamlit as st
import requests

def test_api():
    st.set_page_config(page_title="Terminal 404 Debug")
    st.title("🕵️ 搜尋引擎：路徑診斷最終版")
    
    # 1. 讀取並強力清理 Secrets
    try:
        # 強制移除所有空格、換行、引號
        api_key = "".join(st.secrets["GOOGLE_API_KEY"].split()).replace('"', '').replace("'", "").strip()
        cx = "".join(st.secrets["CX_HK"].split()).replace('"', '').replace("'", "").strip()
        st.info(f"正在診斷引擎 ID: `{cx}`")
    except Exception as e:
        st.error(f"❌ 讀取 Secrets 失敗: {e}")
        st.stop()

    # 2. **完全硬編碼的完整路徑**
    api_url = "https://googleapis.com"
    
    # 3. 發出請求
    params = {
        "key": api_key,
        "cx": cx,
        "q": "香港",
        "num": 1
    }
    
    # 顯示發出的網址 (隱藏關鍵資訊) 以供肉眼檢查
    st.write(f"📡 正在請求: `https://googleapis.com?cx={cx}&q=...`")
    
    try:
        resp = requests.get(api_url, params=params, timeout=15)
        
        if resp.status_code == 200:
            st.success("✅ 恭喜！404 障礙已排除，連線完全成功！")
            st.json(resp.json().get("items", [])[:1])
        else:
            st.error(f"❌ Google 依然拒絕 (HTTP {resp.status_code})")
            if resp.status_code == 404:
                st.warning("💡 診斷：404 代表網址不對。請檢查 Google Cloud 是否啟用了錯誤的 API 類型。")
                st.text_area("回應原始碼 (若見機器人則路徑仍錯):", resp.text[:500])
            else:
                st.json(resp.json())
                
    except Exception as e:
        st.error(f"⚠️ 系統異常: {e}")

if __name__ == "__main__":
    test_api()


