#!/usr/bin/env python3
"""
實時 Barcode 參數調整工具
使用鍵盤即時調整曝光和增益，肉眼觀察最佳參數
"""

import PySpin
import cv2
import numpy as np
import time
import sys
import yaml
import os

class LiveBarcodeTuner:
    def __init__(self):
        """初始化實時調參工具"""
        self.system = None
        self.cam = None
        self.cam_list = None
        self.is_running = False
        
        # 當前參數
        self.current_exposure = 2000  # μs
        self.current_gain = 3         # dB
        self.pixel_format = 'Mono8'
        
        # 參數範圍
        self.exposure_min = 100
        self.exposure_max = 20000
        self.gain_min = 0
        self.gain_max = 24
        
        # 參數步進
        self.exposure_step_small = 100   # 微調
        self.exposure_step_large = 1000  # 大調
        self.gain_step_small = 0.5       # 微調
        self.gain_step_large = 3         # 大調
        
        # 統計信息
        self.stats = {
            'contrast': 0,
            'white_mean': 0,
            'black_mean': 0,
            'overexposed_pct': 0,
            'underexposed_pct': 0
        }
        
        # 圖像處理器
        self.image_processor = None
        
        # 顯示設置
        self.rotation = 0              # 0, 90, 180, 270
        self.flip_horizontal = False   # 水平翻轉
        self.flip_vertical = False     # 垂直翻轉
        
    def initialize_camera(self):
        """初始化相機"""
        try:
            print("正在初始化相機...")
            self.system = PySpin.System.GetInstance()
            self.cam_list = self.system.GetCameras()
            
            if self.cam_list.GetSize() == 0:
                print("❌ 沒有找到相機")
                return False
            
            self.cam = self.cam_list[0]
            self.cam.Init()
            
            # 設置基本參數
            self.cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
            
            # 設置像素格式
            if self.cam.PixelFormat.GetAccessMode() == PySpin.RW:
                self.cam.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
            
            # 獲取相機參數範圍
            if self.cam.ExposureTime.GetAccessMode() == PySpin.RW:
                self.exposure_min = max(100, int(self.cam.ExposureTime.GetMin()))
                self.exposure_max = min(20000, int(self.cam.ExposureTime.GetMax()))
            
            if self.cam.Gain.GetAccessMode() == PySpin.RW:
                self.gain_min = self.cam.Gain.GetMin()
                self.gain_max = self.cam.Gain.GetMax()
            
            # 創建圖像處理器
            self.image_processor = PySpin.ImageProcessor()
            
            print("✓ 相機初始化成功")
            print(f"  曝光範圍: {self.exposure_min} - {self.exposure_max} μs")
            print(f"  增益範圍: {self.gain_min} - {self.gain_max} dB")
            return True
            
        except PySpin.SpinnakerException as ex:
            print(f"❌ 相機初始化錯誤: {ex}")
            return False
    
    def set_parameters(self, exposure_us, gain_db):
        """設置相機參數"""
        try:
            # 設置曝光
            if self.cam.ExposureAuto.GetAccessMode() == PySpin.RW:
                self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
            
            if self.cam.ExposureTime.GetAccessMode() == PySpin.RW:
                exposure_clamped = max(self.exposure_min, min(exposure_us, self.exposure_max))
                self.cam.ExposureTime.SetValue(exposure_clamped)
                self.current_exposure = exposure_clamped
            
            # 設置增益
            if self.cam.GainAuto.GetAccessMode() == PySpin.RW:
                self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
            
            if self.cam.Gain.GetAccessMode() == PySpin.RW:
                gain_clamped = max(self.gain_min, min(gain_db, self.gain_max))
                self.cam.Gain.SetValue(gain_clamped)
                self.current_gain = gain_clamped
            
            return True
            
        except Exception as e:
            print(f"設置參數錯誤: {e}")
            return False
    
    def analyze_barcode_realtime(self, image):
        """實時分析 Barcode 圖像"""
        try:
            # 使用 Otsu 閾值分離黑白
            threshold, _ = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            white_pixels = image[image > threshold]
            black_pixels = image[image <= threshold]
            
            if len(white_pixels) > 0 and len(black_pixels) > 0:
                white_mean = float(np.mean(white_pixels))
                black_mean = float(np.mean(black_pixels))
                contrast = white_mean - black_mean
                
                overexposed = np.sum(image >= 254) / image.size * 100
                underexposed = np.sum(image <= 1) / image.size * 100
                
                self.stats = {
                    'contrast': contrast,
                    'white_mean': white_mean,
                    'black_mean': black_mean,
                    'overexposed_pct': overexposed,
                    'underexposed_pct': underexposed,
                    'threshold': int(threshold)
                }
            
        except Exception as e:
            pass
    
    def draw_overlay(self, image):
        """繪製參數信息和統計數據覆蓋層"""
        overlay = image.copy()
        h, w = image.shape[:2]
        
        # 半透明背景
        cv2.rectangle(overlay, (0, 0), (w, 280), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, image, 0.4, 0, image)
        
        # 標題
        cv2.putText(image, "Barcode Real-time Tuner", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        
        # 當前參數 - 大字體顯示
        y_pos = 70
        cv2.putText(image, f"Exposure: {int(self.current_exposure)} us", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        y_pos += 35
        cv2.putText(image, f"Gain: {self.current_gain:.1f} dB", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # 分隔線
        y_pos += 15
        cv2.line(image, (10, y_pos), (w-10, y_pos), (100, 100, 100), 1)
        
        # 統計數據
        y_pos += 30
        
        # 對比度（帶顏色指示）
        contrast = self.stats.get('contrast', 0)
        contrast_color = (0, 255, 0) if contrast > 150 else (0, 165, 255) if contrast > 100 else (0, 0, 255)
        cv2.putText(image, f"Contrast: {contrast:.1f}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, contrast_color, 2)
        
        y_pos += 30
        
        # 白條平均（帶顏色指示）
        white_mean = self.stats.get('white_mean', 0)
        white_color = (0, 255, 0) if 180 <= white_mean <= 240 else (0, 165, 255) if white_mean > 150 else (0, 0, 255)
        cv2.putText(image, f"White: {white_mean:.1f}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, white_color, 2)
        
        y_pos += 30
        
        # 黑條平均（帶顏色指示）
        black_mean = self.stats.get('black_mean', 0)
        black_color = (0, 255, 0) if 20 <= black_mean <= 60 else (0, 165, 255) if black_mean < 80 else (0, 0, 255)
        cv2.putText(image, f"Black: {black_mean:.1f}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, black_color, 2)
        
        y_pos += 30
        
        # 過曝率
        overexp = self.stats.get('overexposed_pct', 0)
        overexp_color = (0, 255, 0) if overexp < 5 else (0, 165, 255) if overexp < 10 else (0, 0, 255)
        cv2.putText(image, f"Overexp: {overexp:.2f}%", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, overexp_color, 2)
        
        # 右側：鍵盤控制提示
        right_x = w - 350
        y_pos = 70
        
        cv2.putText(image, "Keyboard Controls:", (right_x, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        y_pos += 30
        controls = [
            ("W/S: Exposure +/- (large)", (200, 200, 200)),
            ("A/D: Gain +/- (large)", (200, 200, 200)),
            ("I/K: Exposure +/- (small)", (150, 150, 150)),
            ("J/L: Gain +/- (small)", (150, 150, 150)),
            ("", (0, 0, 0)),  # 空行
            ("SPACE: Save config", (0, 255, 0)),
            ("R: Reset defaults", (255, 165, 0)),
            ("Q: Quit", (0, 0, 255))
        ]
        
        for text, color in controls:
            if text:
                cv2.putText(image, text, (right_x, y_pos),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            y_pos += 25
        
        return image
    
    def save_config(self):
        """保存當前配置"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"barcode_manual_{timestamp}.yaml"
            
            config = {
                'camera': {'pixel_format': 'Mono8'},
                'exposure': {
                    'mode': 'manual',
                    'time_us': int(self.current_exposure)
                },
                'gain': {
                    'mode': 'manual',
                    'value_db': float(self.current_gain)
                },
                'stats': self.stats
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            
            print(f"\n✓ 配置已保存到: {filename}")
            print(f"  曝光: {int(self.current_exposure)} μs")
            print(f"  增益: {self.current_gain:.1f} dB")
            print(f"  對比度: {self.stats.get('contrast', 0):.1f}")
            
            # 也更新主配置文件
            if os.path.exists('camera_config.yaml'):
                response = input("是否要更新 camera_config.yaml? [y/N]: ")
                if response.lower() == 'y':
                    with open('camera_config.yaml', 'r', encoding='utf-8') as f:
                        main_config = yaml.safe_load(f)
                    
                    main_config['exposure']['mode'] = 'manual'
                    main_config['exposure']['time_us'] = int(self.current_exposure)
                    main_config['gain']['mode'] = 'manual'
                    main_config['gain']['value_db'] = float(self.current_gain)
                    
                    # 備份
                    backup_file = f"camera_config_backup_{timestamp}.yaml"
                    os.rename('camera_config.yaml', backup_file)
                    
                    with open('camera_config.yaml', 'w', encoding='utf-8') as f:
                        yaml.dump(main_config, f, default_flow_style=False, allow_unicode=True)
                    
                    print(f"  ✓ 已更新 camera_config.yaml")
                    print(f"  ✓ 原配置備份到: {backup_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ 保存配置失敗: {e}")
            return False
    
    def run(self):
        """運行實時調參"""
        if not self.initialize_camera():
            return False
        
        # 設置初始參數
        self.set_parameters(self.current_exposure, self.current_gain)
        
        # 開始採集
        self.cam.BeginAcquisition()
        self.is_running = True
        
        # 丟棄前幾幀
        for _ in range(5):
            try:
                image_result = self.cam.GetNextImage(2000)
                image_result.Release()
            except:
                pass
        
        print("\n" + "="*70)
        print("實時 Barcode 參數調整工具")
        print("="*70)
        print("\n鍵盤控制:")
        print("  W/S: 曝光 +/- (大步進: 1000 μs)")
        print("  A/D: 增益 +/- (大步進: 3 dB)")
        print("  I/K: 曝光 +/- (小步進: 100 μs)")
        print("  J/L: 增益 +/- (小步進: 0.5 dB)")
        print("\n  SPACE: 保存當前配置")
        print("  R: 重置為默認值 (2000 μs, 3 dB)")
        print("  Q: 退出")
        print("\n顏色指示:")
        print("  綠色 = 理想範圍")
        print("  橙色 = 可接受")
        print("  紅色 = 需要調整")
        print("\n開始調整參數，用肉眼觀察 Barcode 清晰度...")
        print("="*70 + "\n")
        
        update_params = False
        
        while self.is_running:
            try:
                # 獲取圖像
                image_result = self.cam.GetNextImage(2000)
                
                if not image_result.IsIncomplete():
                    # 獲取圖像數據
                    width = image_result.GetWidth()
                    height = image_result.GetHeight()
                    image_data = image_result.GetNDArray()
                    
                    # 分析圖像
                    self.analyze_barcode_realtime(image_data)
                    
                    # 轉換為 BGR 用於顯示
                    display_image = cv2.cvtColor(image_data, cv2.COLOR_GRAY2BGR)
                    
                    # 先應用旋轉和翻轉（在繪製覆蓋層之前）
                    if self.rotation == 90:
                        display_image = cv2.rotate(display_image, cv2.ROTATE_90_CLOCKWISE)
                    elif self.rotation == 180:
                        display_image = cv2.rotate(display_image, cv2.ROTATE_180)
                    elif self.rotation == 270:
                        display_image = cv2.rotate(display_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    
                    # 應用水平翻轉
                    if self.flip_horizontal:
                        display_image = cv2.flip(display_image, 1)  # 1 = 水平翻轉
                    
                    # 應用垂直翻轉
                    if self.flip_vertical:
                        display_image = cv2.flip(display_image, 0)  # 0 = 垂直翻轉
                    
                    # 繪製覆蓋層（在旋轉/翻轉之後，所以文字保持正常方向）
                    display_image = self.draw_overlay(display_image)
                    
                    # 自動縮放顯示
                    # 注意：旋轉後需要重新獲取寬高
                    height, width = display_image.shape[:2]
                    max_display_height = 1000
                    max_display_width = 1900
                    
                    if height > max_display_height or width > max_display_width:
                        scale_h = max_display_height / height
                        scale_w = max_display_width / width
                        scale = min(scale_h, scale_w)
                        
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        display_image = cv2.resize(display_image, (new_width, new_height))
                    
                    # 顯示圖像
                    cv2.imshow("Barcode Real-time Tuner", display_image)
                
                image_result.Release()
                
                # 如果需要更新參數
                if update_params:
                    self.set_parameters(self.current_exposure, self.current_gain)
                    time.sleep(0.1)  # 等待參數生效
                    update_params = False
                
                # 處理按鍵
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q') or key == ord('Q'):
                    print("\n退出...")
                    break
                
                elif key == ord('w') or key == ord('W'):
                    # 增加曝光（大步進）
                    self.current_exposure = min(self.current_exposure + self.exposure_step_large, 
                                               self.exposure_max)
                    update_params = True
                    print(f"曝光: {int(self.current_exposure)} μs")
                
                elif key == ord('s') or key == ord('S'):
                    # 減少曝光（大步進）
                    self.current_exposure = max(self.current_exposure - self.exposure_step_large, 
                                               self.exposure_min)
                    update_params = True
                    print(f"曝光: {int(self.current_exposure)} μs")
                
                elif key == ord('i') or key == ord('I'):
                    # 增加曝光（小步進）
                    self.current_exposure = min(self.current_exposure + self.exposure_step_small, 
                                               self.exposure_max)
                    update_params = True
                    print(f"曝光: {int(self.current_exposure)} μs")
                
                elif key == ord('k') or key == ord('K'):
                    # 減少曝光（小步進）
                    self.current_exposure = max(self.current_exposure - self.exposure_step_small, 
                                               self.exposure_min)
                    update_params = True
                    print(f"曝光: {int(self.current_exposure)} μs")
                
                elif key == ord('d') or key == ord('D'):
                    # 增加增益（大步進）
                    self.current_gain = min(self.current_gain + self.gain_step_large, 
                                           self.gain_max)
                    update_params = True
                    print(f"增益: {self.current_gain:.1f} dB")
                
                elif key == ord('a') or key == ord('A'):
                    # 減少增益（大步進）
                    self.current_gain = max(self.current_gain - self.gain_step_large, 
                                           self.gain_min)
                    update_params = True
                    print(f"增益: {self.current_gain:.1f} dB")
                
                elif key == ord('l') or key == ord('L'):
                    # 增加增益（小步進）
                    self.current_gain = min(self.current_gain + self.gain_step_small, 
                                           self.gain_max)
                    update_params = True
                    print(f"增益: {self.current_gain:.1f} dB")
                
                elif key == ord('j') or key == ord('J'):
                    # 減少增益（小步進）
                    self.current_gain = max(self.current_gain - self.gain_step_small, 
                                           self.gain_min)
                    update_params = True
                    print(f"增益: {self.current_gain:.1f} dB")
                
                elif key == ord(' '):
                    # 保存配置
                    self.save_config()
                
                elif key == ord('r') or key == ord('R'):
                    # 重置為默認值
                    self.current_exposure = 2000
                    self.current_gain = 3
                    update_params = True
                    print("重置為默認值: 曝光=2000μs, 增益=3dB")
                
            except PySpin.SpinnakerException as ex:
                print(f"錯誤: {ex}")
                break
            except KeyboardInterrupt:
                print("\n\n用戶中斷")
                break
        
        # 清理
        self.cleanup()
        return True
    
    def cleanup(self):
        """清理資源"""
        try:
            if self.is_running and self.cam is not None:
                self.cam.EndAcquisition()
                self.is_running = False
            
            if self.cam is not None:
                self.cam.DeInit()
                del self.cam
            
            if self.cam_list is not None:
                self.cam_list.Clear()
            
            if self.system is not None:
                self.system.ReleaseInstance()
            
            cv2.destroyAllWindows()
            print("\n資源清理完成")
            
        except Exception as e:
            print(f"清理警告: {e}")

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='實時 Barcode 參數調整工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
鍵盤控制:
  W/S: 曝光 +/- (大步進: 1000 μs)
  A/D: 增益 +/- (大步進: 3 dB)
  I/K: 曝光 +/- (小步進: 100 μs)
  J/L: 增益 +/- (小步進: 0.5 dB)
  
  SPACE: 保存當前配置
  R: 重置為默認值
  Q: 退出

提示:
  - 用肉眼觀察 Barcode 清晰度
  - 綠色指標 = 理想範圍
  - 橙色指標 = 可接受
  - 紅色指標 = 需要調整
        ''')
    
    parser.add_argument('--exposure', '-e', type=int, default=2000,
                       help='初始曝光時間 (μs, 預設: 2000)')
    parser.add_argument('--gain', '-g', type=float, default=3.0,
                       help='初始增益值 (dB, 預設: 3.0)')
    
    parser.add_argument('--rotate', '-r', type=int, choices=[0, 90, 180, 270],
                       help='旋轉畫面: 0=不旋轉, 90=向右旋轉90度, 180=旋轉180度, 270=向左旋轉90度')
    parser.add_argument('--flip', action='store_true',
                       help='水平翻轉畫面（鏡像，左右翻轉）')
    parser.add_argument('--flip-v', action='store_true',
                       help='垂直翻轉畫面（上下翻轉）')
    
    args = parser.parse_args()
    
    print("="*70)
    print("實時 Barcode 參數調整工具")
    print("="*70)
    
    tuner = LiveBarcodeTuner()
    tuner.current_exposure = args.exposure
    tuner.current_gain = args.gain
    
    # 設置旋轉和翻轉
    if args.rotate is not None:
        tuner.rotation = args.rotate
        rotation_text = {0: "不旋轉", 90: "向右旋轉90度", 180: "旋轉180度", 270: "向左旋轉90度"}
        print(f"✓ 設置旋轉: {rotation_text.get(args.rotate, str(args.rotate))}")
    
    if args.flip:
        tuner.flip_horizontal = True
        print("✓ 設置水平翻轉（鏡像）")
    
    if args.flip_v:
        tuner.flip_vertical = True
        print("✓ 設置垂直翻轉（上下翻轉）")
    
    try:
        tuner.run()
    except KeyboardInterrupt:
        print("\n\n用戶中斷")
        tuner.cleanup()
    except Exception as e:
        print(f"\n錯誤: {e}")
        import traceback
        traceback.print_exc()
        tuner.cleanup()

if __name__ == "__main__":
    main()
