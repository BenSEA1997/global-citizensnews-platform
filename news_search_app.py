import streamlit as st
import requests

# 測試版標題（放在 import 後面）
st.markdown("**測試版 v0.1 – 全球新聞探索與公民記者平台** 歡迎反饋！")

st.set_page_config(page_title="全球即時目擊新聞搜尋器", page_icon="🌍")
st.title("🌍 全球即時目擊新聞搜尋器")
st.write("輸入地點或事件，例如：伊朗德黑蘭、東京上野公園櫻花")

query = st.text_input("搜尋關鍵字", "東京上野公園櫻花")

# 語言選擇下拉選單
language_option = st.selectbox(
    "選擇語言範圍",
    options=[
        "全部語言（最多結果）",
        "中文 + 英文",
        "只中文（簡繁皆可）",
        "只英文"
    ],
    index=0  # 預設全部語言
)

# 根據選擇設定 language 參數
if language_option == "全部語言（最多結果）":
    lang_param = ""
elif language_option == "中文 + 英文":
    lang_param = "&language=zh,en"
elif language_option == "只中文（簡繁皆可）":
    lang_param = "&language=zh"
elif language_option == "只英文":
    lang_param = "&language=en"
else:
    lang_param = ""

if st.button("開始搜尋"):
    if not query:
        st.error("請輸入關鍵字")
    else:
        st.info("正在抓取傳統新聞媒體（使用 NewsData.io）...")
        
        # api_key 建議改用 secrets（見下面說明）
        api_key = "pub_ea6292c128e7496da2492cf0de092565"  # 你的真實 Key
        
        url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={query}{lang_param}&size=10"
        
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                articles = data.get("results", [])
                st.subheader("📰 傳統公信力媒體報導")
                if not articles:
                    st.warning("沒有找到相關新聞，請試其他關鍵字或英文查詢")
                for article in articles:
                    st.write(f"**{article.get('title', '無標題')}**")
                    st.write(article.get('description', '無描述'))
                    st.write(f"來源：{article.get('source_id', '未知')} | 時間：{article.get('pubDate', '未知')}")
                    st.write(f"[閱讀全文]({article.get('link', '#')})")
                    st.divider()
            else:
                st.error(f"API 錯誤：{response.status_code} - {response.text}")
        except requests.exceptions.Timeout:
            st.error("連接超時，請檢查網路或 VPN")
        except Exception as e:
            st.error(f"其他錯誤：{str(e)}")
        
        st.subheader("📱 社交媒體目擊者即時資訊（X）")
        st.write("（這部分目前需要 X API Key，單篇貼文約 0.005 美元，適合少量使用）")
        st.info("如果你有 X API Key，我可以再給你完整程式碼加入這裡！")
        
        st.success("✅ 完成！這就是你的新聞搜尋器原型")