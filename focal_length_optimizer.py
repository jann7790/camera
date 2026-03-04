#!/usr/bin/env python3
"""
FSO 系統焦距優化分析工具

目的：在 galvo mirror (D=1.2cm) 限制下，計算最大可用的 focal length
使得在 30m 距離仍能偵測 LED marker (SNR ≥ 5)

作者：OpenCode
日期：2026-02-06
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import glob
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 系統參數定義
# ============================================================

@dataclass
class CameraParams:
    """FLIR Grasshopper3 GS3-U3-23S6C 參數"""
    name: str = "FLIR Grasshopper3 GS3-U3-23S6C"
    resolution_h: int = 1920  # pixels
    resolution_v: int = 1200  # pixels
    sensor_type: str = "Sony IMX174"
    sensor_format: str = "1/1.2 inch"
    sensor_width_mm: float = 8.867  # mm
    sensor_height_mm: float = 6.604  # mm
    sensor_diagonal_mm: float = 11.0  # mm
    pixel_size_um: float = 5.86  # μm
    is_color: bool = True  # Bayer filter
    max_exposure_ms: float = 100.0  # 最大曝光
    max_gain_db: float = 24.0  # 最大增益

@dataclass
class OpticalParams:
    """光學系統參數"""
    galvo_diameter_mm: float = 12.0  # Galvo mirror 直徑
    current_focal_length_mm: float = 100.0  # 目前測試的焦距
    
    def f_number(self, focal_length_mm: float) -> float:
        """計算 f-number"""
        return focal_length_mm / self.galvo_diameter_mm
    
    def relative_brightness(self, focal_length_mm: float) -> float:
        """相對於 100mm 的亮度比例"""
        f_num_current = self.f_number(self.current_focal_length_mm)
        f_num_new = self.f_number(focal_length_mm)
        return (f_num_current / f_num_new) ** 2

@dataclass
class ApplicationParams:
    """應用場景參數"""
    target_distance_m: float = 30.0  # 目標距離
    marker_size_m: float = 0.20  # CCTag 尺寸 (20cm)
    marker_type: str = "LED array"
    min_snr_reliable: float = 5.0  # 可靠偵測閾值
    min_snr_minimum: float = 3.0  # 最低偵測閾值
    use_filter: bool = False  # 是否使用窄帶濾光片

# ============================================================
# 數據讀取與分析
# ============================================================

class FlashLightDataAnalyzer:
    """分析手電筒測試數據"""
    
    def __init__(self):
        self.camera = CameraParams()
        self.optics = OpticalParams()
        self.datasets = {
            'indoor_mode2': {
                'path': './indoor/mode2',
                'label': 'Indoor_exposure8000_gain0',
                'exposure_us': 8000,
                'gain_db': 0,
                'color': '#2E86AB'
            },
            'indoor_mode4_night': {
                'path': './indoor/mode4_night',
                'label': 'Indoor_exposure35000_gain18',
                'exposure_us': 35000,
                'gain_db': 18,
                'color': '#A23B72'
            },
            'outdoor_500_6_day': {
                'path': './outdoor/500_6_day',
                'label': 'Outdoor_exposure500_gain6',
                'exposure_us': 500,
                'gain_db': 6,
                'color': '#F18F01'
            }
        }
        self.results = {}
    
    def load_all_data(self) -> pd.DataFrame:
        """讀取所有測試數據"""
        all_data = []
        
        for ds_name, ds_info in self.datasets.items():
            print(f"讀取 {ds_info['label']}...")
            
            # 找到所有 raw npy 文件
            pattern = Path(ds_info['path']) / 'flir_raw_*.npy'
            files = sorted(glob.glob(str(pattern)))
            
            if not files:
                print(f"  ⚠️  找不到檔案: {pattern}")
                continue
            
            # 從檔名提取時間戳記
            timestamps = []
            for f in files:
                match = re.search(r'flir_raw_(\d{8}_\d{6})', f)
                if match:
                    timestamps.append(match.group(1))
            
            # 假設第一個檔案是 t=0，最後一個是 t=80-96 秒
            # 線性插值計算距離
            n_samples = len(files)
            
            # 讀取第一個檔案的時間資訊來估算總時長
            # 簡化：假設均勻分布在 80-96 秒範圍
            total_duration_s = 85  # 中間值
            
            for idx, (file_path, ts) in enumerate(zip(files, timestamps)):
                # 估算距離 (0m -> 25m)
                progress = idx / max(n_samples - 1, 1)
                estimated_distance = 25.0 * progress
                
                # 讀取圖像
                img = np.load(file_path)
                
                # 計算手電筒的信號和噪聲
                metrics = self._analyze_image(img)
                
                all_data.append({
                    'dataset': ds_name,
                    'label': ds_info['label'],
                    'exposure_us': ds_info['exposure_us'],
                    'exposure_ms': ds_info['exposure_us'] / 1000,
                    'gain_db': ds_info['gain_db'],
                    'timestamp': ts,
                    'sample_idx': idx,
                    'estimated_distance_m': estimated_distance,
                    **metrics
                })
            
            print(f"  ✓ 完成：{len(files)} 個樣本")
        
        df = pd.DataFrame(all_data)
        self.results['raw_data'] = df
        return df
    
    def _analyze_image(self, img: np.ndarray) -> Dict:
        """分析單張圖像，計算 signal, noise, SNR"""
        
        # 計算動態閾值
        img_mean = np.mean(img)
        img_std = np.std(img)
        img_max = np.max(img)
        
        # 使用與 analyze_flashlight_static.py 相同的方法
        contrast = (img_max - img_mean) / max(img_mean, 1)
        
        if contrast > 5:  # 高對比度
            threshold = max(img_max * 0.7, img_mean + 5 * img_std)
        else:  # 低對比度
            threshold = np.percentile(img, 99.9)
        
        # 識別手電筒區域
        hotspot_mask = img > threshold
        hotspot_pixels = img[hotspot_mask]
        background_pixels = img[~hotspot_mask]
        
        # 計算指標
        if len(hotspot_pixels) > 0:
            signal_max = np.max(hotspot_pixels)
            signal_mean = np.mean(hotspot_pixels)
            hotspot_area = len(hotspot_pixels)
        else:
            signal_max = img_max
            signal_mean = img_max
            hotspot_area = 1
        
        if len(background_pixels) > 0:
            background_mean = np.mean(background_pixels)
            background_std = np.std(background_pixels)
        else:
            background_mean = img_mean
            background_std = max(img_std, 1)
        
        # 計算 SNR
        if background_std > 0:
            snr = (signal_mean - background_mean) / background_std
        else:
            snr = 0
        
        # 計算對比度
        if background_mean > 0:
            contrast_ratio = (signal_max - background_mean) / background_mean
        else:
            contrast_ratio = 0
        
        return {
            'signal_max': float(signal_max),
            'signal_mean': float(signal_mean),
            'hotspot_area_pixels': int(hotspot_area),
            'background_mean': float(background_mean),
            'background_std': float(background_std),
            'snr': float(snr),
            'contrast': float(contrast_ratio),
            'threshold': float(threshold)
        }
    
    def calibrate_snr_model(self, df: pd.DataFrame) -> Dict:
        """校準 SNR 模型參數
        
        目標：建立 SNR = f(distance, exposure, gain) 的模型
        """
        print("\n校準 SNR 模型...")
        
        model_params = {}
        
        for ds_name in df['dataset'].unique():
            ds_data = df[df['dataset'] == ds_name].copy()
            ds_data = ds_data.sort_values('estimated_distance_m')
            
            # 提取參數
            exposure_ms = ds_data['exposure_ms'].iloc[0]
            gain_db = ds_data['gain_db'].iloc[0]
            
            # 擬合 SNR vs distance 的關係
            # 理論上 signal ∝ 1/d²，但 SNR 的關係更複雜
            
            distances = ds_data['estimated_distance_m'].values
            snrs = ds_data['snr'].values
            signals = ds_data['signal_mean'].values
            bg_stds = ds_data['background_std'].values
            
            # 過濾距離為0的點（會導致除以零）
            valid_mask = distances > 0.5
            distances = distances[valid_mask]
            snrs = snrs[valid_mask]
            signals = signals[valid_mask]
            bg_stds = bg_stds[valid_mask]
            
            if len(distances) < 3:
                continue
            
            # 計算平均背景噪聲水平（這個應該相對穩定）
            median_bg_std = np.median(bg_stds)
            
            # 在對數空間擬合 signal vs distance
            # log(signal) = log(k) - 2*log(d)
            # signal = k / d²
            
            try:
                # 過濾掉 signal 為 0 或負數的點
                pos_mask = signals > 0
                if np.sum(pos_mask) < 3:
                    continue
                    
                log_d = np.log(distances[pos_mask])
                log_s = np.log(signals[pos_mask])
                
                # 線性回歸
                coeffs = np.polyfit(log_d, log_s, 1)
                slope = coeffs[0]
                intercept = coeffs[1]
                
                # k = exp(intercept), 理論上 slope 應該接近 -2
                k_signal = np.exp(intercept)
                
                model_params[ds_name] = {
                    'exposure_ms': exposure_ms,
                    'gain_db': gain_db,
                    'k_signal': k_signal,
                    'distance_exponent': slope,
                    'background_std': median_bg_std,
                    'exposure_gain_factor': exposure_ms * (10 ** (gain_db / 20))
                }
                
                print(f"  {ds_name}:")
                print(f"    信號常數 k = {k_signal:.2f}")
                print(f"    距離指數 = {slope:.2f} (理論值 -2)")
                print(f"    背景噪聲 σ = {median_bg_std:.2f}")
                
            except Exception as e:
                print(f"  ⚠️  {ds_name} 擬合失敗: {e}")
                continue
        
        self.results['snr_model'] = model_params
        return model_params

# ============================================================
# 焦距優化分析
# ============================================================

class FocalLengthOptimizer:
    """焦距優化器"""
    
    def __init__(self, camera: CameraParams, optics: OpticalParams, 
                 app: ApplicationParams, snr_model: Dict):
        self.camera = camera
        self.optics = optics
        self.app = app
        self.snr_model = snr_model
        
    def calculate_fov(self, focal_length_mm: float, distance_m: float) -> Tuple[float, float]:
        """計算 Field of View (m)"""
        fov_h = self.camera.sensor_width_mm / focal_length_mm * distance_m
        fov_v = self.camera.sensor_height_mm / focal_length_mm * distance_m
        return fov_h, fov_v
    
    def calculate_marker_projection(self, focal_length_mm: float, 
                                    distance_m: float, marker_size_m: float) -> Tuple[float, int]:
        """計算 marker 在 sensor 上的投影大小（mm 和 pixels）"""
        projection_mm = marker_size_m * focal_length_mm / distance_m
        projection_pixels = projection_mm / (self.camera.pixel_size_um / 1000)
        return projection_mm, int(projection_pixels)
    
    def estimate_snr_at_focal_length(self, focal_length_mm: float, 
                                     distance_m: float,
                                     reference_dataset: str = 'indoor_mode2') -> Dict:
        """估算在給定 focal length 和距離下的 SNR
        
        策略：
        1. 從參考數據集（indoor_mode2: 8ms, 0dB）開始
        2. 計算 focal length 改變導致的亮度變化
        3. 計算距離改變導致的信號衰減
        4. 計算可用的曝光/增益補償
        5. 估算最終 SNR
        """
        
        if reference_dataset not in self.snr_model:
            return {'error': 'Reference dataset not found in model'}
        
        ref = self.snr_model[reference_dataset]
        
        # 1. Focal length 導致的亮度變化
        brightness_ratio = self.optics.relative_brightness(focal_length_mm)
        
        # 2. 距離導致的信號衰減
        # 參考數據是在 25m 距離
        ref_distance = 25.0
        distance_ratio = (ref_distance / distance_m) ** 2
        
        # 3. 總的信號衰減
        total_signal_reduction = brightness_ratio * distance_ratio
        
        # 4. 計算需要的補償
        # 參考設定：8ms, 0dB
        ref_exposure_ms = ref['exposure_ms']
        ref_gain_db = ref['gain_db']
        
        # 可用的補償範圍
        max_exposure_gain = self.camera.max_exposure_ms * (10 ** (self.camera.max_gain_db / 20))
        ref_exposure_gain = ref_exposure_ms * (10 ** (ref_gain_db / 20))
        available_compensation = max_exposure_gain / ref_exposure_gain
        
        # 5. 實際補償後的信號水平
        # 先嘗試用曝光補償（不增加噪聲）
        needed_compensation = 1.0 / total_signal_reduction
        
        if needed_compensation <= available_compensation:
            # 可以補償
            # 優先使用曝光
            exposure_compensation = min(needed_compensation, 
                                       self.camera.max_exposure_ms / ref_exposure_ms)
            remaining_needed = needed_compensation / exposure_compensation
            
            # 剩餘用增益
            if remaining_needed > 1:
                gain_compensation_db = 20 * np.log10(remaining_needed)
                gain_compensation_db = min(gain_compensation_db, 
                                          self.camera.max_gain_db - ref_gain_db)
            else:
                gain_compensation_db = 0
            
            final_exposure_ms = ref_exposure_ms * exposure_compensation
            final_gain_db = ref_gain_db + gain_compensation_db
            
            # 計算補償後的信號水平（相對於參考）
            actual_compensation = exposure_compensation * (10 ** (gain_compensation_db / 20))
            compensated_signal_ratio = total_signal_reduction * actual_compensation
            
        else:
            # 無法完全補償，用到最大值
            final_exposure_ms = self.camera.max_exposure_ms
            final_gain_db = self.camera.max_gain_db
            exposure_compensation = final_exposure_ms / ref_exposure_ms
            gain_compensation_db = final_gain_db - ref_gain_db
            actual_compensation = available_compensation
            compensated_signal_ratio = total_signal_reduction * actual_compensation
        
        # 6. 估算 SNR
        # 從參考數據集的 25m SNR 開始
        # 假設參考 SNR（基於報告，indoor_mode2 在 25m 的 SNR = 39.49）
        ref_snr_at_25m = 39.49
        
        # Signal 的變化
        signal_ratio = compensated_signal_ratio
        
        # Noise 的變化：
        # - Shot noise ∝ sqrt(signal)
        # - Read noise 被曝光 dilute，但被增益放大
        # - 簡化模型：noise ∝ sqrt(signal) × 10^(gain/20) / sqrt(exposure)
        
        # 相對於參考的噪聲變化
        exposure_ratio = final_exposure_ms / ref_exposure_ms
        gain_ratio = 10 ** ((final_gain_db - ref_gain_db) / 20)
        
        # 總噪聲比例（粗略估算）
        # Shot noise 部分
        shot_noise_ratio = np.sqrt(signal_ratio)
        # Read noise 部分（假設佔總噪聲的 30%）
        read_noise_contribution = 0.3
        shot_noise_contribution = 0.7
        
        effective_noise_ratio = (
            shot_noise_contribution * shot_noise_ratio * gain_ratio / np.sqrt(exposure_ratio) +
            read_noise_contribution * gain_ratio / np.sqrt(exposure_ratio)
        )
        
        # SNR = signal / noise
        estimated_snr = ref_snr_at_25m * (signal_ratio / effective_noise_ratio)
        
        # 檢查是否可偵測
        if estimated_snr >= self.app.min_snr_reliable:
            detection_status = "✅ 可靠偵測"
        elif estimated_snr >= self.app.min_snr_minimum:
            detection_status = "⚠️  勉強可行"
        else:
            detection_status = "❌ 無法偵測"
        
        return {
            'focal_length_mm': focal_length_mm,
            'f_number': self.optics.f_number(focal_length_mm),
            'distance_m': distance_m,
            'brightness_ratio': brightness_ratio,
            'distance_ratio': distance_ratio,
            'total_signal_reduction': total_signal_reduction,
            'needed_compensation': needed_compensation,
            'available_compensation': available_compensation,
            'can_compensate': needed_compensation <= available_compensation,
            'final_exposure_ms': final_exposure_ms,
            'final_gain_db': final_gain_db,
            'signal_ratio': signal_ratio,
            'noise_ratio': effective_noise_ratio,
            'estimated_snr': estimated_snr,
            'detection_status': detection_status,
            'is_reliable': estimated_snr >= self.app.min_snr_reliable,
            'is_detectable': estimated_snr >= self.app.min_snr_minimum
        }
    
    def scan_focal_lengths(self, focal_range_mm: List[float], 
                          distance_m: float) -> pd.DataFrame:
        """掃描一系列 focal length"""
        results = []
        
        for f in focal_range_mm:
            # SNR 估算
            snr_result = self.estimate_snr_at_focal_length(f, distance_m)
            
            # FOV 計算
            fov_h, fov_v = self.calculate_fov(f, distance_m)
            
            # Marker 投影大小
            proj_mm, proj_pixels = self.calculate_marker_projection(
                f, distance_m, self.app.marker_size_m
            )
            
            results.append({
                **snr_result,
                'fov_horizontal_m': fov_h,
                'fov_vertical_m': fov_v,
                'marker_projection_mm': proj_mm,
                'marker_projection_pixels': proj_pixels
            })
        
        return pd.DataFrame(results)

# ============================================================
# 可視化
# ============================================================

def plot_optimization_results(df_scan: pd.DataFrame, app: ApplicationParams, 
                              camera: CameraParams, output_dir: str = 'focal_analysis'):
    """繪製優化結果"""
    
    Path(output_dir).mkdir(exist_ok=True)
    
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'DejaVu Sans', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.dpi'] = 150
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle(f'焦距優化分析 - {app.target_distance_m}m 距離', 
                 fontsize=16, fontweight='bold')
    
    focal_lengths = df_scan['focal_length_mm'].values
    
    # 1. SNR vs Focal Length
    ax = axes[0, 0]
    ax.plot(focal_lengths, df_scan['estimated_snr'], 'o-', linewidth=2, markersize=6)
    ax.axhline(app.min_snr_reliable, color='green', linestyle='--', 
               label=f'可靠偵測閾值 (SNR≥{app.min_snr_reliable})')
    ax.axhline(app.min_snr_minimum, color='orange', linestyle='--',
               label=f'最低閾值 (SNR≥{app.min_snr_minimum})')
    ax.fill_between(focal_lengths, app.min_snr_reliable, 100, alpha=0.2, color='green')
    ax.fill_between(focal_lengths, app.min_snr_minimum, app.min_snr_reliable, 
                    alpha=0.2, color='yellow')
    ax.set_xlabel('Focal Length (mm)', fontsize=11, fontweight='bold')
    ax.set_ylabel('估算 SNR', fontsize=11, fontweight='bold')
    ax.set_title('SNR vs Focal Length', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_yscale('log')
    
    # 2. F-number vs Focal Length
    ax = axes[0, 1]
    ax.plot(focal_lengths, df_scan['f_number'], 'o-', color='#E63946', 
            linewidth=2, markersize=6)
    ax.set_xlabel('Focal Length (mm)', fontsize=11, fontweight='bold')
    ax.set_ylabel('F-number (f/#)', fontsize=11, fontweight='bold')
    ax.set_title('F-number vs Focal Length\n(Galvo Ø=1.2cm)', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # 3. Field of View vs Focal Length
    ax = axes[0, 2]
    ax.plot(focal_lengths, df_scan['fov_horizontal_m'], 'o-', 
            label='Horizontal FOV', linewidth=2, markersize=6)
    ax.plot(focal_lengths, df_scan['fov_vertical_m'], 's-', 
            label='Vertical FOV', linewidth=2, markersize=6)
    ax.set_xlabel('Focal Length (mm)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Field of View (m)', fontsize=11, fontweight='bold')
    ax.set_title(f'FOV vs Focal Length\n(at {app.target_distance_m}m)', 
                 fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # 4. Marker 投影大小 vs Focal Length
    ax = axes[1, 0]
    ax.plot(focal_lengths, df_scan['marker_projection_pixels'], 'o-', 
            color='#06A77D', linewidth=2, markersize=6)
    ax.axhline(10, color='red', linestyle='--', alpha=0.7, 
               label='最小可辨識 (~10 pixels)')
    ax.set_xlabel('Focal Length (mm)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Marker 投影大小 (pixels)', fontsize=11, fontweight='bold')
    ax.set_title(f'Marker Size vs Focal Length\n({app.marker_size_m*100}cm marker at {app.target_distance_m}m)', 
                 fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # 5. 曝光/增益需求 vs Focal Length
    ax = axes[1, 1]
    ax2 = ax.twinx()
    l1 = ax.plot(focal_lengths, df_scan['final_exposure_ms'], 'o-', 
                 color='#F77F00', label='需要曝光', linewidth=2, markersize=6)
    l2 = ax2.plot(focal_lengths, df_scan['final_gain_db'], 's-', 
                  color='#9D4EDD', label='需要增益', linewidth=2, markersize=6)
    ax.axhline(camera.max_exposure_ms, color='#F77F00', linestyle='--', alpha=0.5)
    ax2.axhline(camera.max_gain_db, color='#9D4EDD', linestyle='--', alpha=0.5)
    ax.set_xlabel('Focal Length (mm)', fontsize=11, fontweight='bold')
    ax.set_ylabel('曝光時間 (ms)', fontsize=11, fontweight='bold', color='#F77F00')
    ax2.set_ylabel('增益 (dB)', fontsize=11, fontweight='bold', color='#9D4EDD')
    ax.set_title('相機設定需求 vs Focal Length', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    lines = l1 + l2
    labels = [l.get_label() for l in lines]
    ax.legend(lines, labels, loc='upper left')
    
    # 6. 可行性總結
    ax = axes[1, 2]
    ax.axis('off')
    
    # 找出可行的 focal length 範圍
    reliable = df_scan[df_scan['is_reliable']]
    detectable = df_scan[df_scan['is_detectable']]
    
    if len(reliable) > 0:
        f_max_reliable = reliable['focal_length_mm'].max()
        f_min_reliable = reliable['focal_length_mm'].min()
    else:
        f_max_reliable = None
        f_min_reliable = None
    
    if len(detectable) > 0:
        f_max_detectable = detectable['focal_length_mm'].max()
    else:
        f_max_detectable = None
    
    summary_text = f"""
    可行性分析總結
    ━━━━━━━━━━━━━━━━━━━━━
    
    目標距離: {app.target_distance_m}m
    Marker 尺寸: {app.marker_size_m*100}cm × {app.marker_size_m*100}cm
    相機限制: ≤{camera.max_exposure_ms}ms, ≤{camera.max_gain_db}dB
    
    ━━━━━━━━━━━━━━━━━━━━━
    ✅ 可靠偵測 (SNR≥{app.min_snr_reliable})
    """
    
    if f_max_reliable is not None:
        summary_text += f"""
    Focal length: {f_min_reliable:.0f} - {f_max_reliable:.0f} mm
    推薦使用: {f_max_reliable*0.8:.0f} mm (80% 裕度)
    """
    else:
        summary_text += "\n    ❌ 無可靠範圍\n"
    
    summary_text += f"""
    ━━━━━━━━━━━━━━━━━━━━━
    ⚠️  勉強可行 (SNR≥{app.min_snr_minimum})
    """
    
    if f_max_detectable is not None and f_max_detectable > (f_max_reliable or 0):
        summary_text += f"""
    最大 focal length: {f_max_detectable:.0f} mm
    (可能出現偶爾漏檢)
    """
    else:
        summary_text += "\n    無額外範圍\n"
    
    ax.text(0.1, 0.95, summary_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    output_path = Path(output_dir) / 'focal_length_optimization.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 圖表已保存: {output_path}")
    
    return output_path

# ============================================================
# 主程序
# ============================================================

def main():
    print("=" * 60)
    print("FSO 系統焦距優化分析")
    print("=" * 60)
    
    # 初始化參數
    camera = CameraParams()
    optics = OpticalParams()
    app = ApplicationParams()
    
    print(f"\n相機: {camera.name}")
    print(f"  Sensor: {camera.sensor_width_mm:.2f} × {camera.sensor_height_mm:.2f} mm")
    print(f"  解析度: {camera.resolution_h} × {camera.resolution_v} pixels")
    print(f"  像素尺寸: {camera.pixel_size_um:.2f} μm")
    
    print(f"\n光學系統:")
    print(f"  Galvo mirror 直徑: {optics.galvo_diameter_mm:.1f} mm")
    print(f"  當前測試焦距: {optics.current_focal_length_mm:.1f} mm (f/{optics.f_number(100):.1f})")
    
    print(f"\n應用需求:")
    print(f"  目標距離: {app.target_distance_m} m")
    print(f"  Marker 尺寸: {app.marker_size_m*100:.0f} cm")
    print(f"  最低 SNR: {app.min_snr_minimum} (可偵測), {app.min_snr_reliable} (可靠)")
    
    # 步驟 1: 讀取並分析測試數據
    print("\n" + "=" * 60)
    print("步驟 1: 讀取測試數據")
    print("=" * 60)
    
    analyzer = FlashLightDataAnalyzer()
    df_raw = analyzer.load_all_data()
    
    # 步驟 2: 校準 SNR 模型
    print("\n" + "=" * 60)
    print("步驟 2: 校準 SNR 模型")
    print("=" * 60)
    
    snr_model = analyzer.calibrate_snr_model(df_raw)
    
    # 步驟 3: 焦距優化分析
    print("\n" + "=" * 60)
    print("步驟 3: 焦距優化分析")
    print("=" * 60)
    
    optimizer = FocalLengthOptimizer(camera, optics, app, snr_model)
    
    # 掃描 focal length 範圍
    focal_range = np.array([35, 50, 75, 100, 135, 150, 200, 250, 300, 400, 500])
    print(f"\n掃描 focal length: {focal_range[0]} - {focal_range[-1]} mm")
    
    df_scan = optimizer.scan_focal_lengths(focal_range, app.target_distance_m)
    
    # 顯示結果
    print("\n結果摘要:")
    print("-" * 80)
    for _, row in df_scan.iterrows():
        print(f"f={row['focal_length_mm']:3.0f}mm (f/{row['f_number']:4.1f}) | "
              f"SNR={row['estimated_snr']:6.2f} | "
              f"FOV={row['fov_horizontal_m']:4.1f}×{row['fov_vertical_m']:4.1f}m | "
              f"Marker={row['marker_projection_pixels']:3.0f}px | "
              f"{row['detection_status']}")
    
    # 步驟 4: 生成可視化
    print("\n" + "=" * 60)
    print("步驟 4: 生成可視化圖表")
    print("=" * 60)
    
    plot_path = plot_optimization_results(df_scan, app, camera)
    
    # 保存數據
    output_csv = 'focal_analysis/focal_length_scan_results.csv'
    df_scan.to_csv(output_csv, index=False)
    print(f"✓ 數據已保存: {output_csv}")
    
    # 最終建議
    print("\n" + "=" * 60)
    print("最終建議")
    print("=" * 60)
    
    reliable = df_scan[df_scan['is_reliable']]
    detectable = df_scan[df_scan['is_detectable']]
    
    if len(reliable) > 0:
        f_max = reliable['focal_length_mm'].max()
        f_recommended = f_max * 0.8
        
        rec_row = df_scan[df_scan['focal_length_mm'] <= f_recommended].iloc[-1]
        
        print(f"\n✅ 推薦 focal length: {f_recommended:.0f} mm")
        print(f"   (最大可用 {f_max:.0f} mm 的 80%，保留裕度)")
        print(f"\n   預估性能:")
        print(f"   • SNR: {rec_row['estimated_snr']:.1f}")
        print(f"   • FOV: {rec_row['fov_horizontal_m']:.1f} × {rec_row['fov_vertical_m']:.1f} m")
        print(f"   • Marker 投影: {rec_row['marker_projection_pixels']:.0f} pixels")
        print(f"   • 需要曝光: {rec_row['final_exposure_ms']:.1f} ms")
        print(f"   • 需要增益: {rec_row['final_gain_db']:.1f} dB")
        
    else:
        print("\n❌ 警告：在當前配置下無法達到可靠偵測！")
        print("\n建議:")
        print("  1. 使用更大的 galvo mirror (當前 1.2cm)")
        print("  2. 使用更強的 LED (當前假設等同手電筒)")
        print("  3. 在室外使用時加裝 850nm 窄帶濾光片")
    
    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)

if __name__ == '__main__':
    main()
