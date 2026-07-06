"""
稼动率分析页面：每小时稼动率趋势、热力图、损失归因
"""
import streamlit as st
import pandas as pd

from utils.data_loader import is_data_loaded, get_data_summary
from utils.cleaner import DEFAULT_OEE_THRESHOLD
from utils.viz import (
    plot_oee_heatmap, plot_oee_hourly_bars,
    plot_loss_pie, plot_cycle_scatter,
    get_plotly_config,
)
from utils.analysis import compute_machine_stats

st.set_page_config(page_title="稼动率分析", page_icon="⏱️", layout="wide")
st.title("⏱️ 稼动率小时趋势分析")

# ---- 检查数据状态 ----
if not is_data_loaded():
    st.info("📥 请先在左侧导航栏的 **数据导入** 页面加载数据")
    st.page_link("pages/1_📥_数据导入.py", label="→ 前往数据导入")
    st.stop()

merged_df = st.session_state.get('merged_df')
if merged_df is None or merged_df.empty:
    st.error("数据为空，请返回数据导入页面重新上传")
    st.stop()

summary = get_data_summary(merged_df)

# ---- 控制面板 ----
col1, col2 = st.columns([1, 3])

with col1:
    machines = summary['machines']
    selected_machine = st.selectbox(
        "选择机台",
        machines,
        index=0 if machines else None,
        help="选择要分析的注塑机台号",
    )

    stats = compute_machine_stats(merged_df, selected_machine)

    if stats:
        st.metric("总数据时数", stats['total_hours'])
        if 'avg_oee' in stats:
            st.metric("平均稼动率", f"{stats['avg_oee']:.1%}")
        if 'hours_above_90' in stats:
            st.metric("OEE ≥ 90% 时数", f"{stats['hours_above_90']}/{stats['total_hours']}")

# ---- 图表区域 ----
st.markdown("---")

# 上图：热力图 + 饼图
left_col, right_col = st.columns(2)

with left_col:
    st.markdown("#### 🔥 稼动率热力图")
    heatmap_fig = plot_oee_heatmap(merged_df, selected_machine)
    st.plotly_chart(heatmap_fig, use_container_width=True, config=get_plotly_config())

with right_col:
    st.markdown("#### 🥧 不稼动时长归因")
    pie_fig = plot_loss_pie(merged_df, selected_machine)
    st.plotly_chart(pie_fig, use_container_width=True, config=get_plotly_config())

# 下图：柱状图 + 散点图
st.markdown("---")
left_col2, right_col2 = st.columns(2)

with left_col2:
    st.markdown("#### 📊 按天每小时稼动率对比")
    bar_fig = plot_oee_hourly_bars(merged_df, selected_machine)
    st.plotly_chart(bar_fig, use_container_width=True, config=get_plotly_config())

with right_col2:
    st.markdown("#### 🔵 开合模次数 vs 稼动率")
    scatter_fig = plot_cycle_scatter(merged_df, selected_machine)
    st.plotly_chart(scatter_fig, use_container_width=True, config=get_plotly_config())

# ---- 稼动率数据明细表 ----
st.markdown("---")
st.subheader("📋 稼动率数据明细")

machine_df = merged_df[merged_df['机台号'] == selected_machine].copy()

if not machine_df.empty:
    display_cols = ['日期', '时间段', '设备稼动率', '有效生产时长(min)',
                    '离线时长(min)', '待机时长(min)', '报警时长(min)',
                    '开机时长(min)', '开合模次数']

    available_cols = [c for c in display_cols if c in machine_df.columns]
    if 'oee_abnormal_type' in machine_df.columns:
        available_cols.append('oee_abnormal_type')

    machine_df = machine_df.sort_values('_timestamp')

    # 用 pandas Styler 高亮异常行
    def highlight_abnormal_rows(df_display):
        """高亮 OEE 异常的整行"""
        if 'oee_abnormal_type' not in df_display.columns:
            return pd.DataFrame('', index=df_display.index, columns=df_display.columns)
        styles = pd.DataFrame('', index=df_display.index, columns=df_display.columns)
        abnormal_mask = df_display['oee_abnormal_type'] != '正常'
        styles.loc[abnormal_mask, :] = 'background-color: #fff3cd'
        return styles

    styled_df = machine_df[available_cols].style.apply(highlight_abnormal_rows, axis=None)

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=400,
    )