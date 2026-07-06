"""
数据清洗模块：异常值标记、数据质量报告
"""
import pandas as pd

# 共享常量
DEFAULT_OEE_THRESHOLD = 0.90
OEE_ABNORMAL_HIGH = 1.5       # OEE 超高异常阈值（> 此值视为数采异常）


def flag_abnormal_oee(df, col='设备稼动率'):
    """
    标记异常的稼动率值
    - 负值：数采异常
    - > OEE_ABNORMAL_HIGH：数采异常（理论上最大为 1，但允许小幅超出）
    - 返回新增列：oee_abnormal (bool), oee_abnormal_type (str)
    """
    if col not in df.columns:
        return df

    df = df.copy()
    df['oee_abnormal'] = False
    df['oee_abnormal_type'] = '正常'

    neg_mask = df[col] < 0
    high_mask = df[col] > OEE_ABNORMAL_HIGH

    df.loc[neg_mask, 'oee_abnormal'] = True
    df.loc[neg_mask, 'oee_abnormal_type'] = '负数异常'

    df.loc[high_mask, 'oee_abnormal'] = True
    df.loc[high_mask, 'oee_abnormal_type'] = '超高异常'

    return df


def quality_report(df):
    """
    生成数据质量报告
    返回字典：{列名: {missing: int, missing_pct: float, abnormal: int, ...}}
    """
    if df is None or df.empty:
        return {}

    report = {}
    total_rows = len(df)

    # 基本统计
    for col in df.columns:
        info = {
            'dtype': str(df[col].dtype),
            'missing': int(df[col].isna().sum()),
            'missing_pct': round(df[col].isna().sum() / total_rows * 100, 2),
            'unique': int(df[col].nunique()),
        }
        report[col] = info

    # OEE 异常统计
    if 'oee_abnormal' in df.columns:
        abnormal_count = df['oee_abnormal'].sum()
    elif '设备稼动率' in df.columns:
        abnormal_count = ((df['设备稼动率'] < 0) | (df['设备稼动率'] > OEE_ABNORMAL_HIGH)).sum()
    else:
        abnormal_count = 0

    report['_summary'] = {
        'total_rows': total_rows,
        'columns': len(df.columns),
        'oee_abnormal_count': int(abnormal_count),
        'oee_abnormal_pct': round(abnormal_count / total_rows * 100, 2) if total_rows > 0 else 0,
    }

    return report


def get_param_groups():
    """
    返回工艺参数分组定义
    用于前端的参数选择器
    """
    return {
        '射胶参数': [
            '射胶压力一段', '射胶速度一段', '射胶位置一段',
            '射胶压力二段', '射胶速度二段', '射胶位置二段',
            '射胶压力三段', '射胶速度三段', '射胶位置三段',
            '射胶压力四段', '射胶速度四段', '射胶位置四段',
            '射胶压力五段', '射胶速度五段', '射胶位置五段',
        ],
        '保压参数': [
            '保压压力一段', '保压速度一段', '保压时间一段',
            '保压压力二段', '保压速度二段', '保压时间二段',
            '保压压力三段', '保压速度三段', '保压时间三段',
        ],
        '温度参数': [
            '温度一段值', '温度二段值', '温度三段值',
            '温度四段值', '温度五段值', '温度六段值',
        ],
        '其他参数': [
            '储料背压（bar）', '射退位置（mm）', '射退压力（bar）',
            '射退速度（%）', '储料时间（sec）', '射胶终点', '成型周期（s）',
        ],
    }


def get_all_params():
    """返回所有工艺参数的展平列表（按参数组顺序）"""
    all_params = []
    for group_params in get_param_groups().values():
        all_params.extend(group_params)
    return all_params