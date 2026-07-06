"""
数据加载模块：读取 Excel、标准化日期、关联两表、缓存管理、本地持久化
"""
import pandas as pd
import streamlit as st
import os
from datetime import datetime
from io import BytesIO

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.cache')
CACHE_FILE = os.path.join(CACHE_DIR, 'merged_data.pkl')
META_FILE = os.path.join(CACHE_DIR, 'meta.txt')


def normalize_date_str(date_val):
    """将各种日期格式统一为 'YYYY-MM-DD' 字符串"""
    if pd.isna(date_val):
        return None
    s = str(date_val).strip()
    try:
        dt = pd.to_datetime(s, dayfirst=False)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return s


def normalize_time_slot(time_val):
    """标准化时间段格式，如 '14:00-15:00'"""
    if pd.isna(time_val):
        return None
    return str(time_val).strip()


@st.cache_data(ttl=3600, show_spinner="正在加载数据...")
def load_process_report(file_bytes, file_name):
    """加载工艺趋势报表"""
    try:
        df = pd.read_excel(BytesIO(file_bytes))
        if '日期' in df.columns:
            df['日期'] = df['日期'].apply(normalize_date_str)
        if '时间段' in df.columns:
            df['时间段'] = df['时间段'].apply(normalize_time_slot)
        if '机台号' in df.columns:
            df['机台号'] = df['机台号'].astype(str).str.strip()
        return df, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=3600, show_spinner="正在加载数据...")
def load_utilization_report(file_bytes, file_name):
    """加载稼动率小时报表"""
    try:
        df = pd.read_excel(BytesIO(file_bytes))
        if '日期' in df.columns:
            df['日期'] = df['日期'].apply(normalize_date_str)
        if '时间段' in df.columns:
            df['时间段'] = df['时间段'].apply(normalize_time_slot)
        if '机台号' in df.columns:
            df['机台号'] = df['机台号'].astype(str).str.strip()

        numeric_cols = ['设备稼动率', '有效生产时长(min)', '离线时长(min)',
                        '待机时长(min)', '报警时长(min)', '开机时长(min)', '开合模次数']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df, None
    except Exception as e:
        return None, str(e)


def merge_reports(process_df, util_df):
    """按 (机台号, 日期, 时间段) 内连接两个报表"""
    if process_df is None or util_df is None:
        return None, "请先加载两个报表"

    # 复制入参，避免修改调用方的原始 DataFrame
    process_df = process_df.copy()
    util_df = util_df.copy()

    join_keys = ['机台号', '日期', '时间段']
    for key in join_keys:
        if key not in process_df.columns:
            return None, f"工艺报表缺少 '{key}' 列"
        if key not in util_df.columns:
            return None, f"稼动率报表缺少 '{key}' 列"

    for col in join_keys:
        process_df[col] = process_df[col].astype(str).str.strip()
        util_df[col] = util_df[col].astype(str).str.strip()

    util_cols_to_use = [c for c in util_df.columns
                        if c not in process_df.columns
                        or c in join_keys]

    merged = pd.merge(
        process_df,
        util_df[util_cols_to_use],
        on=join_keys,
        how='inner'
    )

    if merged.empty:
        return None, (
            "关联失败：两个报表没有匹配的数据。\n"
            "请确认：\n"
            "1. 机台号是否一致\n"
            "2. 日期格式是否匹配\n"
            "3. 时间段格式是否一致（如 '14:00-15:00'）"
        )

    merged['_timestamp'] = pd.to_datetime(
        merged['日期'] + ' ' + merged['时间段'].str.split('-').str[0],
        format='%Y-%m-%d %H:%M',
        errors='coerce'
    )

    merged = merged.sort_values(['机台号', '_timestamp']).reset_index(drop=True)
    return merged, None


