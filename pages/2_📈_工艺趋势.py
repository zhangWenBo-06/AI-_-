"""
工艺趋势分析页面：查看各工艺参数的时间序列趋势、多机台对比、参数-OEE 相关性
"""
import streamlit as st
import pandas as pd

from utils.data_loader import is_data_loaded, get_data_summary
from utils.cleaner import get_param_groups, get_all_params, DEFAULT_OEE_THRESHOLD
from utils.viz import (
    plot_param_trend, plot_param_box,
    plot_multi_machine_trend, plot_correlation_bars,
    get_plotly_config,
)
from utils.analysis import compute_machine_stats, compute_param_oee_correlation

st.set_page_config(page_title="工艺趋势分析", page_icon="📈", layout="wide")
st.title("📈 工艺参数趋势分析")

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
param_groups = get_param_groups()

# ---- 分析模式选择 ----
st.markdown("### ⚙️ 分析设置")

mode = st.radio(
    "选择分析模式",
    ["📈 单机台趋势分析", "🔄 多机台对比", "🔗 参数-OEE 相关性"],
    horizontal=True,
    help="单机台：查看一台机器的参数趋势；多机台：对比多台机器的同一参数；相关性：分析哪些参数与 OEE 关系最大",
)

st.markdown("---")

# ==================== 模式 1：单机台趋势 ====================
if mode == "📈 单机台趋势分析":
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        machines = summary['machines']
        selected_machine = st.selectbox(
            "选择机台",
            machines,
            index=0 if machines else None,
            help="选择要分析的注塑机台号",
        )

    with col2:
        st.caption("选择要查看的参数类别（可多选）")
        group_cols = st.columns(4)
        selected_groups = {}
        for i, (group_name, params) in enumerate(param_groups.items()):
            with group_cols[i]:
                selected_groups[group_name] = st.checkbox(
                    group_name,
                    value=(group_name == '射胶参数'),
                    help=f"包含 {len(params)} 个参数",
                )

    with col3:
        dates = summary['dates']
        if len(dates) >= 2:
            date_range = st.select_slider(
                "日期范围",
                options=dates,
                value=(dates[0], dates[-1]),
            )
        else:
            date_range = (dates[0], dates[0]) if len(dates) == 1 else None
            st.caption(f"数据日期: {dates[0] if len(dates) == 1 else '无'}")

    all_selected_params = []
    for group_name, checked in selected_groups.items():
        if checked:
            all_selected_params.extend(param_groups[group_name])

    if not all_selected_params:
        st.warning("请至少选择一个参数类别")
        st.stop()

    # 趋势图
    st.subheader(f"📈 机台 {selected_machine} 工艺参数趋势")
    fig = plot_param_trend(merged_df, selected_machine, all_selected_params, date_range)
    st.plotly_chart(fig, use_container_width=True, config=get_plotly_config())

    # 箱线图 + 统计
    st.markdown("---")
    st.subheader("📊 参数分布分析")

    plot_col, info_col = st.columns([3, 1])

    with plot_col:
        box_fig = plot_param_box(merged_df, selected_machine, all_selected_params)
        st.plotly_chart(box_fig, use_container_width=True, config=get_plotly_config())

    with info_col:
        stats = compute_machine_stats(merged_df, selected_machine)
        if stats:
            st.markdown("**机台统计**")
            st.metric("总数据时数", stats['total_hours'])
            if 'avg_oee' in stats:
                st.metric("平均稼动率", f"{stats['avg_oee']:.1%}")
            if 'hours_above_90' in stats:
                st.metric("OEE ≥ 90% 时数", f"{stats['hours_above_90']}/{stats['total_hours']}")
            if 'abnormal_count' in stats:
                st.metric("OEE 异常值数", stats['abnormal_count'],
                          delta="需关注" if stats['abnormal_count'] > 0 else "无异常")

        st.markdown("**数据覆盖日期**")
        for d in stats.get('dates', []):
            st.caption(f"· {d}")

    # 参数数值摘要表
    st.markdown("---")
    st.subheader("📋 参数数值摘要")

    machine_df = merged_df[merged_df['机台号'] == selected_machine].copy()
    valid_params = [p for p in all_selected_params if p in machine_df.columns]

    if valid_params:
        stats_data = []
        for param in valid_params:
            values = machine_df[param].dropna()
            if len(values) == 0:
                continue
            stats_data.append({
                '参数名': param,
                '平均值': round(values.mean(), 2),
                '中位数': round(values.median(), 2),
                '标准差': round(values.std(), 2),
                '最小值': round(values.min(), 2),
                '最大值': round(values.max(), 2),
                '样本数': len(values),
            })

        if stats_data:
            stats_df = pd.DataFrame(stats_data)
            st.dataframe(stats_df, use_container_width=True, hide_index=True)

            csv = stats_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label=f"📥 导出 {selected_machine} 参数统计 CSV",
                data=csv,
                file_name=f'工艺参数统计_{selected_machine}.csv',
                mime='text/csv',
            )

