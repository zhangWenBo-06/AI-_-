"""
核心分析模块：滑动窗口查找最优时段、工艺参数统计、相关性分析
"""
import hashlib
import pandas as pd
import streamlit as st
from utils.cleaner import get_param_groups, get_all_params, DEFAULT_OEE_THRESHOLD


def find_optimal_windows(merged_df, machine, min_hours=12, oee_threshold=DEFAULT_OEE_THRESHOLD):
    """
    对指定机台，用滑动窗口查找 OEE >= 阈值且连续 >= min_hours 的时段。
    通过 _timestamp 差值检测数据缺口：连续两行时间差 > 1.5 小时视为断点。
    """
    df = merged_df[merged_df['机台号'] == machine].copy()
    if df.empty:
        return []

    df = df.sort_values('_timestamp').reset_index(drop=True)

    if '设备稼动率' not in df.columns:
        return []

    df['_oee_clipped'] = df['设备稼动率'].clip(0, 1)
    df['_qualified'] = df['_oee_clipped'] >= oee_threshold

    windows = []
    i = 0
    n = len(df)

    while i < n:
        if df.loc[i, '_qualified']:
            j = i
            while j < n and df.loc[j, '_qualified']:
                # 检测时间缺口：连续两行时间差 > 1.5 小时即断点
                if j > i:
                    time_gap = (df.loc[j, '_timestamp'] - df.loc[j - 1, '_timestamp']).total_seconds() / 3600
                    if time_gap > 1.5:
                        break
                j += 1

            consecutive_hours = j - i
            if consecutive_hours >= min_hours:
                window_df = df.iloc[i:j]
                num_abnormal = window_df['oee_abnormal'].sum() if 'oee_abnormal' in window_df.columns else 0

                windows.append({
                    'machine': machine,
                    'start_time': window_df['_timestamp'].iloc[0],
                    'end_time': window_df['_timestamp'].iloc[-1],
                    'duration_hours': consecutive_hours,
                    'avg_oee': round(window_df['_oee_clipped'].mean(), 4),
                    'min_oee': round(window_df['_oee_clipped'].min(), 4),
                    'max_oee': round(window_df['_oee_clipped'].max(), 4),
                    'num_abnormal': num_abnormal,
                    'start_date': window_df['日期'].iloc[0],
                    'end_date': window_df['日期'].iloc[-1],
                    'start_slot': window_df['时间段'].iloc[0],
                    'end_slot': window_df['时间段'].iloc[-1],
                })

            i = j
        else:
            i += 1

    windows.sort(key=lambda w: (w['duration_hours'], w['avg_oee']), reverse=True)
    return windows


def compute_optimal_params(merged_df, machine, window):
    """对最优窗口内的工艺参数计算统计值"""
    df = merged_df[merged_df['机台号'] == machine].copy()
    mask = (df['_timestamp'] >= window['start_time']) & (df['_timestamp'] <= window['end_time'])
    window_df = df[mask]

    if window_df.empty:
        return None

    all_params = get_all_params()

    valid_params = [p for p in all_params if p in window_df.columns]
    if not valid_params:
        return None

    results = []
    for param in valid_params:
        values = window_df[param].dropna()
        if len(values) == 0:
            continue

        results.append({
            '工艺参数': param,
            '推荐值': round(values.median(), 2),
            '下限(Q25)': round(values.quantile(0.25), 2),
            '上限(Q75)': round(values.quantile(0.75), 2),
            '平均值': round(values.mean(), 2),
            '标准差': round(values.std(), 2) if len(values) > 1 else 0,
            '最小值': round(values.min(), 2),
            '最大值': round(values.max(), 2),
            '有效样本数': len(values),
        })

    result_df = pd.DataFrame(results)
    param_order = {p: i for i, p in enumerate(all_params)}
    result_df['_sort'] = result_df['工艺参数'].map(lambda x: param_order.get(x, 999))
    result_df = result_df.sort_values('_sort').drop(columns=['_sort']).reset_index(drop=True)

    return result_df


