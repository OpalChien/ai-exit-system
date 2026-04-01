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

# --- 2. 數據指標定義 (全細項) ---
EXIT_SOP = {
    "🛑 直接退場條件": ["涉及資安違規拒修", "效能嚴重衰退至紅燈區", "合約終止"],
    "⚠️ 審議退場條件": ["成本效益不符", "技術汰換", "使用率極低", "PoC 逾 12 個月未結案"],
    "✅ 行政程序查核": ["臨床衝擊評估 (PI 已完成)", "技術切斷 (API/VM 移除)", "資料封存", "更新透明性網頁紀錄"]
}

DB_NAME = "final_exit_v1000.csv"

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
    advice = st.text_area("💬 審議建議", height=100)
    if st.button("🚀 提交決議", use_container_width=True, type="primary"):
        if not voter or not advice:
            st.warning("⚠️ 請輸入姓名與意見"); return
        init_db()
        df = pd.read_csv(DB_NAME)
        row = {"Project": p_target, "Voter": voter, "Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Advice": advice}
        row.update(votes)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_csv(DB_NAME, index=False)
        st.balloons()
        st.success("✅ 提交成功！")
        time.sleep(2); st.query_params.clear(); st.rerun()

# --- 4. 看板端介面 (電腦) ---
def admin_dashboard():
    with st.sidebar:
        st.title("⚙️ 管理")
        if st.button("🗑️ 清空數據"):
            if os.path.exists(DB_NAME): os.remove(DB_NAME)
            st.session_state.clear(); st.rerun()
        new_p = st.text_input("➕ 新專案")
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
    if not projs: st.info("請建立專案"); return
    curr = st.selectbox("🎯 選擇目標專案：", projs)
    
    st.markdown(f"<h1 style='text-align:center;'>📊 {curr} - 退場審議戰情室</h1>", unsafe_allow_html=True)
    
    base_url = "https://ai-exit-system.streamlit.app" # 部署後請視情況微調
    vote_link = f"{base_url}/?m=vote&t={urllib.parse.quote(curr)}"
    
    c1, c2 = st.columns([1, 4])
    c1.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(vote_link)}")
    c2.info(f"掃碼投票連結：{vote_link}")

    st.divider()

    df_p = df_all[(df_all["Project"] == curr) & (df_all["Voter"] != "SYSTEM")]
    if not df_p.empty:
        df_u = df_p.sort_values("Time").drop_duplicates(subset=["Voter"], keep="last")
        v_count = len(df_u)
        st.metric("已參與評審人數", f"{v_count} 人")

        # --- 雙圖表併列區 ---
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("📌 大類佔比分析")
            pie_list = []
            for cat, items in EXIT_SOP.items():
                triggered_count = sum(df_u[it].sum() for it in items)
                pie_list.append({"分類": cat, "觸發次數": triggered_count})
            
            pie_chart = alt.Chart(pd.DataFrame(pie_list)).mark_arc(innerRadius=60).encode(
                theta=alt.Theta(field="觸發次數", type="quantitative"),
                color=alt.Color(field="分類", type="nominal", scale=alt.Scale(range=["#dc3545", "#ffc107", "#28a745"])),
                tooltip=["分類", "觸發次數"]
            ).properties(height=350)
            st.altair_chart(pie_chart, use_container_width=True)

        with col_right:
            st.subheader("🔍 指標細項分析 (票數)")
            detail_list = []
            for cat, items in EXIT_SOP.items():
                for it in items:
                    detail_list.append({"細項指標": it, "勾選人數": int(df_u[it].sum()), "分類": cat})
            
            detail_df = pd.DataFrame(detail_list)
            # 橫向長條圖列出所有細項
            detail_chart = alt.Chart(detail_df).mark_bar().encode(
                x=alt.X("勾選人數:Q", axis=alt.Axis(tickMinStep=1)),
                y=alt.Y("細項指標:N", sort="-x", axis=alt.Axis(labelLimit=300)),
                color=alt.Color("分類:N", scale=alt.Scale(range=["#dc3545", "#ffc107", "#28a745"]), legend=None),
                tooltip=["細項指標", "勾選人數"]
            ).properties(height=350)
            st.altair_chart(detail_chart, use_container_width=True)

        st.divider()
        st.subheader("💬 評審委員會意見 (匿名)")
        for idx, row in df_u.reset_index().iterrows():
            st.markdown(f"> **審議委員 {chr(65+idx)}**：{row['Advice']} (_{row['Time']}_)")
    else:
        st.warning("⏳ 等待首位評審數據...")

# --- 5. 路由 ---
params = st.query_params
if params.get("m") == "vote" and params.get("t"):
    reviewer_page(params.get("t"))
else:
    admin_dashboard()
