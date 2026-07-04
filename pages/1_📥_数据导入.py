"""
数据导入页面：上传两个报表、预览数据、查看清洗与关联结果
"""
import streamlit as st
import pandas as pd

from utils.data_loader import (
    load_process_report, load_utilization_report,
    merge_reports, get_data_summary, store_data_in_session, is_data_loaded,
    save_cache_to_disk, has_cache, get_cache_info, clear_cache,
)
from utils.cleaner import flag_abnormal_oee, quality_report

st.set_page_config(page_title="数据导入", page_icon="📥", layout="wide")
st.title("📥 数据导入")

st.markdown("请依次上传两份报表，系统将自动完成日期标准化、数据清洗与两表关联。")

# ---- 缓存状态提示 ----
if has_cache() and not is_data_loaded():
    cache_info = get_cache_info()
    if cache_info:
        st.info(
            f"💾 检测到本地缓存数据（{cache_info.get('cache_time', '未知')}），"
            "已自动恢复。如需重新上传新文件，请直接上传即可覆盖。"
        )

# ---- 清除缓存按钮 ----
if is_data_loaded():
    col_title, col_clear = st.columns([5, 1])
    with col_clear:
        if st.button("🗑️ 清除数据", type="secondary",
                     help="清除所有已加载数据及本地缓存，重新开始"):
            clear_cache()
            st.rerun()

# ---- 文件上传 ----
col1, col2 = st.columns(2)

with col1:
    st.subheader("① 工艺趋势报表")
    proc_file = st.file_uploader(
        "选择工艺趋势报表文件 (.xlsx)",
        type=['xlsx'],
        key='proc_uploader',
        help="应包含：日期、机台号、时间段、各工艺参数（射胶/保压/温度/储料背压等）",
    )

with col2:
    st.subheader("② 稼动率小时报表")
    util_file = st.file_uploader(
        "选择稼动率小时报表文件 (.xlsx)",
        type=['xlsx'],
        key='util_uploader',
        help="应包含：日期、机台号、时间段、设备稼动率、有效/离线/待机/报警时长、开合模次数",
    )

st.markdown("---")