def find_all_machines_optimal(merged_df, min_hours=12, oee_threshold=DEFAULT_OEE_THRESHOLD,
                               selected_machines=None):
    """
    对所有（或选定的）机台查找最优窗口和工艺参数。
    缓存 key 包含数据摘要，重新上传数据后缓存自动失效。
    """
    if merged_df is None or merged_df.empty:
        return None

    machines = selected_machines if selected_machines else sorted(merged_df['机台号'].unique())

    # 缓存键：包含数据摘要（行数+机台数），数据变更时自动失效
    data_fingerprint = hashlib.md5(
        f"{len(merged_df)}_{merged_df['机台号'].nunique()}_{merged_df['_timestamp'].max()}".encode()
    ).hexdigest()[:8]
    cache_key = f"analysis_{min_hours}_{oee_threshold}_{'_'.join(sorted(machines))}_{data_fingerprint}"
    if 'analysis_cache' not in st.session_state:
        st.session_state['analysis_cache'] = {}

    if cache_key in st.session_state['analysis_cache']:
        return st.session_state['analysis_cache'][cache_key]

    all_windows = {}
    optimal_params = {}
    no_result_machines = []

    progress = st.progress(0, text="正在分析机台...")
    total = len(machines)

    for idx, machine in enumerate(machines):
        progress.progress((idx + 1) / total, text=f"正在分析机台 {machine} ({idx+1}/{total})...")
        windows = find_optimal_windows(merged_df, machine, min_hours, oee_threshold)

        if windows:
            all_windows[machine] = windows
            best_window = windows[0]
            params_df = compute_optimal_params(merged_df, machine, best_window)
            optimal_params[machine] = {
                'params_df': params_df,
                'window': best_window,
            }
        else:
            no_result_machines.append(machine)

    progress.empty()

    summary_rows = []
    for machine, params_info in optimal_params.items():
        w = params_info['window']
        summary_rows.append({
            '机台号': machine,
            '开始时间': w['start_time'],
            '结束时间': w['end_time'],
            '持续小时': w['duration_hours'],
            '平均稼动率': w['avg_oee'],
            '最低稼动率': w['min_oee'],
            '异常值数': w['num_abnormal'],
        })

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(['持续小时', '平均稼动率'], ascending=[False, False])

    result = {
        'all_windows': all_windows,
        'optimal_params': optimal_params,
        'summary_df': summary_df,
        'no_result_machines': no_result_machines,
    }

    st.session_state['analysis_cache'][cache_key] = result
    return result


def compute_machine_stats(merged_df, machine):
    """计算单台机器的基础统计"""
    df = merged_df[merged_df['机台号'] == machine].copy()
    if df.empty:
        return None

    stats = {
        'machine': machine,
        'total_hours': len(df),
        'dates': sorted(df['日期'].unique()),
        'num_dates': len(df['日期'].unique()),
    }

    if '设备稼动率' in df.columns:
        oee = df['设备稼动率'].clip(0, 1)
        stats['avg_oee'] = round(oee.mean(), 4)
        stats['median_oee'] = round(oee.median(), 4)
        stats['hours_above_90'] = int((oee >= DEFAULT_OEE_THRESHOLD).sum())

        if 'oee_abnormal' in df.columns:
            stats['abnormal_count'] = int(df['oee_abnormal'].sum())

    return stats


# ==================== 参数-OEE 相关性分析 ====================

def compute_param_oee_correlation(merged_df, machine):
    """
    计算指定机台的所有工艺参数与 OEE 的 Pearson 相关系数
    返回按相关系数绝对值降序排列的 DataFrame
    """
    df = merged_df[merged_df['机台号'] == machine].copy()
    if df.empty:
        return None

    # 裁剪 OEE
    oee = df['设备稼动率'].clip(0, 1)

    # 获取所有工艺参数列
    all_params = get_all_params()

    valid_params = [p for p in all_params if p in df.columns]
    if not valid_params:
        return None

    correlations = []
    for param in valid_params:
        values = df[param].dropna()
        if len(values) < 5:
            continue

        # 对齐 OEE 和参数值（dropna 后索引可能不一致）
        common_idx = oee.index.intersection(df[param].dropna().index)
        if len(common_idx) < 5:
            continue

        corr = oee.loc[common_idx].corr(df.loc[common_idx, param])
        if pd.notna(corr):
            correlations.append({
                '工艺参数': param,
                '相关系数': round(corr, 4),
                '绝对值': round(abs(corr), 4),
                '相关性方向': '正相关' if corr > 0 else '负相关',
                '有效样本数': len(common_idx),
            })

    if not correlations:
        return None

    corr_df = pd.DataFrame(correlations)
    corr_df = corr_df.sort_values('绝对值', ascending=False).reset_index(drop=True)
    return corr_df


def get_all_machines_oee_ranking(merged_df):
    """获取所有机台的平均 OEE 排名"""
    if merged_df is None or merged_df.empty:
        return None

    ranking = []
    for machine in sorted(merged_df['机台号'].unique()):
        mdf = merged_df[merged_df['机台号'] == machine]
        oee = mdf['设备稼动率'].clip(0, 1)
        ranking.append({
            '机台号': machine,
            '平均OEE': round(oee.mean(), 4),
            'OEE中位数': round(oee.median(), 4),
            '≥90%时数': int((oee >= DEFAULT_OEE_THRESHOLD).sum()),
            '总时数': len(oee),
            '≥90%占比': round((oee >= DEFAULT_OEE_THRESHOLD).sum() / len(oee) * 100, 1),
        })

    ranking_df = pd.DataFrame(ranking)
    ranking_df = ranking_df.sort_values('平均OEE', ascending=False).reset_index(drop=True)
    return ranking_df