def get_data_summary(merged_df):
    """返回数据摘要信息"""
    if merged_df is None or merged_df.empty:
        return None

    machines = merged_df['机台号'].unique()
    dates = merged_df['日期'].unique()

    EXCLUDE_COLS = {'日期', '车间', '产线', '固资编码', '机型', '机台号',
                    '时间段', '最后数采时间', '_timestamp', '__source'}
    param_cols = [c for c in merged_df.columns if c not in EXCLUDE_COLS
                  and merged_df[c].dtype in ('int64', 'float64')
                  and '时长' not in c and '时长(min)' not in c
                  and '次数' not in c and '设备稼动率' not in c
                  and '报警' not in c and '离线' not in c
                  and '待机' not in c and '开机' not in c]

    return {
        'total_rows': len(merged_df),
        'num_machines': len(machines),
        'machines': sorted(machines),
        'dates': sorted(dates),
        'date_range': f"{dates[0]} ~ {dates[-1]}" if len(dates) > 0 else "无",
        'num_param_cols': len(param_cols),
        'param_cols': param_cols,
    }


def store_data_in_session(process_df, util_df, merged_df, proc_name, util_name):
    """将数据存入 session_state，供各页面使用"""
    st.session_state['process_df'] = process_df
    st.session_state['util_df'] = util_df
    st.session_state['merged_df'] = merged_df
    st.session_state['data_loaded'] = True
    st.session_state['proc_file_name'] = proc_name
    st.session_state['util_file_name'] = util_name


def is_data_loaded():
    """检查数据是否已加载"""
    return st.session_state.get('data_loaded', False)


# ==================== 本地持久化缓存 ====================

def save_cache_to_disk():
    """将 merged_df 保存到本地磁盘，下次启动时自动恢复"""
    merged_df = st.session_state.get('merged_df')
    if merged_df is None or merged_df.empty:
        return False

    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        merged_df.to_pickle(CACHE_FILE)
        with open(META_FILE, 'w', encoding='utf-8') as f:
            f.write(f"cache_time={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"proc_file={st.session_state.get('proc_file_name', '')}\n")
            f.write(f"util_file={st.session_state.get('util_file_name', '')}\n")
            f.write(f"rows={len(merged_df)}\n")
            f.write(f"machines={st.session_state['merged_df']['机台号'].nunique()}\n")
        return True
    except Exception as e:
        st.toast(f"⚠️ 本地缓存保存失败: {e}", icon="⚠️")
        return False


def load_cache_from_disk():
    """从本地磁盘恢复缓存数据"""
    if not os.path.exists(CACHE_FILE):
        return None, None

    try:
        merged_df = pd.read_pickle(CACHE_FILE)
        meta = {}
        if os.path.exists(META_FILE):
            with open(META_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line:
                        k, v = line.strip().split('=', 1)
                        meta[k] = v

        return merged_df, meta
    except Exception:
        return None, None


def restore_from_cache():
    """从磁盘缓存恢复数据到 session_state"""
    merged_df, meta = load_cache_from_disk()
    if merged_df is None:
        return False

    st.session_state['merged_df'] = merged_df
    st.session_state['data_loaded'] = True
    st.session_state['proc_file_name'] = meta.get('proc_file', '(缓存恢复)')
    st.session_state['util_file_name'] = meta.get('util_file', '(缓存恢复)')
    st.session_state['cache_time'] = meta.get('cache_time', '未知')
    st.session_state['cache_rows'] = meta.get('rows', '?')
    st.session_state['cache_machines'] = meta.get('machines', '?')
    return True


def clear_cache():
    """清除本地缓存和 session 数据"""
    for key in ['process_df', 'util_df', 'merged_df', 'data_loaded',
                'proc_file_name', 'util_file_name', 'cache_time',
                'cache_rows', 'cache_machines', 'analysis_cache']:
        st.session_state.pop(key, None)

    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    if os.path.exists(META_FILE):
        os.remove(META_FILE)

    st.cache_data.clear()
    return True


def has_cache():
    """检查是否有本地缓存"""
    return os.path.exists(CACHE_FILE) and os.path.exists(META_FILE)


def get_cache_info():
    """获取缓存信息"""
    if not has_cache():
        return None
    meta = {}
    if os.path.exists(META_FILE):
        with open(META_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    meta[k] = v
    return meta