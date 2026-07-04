"""
注塑机台最优工艺卡分析系统 — 主页
"""
import streamlit as st

st.set_page_config(
    page_title="注塑机台最优工艺卡",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- 自动从缓存恢复 ----
if not st.session_state.get('data_loaded') and not st.session_state.get('_cache_checked'):
    from utils.data_loader import restore_from_cache, has_cache, get_cache_info
    st.session_state['_cache_checked'] = True
    if has_cache():
        restored = restore_from_cache()
        if restored:
            st.toast("✅ 已从本地缓存恢复上次加载的数据", icon="💾")

st.title("🏭 注塑机台最优工艺卡分析系统")

st.markdown("""
### 系统简介

本系统用于分析注塑机台的工艺参数与稼动率数据，自动找出 **OEE 持续稳定 ≥ 90%** 的时段，
并提取该时段内的工艺参数作为 **最优工艺卡** 推荐值。
""")

st.markdown("---")

# 数据状态
col_status, col_quick = st.columns([3, 2])

with col_status:
    st.subheader("📊 当前数据状态")
    if st.session_state.get('data_loaded', False):
        merged_df = st.session_state.get('merged_df')
        if merged_df is not None:
            from utils.data_loader import get_data_summary
            summary = get_data_summary(merged_df)

            st.success("✅ 数据已加载")

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("关联数据行数", f"{len(merged_df):,}")
            with m2:
                st.metric("可分析机台数", str(summary['num_machines']) if summary else "—")
            with m3:
                st.metric("数据日期范围", summary['date_range'] if summary else "—")
            with m4:
                cache_time = st.session_state.get('cache_time', '')
                if cache_time:
                    st.caption(f"💾 缓存时间: {cache_time}")
                st.caption(f"📄 {st.session_state.get('proc_file_name', '')}")
                st.caption(f"📄 {st.session_state.get('util_file_name', '')}")

            # 重置按钮
            col_reset1, col_reset2 = st.columns([1, 4])
            with col_reset1:
                if st.button("🗑️ 清除数据", type="secondary", help="清除所有已加载数据及本地缓存"):
                    from utils.data_loader import clear_cache
                    clear_cache()
                    st.rerun()
        else:
            st.warning("⚠️ 数据加载异常")
    else:
        st.info("📥 请先在左侧导航栏的 **数据导入** 页面加载报表数据")

        from utils.data_loader import has_cache, get_cache_info
        if has_cache():
            cache_info = get_cache_info()
            if cache_info:
                st.info(
                    f"💾 检测到本地缓存数据（{cache_info.get('cache_time', '未知时间')}），"
                    "已自动恢复。如需重新上传，请前往数据导入页面。"
                )

with col_quick:
    st.subheader("🚀 快速导航")
    if st.session_state.get('data_loaded', False):
        st.page_link("pages/2_📈_工艺趋势.py", label="📈 工艺参数趋势分析 →")
        st.page_link("pages/3_⏱️_稼动率分析.py", label="⏱️ 稼动率小时趋势分析 →")
        st.page_link("pages/4_🏆_最优工艺卡.py", label="🏆 生成最优工艺卡 →")
    else:
        st.page_link("pages/1_📥_数据导入.py", label="📥 先导入数据，开始使用 →")

st.markdown("---")

# ---- OEE 排名预览（数据已加载时） ----
if st.session_state.get('data_loaded', False):
    merged_df = st.session_state.get('merged_df')
    if merged_df is not None and not merged_df.empty:
        from utils.analysis import get_all_machines_oee_ranking
        from utils.viz import plot_oee_ranking_bars, get_plotly_config

        ranking_df = get_all_machines_oee_ranking(merged_df)
        if ranking_df is not None and not ranking_df.empty:
            col_rank, col_detail = st.columns([2, 1])

            with col_rank:
                st.subheader("🏅 机台 OEE 排名")
                rank_fig = plot_oee_ranking_bars(ranking_df)
                st.plotly_chart(rank_fig, use_container_width=True, config=get_plotly_config())

            with col_detail:
                st.subheader("📊 统计摘要")
                st.metric("平均 OEE", f"{ranking_df['平均OEE'].mean():.1%}")
                st.metric("最高 OEE", f"{ranking_df['平均OEE'].max():.1%}",
                          delta=f"机台 {ranking_df['机台号'].iloc[0]}")
                st.metric("最低 OEE", f"{ranking_df['平均OEE'].min():.1%}",
                          delta=f"机台 {ranking_df['机台号'].iloc[-1]}")
                st.metric("OEE ≥ 90% 机台数",
                          f"{int((ranking_df['平均OEE'] >= 0.9).sum())}/{len(ranking_df)}")

st.markdown("---")

st.subheader("📋 操作流程")
cols = st.columns(4)
steps = [
    ("📥", "数据导入", "上传工艺趋势报表与稼动率小时报表，\n系统自动清洗与关联两份数据"),
    ("📈", "工艺趋势", "按机台选择参数，查看工艺参数趋势，\n支持多机台对比与 OEE 相关性分析"),
    ("⏱️", "稼动率分析", "查看每小时稼动率热力图、\n不稼动时长归因与 OEE 损失分析"),
    ("🏆", "最优工艺卡", "设定筛选条件，系统自动扫描\n稳定生产时段，生成最优工艺参数推荐表"),
]
for i, (icon, title, desc) in enumerate(steps):
    with cols[i]:
        st.markdown(f"### {icon} {title}")
        st.caption(desc)

st.markdown("---")
st.caption("💡 提示：使用左侧边栏导航切换页面。数据首次加载后会自动缓存到本地，下次打开无需重新上传。")