# ---- 加载与处理 ----
if proc_file and util_file:
    proc_bytes = proc_file.read()
    util_bytes = util_file.read()

    with st.spinner("正在读取并关联两份报表..."):
        proc_df, proc_err = load_process_report(proc_bytes, proc_file.name)
        util_df, util_err = load_utilization_report(util_bytes, util_file.name)

        if proc_err:
            st.error(f"工艺报表加载失败：{proc_err}")
            st.stop()
        if util_err:
            st.error(f"稼动率报表加载失败：{util_err}")
            st.stop()

        if proc_df is None or util_df is None:
            st.error("数据加载失败，请检查文件是否为有效的 Excel 格式")
            st.stop()

        merged_df, merge_err = merge_reports(proc_df, util_df)

        if merge_err:
            st.error(merge_err)
            with st.expander("🔍 调试信息：查看两表关键列数据"):
                st.write("**工艺报表 — 机台号前 5 个**:", proc_df['机台号'].unique()[:5])
                st.write("**工艺报表 — 日期前 5 个**:", proc_df['日期'].unique()[:5])
                st.write("**工艺报表 — 时间段前 5 个**:", proc_df['时间段'].unique()[:5])
                st.write("**稼动率报表 — 机台号前 5 个**:", util_df['机台号'].unique()[:5])
                st.write("**稼动率报表 — 日期前 5 个**:", util_df['日期'].unique()[:5])
                st.write("**稼动率报表 — 时间段前 5 个**:", util_df['时间段'].unique()[:5])
            st.stop()

        # 标记异常 OEE
        merged_df = flag_abnormal_oee(merged_df)

        # 存入 session state
        store_data_in_session(proc_df, util_df, merged_df, proc_file.name, util_file.name)

        # 保存到本地磁盘缓存
        save_cache_to_disk()

        st.success(f"✅ 数据加载完成！两份报表关联成功，共 **{len(merged_df):,}** 条记录")

    # ---- 数据预览 ----
    st.markdown("---")
    st.subheader("📋 数据预览")

    tab1, tab2, tab3 = st.tabs(["工艺报表原始数据", "稼动率报表原始数据", "关联后合并数据"])

    with tab1:
        st.caption(f"共 {len(proc_df):,} 行 × {len(proc_df.columns)} 列")
        st.dataframe(proc_df.head(100), use_container_width=True, hide_index=True)

    with tab2:
        st.caption(f"共 {len(util_df):,} 行 × {len(util_df.columns)} 列")
        st.dataframe(util_df.head(100), use_container_width=True, hide_index=True)

    with tab3:
        st.caption(f"关联后共 {len(merged_df):,} 行 × {len(merged_df.columns)} 列  "
                   f"|  可分析机台: {merged_df['机台号'].nunique()} 台")
        st.dataframe(merged_df.head(100), use_container_width=True, hide_index=True)

    # ---- 数据质量报告 ----
    st.markdown("---")
    st.subheader("🔍 数据质量报告")

    summary = get_data_summary(merged_df)
    qr = quality_report(merged_df)

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.metric("关联后数据行数", f"{summary['total_rows']:,}")
    with mc2:
        st.metric("可分析机台数", str(summary['num_machines']))
    with mc3:
        st.metric("覆盖天数", f"{len(summary['dates'])} 天")
    with mc4:
        oee_ab = qr.get('_summary', {}).get('oee_abnormal_count', 0)
        st.metric("OEE 异常记录数", oee_ab,
                  delta=f"{oee_ab} 条需关注" if oee_ab > 0 else "无异常")

    if oee_ab > 0 and 'oee_abnormal' in merged_df.columns:
        with st.expander("⚠️ 稼动率异常值详情（将参与分析但已被标记）"):
            abnormal_df = merged_df[merged_df['oee_abnormal']]
            st.write(f"共 **{len(abnormal_df)}** 条异常记录（负数或 >150% 的值）：")
            st.dataframe(
                abnormal_df[['机台号', '日期', '时间段', '设备稼动率', 'oee_abnormal_type']].head(20),
                use_container_width=True, hide_index=True
            )

    with st.expander("📊 完整机台列表"):
        machines = summary['machines']
        st.write(f"共 **{len(machines)}** 台机台在两份报表中均有数据：")
        cols_per_row = 10
        rows = [machines[i:i+cols_per_row] for i in range(0, len(machines), cols_per_row)]
        for row in rows:
            st.text("  ".join(f"{m:6s}" for m in row))

elif proc_file or util_file:
    st.info("请同时上传两份报表文件以完成关联分析。")

else:
    st.info("👆 请在上方分别上传工艺趋势报表和稼动率小时报表（均为 Excel 格式）")

    with st.expander("📄 报表格式说明"):
        st.markdown("""
        **工艺趋势报表** 应包含以下列：
        - 日期、车间、产线、固资编码、机型、机台号、时间段、最后数采时间
        - 射胶参数（压力 / 速度 / 位置 × 5段）
        - 保压参数（压力 / 速度 / 时间 × 3段）
        - 温度参数（一段值 ~ 六段值）
        - 储料背压（bar）、射退位置（mm）、射退压力（bar）、射退速度（%）
        - 储料时间（sec）、射胶终点、成型周期（s）

        **稼动率小时报表** 应包含以下列：
        - 日期、车间、产线、固资编码、机型、机台号
        - 设备稼动率、时间段
        - 有效生产时长(min)、离线时长(min)、待机时长(min)、报警时长(min)、开机时长(min)
        - 开合模次数
        """)

    st.markdown("---")
    st.info("💡 也可以直接使用项目目录中的示例报表文件进行测试：\n"
            "  · `工艺趋势报表.260325142723.xlsx`\n"
            "  · `注塑机稼动率小时报表报表.260325142609.xlsx`")