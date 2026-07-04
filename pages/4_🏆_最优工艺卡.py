"""
最优工艺卡页面：自动筛选最优时段 → 提取工艺参数 → 导出
"""
import streamlit as st
import pandas as pd
from io import BytesIO

from utils.data_loader import is_data_loaded, get_data_summary
from utils.analysis import find_all_machines_optimal
from utils.cleaner import get_param_groups

st.set_page_config(page_title="最优工艺卡", page_icon="🏆", layout="wide")
st.title("🏆 最优工艺卡生成")

# ---- 初始化 session state ----
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'analysis_params' not in st.session_state:
    st.session_state.analysis_params = {}

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

# ---- 筛选条件 ----
st.markdown("### ⚙️ 设置筛选条件")

control_col1, control_col2, control_col3, control_col4 = st.columns([1, 1, 1, 1])

with control_col1:
    min_hours = st.slider(
        "最少连续生产时数",
        min_value=4,
        max_value=48,
        value=12,
        step=2,
        help="OEE 必须连续达标的最少小时数，默认为 12 小时",
    )

with control_col2:
    oee_threshold = st.slider(
        "OEE 阈值",
        min_value=0.80,
        max_value=1.0,
        value=0.90,
        step=0.01,
        format="%.2f",
        help="稼动率必须 ≥ 此阈值才视为达标，默认 0.90（即 90%）",
    )

with control_col3:
    all_machines = sorted(summary['machines'])
    select_all = st.checkbox("全选机台", value=True)
    if select_all:
        selected_machines = all_machines
    else:
        selected_machines = st.multiselect(
            "手动选择机台",
            all_machines,
            default=all_machines[:5] if len(all_machines) > 5 else all_machines,
        )

with control_col4:
    st.markdown("<br>", unsafe_allow_html=True)
    analyze_btn = st.button("🔍 开始分析", type="primary", use_container_width=True)

# ---- 分析逻辑（仅触发计算，结果存入 session_state） ----
if analyze_btn:
    if not selected_machines:
        st.warning("请至少选择一台机台")
        st.stop()

    with st.spinner(f"正在分析 {len(selected_machines)} 台机台的最优时段..."):
        result = find_all_machines_optimal(
            merged_df,
            min_hours=min_hours,
            oee_threshold=oee_threshold,
            selected_machines=selected_machines,
        )

    if result is None:
        st.error("分析失败，数据异常")
        st.session_state.analysis_result = None
        st.stop()

    # 保存到 session_state，在 rerun 后仍然可用
    st.session_state.analysis_result = result
    st.session_state.analysis_params = {
        'min_hours': min_hours,
        'oee_threshold': oee_threshold,
        'selected_machines': selected_machines,
    }

