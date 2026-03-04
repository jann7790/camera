#!/usr/bin/env python3
"""
快速打印分析摘要
"""
import numpy as np
from pathlib import Path
from analyze_flashlight_test import FlashlightAnalyzer

def print_summary():
    analyzer = FlashlightAnalyzer(base_path=".")
    all_data = analyzer.process_all_datasets()
    
    print("\n" + "=" * 70)
    print("📊 手電筒偵測能力分析 - 快速摘要")
    print("=" * 70)
    
    for key, df in all_data.items():
        if len(df) == 0:
            continue
        
        dataset = analyzer.datasets[key]
        print(f"\n【{dataset['label']}】")
        print(f"  曝光: {dataset['exposure_us']/1000:.1f}ms, 增益: {dataset['gain_db']}dB")
        print(f"  樣本數: {len(df)}")
        print(f"  時間跨度: {df['time_seconds'].iloc[-1]:.1f}秒")
        
        # 起始點數據
        print(f"\n  起始點 (0m):")
        print(f"    最大亮度: {df.iloc[0]['max_brightness']:.1f}")
        print(f"    亮點面積: {df.iloc[0]['hotspot_area']:.0f} pixels")
        print(f"    SNR: {df.iloc[0]['snr']:.2f}")
        print(f"    對比度: {df.iloc[0]['contrast']:.2f}")
        
        # 終點數據
        print(f"\n  終點 (~25m):")
        print(f"    最大亮度: {df.iloc[-1]['max_brightness']:.1f}")
        print(f"    亮點面積: {df.iloc[-1]['hotspot_area']:.0f} pixels")
        print(f"    SNR: {df.iloc[-1]['snr']:.2f}")
        print(f"    對比度: {df.iloc[-1]['contrast']:.2f}")
        
        # 偵測能力判斷
        final_snr = df.iloc[-1]['snr']
        if final_snr >= 5:
            status = "✅ 可以可靠偵測"
            color = "\033[92m"  # Green
        elif final_snr >= 3:
            status = "⚠️  勉強可以偵測"
            color = "\033[93m"  # Yellow
        else:
            status = "❌ 無法可靠偵測"
            color = "\033[91m"  # Red
        
        print(f"\n  {color}結論: {status} (SNR={final_snr:.2f})\033[0m")
        
        # 找到 SNR < 5 的距離
        snr_below_5 = df[df['snr'] < 5]
        if len(snr_below_5) > 0:
            detection_limit = snr_below_5.iloc[0]['estimated_distance_m']
            print(f"  估算偵測極限: ~{detection_limit:.1f}m")
        else:
            print(f"  估算偵測極限: >{df.iloc[-1]['estimated_distance_m']:.1f}m")
    
    print("\n" + "=" * 70)
    print("💡 建議:")
    print("=" * 70)
    print("  1. 打開 flashlight_analysis_report.html 查看完整互動式圖表")
    print("  2. 關注 SNR 圖表，SNR≥5 表示可靠偵測")
    print("  3. 比較不同曝光/增益設定對偵測能力的影響")
    print("=" * 70)
    print()

if __name__ == '__main__':
    print_summary()
