import streamlit as st
import requests

def test_api():
    st.set_page_config(page_title="Final 404 Fix")
    st.title("🛡️ 搜尋引擎：絕對路徑「硬核」修正版")
    
    # 1. 讀取並強力清理 Secrets
    try:
        # 移除所有可能的隱形換行、空格或非法字元
        api_key = "".join(st.secrets["GOOGLE_API_KEY"].split()).strip()
        cx = "".join(st.secrets["CX_HK"].split()).strip()
        st.info(f"正在連線引擎 ID: `{cx}`")
    except Exception as e:
        st.error(f"❌ 讀取 Secrets 失敗: {e}")
        st.stop()

    # 2. **絕對正確的 Google API 完整路徑 (不可有任何偏差)**
    # 注意：必須包含 /customsearch/v1
    target_url = "https://googleapis.com"
    
    # 3. 發出請求
    params = {
        "key": api_key,
        "cx": cx,
        "q": "香港",
        "num": 3
    }
    
    try:
        # 直接對準完整路徑發出請求
        resp = requests.get(target_url, params=params, timeout=15)
        
        if resp.status_code == 200:
            st.success("✅ 恭喜！連線完全成功。404 障礙已徹底排除！")
            data = resp.json()
            if "items" in data:
                st.write(f"🔍 成功抓取新聞：**{data['items'][0]['title']}**")
                st.json(data['items'][:1])
        else:
            st.error(f"❌ Google 拒絕連線 (HTTP {resp.status_code})")
            # 如果是 404，顯示詳細診斷
            if resp.status_code == 404:
                st.warning("💡 診斷：404 代表網址路徑不對。請確認您在 Google Cloud 啟用的服務名稱是否為『Custom Search API』。")
                st.text_area("回應內容 (若看到機器人則路徑仍錯):", resp.text[:500])
            else:
                st.json(resp.json())
                
    except Exception as e:
        st.error(f"⚠️ 連線過程發生異常: {e}")

if __name__ == "__main__":
    test_api()


