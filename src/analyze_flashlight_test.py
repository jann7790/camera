#!/usr/bin/env python3
"""
FLIR Camera Flashlight Detection Analysis
手電筒遠距離偵測能力量化分析

分析三個數據集：
- indoor/mode2: 曝光8ms, 增益0dB (室內明亮)
- indoor/mode4_night: 曝光35ms, 增益18dB (室內黑暗/高靈敏度)
- outdoor/500_6_day: 曝光0.5ms, 增益6dB (戶外白天)

測試場景：手持手電筒從相機前走到25m距離
相機配置：f=100mm, 有效孔徑D=1.2cm, f/8.3

使用動態閾值（基於最大值比例）來識別手電筒光源
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime
import re
from typing import Dict, List, Tuple
import json

class FlashlightAnalyzer:
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.datasets = {
            'indoor_mode2': {
                'path': self.base_path / 'indoor' / 'mode2',
                'label': 'Indoor Mode2 (8ms, 0dB)',
                'exposure_us': 8000,
                'gain_db': 0,
                'color': 'rgb(255, 127, 14)'
            },
            'indoor_mode4_night': {
                'path': self.base_path / 'indoor' / 'mode4_night',
                'label': 'Indoor Mode4 Night (35ms, 18dB)',
                'exposure_us': 35000,
                'gain_db': 18,
                'color': 'rgb(44, 160, 44)'
            },
            'outdoor_500_6_day': {
                'path': self.base_path / 'outdoor' / '500_6_day',
                'label': 'Outdoor Day (0.5ms, 6dB)',
                'exposure_us': 500,
                'gain_db': 6,
                'color': 'rgb(31, 119, 180)'
            }
        }
        
        # 相機光學參數
        self.focal_length_mm = 100
        self.aperture_diameter_mm = 12  # 1.2cm
        self.f_number = self.focal_length_mm / self.aperture_diameter_mm
        
        # 分析參數
        self.hotspot_threshold_ratio = 0.7  # 亮點閾值 = max * 0.7
        self.max_distance_m = 25  # 最大測試距離
        
    def parse_timestamp(self, filename: str) -> datetime:
        """從文件名提取時間戳"""
        match = re.search(r'(\d{8})_(\d{6})', filename)
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            return datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
        return None
    
    def analyze_single_image(self, npy_path: Path) -> Dict:
        """
        分析單張圖像
        使用動態閾值識別手電筒光源
        
        返回：
        - max_brightness: 最大像素值（手電筒最亮點）
        - hotspot_area: 亮點像素數量（動態閾值）
        - hotspot_mean: 亮點區域平均亮度
        - hotspot_centroid: 亮點質心位置
        - background_median: 背景中位數亮度
        - background_mean: 背景平均亮度
        - background_std: 背景標準差（噪聲水平）
        - snr: 信噪比
        - contrast: 對比度
        """
        # 讀取原始數據
        image = np.load(npy_path)
        
        # 基本統計
        max_val = np.max(image)
        min_val = np.min(image)
        mean_val = np.mean(image)
        std_val = np.std(image)
        median_val = np.median(image)
        
        # 智能動態閾值
        # 方法1: 基於最大值比例 (max * 0.7)
        threshold_1 = max_val * self.hotspot_threshold_ratio
        
        # 方法2: 基於統計學 (mean + 5*std) - 適合高對比度場景
        threshold_2 = mean_val + 5 * std_val
        
        # 方法3: 基於百分位數 (99.9th percentile) - 最亮的0.1%
        threshold_3 = np.percentile(image, 99.9)
        
        # 選擇最合適的閾值
        # 如果 max 和 mean 差異很大（> 3*std），用 max*0.7
        # 否則用統計學方法
        if (max_val - mean_val) > 3 * std_val:
            hotspot_threshold = max(threshold_1, threshold_2)
        else:
            # 低對比度場景，使用更保守的閾值
            hotspot_threshold = threshold_3
        
        hotspot_mask = image > hotspot_threshold
        
        # 亮點區域分析
        hotspot_pixels = image[hotspot_mask]
        hotspot_area = np.sum(hotspot_mask)
        
        if hotspot_area > 0:
            hotspot_mean = np.mean(hotspot_pixels)
            hotspot_std = np.std(hotspot_pixels)
            
            # 計算質心
            y_indices, x_indices = np.where(hotspot_mask)
            centroid_x = np.mean(x_indices)
            centroid_y = np.mean(y_indices)
        else:
            hotspot_mean = max_val
            hotspot_std = 0
            centroid_x = 0
            centroid_y = 0
        
        # 背景定義：排除亮點區域
        background_mask = ~hotspot_mask
        background_pixels = image[background_mask]
        
        if len(background_pixels) > 0:
            background_mean = np.mean(background_pixels)
            background_median = np.median(background_pixels)
            background_std = np.std(background_pixels)
        else:
            background_mean = mean_val
            background_median = median_val
            background_std = std_val
        
        # 計算 SNR 和對比度
        if background_std > 0:
            snr = (hotspot_mean - background_mean) / background_std
        else:
            snr = 0
        
        if background_mean > 0:
            contrast = (max_val - background_mean) / background_mean
            weber_contrast = (hotspot_mean - background_mean) / background_mean
        else:
            contrast = 0
            weber_contrast = 0
        
        return {
            'max_brightness': max_val,
            'min_brightness': min_val,
            'overall_mean': mean_val,
            'overall_std': std_val,
            'overall_median': median_val,
            'hotspot_threshold': hotspot_threshold,
            'hotspot_area': hotspot_area,
            'hotspot_mean': hotspot_mean,
            'hotspot_std': hotspot_std,
            'centroid_x': centroid_x,
            'centroid_y': centroid_y,
            'background_mean': background_mean,
            'background_median': background_median,
            'background_std': background_std,
            'snr': snr,
            'contrast': contrast,
            'weber_contrast': weber_contrast,
            'image_shape': image.shape
        }
    
    def process_dataset(self, dataset_key: str) -> pd.DataFrame:
        """處理單個數據集，返回時間序列數據"""
        dataset = self.datasets[dataset_key]
        npy_files = sorted(dataset['path'].glob('flir_raw_*.npy'))
        
        print(f"\n正在處理 {dataset['label']}...")
        print(f"  找到 {len(npy_files)} 個 .npy 文件")
        
        results = []
        
        for npy_file in npy_files:
            timestamp = self.parse_timestamp(npy_file.name)
            if timestamp is None:
                continue
            
            analysis = self.analyze_single_image(npy_file)
            analysis['timestamp'] = timestamp
            analysis['filename'] = npy_file.name
            results.append(analysis)
        
        df = pd.DataFrame(results)
        
        if len(df) > 0:
            # 計算相對時間（秒）
            df = df.sort_values('timestamp')
            df['time_seconds'] = (df['timestamp'] - df['timestamp'].iloc[0]).dt.total_seconds()
            
            # 估算距離（假設線性移動從0到25m）
            total_time = df['time_seconds'].iloc[-1]
            df['estimated_distance_m'] = (df['time_seconds'] / total_time) * self.max_distance_m
            
            print(f"  處理完成：{len(df)} 個樣本")
            print(f"  時間範圍：{df['time_seconds'].iloc[0]:.1f}s 到 {df['time_seconds'].iloc[-1]:.1f}s")
            print(f"  估算距離：0m 到 {df['estimated_distance_m'].iloc[-1]:.1f}m")
        
        return df
    
    def process_all_datasets(self) -> Dict[str, pd.DataFrame]:
        """處理所有數據集"""
        all_data = {}
        for key in self.datasets.keys():
            all_data[key] = self.process_dataset(key)
        return all_data
    
    def plot_brightness_vs_distance(self, all_data: Dict[str, pd.DataFrame]) -> go.Figure:
        """繪製亮度 vs 距離圖"""
        fig = go.Figure()
        
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            
            dataset = self.datasets[key]
            
            # 最大亮度
            fig.add_trace(go.Scatter(
                x=df['estimated_distance_m'],
                y=df['max_brightness'],
                mode='lines+markers',
                name=f"{dataset['label']} - Max",
                line=dict(color=dataset['color'], width=2),
                marker=dict(size=8),
                hovertemplate='<b>距離</b>: %{x:.1f}m<br>' +
                              '<b>最大亮度</b>: %{y:.1f}<br>' +
                              '<extra></extra>'
            ))
            
            # 亮點平均亮度
            fig.add_trace(go.Scatter(
                x=df['estimated_distance_m'],
                y=df['hotspot_mean'],
                mode='lines+markers',
                name=f"{dataset['label']} - Hotspot Mean",
                line=dict(color=dataset['color'], width=2, dash='dash'),
                marker=dict(size=6, symbol='diamond'),
                hovertemplate='<b>距離</b>: %{x:.1f}m<br>' +
                              '<b>亮點平均</b>: %{y:.1f}<br>' +
                              '<extra></extra>'
            ))
        
        fig.update_layout(
            title='手電筒亮度 vs 距離分析<br><sub>動態閾值 (threshold = max * 0.7)</sub>',
            xaxis_title='估算距離 (m)',
            yaxis_title='像素亮度值 (0-255)',
            hovermode='closest',
            template='plotly_white',
            height=600,
            legend=dict(x=0.7, y=0.95)
        )
        
        return fig
    
    def plot_snr_vs_distance(self, all_data: Dict[str, pd.DataFrame]) -> go.Figure:
        """繪製 SNR vs 距離圖"""
        fig = go.Figure()
        
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            
            dataset = self.datasets[key]
            
            fig.add_trace(go.Scatter(
                x=df['estimated_distance_m'],
                y=df['snr'],
                mode='lines+markers',
                name=dataset['label'],
                line=dict(color=dataset['color'], width=2),
                marker=dict(size=8),
                hovertemplate='<b>距離</b>: %{x:.1f}m<br>' +
                              '<b>SNR</b>: %{y:.2f}<br>' +
                              '<extra></extra>'
            ))
        
        # 添加可靠偵測閾值線
        max_distance = max([df['estimated_distance_m'].max() for df in all_data.values() if len(df) > 0])
        fig.add_hline(y=5, line_dash="dot", line_color="red", 
                      annotation_text="SNR=5 (可靠偵測閾值)")
        fig.add_hline(y=3, line_dash="dot", line_color="orange", 
                      annotation_text="SNR=3 (最低偵測閾值)")
        
        fig.update_layout(
            title='信噪比 (SNR) vs 距離分析<br><sub>SNR = (Hotspot_mean - Background_mean) / Background_std</sub>',
            xaxis_title='估算距離 (m)',
            yaxis_title='信噪比 (SNR)',
            hovermode='closest',
            template='plotly_white',
            height=600,
            legend=dict(x=0.7, y=0.95)
        )
        
        return fig
    
    def plot_hotspot_area_vs_distance(self, all_data: Dict[str, pd.DataFrame]) -> go.Figure:
        """繪製亮點面積 vs 距離圖"""
        fig = go.Figure()
        
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            
            dataset = self.datasets[key]
            
            fig.add_trace(go.Scatter(
                x=df['estimated_distance_m'],
                y=df['hotspot_area'],
                mode='lines+markers',
                name=dataset['label'],
                line=dict(color=dataset['color'], width=2),
                marker=dict(size=8),
                hovertemplate='<b>距離</b>: %{x:.1f}m<br>' +
                              '<b>亮點像素數</b>: %{y:.0f}<br>' +
                              '<extra></extra>'
            ))
        
        fig.update_layout(
            title='手電筒光源面積 vs 距離分析<br><sub>亮點定義：像素值 > max * 0.7</sub>',
            xaxis_title='估算距離 (m)',
            yaxis_title='亮點像素數量',
            hovermode='closest',
            template='plotly_white',
            height=600,
            legend=dict(x=0.7, y=0.95)
        )
        
        return fig
    
    def plot_trajectory(self, all_data: Dict[str, pd.DataFrame]) -> go.Figure:
        """繪製手電筒位置軌跡"""
        fig = go.Figure()
        
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            
            dataset = self.datasets[key]
            
            # 創建顏色梯度（距離）
            fig.add_trace(go.Scatter(
                x=df['centroid_x'],
                y=df['centroid_y'],
                mode='lines+markers',
                name=dataset['label'],
                line=dict(color=dataset['color'], width=2),
                marker=dict(
                    size=10,
                    color=df['estimated_distance_m'],
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(title='距離 (m)')
                ),
                hovertemplate='<b>位置</b>: (%{x:.0f}, %{y:.0f})<br>' +
                              '<b>距離</b>: %{marker.color:.1f}m<br>' +
                              '<extra></extra>'
            ))
        
        fig.update_layout(
            title='手電筒在圖像中的位置軌跡<br><sub>質心位置隨距離變化（顏色表示距離）</sub>',
            xaxis_title='X 座標 (pixel)',
            yaxis_title='Y 座標 (pixel)',
            hovermode='closest',
            template='plotly_white',
            height=600,
            yaxis=dict(autorange='reversed')  # 反轉 Y 軸以匹配圖像座標
        )
        
        return fig
    
    def plot_contrast_vs_distance(self, all_data: Dict[str, pd.DataFrame]) -> go.Figure:
        """繪製對比度 vs 距離圖"""
        fig = go.Figure()
        
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            
            dataset = self.datasets[key]
            
            fig.add_trace(go.Scatter(
                x=df['estimated_distance_m'],
                y=df['contrast'],
                mode='lines+markers',
                name=dataset['label'],
                line=dict(color=dataset['color'], width=2),
                marker=dict(size=8),
                hovertemplate='<b>距離</b>: %{x:.1f}m<br>' +
                              '<b>對比度</b>: %{y:.2f}<br>' +
                              '<extra></extra>'
            ))
        
        fig.update_layout(
            title='對比度 vs 距離分析<br><sub>Contrast = (Max - Background) / Background</sub>',
            xaxis_title='估算距離 (m)',
            yaxis_title='對比度',
            hovermode='closest',
            template='plotly_white',
            height=600,
            legend=dict(x=0.7, y=0.95)
        )
        
        return fig
    
    def generate_summary_table(self, all_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """生成總結統計表"""
        summary_rows = []
        
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            
            dataset = self.datasets[key]
            
            # 找到 SNR < 5 的第一個點（認為無法可靠偵測）
            snr_threshold_idx = df[df['snr'] < 5].index
            if len(snr_threshold_idx) > 0:
                detection_limit_m = df.loc[snr_threshold_idx[0], 'estimated_distance_m']
            else:
                detection_limit_m = self.max_distance_m
            
            summary_rows.append({
                '數據集': dataset['label'],
                '曝光時間 (μs)': dataset['exposure_us'],
                '增益 (dB)': dataset['gain_db'],
                '樣本數': len(df),
                '最大亮度 (起始)': df.iloc[0]['max_brightness'],
                '最大亮度 (結束)': df.iloc[-1]['max_brightness'],
                '起始 SNR': df.iloc[0]['snr'],
                '結束 SNR': df.iloc[-1]['snr'],
                '估算偵測極限 (m)': f"{detection_limit_m:.1f}",
                '25m處是否可偵測': '是' if df.iloc[-1]['snr'] >= 5 else '否'
            })
        
        return pd.DataFrame(summary_rows)
    
    def generate_html_report(self, all_data: Dict[str, pd.DataFrame], output_file: str = 'flashlight_analysis_report.html'):
        """生成完整的 HTML 分析報告"""
        print("\n正在生成 HTML 報告...")
        
        # 創建所有圖表
        fig_brightness = self.plot_brightness_vs_distance(all_data)
        fig_snr = self.plot_snr_vs_distance(all_data)
        fig_area = self.plot_hotspot_area_vs_distance(all_data)
        fig_contrast = self.plot_contrast_vs_distance(all_data)
        fig_trajectory = self.plot_trajectory(all_data)
        
        # 將圖表轉為獨立 HTML div
        from plotly.offline import plot
        brightness_div = plot(fig_brightness, output_type='div', include_plotlyjs=False)
        snr_div = plot(fig_snr, output_type='div', include_plotlyjs=False)
        area_div = plot(fig_area, output_type='div', include_plotlyjs=False)
        contrast_div = plot(fig_contrast, output_type='div', include_plotlyjs=False)
        trajectory_div = plot(fig_trajectory, output_type='div', include_plotlyjs=False)
        
        # 生成總結表
        summary_df = self.generate_summary_table(all_data)
        
        # 構建 HTML
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>手電筒遠距離偵測能力分析報告</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 40px;
            border-left: 4px solid #3498db;
            padding-left: 15px;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .info-box {{
            background: #e8f4f8;
            padding: 15px;
            border-left: 4px solid #3498db;
            margin: 15px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .plot-container {{
            margin: 30px 0;
        }}
        .conclusion {{
            background: #d5f4e6;
            padding: 20px;
            border-left: 4px solid #27ae60;
            margin: 20px 0;
        }}
        .warning {{
            background: #ffe5e5;
            padding: 20px;
            border-left: 4px solid #e74c3c;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <h1>🔦 FLIR Camera 手電筒遠距離偵測能力分析報告</h1>
    
    <div class="section">
        <h2>📋 測試概述</h2>
        <div class="info-box">
            <p><strong>測試目的：</strong>評估小孔徑長焦鏡頭配置下，FLIR 相機能否偵測到 25m 距離的手電筒光源</p>
            <p><strong>相機配置：</strong></p>
            <ul>
                <li>鏡頭焦距：f = {self.focal_length_mm} mm</li>
                <li>有效孔徑：D = {self.aperture_diameter_mm} mm (1.2 cm)</li>
                <li>光圈值：f/{self.f_number:.1f}</li>
            </ul>
            <p><strong>測試方法：</strong>手持手電筒從相機前逐漸遠離至 25m 距離，每 5 秒記錄一次</p>
            <p><strong>分析方法：</strong>使用動態閾值（threshold = max × 0.7）識別手電筒光源，計算 SNR 評估偵測能力</p>
        </div>
    </div>
    
    <div class="section">
        <h2>📊 總結統計表</h2>
        {summary_df.to_html(index=False, classes='summary-table')}
    </div>
    
    <div class="section">
        <h2>📈 分析圖表</h2>
        
        <h3>1. 亮度 vs 距離</h3>
        <div class="plot-container">
            {brightness_div}
        </div>
        <p>此圖顯示手電筒的最大亮度和亮點平均亮度隨距離的衰減。理論上應符合平方反比定律（1/d²）。</p>
        
        <h3>2. 信噪比 (SNR) vs 距離</h3>
        <div class="plot-container">
            {snr_div}
        </div>
        <p><strong>關鍵指標：</strong>SNR ≥ 5 認為可靠偵測，SNR ≥ 3 認為最低偵測閾值。SNR < 3 則無法可靠區分光源與噪聲。</p>
        
        <h3>3. 手電筒光源面積 vs 距離</h3>
        <div class="plot-container">
            {area_div}
        </div>
        <p>顯示手電筒在圖像中的像素面積隨距離減少。面積過小時（< 10 pixels）可能難以辨識為光源。</p>
        
        <h3>4. 對比度 vs 距離</h3>
        <div class="plot-container">
            {contrast_div}
        </div>
        <p>對比度反映手電筒相對於背景的亮度差異。高對比度表示更容易偵測。</p>
        
        <h3>5. 手電筒位置軌跡</h3>
        <div class="plot-container">
            {trajectory_div}
        </div>
        <p>顯示手電筒在圖像中的移動軌跡，顏色表示估算距離。</p>
    </div>
    
    <div class="section">
        <h2>🔍 結論與建議</h2>
        <div id="conclusions"></div>
    </div>
    
</body>
</html>
"""
        
        # 添加結論
        conclusions_html = self.generate_conclusions(all_data)
        html_content = html_content.replace('<div id="conclusions"></div>', conclusions_html)
        
        # 寫入文件
        output_path = self.base_path / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n✅ 報告已生成：{output_path}")
        print(f"   請用瀏覽器打開查看：file://{output_path.absolute()}")
        
        return output_path
    
    def generate_conclusions(self, all_data: Dict[str, pd.DataFrame]) -> str:
        """生成結論和建議的 HTML"""
        conclusions = []
        
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            
            dataset = self.datasets[key]
            final_snr = df.iloc[-1]['snr']
            final_distance = df.iloc[-1]['estimated_distance_m']
            final_brightness = df.iloc[-1]['max_brightness']
            final_area = df.iloc[-1]['hotspot_area']
            
            if final_snr >= 5:
                status_class = 'conclusion'
                status_icon = '✅'
                detection_status = f"在 {final_distance:.1f}m 距離處，<strong>可以可靠偵測</strong>手電筒光源"
            elif final_snr >= 3:
                status_class = 'warning'
                status_icon = '⚠️'
                detection_status = f"在 {final_distance:.1f}m 距離處，<strong>勉強可以偵測</strong>手電筒光源，但不夠穩定"
            else:
                status_class = 'warning'
                status_icon = '❌'
                detection_status = f"在 {final_distance:.1f}m 距離處，<strong>無法可靠偵測</strong>手電筒光源"
            
            conclusions.append(f"""
            <div class="{status_class}">
                <h3>{status_icon} {dataset['label']}</h3>
                <p>{detection_status}</p>
                <ul>
                    <li>最終 SNR：{final_snr:.2f}</li>
                    <li>最終亮度：{final_brightness:.1f} / 255</li>
                    <li>最終光源面積：{final_area:.0f} pixels</li>
                    <li>曝光設定：{dataset['exposure_us']/1000:.1f}ms，增益 {dataset['gain_db']}dB</li>
                </ul>
            </div>
            """)
        
        return '\n'.join(conclusions)


def main():
    print("=" * 60)
    print("FLIR Camera 手電筒遠距離偵測能力分析")
    print("=" * 60)
    
    # 創建分析器
    analyzer = FlashlightAnalyzer(base_path=".")
    
    # 處理所有數據集
    all_data = analyzer.process_all_datasets()
    
    # 生成 HTML 報告
    output_file = analyzer.generate_html_report(all_data)
    
    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()
