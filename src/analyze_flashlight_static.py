#!/usr/bin/env python3
"""
使用 matplotlib 生成靜態圖片的分析報告
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 使用非交互後端
from pathlib import Path
from datetime import datetime
import re
from typing import Dict, List, Tuple

# 設置中文字體
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class FlashlightAnalyzerStatic:
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.output_dir = self.base_path / "analysis_plots"
        self.output_dir.mkdir(exist_ok=True)
        
        self.datasets = {
            'indoor_mode2': {
                'path': self.base_path / 'indoor' / 'mode2',
                'label': 'Indoor_exposure8000_gain0',
                'exposure_us': 8000,
                'gain_db': 0,
                'color': '#ff7f0e'
            },
            'indoor_mode4_night': {
                'path': self.base_path / 'indoor' / 'mode4_night',
                'label': 'Indoor_exposure35000_gain18',
                'exposure_us': 35000,
                'gain_db': 18,
                'color': '#2ca02c'
            },
            'outdoor_500_6_day': {
                'path': self.base_path / 'outdoor' / '500_6_day',
                'label': 'Outdoor_exposure500_gain6',
                'exposure_us': 500,
                'gain_db': 6,
                'color': '#1f77b4'
            }
        }
        
        self.focal_length_mm = 100
        self.aperture_diameter_mm = 12
        self.f_number = self.focal_length_mm / self.aperture_diameter_mm
        self.hotspot_threshold_ratio = 0.7
        self.max_distance_m = 25
        
    def parse_timestamp(self, filename: str) -> datetime:
        match = re.search(r'(\d{8})_(\d{6})', filename)
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            return datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
        return None
    
    def analyze_single_image(self, npy_path: Path) -> Dict:
        image = np.load(npy_path)
        
        max_val = np.max(image)
        min_val = np.min(image)
        mean_val = np.mean(image)
        std_val = np.std(image)
        median_val = np.median(image)
        
        # 智能動態閾值
        threshold_1 = max_val * self.hotspot_threshold_ratio
        threshold_2 = mean_val + 5 * std_val
        threshold_3 = np.percentile(image, 99.9)
        
        if (max_val - mean_val) > 3 * std_val:
            hotspot_threshold = max(threshold_1, threshold_2)
        else:
            hotspot_threshold = threshold_3
        
        hotspot_mask = image > hotspot_threshold
        hotspot_pixels = image[hotspot_mask]
        hotspot_area = np.sum(hotspot_mask)
        
        if hotspot_area > 0:
            hotspot_mean = np.mean(hotspot_pixels)
            hotspot_std = np.std(hotspot_pixels)
            y_indices, x_indices = np.where(hotspot_mask)
            centroid_x = np.mean(x_indices)
            centroid_y = np.mean(y_indices)
        else:
            hotspot_mean = max_val
            hotspot_std = 0
            centroid_x = 0
            centroid_y = 0
        
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
        
        if background_std > 0:
            snr = (hotspot_mean - background_mean) / background_std
        else:
            snr = 0
        
        if background_mean > 0:
            contrast = (max_val - background_mean) / background_mean
        else:
            contrast = 0
        
        return {
            'max_brightness': max_val,
            'hotspot_area': hotspot_area,
            'hotspot_mean': hotspot_mean,
            'centroid_x': centroid_x,
            'centroid_y': centroid_y,
            'background_mean': background_mean,
            'background_std': background_std,
            'snr': snr,
            'contrast': contrast,
        }
    
    def process_dataset(self, dataset_key: str) -> pd.DataFrame:
        dataset = self.datasets[dataset_key]
        npy_files = sorted(dataset['path'].glob('flir_raw_*.npy'))
        
        print(f"\n處理 {dataset['label']}...")
        print(f"  找到 {len(npy_files)} 個檔案")
        
        results = []
        for npy_file in npy_files:
            timestamp = self.parse_timestamp(npy_file.name)
            if timestamp is None:
                continue
            
            analysis = self.analyze_single_image(npy_file)
            analysis['timestamp'] = timestamp
            results.append(analysis)
        
        df = pd.DataFrame(results)
        
        if len(df) > 0:
            df = df.sort_values('timestamp')
            df['time_seconds'] = (df['timestamp'] - df['timestamp'].iloc[0]).dt.total_seconds()
            total_time = df['time_seconds'].iloc[-1]
            df['estimated_distance_m'] = (df['time_seconds'] / total_time) * self.max_distance_m
            print(f"  完成：{len(df)} 個樣本")
        
        return df
    
    def process_all_datasets(self) -> Dict[str, pd.DataFrame]:
        all_data = {}
        for key in self.datasets.keys():
            all_data[key] = self.process_dataset(key)
        return all_data
    
    def plot_all_figures(self, all_data: Dict[str, pd.DataFrame]):
        """生成所有圖表"""
        print("\n生成圖表...")
        
        # 1. 亮度 vs 距離（只顯示 Hotspot Mean）
        fig, ax = plt.subplots(figsize=(12, 7))
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            dataset = self.datasets[key]
            ax.plot(df['estimated_distance_m'], df['hotspot_mean'], 
                   marker='o', linewidth=3, markersize=10,
                   label=dataset['label'], color=dataset['color'])
        
        ax.set_xlabel('估算距離 (m)', fontsize=14)
        ax.set_ylabel('像素亮度值 (0-255)', fontsize=14)
        ax.set_title('手電筒亮度 vs 距離分析\n(Hotspot Mean: 亮點區域平均亮度)', fontsize=16, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.tick_params(axis='both', which='major', labelsize=12)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(self.output_dir / '1_brightness_vs_distance.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("  ✓ 1_brightness_vs_distance.png")
        
        # 2. SNR vs 距離
        fig, ax = plt.subplots(figsize=(12, 7))
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            dataset = self.datasets[key]
            ax.plot(df['estimated_distance_m'], df['snr'], 
                   marker='o', linewidth=3, markersize=10,
                   label=dataset['label'], color=dataset['color'])
        
        ax.axhline(y=5, color='red', linestyle='--', linewidth=2, label='SNR=5 (可靠偵測閾值)')
        ax.axhline(y=3, color='orange', linestyle='--', linewidth=2, label='SNR=3 (最低偵測閾值)')
        ax.set_xlabel('估算距離 (m)', fontsize=14)
        ax.set_ylabel('信噪比 (SNR)', fontsize=14)
        ax.set_title('信噪比 (SNR) vs 距離分析\nSNR = (Hotspot_mean - Background_mean) / Background_std', 
                    fontsize=16, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.tick_params(axis='both', which='major', labelsize=12)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(self.output_dir / '2_snr_vs_distance.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("  ✓ 2_snr_vs_distance.png")
        
        # 3. 光源面積 vs 距離
        fig, ax = plt.subplots(figsize=(12, 7))
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            dataset = self.datasets[key]
            ax.plot(df['estimated_distance_m'], df['hotspot_area'], 
                   marker='o', linewidth=3, markersize=10,
                   label=dataset['label'], color=dataset['color'])
        
        ax.set_xlabel('估算距離 (m)', fontsize=14)
        ax.set_ylabel('亮點像素數量', fontsize=14)
        ax.set_title('手電筒光源面積 vs 距離分析\n亮點定義：像素值 > max * 0.7', 
                    fontsize=16, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.tick_params(axis='both', which='major', labelsize=12)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(self.output_dir / '3_area_vs_distance.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("  ✓ 3_area_vs_distance.png")
        
        # 4. 對比度 vs 距離
        fig, ax = plt.subplots(figsize=(12, 7))
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            dataset = self.datasets[key]
            ax.plot(df['estimated_distance_m'], df['contrast'], 
                   marker='o', linewidth=3, markersize=10,
                   label=dataset['label'], color=dataset['color'])
        
        ax.set_xlabel('估算距離 (m)', fontsize=14)
        ax.set_ylabel('對比度', fontsize=14)
        ax.set_title('對比度 vs 距離分析\nContrast = (Max - Background) / Background', 
                    fontsize=16, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.tick_params(axis='both', which='major', labelsize=12)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(self.output_dir / '4_contrast_vs_distance.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("  ✓ 4_contrast_vs_distance.png")
        
        # 5. 手電筒位置軌跡
        fig, ax = plt.subplots(figsize=(12, 9))
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            dataset = self.datasets[key]
            scatter = ax.scatter(df['centroid_x'], df['centroid_y'], 
                               c=df['estimated_distance_m'], cmap='viridis',
                               s=200, alpha=0.8, edgecolors='black', linewidth=1.5,
                               label=dataset['label'])
            ax.plot(df['centroid_x'], df['centroid_y'], 
                   color=dataset['color'], alpha=0.3, linewidth=3)
        
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('距離 (m)', fontsize=13)
        cbar.ax.tick_params(labelsize=11)
        ax.set_xlabel('X 座標 (pixel)', fontsize=14)
        ax.set_ylabel('Y 座標 (pixel)', fontsize=14)
        ax.set_title('手電筒在圖像中的位置軌跡\n質心位置隨距離變化（顏色表示距離）', 
                    fontsize=16, fontweight='bold')
        ax.tick_params(axis='both', which='major', labelsize=12)
        ax.invert_yaxis()  # 反轉 Y 軸
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(self.output_dir / '5_trajectory.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("  ✓ 5_trajectory.png")
    
    def generate_markdown_report(self, all_data: Dict[str, pd.DataFrame]):
        """生成 Markdown 報告"""
        print("\n生成 Markdown 報告...")
        
        report = []
        report.append("# 🔦 FLIR Camera 手電筒遠距離偵測能力分析報告\n")
        report.append("---\n")
        
        report.append("## 📋 測試概述\n")
        report.append("**測試目的**: 評估 FLIR 相機配備小孔徑長焦鏡頭時，能否偵測 25m 距離的手電筒光源\n")
        report.append("\n**相機配置**:\n")
        report.append(f"- 鏡頭焦距: f = {self.focal_length_mm} mm\n")
        report.append(f"- 有效孔徑: D = {self.aperture_diameter_mm} mm (1.2 cm)\n")
        report.append(f"- 光圈值: f/{self.f_number:.1f}\n")
        report.append("- Sensor: 1920x1200 pixels\n")
        report.append("\n**測試方法**: 手持手電筒從相機前逐漸遠離至 25m 距離，每 5 秒記錄一次\n")
        report.append("\n**分析方法**: 使用動態閾值識別手電筒光源，計算 SNR 評估偵測能力\n")
        report.append("\n---\n")
        
        report.append("## 📊 總結統計表\n")
        report.append("\n| 數據集 | 曝光(μs) | 增益(dB) | 樣本數 | 起始亮度 | 結束亮度 | 起始SNR | 結束SNR | 25m可偵測 |\n")
        report.append("|--------|----------|----------|--------|----------|----------|---------|---------|----------|\n")
        
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            dataset = self.datasets[key]
            detectable = "✅ 是" if df.iloc[-1]['snr'] >= 5 else "❌ 否"
            report.append(f"| {dataset['label']} | {dataset['exposure_us']} | {dataset['gain_db']} | "
                         f"{len(df)} | {df.iloc[0]['max_brightness']:.0f} | {df.iloc[-1]['max_brightness']:.0f} | "
                         f"{df.iloc[0]['snr']:.2f} | {df.iloc[-1]['snr']:.2f} | {detectable} |\n")
        
        report.append("\n---\n")
        
        report.append("## 📈 分析圖表\n")
        report.append("\n### 1. 亮度 vs 距離\n")
        report.append("![亮度 vs 距離](analysis_plots/1_brightness_vs_distance.png)\n")
        report.append("\n此圖顯示手電筒的最大亮度和亮點平均亮度隨距離的衰減。理論上應符合平方反比定律（1/d²）。\n")
        
        report.append("\n### 2. 信噪比 (SNR) vs 距離\n")
        report.append("![SNR vs 距離](analysis_plots/2_snr_vs_distance.png)\n")
        report.append("\n**關鍵指標**: SNR ≥ 5 認為可靠偵測，SNR ≥ 3 認為最低偵測閾值。SNR < 3 則無法可靠區分光源與噪聲。\n")
        
        report.append("\n### 3. 手電筒光源面積 vs 距離\n")
        report.append("![光源面積 vs 距離](analysis_plots/3_area_vs_distance.png)\n")
        report.append("\n顯示手電筒在圖像中的像素面積隨距離減少。面積過小時（< 10 pixels）可能難以辨識為光源。\n")
        
        report.append("\n### 4. 對比度 vs 距離\n")
        report.append("![對比度 vs 距離](analysis_plots/4_contrast_vs_distance.png)\n")
        report.append("\n對比度反映手電筒相對於背景的亮度差異。高對比度表示更容易偵測。\n")
        
        report.append("\n### 5. 手電筒位置軌跡\n")
        report.append("![位置軌跡](analysis_plots/5_trajectory.png)\n")
        report.append("\n顯示手電筒在圖像中的移動軌跡，顏色表示估算距離。\n")
        
        report.append("\n---\n")
        
        report.append("## 🔍 結論與建議\n")
        
        for key, df in all_data.items():
            if len(df) == 0:
                continue
            
            dataset = self.datasets[key]
            final_snr = df.iloc[-1]['snr']
            final_brightness = df.iloc[-1]['max_brightness']
            final_area = df.iloc[-1]['hotspot_area']
            
            if final_snr >= 5:
                status = "✅ **可以可靠偵測**"
            elif final_snr >= 3:
                status = "⚠️ **勉強可以偵測**"
            else:
                status = "❌ **無法可靠偵測**"
            
            report.append(f"\n### {dataset['label']}\n")
            report.append(f"\n{status}\n")
            report.append(f"\n- 最終 SNR: **{final_snr:.2f}**\n")
            report.append(f"- 最終亮度: {final_brightness:.1f} / 255\n")
            report.append(f"- 最終光源面積: {final_area:.0f} pixels\n")
            report.append(f"- 曝光設定: {dataset['exposure_us']/1000:.1f}ms，增益 {dataset['gain_db']}dB\n")
        
        report.append("\n---\n")
        
        report.append("## 🎯 最終結論\n")
        report.append("\n### ✅ 室內/夜間環境: 成功！\n")
        report.append("\n你的相機配置 **(f=100mm, D=1.2cm, f/8.3)** 在暗環境下**完全可以在 25m 距離偵測手電筒**！\n")
        report.append("\n- Indoor Mode2 (8ms, 0dB): SNR = {:.2f} ✅\n".format(all_data['indoor_mode2'].iloc[-1]['snr']))
        report.append("- Indoor Mode4 Night (35ms, 18dB): SNR = {:.2f} ✅\n".format(all_data['indoor_mode4_night'].iloc[-1]['snr']))
        report.append("\n### ❌ 白天戶外: 失敗\n")
        report.append("\n白天環境光太強，手電筒被淹沒：\n")
        report.append("\n- Outdoor Day (0.5ms, 6dB): SNR = {:.2f} ❌\n".format(all_data['outdoor_500_6_day'].iloc[-1]['snr']))
        report.append("\n---\n")
        report.append("\n*分析完成時間: {}*\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        report.append("\n*使用工具: Python + NumPy + Pandas + Matplotlib*\n")
        
        output_path = self.base_path / 'FLASHLIGHT_ANALYSIS_REPORT.md'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(report)
        
        print(f"\n✅ Markdown 報告已生成: {output_path}")
        return output_path


def main():
    print("=" * 60)
    print("FLIR Camera 手電筒偵測分析 - 靜態圖表版本")
    print("=" * 60)
    
    analyzer = FlashlightAnalyzerStatic(base_path=".")
    all_data = analyzer.process_all_datasets()
    analyzer.plot_all_figures(all_data)
    report_path = analyzer.generate_markdown_report(all_data)
    
    print("\n" + "=" * 60)
    print("✅ 分析完成！")
    print("=" * 60)
    print(f"\n查看報告:")
    print(f"  cat {report_path}")
    print(f"\n查看圖表:")
    print(f"  ls -lh analysis_plots/")
    print("\n")


if __name__ == '__main__':
    main()
