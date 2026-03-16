import streamlit as st
import requests

def test_api():
    st.set_page_config(page_title="Final API Test")
    st.title("🕵️ 終極連線診斷 (URL 絕對修正版)")
    
    # 1. 讀取並清理 Secrets (防止隱形空格)
    try:
        # 使用 .strip() 移除前後可能存在的空格或換行
        api_key = st.secrets["GOOGLE_API_KEY"].strip()
        cx = st.secrets["CX_HK"].strip()
        st.info(f"正在診斷引擎 ID: `{cx}`")
    except Exception as e:
        st.error(f"❌ 無法讀取 Secrets: {e}")
        st.stop()

    # 2. **最關鍵的 URL 完整路徑**
    # 必須精確為這個字串，不能有任何偏差
    api_url = "https://googleapis.com"
    
    params = {
        "key": api_key,
        "cx": cx,
        "q": "香港",
        "num": 3
    }
    
    # 3. 執行請求
    try:
        # 使用傳遞 params 的方式，避免手動拼湊 URL 出錯
        resp = requests.get(api_url, params=params, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            st.success("✅ 恭喜！連線完全成功！Google 已認可您的 API Key 2 與 CX ID。")
            
            if "items" in data:
                st.write("---")
                st.write(f"🔍 成功抓取到新聞：**{data['items'][0]['title']}**")
                st.json(data['items'][:1])
            else:
                st.warning("⚠️ 連線成功，但您的白名單內找不到『香港』相關內容。請檢查 PSE 後台的網域設定。")
                
        else:
            # 如果不是 200，印出診斷資訊
            st.error(f"❌ Google 拒絕連線 (HTTP 狀態碼: {resp.status_code})")
            st.write(f"請求網址範例 (已隱藏金鑰): `https://googleapis.com?cx={cx}&q=...`")
            
            try:
                # 嘗試顯示 JSON 格式的錯誤原因
                st.json(resp.json())
            except:
                # 如果 Google 回傳的是 HTML 錯誤頁面 (404)
                st.warning("⚠️ Google 回傳了 HTML 錯誤頁面。這通常代表網址路徑不對或 API Key 格式有問題。")
                st.text_area("原始回應 (前500字):", resp.text[:500])
                
    except Exception as e:
        st.error(f"⚠️ 連線過程發生系統異常: {e}")

if __name__ == "__main__":
    test_api()





