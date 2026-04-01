import streamlit as st
import pandas as pd
import os
import time
import altair as alt
from datetime import datetime
import urllib.parse

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="新光醫院 AI 退場審定系統", layout="wide")

# --- 2. 數據指標定義 ---
EXIT_SOP = {
    "🛑 直接退場條件": ["涉及資安違規拒修", "效能嚴重衰退至紅燈區", "合約終止"],
    "⚠️ 審議退場條件": ["成本效益不符", "技術汰換", "使用率極低", "PoC 逾 12 個月未結案"],
    "✅ 行政程序查核": ["臨床衝擊評估 (PI 已完成)", "技術切斷 (API/VM 移除)", "資料封存", "更新透明性網頁紀錄"]
}

DB_NAME = "final_exit_v800.csv"

def init_db():
    if not os.path.exists(DB_NAME):
        cols = ["Project", "Voter", "Time", "Advice"]
        for items in EXIT_SOP.values(): cols.extend(items)
        pd.DataFrame(columns=cols).to_csv(DB_NAME, index=False)

# --- 3. 評審填報介面 (手機端) ---
def reviewer_page(p_target):
    st.markdown(f"## 🏛️ AI 退場評審填報端")
    st.error(f"📍 當前審議專案：{p_target}")
    
    voter = st.text_input("評審姓名", key="v_name", placeholder="請輸入您的姓名")
    st.divider()
    
    votes = {}
    for cat, items in EXIT_SOP.items():
        st.subheader(cat)
        for i in items:
            val = st.checkbox(i, key=f"chk_{i}")
            votes[i] = 1 if val else 0
            
    advice = st.text_area("💬 審議具體建議", height=150, placeholder="請輸入您對此案退場與否的專業意見...")
    
    if st.button("🚀 提交審議決議", use_container_width=True, type="primary"):
        if not voter or not advice:
            st.warning("⚠️ 請填寫姓名與建議意見再送出。")
            return
            
        init_db()
        df = pd.read_csv(DB_NAME)
        row = {"Project": p_target, "Voter": voter, "Time": datetime.now().strftime("%Y-%m-%d %H:%M"), "Advice": advice}
        row.update(votes)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_csv(DB_NAME, index=False)
        
        # ✨ 氣球特效 ✨
        st.balloons()
        st.success(f"✅ 提交成功！謝謝 {voter} 委員的評分。")
        
        time.sleep(2)
        st.query_params.clear()
        st.rerun()

# --- 4. 看板端介面 (電腦端) ---
def admin_dashboard():
    with st.sidebar:
        st.title("⚙️ 管理選單")
        if st.button("🗑️ 清空所有數據"):
            if os.path.exists(DB_NAME): os.remove(DB_NAME)
            st.session_state.clear()
            st.rerun()
        st.divider()
        new_p = st.text_input("➕ 新增待審專案名稱")
        if st.button("建立專案"):
            if new_p:
                init_db()
                df = pd.read_csv(DB_NAME)
                df = pd.concat([df, pd.DataFrame([{"Project": new_p, "Voter": "SYSTEM"}])], ignore_index=True)
                df.to_csv(DB_NAME, index=False)
                st.session_state["p_focus"] = new_p
                st.rerun()

    init_db()
    df_all = pd.read_csv(DB_NAME)
    projs = sorted([str(p) for p in df_all["Project"].dropna().unique() if str(p) != "SYSTEM"])
    
    if not projs:
        st.info("👋 您好，請在左側建立專案以開始審理。")
        return

    curr = st.selectbox("🎯 選擇顯示專案：", projs)
    st.markdown(f"<h1 style='text-align:center;'>📊 {curr} - 退場審議看板</h1>", unsafe_allow_html=True)
    
    # 🔗 自動校對網址
    base_url = "https://ai-exit-system.streamlit.app" 
    vote_link = f"{base_url}/?m=vote&t={urllib.parse.quote(curr)}"
    
    c1, c2 = st.columns([1, 4])
    c1.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(vote_link)}")
    c2.info(f"評審手機掃碼連結：\n{vote_link}")

    st.divider()

    df_p = df_all[(df_all["Project"] == curr) & (df_all["Voter"] != "SYSTEM")]
    
    if not df_p.empty:
        df_u = df_p.sort_values("Time").drop_duplicates(subset=["Voter"], keep="last")
        v_count = len(df_u)

        col1, col2 = st.columns(2)
        col1.metric("已參與評審人數", f"{v_count} 人")
        
        direct_items = EXIT_SOP["🛑 直接退場條件"]
        triggered_red = any(df_u[it].sum() > 0 for it in direct_items)
        if triggered_red:
            col2.error("🚨 結論建議：觸發直接退場條件")
        else:
            col2.warning("⚖️ 結論建議：委員會討論判定")

        st.divider()

        # 📊 統計圖表
        st.subheader("📌 各項指標觸發百分比 (%)")
        chart_data = []
        for cat, items in EXIT_SOP.items():
            for i in items:
                pct = (df_u[i].sum() / v_count) * 100
                chart_data.append({"項目": i, "觸發率(%)": pct, "分類": cat})
        
        plot_df = pd.DataFrame(chart_data)
        bar = alt.Chart(plot_df).mark_bar().encode(
            x=alt.X("觸發率(%)", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("項目", sort=None),
            color="分類"
        ).properties(height=450)
        st.altair_chart(bar, use_container_width=True)

        st.divider()
        st.subheader("💬 評審意見牆")
        for _, row in df_u.iterrows():
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:10px; border-left: 6px solid #4B0082;">
                <strong>委員：{row['Voter']}</strong> <br>
                {row['Advice']} <br>
                <small style='color:gray;'>時間：{row['Time']}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("目前尚無評審填報數據。")

# --- 5. 核心路由 (名稱校對版) ---
params = st.query_params
if params.get("m") == "vote" and params.get("t"):
    reviewer_page(params.get("t")) # 這裡原本寫錯了，現在修好了
else:
    admin_dashboard() # 這裡原本也寫錯了，現在修好了
