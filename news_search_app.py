import streamlit as st
import requests

def test_api():
    st.set_page_config(page_title="Final Final Success")
    st.title("🛡️ 搜尋引擎：路徑強制修正版")
    
    # 1. 讀取並強力清理 Secrets
    try:
        # 強制移除所有換行、空格
        api_key = st.secrets["GOOGLE_API_KEY"].strip().replace('\n', '').replace(' ', '')
        cx = st.secrets["CX_HK"].strip().replace('\n', '').replace(' ', '')
        st.info(f"正在測試引擎 ID: `{cx}`")
    except Exception as e:
        st.error(f"❌ 讀取 Secrets 失敗: {e}")
        st.stop()

    # 2. **手動強行拼湊最正確的 URL**
    # 我們不使用變數組合，直接寫死完整字串
    full_api_url = "https://googleapis.com"
    
    st.write(f"📡 最終發出請求至: `{full_api_url}`")
    
    # 3. 發出請求
    params = {
        "key": api_key,
        "cx": cx,
        "q": "香港"
    }
    
    try:
        # 使用 verify=True 確保 SSL 安全連線
        resp = requests.get(full_api_url, params=params, timeout=20)
        
        if resp.status_code == 200:
            st.success("✅ 恭喜！連線完全成功。我們終於抓到正確的路徑了！")
            data = resp.json()
            if "items" in data:
                st.write("---")
                st.write(f"🔍 搜尋結果範例：**{data['items'][0]['title']}**")
                st.json(data['items'][:1])
            else:
                st.warning("⚠️ 連線成功，但白名單內找不到關於『香港』的內容。")
        else:
            st.error(f"❌ Google 拒絕連線 (HTTP {resp.status_code})")
            # 顯示 Google 的 JSON 錯誤訊息
            try:
                st.json(resp.json())
            except:
                st.text_area("原始錯誤內容:", resp.text[:500])
                
    except Exception as e:
        st.error(f"⚠️ 連線過程發生異常: {e}")

if __name__ == "__main__":
    test_api()






