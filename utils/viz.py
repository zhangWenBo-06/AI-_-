"""
可视化模块：Plotly 图表封装
"""
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


def plot_param_trend(df, machine, selected_params, date_range=None):
    """
    工艺参数趋势折线图
    """
    machine_df = df[df['机台号'] == machine].copy()
    if machine_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="该机台无数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=16))
        return fig

    if date_range and len(date_range) == 2:
        machine_df = machine_df[
            (machine_df['日期'] >= str(date_range[0])) &
            (machine_df['日期'] <= str(date_range[1]))
        ]

    if machine_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="所选日期范围内无数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=16))
        return fig

    machine_df = machine_df.sort_values('_timestamp')

    valid_params = [p for p in selected_params if p in machine_df.columns]
    if not valid_params:
        valid_params = [c for c in machine_df.columns
                        if c not in ('日期', '车间', '产线', '固资编码', '机型',
                                     '机台号', '时间段', '最后数采时间', '_timestamp')
                        and machine_df[c].dtype in ('int64', 'float64')][:6]

    if not valid_params:
        fig = go.Figure()
        fig.add_annotation(text="无可用参数列", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=16))
        return fig

    temp_params = [p for p in valid_params if '温度' in p]
    other_params = [p for p in valid_params if '温度' not in p]

    colors = px.colors.qualitative.Plotly + px.colors.qualitative.Set2
    color_map = {}
    for i, p in enumerate(valid_params):
        color_map[p] = colors[i % len(colors)]

    use_secondary = len(temp_params) > 0 and len(other_params) > 0
    fig = make_subplots(specs=[[{"secondary_y": use_secondary}]])

    for param in other_params:
        fig.add_trace(
            go.Scatter(
                x=machine_df['_timestamp'],
                y=machine_df[param],
                mode='lines+markers',
                name=param,
                line=dict(color=color_map[param], width=1.5),
                marker=dict(size=3),
                hovertemplate='%{x|%m/%d %H:%M}<br>' + param + ': %{y}<extra></extra>',
            ),
            secondary_y=False,
        )

    for param in temp_params:
        fig.add_trace(
            go.Scatter(
                x=machine_df['_timestamp'],
                y=machine_df[param],
                mode='lines+markers',
                name=param,
                line=dict(color=color_map[param], width=1.5, dash='dash'),
                marker=dict(size=3, symbol='triangle-up'),
                hovertemplate='%{x|%m/%d %H:%M}<br>' + param + ': %{y}℃<extra></extra>',
            ),
            secondary_y=use_secondary,  # 仅在双Y轴模式时使用右轴
        )

    fig.update_layout(
        title=f'机台 {machine} — 工艺参数趋势',
        xaxis_title='时间',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
        height=500,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    if use_secondary:
        fig.update_yaxes(title_text='压力 / 速度 / 位置 等', secondary_y=False)
        fig.update_yaxes(title_text='温度 (℃)', secondary_y=True)
    elif temp_params and not other_params:
        fig.update_yaxes(title_text='温度 (℃)')
    else:
        fig.update_yaxes(title_text='参数值')

    return fig


def plot_oee_heatmap(df, machine):
    """
    稼动率热力图：行=日期，列=小时，颜色=稼动率
    """
    machine_df = df[df['机台号'] == machine].copy()
    if machine_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="该机台无数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    machine_df['_hour'] = machine_df['时间段'].str.extract(r'(\d{2}):')[0]
    machine_df['_hour'] = pd.to_numeric(machine_df['_hour'], errors='coerce')

    # 裁剪到 [0,1] 避免异常值颜色失真
    oee_values = machine_df['设备稼动率'].clip(0, 1)

    pivot = machine_df.assign(_oee_display=oee_values).pivot_table(
        values='_oee_display', index='日期', columns='_hour', aggfunc='mean'
    ).sort_index(ascending=False)

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[f'{int(h):02d}:00' for h in pivot.columns],
        y=pivot.index,
        colorscale=[
            [0, '#ff4d4d'],
            [0.5, '#ffcc00'],
            [0.9, '#66cc66'],
            [1, '#008800'],
        ],
        zmin=0, zmax=1,
        text=np.round(pivot.values, 2),
        texttemplate='%{text}',
        textfont=dict(size=10),
        hovertemplate='日期: %{y}<br>小时: %{x}<br>稼动率: %{z}<extra></extra>',
        colorbar=dict(title='稼动率', tickformat='.0%'),
    ))

    fig.update_layout(
        title=f'机台 {machine} — 稼动率小时热力图',
        xaxis_title='小时',
        yaxis_title='日期',
        template='plotly_white',
        height=300,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    return fig


def plot_oee_hourly_bars(df, machine):
    """
    按天分组的每小时平均稼动率柱状图
    """
    machine_df = df[df['机台号'] == machine].copy()
    if machine_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="该机台无数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    machine_df['_hour'] = machine_df['时间段'].str.extract(r'(\d{2}):')[0]
    machine_df['_hour'] = pd.to_numeric(machine_df['_hour'], errors='coerce')

    dates = sorted(machine_df['日期'].unique())

    fig = go.Figure()
    for date in dates:
        date_df = machine_df[machine_df['日期'] == date].sort_values('_hour')
        fig.add_trace(go.Bar(
            x=[f'{int(h):02d}:00' for h in date_df['_hour']],
            y=date_df['设备稼动率'],
            name=str(date),
            hovertemplate='%{x}<br>稼动率: %{y:.0%}<extra>%{data.name}</extra>',
        ))

    fig.add_hline(y=0.9, line_dash="dash", line_color="red",
                  annotation_text="90% 阈值", annotation_position="bottom right")

    fig.update_layout(
        title=f'机台 {machine} — 按天每小时稼动率对比',
        xaxis_title='小时',
        yaxis_title='稼动率',
        yaxis_tickformat='.0%',
        barmode='group',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        template='plotly_white',
        height=400,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    return fig


def plot_loss_pie(df, machine):
    """
    不稼动时长归因饼图：离线/待机/报警时长占比
    """
    machine_df = df[df['机台号'] == machine].copy()
    if machine_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="该机台无数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    loss_cols = {
        '离线时长': '离线时长(min)',
        '待机时长': '待机时长(min)',
        '报警时长': '报警时长(min)',
    }

    values = []
    labels = []
    for label, col in loss_cols.items():
        if col in machine_df.columns:
            total = machine_df[col].sum()
            if total > 0:
                values.append(total)
                labels.append(label)

    if not values or sum(values) == 0:
        fig = go.Figure()
        fig.add_annotation(text="该机台无不稼动时长<br>（所有时段都在生产）",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(size=14, color='green'))
        fig.update_layout(height=350)
        return fig

    colors_pie = ['#ff6b6b', '#ffd93d', '#6bcb77']

    fig = go.Figure(data=go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(colors=colors_pie[:len(labels)]),
        textinfo='label+percent',
        hovertemplate='%{label}<br>%{value:.1f} 分钟<br>占比: %{percent}',
    ))

    total_loss = sum(values)
    fig.update_layout(
        title=f'机台 {machine} — 不稼动时长分布（总计 {total_loss:.0f} 分钟）',
        template='plotly_white',
        height=350,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    return fig


def plot_cycle_scatter(df, machine):
    """
    开合模次数 vs 稼动率散点图
    """
    machine_df = df[df['机台号'] == machine].copy()
    if machine_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="该机台无数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    if '开合模次数' not in machine_df.columns:
        fig = go.Figure()
        fig.add_annotation(text="缺少开合模次数数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    fig = go.Figure()

    has_abnormal_col = 'oee_abnormal' in machine_df.columns
    if has_abnormal_col:
        normal_mask = ~machine_df['oee_abnormal']
    else:
        normal_mask = pd.Series(True, index=machine_df.index)

    fig.add_trace(go.Scatter(
        x=machine_df.loc[normal_mask, '开合模次数'],
        y=machine_df.loc[normal_mask, '设备稼动率'],
        mode='markers',
        name='正常数据',
        marker=dict(color='#3366cc', size=8, opacity=0.7),
        hovertemplate='开合模次数: %{x}<br>稼动率: %{y:.0%}<extra></extra>',
    ))

    if has_abnormal_col and machine_df['oee_abnormal'].any():
        abnormal_mask = machine_df['oee_abnormal']
        fig.add_trace(go.Scatter(
            x=machine_df.loc[abnormal_mask, '开合模次数'],
            y=machine_df.loc[abnormal_mask, '设备稼动率'],
            mode='markers',
            name='数采异常',
            marker=dict(color='#ff4444', size=10, symbol='x', opacity=0.8),
            hovertemplate='开合模次数: %{x}<br>稼动率: %{y}<br>⚠ 数采异常<extra></extra>',
        ))

    fig.update_layout(
        title=f'机台 {machine} — 开合模次数 vs 稼动率',
        xaxis_title='开合模次数',
        yaxis_title='设备稼动率',
        yaxis_tickformat='.0%',
        template='plotly_white',
        height=350,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    return fig


def plot_param_box(df, machine, selected_params):
    """
    工艺参数箱线图，展示分布范围
    """
    machine_df = df[df['机台号'] == machine].copy()
    if machine_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="该机台无数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    valid_params = [p for p in selected_params if p in machine_df.columns and p != '时间段']
    if not valid_params:
        fig = go.Figure()
        fig.add_annotation(text="无可用参数", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    fig = go.Figure()
    for param in valid_params[:12]:
        fig.add_trace(go.Box(
            y=machine_df[param],
            name=param,
            boxmean='sd',
            hovertemplate=param + '<br>值: %{y}<extra></extra>',
        ))

    fig.update_layout(
        title=f'机台 {machine} — 工艺参数分布箱线图',
        yaxis_title='参数值',
        template='plotly_white',
        height=500,
        margin=dict(l=40, r=40, t=60, b=80),
        showlegend=False,
    )

    fig.update_xaxes(tickangle=45)

    return fig


# ==================== 多机台对比 + 相关性分析 ====================

def plot_multi_machine_trend(df, machines, param, date_range=None):
    """
    多机台单参数对比折线图
    """
    valid_machines = [m for m in machines if m in df['机台号'].values]
    if not valid_machines:
        fig = go.Figure()
        fig.add_annotation(text="所选机台均无数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    fig = go.Figure()
    colors = px.colors.qualitative.Plotly

    for idx, machine in enumerate(valid_machines):
        mdf = df[df['机台号'] == machine].copy()
        if date_range and len(date_range) == 2:
            mdf = mdf[(mdf['日期'] >= str(date_range[0])) &
                      (mdf['日期'] <= str(date_range[1]))]
        mdf = mdf.sort_values('_timestamp')

        if param not in mdf.columns:
            continue

        color = colors[idx % len(colors)]
        fig.add_trace(go.Scatter(
            x=mdf['_timestamp'],
            y=mdf[param],
            mode='lines+markers',
            name=f'机台 {machine}',
            line=dict(color=color, width=2),
            marker=dict(size=4),
            hovertemplate='%{x|%m/%d %H:%M}<br>' + f'{machine}: %{{y}}<extra></extra>',
        ))

    fig.update_layout(
        title=f'多机台对比 — {param}',
        xaxis_title='时间',
        yaxis_title=param,
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        template='plotly_white',
        height=500,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    return fig


def plot_correlation_bars(corr_df, top_n=20):
    """
    参数-OEE 相关性柱状图
    corr_df: compute_param_oee_correlation 返回的 DataFrame
    """
    if corr_df is None or corr_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="无足够数据计算相关性", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    top_df = corr_df.head(top_n).iloc[::-1]  # 反转以便从上到下显示

    fig = go.Figure()

    colors = ['#ff6b6b' if v < 0 else '#51cf66' for v in top_df['相关系数']]

    fig.add_trace(go.Bar(
        y=top_df['工艺参数'],
        x=top_df['相关系数'],
        orientation='h',
        marker=dict(color=colors),
        text=top_df['相关系数'].apply(lambda x: f'{x:+.3f}'),
        textposition='outside',
        hovertemplate='%{y}<br>相关系数: %{x:+.4f}<extra></extra>',
    ))

    fig.add_vline(x=0, line_color='#888', line_width=1)

    fig.update_layout(
        title='工艺参数与 OEE 的相关系数（Pearson）',
        xaxis_title='相关系数（正=正相关, 负=负相关）',
        xaxis=dict(range=[-1.1, 1.1]),
        template='plotly_white',
        height=max(400, len(top_df) * 22),
        margin=dict(l=40, r=80, t=60, b=40),
        showlegend=False,
    )

    return fig


def plot_oee_ranking_bars(ranking_df, top_n=15):
    """
    机台 OEE 排名柱状图
    """
    if ranking_df is None or ranking_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="无数据", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    top_df = ranking_df.head(top_n).iloc[::-1]

    fig = go.Figure(go.Bar(
        y=top_df['机台号'],
        x=top_df['平均OEE'],
        orientation='h',
        marker=dict(
            color=top_df['平均OEE'],
            colorscale='RdYlGn',
            cmin=0, cmax=1,
            showscale=True,
            colorbar=dict(title='平均OEE', tickformat='.0%'),
        ),
        text=top_df['平均OEE'].apply(lambda x: f'{x:.1%}'),
        textposition='outside',
        hovertemplate='%{y}<br>平均OEE: %{x:.1%}<br>≥90%占比: %{customdata:.0f}%<extra></extra>',
        customdata=top_df['≥90%占比'],
    ))

    fig.add_vline(x=0.9, line_dash='dash', line_color='red',
                  annotation_text='90%', annotation_position='top')

    fig.update_layout(
        title='机台平均 OEE 排名',
        xaxis_title='平均稼动率',
        xaxis_tickformat='.0%',
        xaxis=dict(range=[0, 1.05]),
        template='plotly_white',
        height=max(350, len(top_df) * 25),
        margin=dict(l=40, r=80, t=60, b=40),
        showlegend=False,
    )

    return fig


# ==================== Plotly 图表中文配置 ====================

def get_plotly_config():
    """
    返回统一的 Plotly 图表配置，将工具栏按钮改为中文显示
    """
    return {
        'displayModeBar': True,
        'modeBarButtonsToRemove': [
            'lasso2d', 'select2d', 'sendDataToCloud',
        ],
        'displaylogo': False,
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'chart',
            'height': 800,
            'width': 1400,
            'scale': 2,
        },
        'locale': 'zh-CN',
        'scrollZoom': True,
    }