# ========== 从 session_state 展示结果（不依赖 analyze_btn 的值） ==========
if st.session_state.analysis_result is not None:
    result = st.session_state.analysis_result
    params = st.session_state.analysis_params

    # ---- 结果展示 ----
    st.markdown("---")
    st.subheader("📊 分析结果汇总")

    summary_df = result.get('summary_df', pd.DataFrame())
    no_result = result.get('no_result_machines', [])
    selected_machines = params.get('selected_machines', [])
    min_hours = params.get('min_hours', 12)
    oee_threshold = params.get('oee_threshold', 0.9)

    card_cols = st.columns(5)
    with card_cols[0]:
        st.metric("分析机台数", len(selected_machines))
    with card_cols[1]:
        st.metric("找到最优窗口", len(result['optimal_params']))
    with card_cols[2]:
        st.metric("无达标窗口", len(no_result))
    with card_cols[3]:
        st.metric("OEE 阈值", f"≥ {oee_threshold:.0%}")
    with card_cols[4]:
        st.metric("最少连续", f"{min_hours} 小时")

    if len(no_result) == len(selected_machines):
        st.warning(
            f"⚠️ **所有选中的 {len(selected_machines)} 台机台都没有找到符合条件的时段。**\n\n"
            "可能原因：\n"
            f"- OEE 阈值过高（当前为 {oee_threshold:.0%}），可尝试降低到 80%\n"
            f"- 最少连续时数太大（当前为 {min_hours} 小时），可尝试降低到 6 ~ 8 小时\n"
            "- 数据中确实缺乏长时间稳定生产时段"
        )
        st.stop()

    if no_result and len(no_result) <= 20:
        st.warning(f"⚠️ 以下 **{len(no_result)}** 台机台未找到达标窗口: "
                   + "、".join(no_result[:20])
                   + ("..." if len(no_result) > 20 else ""))
    elif no_result:
        st.warning(f"⚠️ **{len(no_result)}** 台机台未找到达标窗口")

    # ---- 最优时段摘要 ----
    st.markdown("---")
    st.subheader("📋 最优时段摘要")

    if not summary_df.empty:
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                '机台号': st.column_config.TextColumn('机台号', width='small'),
                '开始时间': st.column_config.DatetimeColumn('开始时间', format='MM/DD HH:mm'),
                '结束时间': st.column_config.DatetimeColumn('结束时间', format='MM/DD HH:mm'),
                '持续小时': st.column_config.NumberColumn('持续时长(小时)', format='%d'),
                '平均稼动率': st.column_config.ProgressColumn('平均 OEE', format='%.1%', min_value=0, max_value=1),
                '最低稼动率': st.column_config.NumberColumn('最低 OEE', format='%.1%'),
                '异常值数': st.column_config.NumberColumn('异常值数', format='%d'),
            },
        )

        csv_summary = summary_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下载最优时段摘要 CSV",
            data=csv_summary,
            file_name=f'最优时段摘要_{min_hours}h_{int(oee_threshold*100)}pct.csv',
            mime='text/csv',
        )

    # ---- 最优工艺卡（每台机台） ----
    st.markdown("---")
    st.subheader("🏆 最优工艺卡详情")

    optimal_params = result.get('optimal_params', {})
    machine_list = list(optimal_params.keys())

    if machine_list:
        selected_machine = st.selectbox(
            "选择机台查看最优工艺卡",
            machine_list,
            format_func=lambda m: f"🟢 机台 {m} — 持续 {optimal_params[m]['window']['duration_hours']}h — 平均 OEE {optimal_params[m]['window']['avg_oee']:.1%}",
            help="选择一台机台查看其最优工艺参数详情",
        )

        if selected_machine:
            params_info = optimal_params[selected_machine]
            params_df = params_info['params_df']
            window = params_info['window']

            info_cols = st.columns(4)
            with info_cols[0]:
                st.metric("开始时间", str(window['start_time'])[:16])
            with info_cols[1]:
                st.metric("结束时间", str(window['end_time'])[:16])
            with info_cols[2]:
                st.metric("持续时长", f"{window['duration_hours']} 小时")
            with info_cols[3]:
                st.metric("平均稼动率", f"{window['avg_oee']:.1%}")

            if window['num_abnormal'] > 0:
                st.caption(f"⚠️ 该窗口内包含 {window['num_abnormal']} 条数采异常记录，已参与分析但标记异常")

            if params_df is not None and not params_df.empty:
                param_groups = get_param_groups()

                for group_name, group_params in param_groups.items():
                    group_df = params_df[params_df['工艺参数'].isin(group_params)]
                    if group_df.empty:
                        continue

                    st.markdown(f"**{group_name}**")
                    st.dataframe(
                        group_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            '工艺参数': st.column_config.TextColumn('参数名', width='medium'),
                            '推荐值': st.column_config.NumberColumn('推荐值 ⭐', format='%.2f'),
                            '下限(Q25)': st.column_config.NumberColumn('建议下限', format='%.2f'),
                            '上限(Q75)': st.column_config.NumberColumn('建议上限', format='%.2f'),
                            '平均值': st.column_config.NumberColumn('窗口均值', format='%.2f'),
                            '标准差': st.column_config.NumberColumn('标准差', format='%.2f'),
                        },
                    )

            # 单机台下载
            csv_single = params_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label=f"📥 下载 {selected_machine} 最优工艺卡 CSV",
                data=csv_single,
                file_name=f'最优工艺卡_{selected_machine}.csv',
                mime='text/csv',
            )
    else:
        st.info("没有找到符合条件的机台")

    # ---- 全部机台导出 ----
    # st.markdown("---")
    # st.subheader("📥 导出最优工艺卡")

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for machine in sorted(optimal_params.keys()):
            params_info = optimal_params[machine]
            df = params_info['params_df']

            if df is not None and not df.empty:
                sheet_name = f"{machine}"[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        if not summary_df.empty:
            summary_df.to_excel(writer, sheet_name='最优时段摘要', index=False)

    output.seek(0)

    # st.download_button(
    #     label=f"📥 下载全部最优工艺卡 Excel（{len(optimal_params)} 台机台）",
    #     data=output,
    #     file_name=f'最优工艺卡_{min_hours}h_{int(oee_threshold*100)}pct.xlsx',
    #     mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    #     type="primary",
    # )

    # st.caption(
    #     "Excel 文件中每个机台一个 Sheet，每行一个工艺参数，"
    #     "包含推荐值（中位数）、建议下限（Q25）、建议上限（Q75）及统计量。"
    # )

else:
    # ---- 无分析结果时的说明 ----
    st.markdown("---")
    st.info("👆 设置好筛选条件后，点击 **开始分析** 按钮")

    st.markdown("### 📖 分析逻辑说明")
    st.markdown("""
    1. **滑动窗口扫描**：对每台机台，按时间顺序逐小时扫描稼动率数据
    2. **OEE 达标判断**：每小时稼动率 ≥ 设定阈值（默认 90%）视为达标
    3. **连续性筛选**：找到所有连续达标 ≥ 设定时数（默认 12 小时）的窗口
    4. **最优窗口选取**：优先选择连续时长最长的窗口；相同时选择平均 OEE 最高的
    5. **工艺参数提取**：取最优窗口内所有工艺参数的 **中位数** 作为推荐值，
       **Q25 ~ Q75** 作为建议范围
    """)

    st.markdown("### 📊 当前数据概况")
    preview_cols = st.columns(4)
    with preview_cols[0]:
        st.metric("可分析机台数", len(summary.get('machines', [])))
    with preview_cols[1]:
        st.metric("数据总行数", summary.get('total_rows', 0))
    with preview_cols[2]:
        st.metric("数据天数", len(summary.get('dates', [])))
    with preview_cols[3]:
        st.metric("数据日期范围", summary.get('date_range', '无'))