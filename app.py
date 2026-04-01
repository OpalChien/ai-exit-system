import streamlit as st
import pandas as pd
import os
import time
import altair as alt
from datetime import datetime
import urllib.parse
from streamlit_autorefresh import st_autorefresh

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="新光醫院 AI 退場審定系統", layout="wide")

# ✅ 自動重新整理 (5 秒一次)
st_autorefresh(interval=5000, key="data_refresh")

# --- 2. 數據指標定義 (移除行政查核，保留審議核心) ---
EXIT_SOP = {
    "🛑 直接退場條件": ["涉及資安違規拒修", "效能嚴重衰退至紅燈區", "合約終止"],
    "⚠️ 審議退場條件": ["成本效益不符", "技術汰換", "使用率極低", "PoC 逾 12 個月未結案"]
}

DB_NAME = "final_exit_v1100.csv"

def init_db():
    if not os.path.exists(DB_NAME):
        cols = ["Project", "Voter", "Time", "Advice"]
        for items in EXIT_SOP.values(): cols.extend(items)
        pd.DataFrame(columns=cols).to_csv(DB_NAME, index=False)

# --- 3. 評審填報介面 (手機) ---
def reviewer_page(p_target):
    st.markdown(f"## 🏛️ AI 退場評審填報端")
    st.error(f"📍 專案：{p_target}")
    voter = st.text_input("評審姓名", key="v_name")
    st.divider()
    
    votes = {}
    for cat, items in EXIT_SOP.items():
        st.subheader(cat)
        for i in items:
            val = st.checkbox(i, key=f"chk_{i}")
            votes[i] = 1 if val else 0
            
    # ✅ 移除必填限制 (標註為選填)
    advice = st.text_area("💬 審議建議 (選填)", height=100)
    
    if st.button("🚀 提交決議", use_container_width=True, type="primary"):
        if not voter:
            st.warning("⚠️ 請輸入姓名再提交"); return
        
        init_db()
        df = pd.read_csv(DB_NAME)
        # 如果 advice 為空，填入預設值
        final_advice = advice if advice.strip() else "無特定建議"
        
        row = {"Project": p_target, "Voter": voter, "Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Advice": final_advice}
        row.update(votes)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_csv(DB_NAME, index=False)
        st.balloons()
        st.success("✅ 提交成功！")
        time.sleep(2); st.query_params.clear(); st.rerun()

# --- 4. 看板端介面 (電腦) ---
def admin_dashboard():
    with st.sidebar:
        st.title("⚙️ 管理選單")
        if st.button("🗑️ 清空數據紀錄"):
            if os.path.exists(DB_NAME): os.remove(DB_NAME)
            st.session_state.clear(); st.rerun()
        st.divider()
        new_p = st.text_input("➕ 新增待審專案")
        if st.button("建立"):
            if new_p:
                init_db()
                df = pd.read_csv(DB_NAME)
                df = pd.concat([df, pd.DataFrame([{"Project": new_p, "Voter": "SYSTEM"}])], ignore_index=True)
                df.to_csv(DB_NAME, index=False)
                st.session_state["p_focus"] = new_p; st.rerun()

    init_db()
    df_all = pd.read_csv(DB_NAME)
    projs = sorted([str(p) for p in df_all["Project"].dropna().unique() if str(p) != "SYSTEM"])
    if not projs: st.info("👋 請在左側建立專案。"); return
    curr = st.selectbox("🎯 選擇目標專案：", projs)
    
    st.markdown(f"<h1 style='text-align:center;'>📊 {curr} - 退場審議戰情室</h1>", unsafe_allow_html=True)
    
    # 🔗 請更換為您的正式網址
    base_url = "https://ai-exit-system.streamlit.app" 
    vote_link = f"{base_url}/?m=vote&t={urllib.parse.quote(curr)}"
    
    c1, c2 = st.columns([1, 4])
    c1.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(vote_link)}")
    c2.info(f"掃碼投票連結 (已開啟自動同步)：{vote_link}")

    st.divider()

    df_p = df_all[(df_all["Project"] == curr) & (df_all["Voter"] != "SYSTEM")]
    if not df_p.empty:
        df_u = df_p.sort_values("Time").drop_duplicates(subset=["Voter"], keep="last")
        v_count = len(df_u)
        st.metric("已參與評審人數", f"{v_count} 人")

        # --- 圖表區 ---
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("📌 核心指標佔比")
            pie_list = []
            for cat, items in EXIT_SOP.items():
                triggered_count = sum(df_u[it].sum() for it in items)
                pie_list.append({"分類": cat, "觸發次數": triggered_count})
            
            pie_chart = alt.Chart(pd.DataFrame(pie_list)).mark_arc(innerRadius=60).encode(
                theta=alt.Theta(field="觸發次數", type="quantitative"),
                color=alt.Color(field="分類", type="nominal", scale=alt.Scale(range=["#dc3545", "#ffc107"])),
                tooltip=["分類", "觸發次數"]
            ).properties(height=350)
            st.altair_chart(pie_chart, use_container_width=True)

        with col_right:
            st.subheader("🔍 指標細項統計 (票數)")
            detail_list = []
            for cat, items in EXIT_SOP.items():
                for it in items:
                    detail_list.append({"指標細項": it, "勾選票數": int(df_u[it].sum()), "分類": cat})
            
            detail_df = pd.DataFrame(detail_list)
            detail_chart = alt.Chart(detail_df).mark_bar().encode(
                x=alt.X("勾選票數:Q", axis=alt.Axis(tickMinStep=1)),
                y=alt.Y("指標細項:N", sort="-x"),
                color=alt.Color("分類:N", scale=alt.Scale(range=["#dc3545", "#ffc107"]), legend=None),
                tooltip=["指標細項", "勾選票數"]
            ).properties(height=350)
            st.altair_chart(detail_chart, use_container_width=True)

        st.divider()
        st.subheader("💬 委員審議意見 (匿名)")
        for idx, row in df_u.reset_index().iterrows():
            st.markdown(f"> **審議委員 {chr(65+idx)}**：{row['Advice']} (_{row['Time']}_)")
    else:
        st.warning("⏳ 正在等待委員掃碼填報...")

# --- 5. 路由 ---
params = st.query_params
if params.get("m") == "vote" and params.get("t"):
    reviewer_page(params.get("t"))
else:
    admin_dashboard()
