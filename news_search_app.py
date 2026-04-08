# ==================== 1. 配置更新 (針對 English 與 China) ====================
# 新增：中國大陸常用核心域名 (確保補充包也能識別)
MAINLAND_DOMAINS = {"xinhuanet.com", "people.com.cn", "chinadaily.com.cn", "thepaper.cn", "caixin.com", "cctv.com", "ifeng.com"}
# 新增：英文全球 TLD 白名單 (阻斷 .hk 滲入英文引擎)
ENGLISH_TLD_ALLOWED = {".com", ".org", ".net", ".edu", ".gov", ".uk", ".us", ".au", ".ca"}

# ==================== 2. UI 邏輯修正 ====================
# (fetch_google_news 與 split_date_ranges 保持 Ver 10.1 不動)

# ... [中間代碼省略，直接看搜尋邏輯區] ...

if st.button("執行搜尋", type="primary"):
    # ... [日期處理省略] ...
    
    # 【關鍵修正】區域參數重新定義
    tld_target = ""
    is_china_mode = False
    
    if "香港" in region:
        white_list, gl, hl, ceid, tld_target = HK_WHITE_LIST, "HK", "zh-HK", "HK:zh-Hant", ".hk"
    elif "台灣" in region:
        white_list, gl, hl, ceid, tld_target = TW_WHITE_LIST, "TW", "zh-TW", "TW:zh-Hant", ".tw"
    elif "英文" in region:
        # 修正：確保英文引擎使用正確白名單，且 TLD 排除 .hk
        white_list, gl, hl, ceid, tld_target = ENGLISH_GLOBAL_LIST, "US", "en", "US:en", "GLOBAL_EN"
    else: # 中國大陸
        # 修正：將 ceid 轉向新加坡簡體，避免 CN 接口回傳 0
        white_list, gl, hl, ceid, tld_target = MAINLAND_CHINA_WHITE_LIST, "SG", "zh-CN", "SG:zh-Hans", ".cn"
        is_china_mode = True

    # ... [分段挖掘 build_url 邏輯保持 Ver 10.1 不動] ...

    # ==================== 3. 三層過濾邏輯優化 ====================
    final_results, seen = [], set()
    count_white, count_supp = 0, 0
    
    for a in (all_raw_white + all_raw_supp):
        if a['title'] in seen: continue
        d, s_title = a['real_domain'], a['source']
        label = ""
        
        # A. 核心白名單判定
        if any(w_domain in d for w_domain in white_list):
            # 額外檢查：如果是英文模式，阻斷任何帶有 .hk 的虛假英文白名單
            if tld_target == "GLOBAL_EN" and ".hk" in d: continue
            label, count_white = "✅ 核心白名單", count_white + 1
        
        # B. 補充包判定
        else:
            if is_china_mode:
                # 中國模式：放行 .cn 或 核心大陸網域
                if d.endswith(".cn") or any(md in d for md in MAINLAND_DOMAINS):
                    label, count_supp = "🌐 區域補充包", count_supp + 1
            elif tld_target == "GLOBAL_EN":
                # 英文模式：只放行主流英文 TLD，排除 .hk / .tw
                if any(d.endswith(ext) for ext in ENGLISH_TLD_ALLOWED) and not any(bad in d for bad in [".hk", ".tw", ".cn"]):
                    label, count_supp = "🌐 區域補充包", count_supp + 1
            elif tld_target and d.endswith(tld_target):
                # 香港/台灣模式：維持 Ver 10.1 的 TLD 鎖定
                label, count_supp = "🌐 區域補充包", count_supp + 1
            elif any(sk in s_title for sk in HK_SUPP_KEYWORDS) and "香港" in region:
                # 香港模式：關鍵字放寬
                label, count_supp = "🌐 區域補充包", count_supp + 1
            
        if label:
            a['final_label'] = label
            final_results.append(a)
            seen.add(a['title'])

    # ... [顯示與診斷面板保持 Ver 10.1 不動] ...
