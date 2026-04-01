import streamlit as st
import pandas as pd
import os
import time
import altair as alt
from datetime import datetime
import urllib.parse

# --- 1. 頁面設定 ---
st.set_page_config(page_title="新光醫院 AI 退場審定系統", layout="wide")

# --- 2. 退場條件定義 ---
EXIT_SOP = {
    "🛑 直接退場條件": ["涉及資安違規拒修", "效能嚴重衰退至紅燈區", "合約終止"],
    "⚠️ 審議退場條件": ["成本效益不符", "技術汰換", "使用率極低", "PoC 逾 12 個月未結案"],
    "✅ 行政執行程序": ["臨床衝擊評估 (PI 已完成)", "技術切斷 (API/VM 移除)", "資料封存", "更新透明性網頁紀錄"]
}

DB_NAME = "final_exit_v500.csv"

def init_db():
    if not os.path.exists(DB_NAME):
        cols = ["Project", "Voter", "Time", "Advice"]
        for items in EXIT_SOP.values(): cols.extend(items)
        pd.DataFrame(columns=cols).to_csv(DB_NAME, index=False)

# --- 3. 評審填報介面 (手機) ---
def reviewer_view(p_target):
    st.markdown(f"# 🏛️ AI 退場評審專用表")
    st.error(f"📍 審定目標：{p_target}")
    voter = st.text_input("評審姓名", key="voter_name")
    
    votes = {}
    for cat, items in EXIT_SOP.items():
        st.subheader(cat)
        for i in items:
            val = st.checkbox(i, key=f"chk_{i}")
            votes[i] = 1 if val else 0
            
    advice = st.text_area("💬 建議意見")
    
    if st.button("🚀 提交決議", use_container_width=True, type="primary"):
        if not voter: st.error("❌ 請填寫姓名"); return
        init_db()
        df = pd.read_csv(DB_NAME)
        row = {"Project": p_target, "Voter": voter, "Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Advice": advice}
        row.update(votes)
        pd.DataFrame([row]).to_csv(DB_NAME, mode='a', index=False, header=False)
        st.success("✅ 提交成功！")
        time.sleep(1)
        st.query_params.clear()
        st.rerun()

# --- 4. 看板端介面 (電腦) ---
def admin_view():
    with st.sidebar:
        st.title("⚙️ 管理選單")
        if st.button("🗑️ 清空數據紀錄"):
            if os.path.exists(DB_NAME): os.remove(DB_NAME)
            st.session_state.clear()
            st.rerun()
        st.divider()
        new_p = st.text_input("➕ 新增待審專案")
        if st.button("建立"):
            if new_p:
                init_db()
                pd.DataFrame([{"Project": new_p, "Voter": "SYSTEM"}]).to_csv(DB_NAME, mode='a', index=False, header=False)
                st.session_state["p_focus"] = new_p
                st.rerun()

    init_db()
    df_all = pd.read_csv(DB_NAME)
    projs = sorted([str(p) for p in df_all["Project"].dropna().unique() if str(p) != "SYSTEM"])
    
    if not projs:
        st.info("👋 您好，請在左側建立專案以開始。")
        return

    curr = st.selectbox("🎯 選擇目標專案：", projs)
    st.markdown(f"# 📉 {curr} - 退場審議看板")
    
    # ✅ 自動偵測目前 App 運行的網址 (最高階解法)
    try:
        # 獲取當前運行的完整 URL，避免 localhost 錯誤
        current_url = "https://ai-exit-system.streamlit.app" # 部署後如果網址不同請修改此行
        vote_link = f"{current_url}/?m=vote&t={urllib.parse.quote(curr)}"
    except:
        vote_link = "網址產生中..."

    c1, c2 = st.columns([1, 4])
    c1.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(vote_link)}")
    st.info(f"評審填報網址：{vote_link}")

# --- 5. 路由控管 ---
q = st.query_params
if q.get("m") == "vote" and q.get("t"):
    reviewer_view(q.get("t"))
else:
    admin_view()