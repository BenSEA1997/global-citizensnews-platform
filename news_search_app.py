import streamlit as st
import requests

def test_api():
    st.set_page_config(page_title="Path Fix Force")
    st.title("🛡️ 搜尋引擎：路徑強制修正版 (v2)")
    
    # 1. 讀取並強力清理 Secrets
    try:
        api_key = st.secrets["GOOGLE_API_KEY"].strip().replace('\n', '').replace(' ', '')
        cx = st.secrets["CX_HK"].strip().replace('\n', '').replace(' ', '')
        st.info(f"正在測試引擎 ID: `{cx}`")
    except Exception as e:
        st.error(f"❌ 讀取 Secrets 失敗: {e}")
        st.stop()

    # 2. **拆解網址，防止任何截斷錯誤**
    part1 = "https://www."
    part2 = "googleapis.com"
    part3 = "/customsearch/v1"
    full_api_url = part1 + part2 + part3
    
    st.write(f"📡 最終發出請求至 (驗證完整路徑): `{full_api_url}`")
    
    # 3. 發出請求
    params = {
        "key": api_key,
        "cx": cx,
        "q": "香港"
    }
    
    try:
        # 直接使用拼接好的完整網址
        resp = requests.get(full_api_url, params=params, timeout=20)
        
        if resp.status_code == 200:
            st.success("✅ 終於成功了！連線完全正常。")
            data = resp.json()
            if "items" in data:
                st.write(f"🔍 搜尋結果範例：**{data['items'][0]['title']}**")
                st.json(data['items'][0])
            else:
                st.warning("⚠️ 連線成功，但該引擎內找不到『香港』。")
        else:
            st.error(f"❌ Google 拒絕連線 (HTTP {resp.status_code})")
            try:
                st.json(resp.json())
            except:
                st.text_area("原始錯誤內容 (404代表路徑依然不對):", resp.text[:500])
                
    except Exception as e:
        st.error(f"⚠️ 連線異常: {e}")

if __name__ == "__main__":
    test_api()






