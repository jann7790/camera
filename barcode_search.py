#!/usr/bin/env python3
"""
Barcode 專用參數搜索工具
自動測試不同的曝光和增益組合，找出最適合 Barcode 識別的參數
"""

import PySpin
import cv2
import numpy as np
import time
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import yaml

class BarcodeParameterSearch:
    def __init__(self, exposure_range, gain_range, output_dir='results'):
        """
        初始化參數搜索器
        
        參數:
            exposure_range: 曝光時間列表 (微秒)
            gain_range: 增益值列表 (dB)
            output_dir: 結果保存目錄
        """
        self.exposure_range = exposure_range
        self.gain_range = gain_range
        self.output_dir = output_dir
        self.results = []
        
        # 創建輸出目錄
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'images'), exist_ok=True)
        
        # 相機相關
        self.system = None
        self.cam_list = None
        self.cam = None
        self.image_processor = None
        
    def initialize_camera(self):
        """初始化相機"""
        try:
            print("正在初始化相機...")
            self.system = PySpin.System.GetInstance()
            self.cam_list = self.system.GetCameras()
            
            num_cameras = self.cam_list.GetSize()
            if num_cameras == 0:
                print("❌ 沒有找到相機")
                return False
            
            self.cam = self.cam_list[0]
            self.cam.Init()
            
            # 設置基本參數
            self.cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
            
            # 設置像素格式為 Mono8
            if self.cam.PixelFormat.GetAccessMode() == PySpin.RW:
                self.cam.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
            
            # 創建圖像處理器
            self.image_processor = PySpin.ImageProcessor()
            
            print("✓ 相機初始化成功")
            return True
            
        except PySpin.SpinnakerException as ex:
            print(f"❌ 相機初始化錯誤: {ex}")
            return False
    
    def set_camera_parameters(self, exposure_us, gain_db):
        """設置相機參數"""
        try:
            # 設置曝光
            if self.cam.ExposureAuto.GetAccessMode() == PySpin.RW:
                self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                time.sleep(0.1)
            
            if self.cam.ExposureTime.GetAccessMode() == PySpin.RW:
                exposure_time = min(max(exposure_us, 
                                      self.cam.ExposureTime.GetMin()),
                                   self.cam.ExposureTime.GetMax())
                self.cam.ExposureTime.SetValue(exposure_time)
                time.sleep(0.05)
            
            # 設置增益
            if self.cam.GainAuto.GetAccessMode() == PySpin.RW:
                self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
                time.sleep(0.1)
            
            if self.cam.Gain.GetAccessMode() == PySpin.RW:
                gain_value = min(max(gain_db,
                                   self.cam.Gain.GetMin()),
                                self.cam.Gain.GetMax())
                self.cam.Gain.SetValue(gain_value)
                time.sleep(0.05)
            
            return True
            
        except Exception as e:
            print(f"❌ 設置參數錯誤: {e}")
            return False
    
    def capture_images(self, num_images=3):
        """捕捉多張圖像並返回平均值"""
        images = []
        
        try:
            # 開始採集
            self.cam.BeginAcquisition()
            
            # 丟棄前幾幀
            for _ in range(3):
                try:
                    image_result = self.cam.GetNextImage(2000)
                    image_result.Release()
                except:
                    pass
            
            # 捕捉實際圖像
            for i in range(num_images):
                image_result = self.cam.GetNextImage(2000)
                
                if not image_result.IsIncomplete():
                    # 獲取圖像數據
                    image_data = image_result.GetNDArray()
                    images.append(image_data.copy())
                
                image_result.Release()
                time.sleep(0.1)
            
            # 停止採集
            self.cam.EndAcquisition()
            
            if len(images) == 0:
                return None
            
            # 返回平均圖像
            avg_image = np.mean(images, axis=0).astype(np.uint8)
            return avg_image
            
        except Exception as e:
            print(f"❌ 捕捉圖像錯誤: {e}")
            try:
                self.cam.EndAcquisition()
            except:
                pass
            return None
    
    def evaluate_barcode_image(self, image):
        """
        評估 Barcode 圖像質量
        
        返回:
            score: 綜合評分 (0-100)
            metrics: 詳細指標字典
        """
        metrics = {}
        
        # 1. 使用 Otsu 閾值分離黑白區域
        threshold, _ = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        white_pixels = image[image > threshold]
        black_pixels = image[image <= threshold]
        
        if len(white_pixels) == 0 or len(black_pixels) == 0:
            # 圖像全黑或全白
            return 0.0, {'error': 'Image is all black or all white'}
        
        # 2. 計算白條和黑條的統計數據
        white_mean = float(np.mean(white_pixels))
        white_std = float(np.std(white_pixels))
        black_mean = float(np.mean(black_pixels))
        black_std = float(np.std(black_pixels))
        
        metrics['white_mean'] = white_mean
        metrics['white_std'] = white_std
        metrics['black_mean'] = black_mean
        metrics['black_std'] = black_std
        metrics['otsu_threshold'] = int(threshold)
        
        # 3. 計算對比度
        contrast = white_mean - black_mean
        metrics['contrast'] = contrast
        
        # 對比度評分 (理想: > 150)
        contrast_score = min(contrast / 180.0, 1.0) * 100
        
        # 4. 檢測過曝和欠曝
        total_pixels = image.size
        overexposed_pixels = np.sum(image >= 254)
        underexposed_pixels = np.sum(image <= 1)
        
        overexposed_ratio = overexposed_pixels / total_pixels
        underexposed_ratio = underexposed_pixels / total_pixels
        
        metrics['overexposed_ratio'] = float(overexposed_ratio)
        metrics['underexposed_ratio'] = float(underexposed_ratio)
        
        # 過曝/欠曝懲罰
        exposure_penalty = (overexposed_ratio + underexposed_ratio) * 100
        
        # 5. 檢查白條和黑條是否在理想範圍
        # 白條理想範圍: 180-240
        # 黑條理想範圍: 20-60
        white_range_score = 0
        if 180 <= white_mean <= 240:
            white_range_score = 100
        elif white_mean < 180:
            white_range_score = max(0, (white_mean / 180) * 100)
        else:  # > 240
            white_range_score = max(0, 100 - (white_mean - 240) * 2)
        
        black_range_score = 0
        if 20 <= black_mean <= 60:
            black_range_score = 100
        elif black_mean < 20:
            black_range_score = max(0, (black_mean / 20) * 100)
        else:  # > 60
            black_range_score = max(0, 100 - (black_mean - 60))
        
        range_score = (white_range_score + black_range_score) / 2
        metrics['range_score'] = range_score
        
        # 6. 邊緣清晰度 (使用 Canny 邊緣檢測)
        edges = cv2.Canny(image, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        edge_score = min(edge_density * 500, 100)  # 歸一化到 0-100
        metrics['edge_score'] = edge_score
        
        # 7. 圖像整體亮度
        mean_brightness = float(np.mean(image))
        metrics['mean_brightness'] = mean_brightness
        
        # 8. 計算綜合評分
        # 權重分配：對比度 40%, 範圍 30%, 邊緣 20%, 曝光懲罰 10%
        score = (contrast_score * 0.40 + 
                range_score * 0.30 + 
                edge_score * 0.20 + 
                max(0, 100 - exposure_penalty) * 0.10)
        
        metrics['final_score'] = score
        
        return score, metrics
    
    def run_search(self):
        """執行參數搜索"""
        if not self.initialize_camera():
            return False
        
        total_combinations = len(self.exposure_range) * len(self.gain_range)
        current_test = 0
        
        print("\n" + "="*70)
        print("開始 Barcode 參數搜索")
        print("="*70)
        print(f"曝光範圍: {self.exposure_range} μs")
        print(f"增益範圍: {self.gain_range} dB")
        print(f"總測試數: {total_combinations}")
        print("="*70 + "\n")
        
        start_time = time.time()
        
        for exposure in self.exposure_range:
            for gain in self.gain_range:
                current_test += 1
                print(f"\n[{current_test}/{total_combinations}] 測試: 曝光={exposure}μs, 增益={gain}dB")
                
                # 設置參數
                if not self.set_camera_parameters(exposure, gain):
                    print("  ⚠ 跳過此組合")
                    continue
                
                # 等待相機穩定
                time.sleep(0.3)
                
                # 捕捉圖像
                print("  正在捕捉圖像...")
                image = self.capture_images(num_images=3)
                
                if image is None:
                    print("  ⚠ 捕捉失敗，跳過")
                    continue
                
                # 評估圖像
                print("  正在評估質量...")
                score, metrics = self.evaluate_barcode_image(image)
                
                # 保存圖像
                image_filename = f"exp{exposure}_gain{gain}.png"
                image_path = os.path.join(self.output_dir, 'images', image_filename)
                cv2.imwrite(image_path, image)
                
                # 記錄結果
                result = {
                    'exposure_us': exposure,
                    'gain_db': gain,
                    'score': score,
                    'metrics': metrics,
                    'image_path': image_path,
                    'timestamp': datetime.now().isoformat()
                }
                self.results.append(result)
                
                # 顯示關鍵指標
                print(f"  ✓ 評分: {score:.1f}")
                print(f"    對比度: {metrics.get('contrast', 0):.1f}")
                print(f"    白條平均: {metrics.get('white_mean', 0):.1f}")
                print(f"    黑條平均: {metrics.get('black_mean', 0):.1f}")
                print(f"    過曝率: {metrics.get('overexposed_ratio', 0)*100:.2f}%")
        
        elapsed_time = time.time() - start_time
        print(f"\n✓ 搜索完成！耗時: {elapsed_time:.1f} 秒")
        
        # 清理相機
        self.cleanup()
        
        # 保存結果
        self.save_results()
        
        # 顯示最佳結果
        self.display_top_results()
        
        return True
    
    def save_results(self):
        """保存搜索結果到 JSON 文件"""
        results_file = os.path.join(self.output_dir, 'search_results.json')
        
        data = {
            'search_info': {
                'exposure_range': self.exposure_range,
                'gain_range': self.gain_range,
                'timestamp': datetime.now().isoformat(),
                'total_tests': len(self.results)
            },
            'results': self.results
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 結果已保存到: {results_file}")
    
    def display_top_results(self, top_n=5):
        """顯示最佳結果"""
        if not self.results:
            print("沒有結果可顯示")
            return
        
        # 按評分排序
        sorted_results = sorted(self.results, key=lambda x: x['score'], reverse=True)
        
        print("\n" + "="*70)
        print(f"Top {top_n} 最佳配置")
        print("="*70)
        
        medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        
        for i, result in enumerate(sorted_results[:top_n]):
            medal = medals[i] if i < len(medals) else f"{i+1}️⃣"
            metrics = result['metrics']
            
            print(f"\n{medal} Rank {i+1} (評分: {result['score']:.1f})")
            print(f"   曝光: {result['exposure_us']} μs")
            print(f"   增益: {result['gain_db']} dB")
            print(f"   對比度: {metrics.get('contrast', 0):.1f}")
            print(f"   白條平均: {metrics.get('white_mean', 0):.1f}")
            print(f"   黑條平均: {metrics.get('black_mean', 0):.1f}")
            print(f"   過曝率: {metrics.get('overexposed_ratio', 0)*100:.2f}%")
            print(f"   欠曝率: {metrics.get('underexposed_ratio', 0)*100:.2f}%")
            print(f"   邊緣評分: {metrics.get('edge_score', 0):.1f}")
        
        print("\n" + "="*70)
        
        # 保存最佳配置
        best_result = sorted_results[0]
        self.save_best_config(best_result)
    
    def save_best_config(self, best_result):
        """保存最佳配置到 YAML 文件"""
        config_file = os.path.join(self.output_dir, 'best_config.yaml')
        
        config = {
            'camera': {'pixel_format': 'Mono8'},
            'exposure': {
                'mode': 'manual',
                'time_us': best_result['exposure_us']
            },
            'gain': {
                'mode': 'manual',
                'value_db': best_result['gain_db']
            },
            'image': {'gamma': 1.0},
            'analysis': {'brightness_threshold': 180},
            'display': {
                'scale': 'auto',
                'flip_horizontal': False,
                'flip_vertical': False
            }
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        print(f"\n✓ 最佳配置已保存到: {config_file}")
        print(f"  可使用以下命令應用:")
        print(f"  ./run_camera.sh --exposure {best_result['exposure_us']} --gain {best_result['gain_db']}")
    
    def cleanup(self):
        """清理相機資源"""
        try:
            if self.cam is not None:
                try:
                    if self.cam.IsStreaming():
                        self.cam.EndAcquisition()
                except:
                    pass
                self.cam.DeInit()
                del self.cam
            
            if self.cam_list is not None:
                self.cam_list.Clear()
            
            if self.system is not None:
                self.system.ReleaseInstance()
            
        except Exception as e:
            print(f"清理警告: {e}")

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Barcode 參數自動搜索工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
範例:
  # 快速搜索 (預設)
  python barcode_search.py
  
  # 自定義範圍
  python barcode_search.py --exposure 500,1000,2000,5000 --gain 0,3,6,9
  
  # 精細搜索
  python barcode_search.py --fine
        ''')
    
    parser.add_argument('--exposure', type=str, 
                       help='曝光時間列表，用逗號分隔 (例如: 500,1000,2000)')
    parser.add_argument('--gain', type=str,
                       help='增益值列表，用逗號分隔 (例如: 0,3,6,9)')
    parser.add_argument('--fine', action='store_true',
                       help='使用精細搜索模式 (更多測試點)')
    parser.add_argument('--output', '-o', type=str, default='results',
                       help='結果保存目錄 (預設: results)')
    
    args = parser.parse_args()
    
    # 設定搜索範圍
    if args.fine:
        # 精細模式
        exposure_range = [500, 800, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 8000]
        gain_range = [0, 2, 4, 6, 8, 10, 12]
    elif args.exposure and args.gain:
        # 自定義範圍
        exposure_range = [int(x.strip()) for x in args.exposure.split(',')]
        gain_range = [float(x.strip()) for x in args.gain.split(',')]
    else:
        # 快速模式 (預設) - 針對 Barcode 優化的範圍
        exposure_range = [500, 1000, 2000, 3000, 5000, 8000]
        gain_range = [0, 3, 6, 9]
    
    print("="*70)
    print("Barcode 參數自動搜索工具")
    print("="*70)
    print(f"輸出目錄: {args.output}")
    print(f"測試組合數: {len(exposure_range)} x {len(gain_range)} = {len(exposure_range) * len(gain_range)}")
    print("="*70)
    
    # 創建搜索器並運行
    searcher = BarcodeParameterSearch(
        exposure_range=exposure_range,
        gain_range=gain_range,
        output_dir=args.output
    )
    
    try:
        success = searcher.run_search()
        if success:
            print("\n✓ 搜索成功完成！")
            print(f"\n查看結果:")
            print(f"  - 圖像: {args.output}/images/")
            print(f"  - 數據: {args.output}/search_results.json")
            print(f"  - 最佳配置: {args.output}/best_config.yaml")
            print(f"\n下一步:")
            print(f"  python visualize_results.py")
            print(f"  或")
            print(f"  ./apply_best_config.sh")
        else:
            print("\n❌ 搜索失敗")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠ 用戶中斷搜索")
        searcher.cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        searcher.cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()