# ==================== 模式 2：多机台对比 ====================
elif mode == "🔄 多机台对比":
    col_a, col_b = st.columns([1, 3])

    with col_a:
        machines = summary['machines']
        compare_machines = st.multiselect(
            "选择对比机台（建议 2 ~ 4 台）",
            machines,
            default=machines[:3] if len(machines) >= 3 else machines,
            max_selections=6,
            help="选择多台机台，对比同一工艺参数的趋势",
        )

        # 参数选择
        all_params = get_all_params()
        compare_param = st.selectbox(
            "选择对比参数",
            all_params,
            index=0,
            help="选择要对比的工艺参数",
        )

        dates = summary['dates']
        if len(dates) >= 2:
            date_range = st.select_slider(
                "日期范围",
                options=dates,
                value=(dates[0], dates[-1]),
            )
        else:
            date_range = None

    with col_b:
        if compare_machines:
            st.subheader(f"🔄 多机台对比 — {compare_param}")
            fig = plot_multi_machine_trend(
                merged_df, compare_machines, compare_param, date_range
            )
            st.plotly_chart(fig, use_container_width=True, config=get_plotly_config())

            # 对比统计表
            st.markdown("---")
            st.subheader("📊 对比统计")

            compare_data = []
            for machine in compare_machines:
                mdf = merged_df[merged_df['机台号'] == machine]
                if compare_param not in mdf.columns:
                    continue
                values = mdf[compare_param].dropna()
                oee = mdf['设备稼动率'].clip(0, 1)
                compare_data.append({
                    '机台号': machine,
                    f'{compare_param} 平均值': round(values.mean(), 2),
                    f'{compare_param} 中位数': round(values.median(), 2),
                    f'{compare_param} 标准差': round(values.std(), 2),
                    '平均 OEE': f"{oee.mean():.1%}",
                    '样本数': len(values),
                })

            if compare_data:
                st.dataframe(pd.DataFrame(compare_data), use_container_width=True, hide_index=True)
        else:
            st.info("请选择至少 2 台机台进行对比")

# ==================== 模式 3：参数-OEE 相关性 ====================
elif mode == "🔗 参数-OEE 相关性":
    col_a, col_b = st.columns([1, 3])

    with col_a:
        machines = summary['machines']
        selected_machine = st.selectbox(
            "选择机台",
            machines,
            index=0 if machines else None,
            help="分析该机台的工艺参数与 OEE 的相关性",
        )

        top_n = st.slider(
            "显示前 N 个参数",
            min_value=10,
            max_value=36,
            value=20,
            step=2,
            help="显示相关系数绝对值最大的前 N 个参数",
        )

    with col_b:
        if selected_machine:
            corr_df = compute_param_oee_correlation(merged_df, selected_machine)

            if corr_df is not None and not corr_df.empty:
                st.subheader(f"🔗 机台 {selected_machine} — 参数与 OEE 相关性")
                corr_fig = plot_correlation_bars(corr_df, top_n=top_n)
                st.plotly_chart(corr_fig, use_container_width=True, config=get_plotly_config())

                # 说明
                st.caption(
                    "正相关（绿色）：参数值越大，OEE 越高；"
                    "负相关（红色）：参数值越大，OEE 越低。"
                    "| 相关系数绝对值越接近 1，关系越强。"
                )

                st.markdown("---")
                st.subheader("📋 完整相关性数据")

                st.dataframe(
                    corr_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        '工艺参数': st.column_config.TextColumn('工艺参数'),
                        '相关系数': st.column_config.NumberColumn('Pearson 相关系数', format='+.4f'),
                        '绝对值': st.column_config.NumberColumn('|r|', format='.4f'),
                        '相关性方向': st.column_config.TextColumn('方向'),
                        '有效样本数': st.column_config.NumberColumn('样本数', format='%d'),
                    },
                )

                csv_corr = corr_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label=f"📥 下载 {selected_machine} 相关性分析 CSV",
                    data=csv_corr,
                    file_name=f'参数相关性_{selected_machine}.csv',
                    mime='text/csv',
                )
            else:
                st.warning("该机台数据不足以计算相关性（需要至少 5 个有效数据点）")
        else:
            st.info("请选择一台机台")