#!/usr/bin/env python3
"""
自動迭代參數拍攝工具
自動測試多組曝光和增益參數組合，保存圖像用於比較
"""

import PySpin
import cv2
import numpy as np
import time
import sys
import yaml
import os
from datetime import datetime
import argparse

class ParameterIterator:
    def __init__(self):
        """初始化參數迭代器"""
        self.system = None
        self.cam = None
        self.cam_list = None
        self.image_processor = None
        
        # 參數範圍
        self.exposure_min = 100
        self.exposure_max = 20000
        self.gain_min = 0
        self.gain_max = 24
        
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
            
            # 設置增益
            if self.cam.GainAuto.GetAccessMode() == PySpin.RW:
                self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
            
            if self.cam.Gain.GetAccessMode() == PySpin.RW:
                gain_clamped = max(self.gain_min, min(gain_db, self.gain_max))
                self.cam.Gain.SetValue(gain_clamped)
            
            return True
            
        except Exception as e:
            print(f"❌ 設置參數錯誤: {e}")
            return False
    
    def capture_image(self, num_frames_to_skip=3):
        """採集圖像"""
        try:
            # 跳過前幾幀（讓參數穩定）
            for _ in range(num_frames_to_skip):
                image_result = self.cam.GetNextImage(2000)
                image_result.Release()
            
            # 採集實際圖像
            image_result = self.cam.GetNextImage(2000)
            
            if image_result.IsIncomplete():
                print("❌ 圖像不完整")
                image_result.Release()
                return None
            
            # 獲取圖像數據
            image_data = image_result.GetNDArray()
            image_result.Release()
            
            return image_data
            
        except PySpin.SpinnakerException as ex:
            print(f"❌ 採集圖像錯誤: {ex}")
            return None
    
    def analyze_image(self, image):
        """分析圖像統計"""
        try:
            # 使用 Otsu 閾值分離黑白
            threshold, _ = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            white_pixels = image[image > threshold]
            black_pixels = image[image <= threshold]
            
            stats = {
                'mean': float(np.mean(image)),
                'std': float(np.std(image)),
                'min': int(np.min(image)),
                'max': int(np.max(image)),
                'threshold': int(threshold)
            }
            
            if len(white_pixels) > 0 and len(black_pixels) > 0:
                white_mean = float(np.mean(white_pixels))
                black_mean = float(np.mean(black_pixels))
                contrast = white_mean - black_mean
                
                stats['white_mean'] = white_mean
                stats['black_mean'] = black_mean
                stats['contrast'] = contrast
                stats['overexposed_pct'] = float(np.sum(image >= 254) / image.size * 100)
                stats['underexposed_pct'] = float(np.sum(image <= 1) / image.size * 100)
            
            return stats
            
        except Exception as e:
            print(f"❌ 分析圖像錯誤: {e}")
            return {}
    
    def add_info_overlay(self, image, exposure, gain, stats, index, total):
        """在圖像上添加參數信息"""
        # 轉換為 BGR 用於顯示
        if len(image.shape) == 2:
            display_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            display_image = image.copy()
        
        h, w = display_image.shape[:2]
        
        # 半透明背景
        overlay = display_image.copy()
        cv2.rectangle(overlay, (0, 0), (w, 200), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, display_image, 0.3, 0, display_image)
        
        # 標題
        cv2.putText(display_image, f"Image {index}/{total}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        
        # 參數
        y_pos = 70
        cv2.putText(display_image, f"Exposure: {int(exposure)} us", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        y_pos += 35
        cv2.putText(display_image, f"Gain: {gain:.1f} dB", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # 統計數據
        y_pos += 35
        if 'contrast' in stats:
            cv2.putText(display_image, f"Contrast: {stats['contrast']:.1f}", (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        y_pos += 30
        cv2.putText(display_image, f"Mean: {stats.get('mean', 0):.1f}", (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        return display_image
    
    def iterate_and_capture(self, exposure_list, gain_list, output_dir, 
                           delay_seconds=1, show_preview=True, 
                           rotation=0, flip_horizontal=False, flip_vertical=False):
        """迭代參數並拍攝圖像"""
        
        # 創建輸出目錄
        os.makedirs(output_dir, exist_ok=True)
        
        # 開始採集
        self.cam.BeginAcquisition()
        
        # 計算總數
        total_combinations = len(exposure_list) * len(gain_list)
        current_index = 0
        
        # 保存所有結果
        results = []
        
        print("\n" + "="*70)
        print(f"開始迭代拍攝 - 共 {total_combinations} 組參數")
        print("="*70 + "\n")
        
        try:
            for exposure in exposure_list:
                for gain in gain_list:
                    current_index += 1
                    
                    print(f"\n[{current_index}/{total_combinations}] 曝光: {exposure} μs, 增益: {gain} dB")
                    
                    # 設置參數
                    if not self.set_parameters(exposure, gain):
                        print("  ⚠️ 設置參數失敗，跳過")
                        continue
                    
                    # 等待參數穩定
                    time.sleep(delay_seconds)
                    
                    # 採集圖像
                    image = self.capture_image()
                    if image is None:
                        print("  ⚠️ 採集圖像失敗，跳過")
                        continue
                    
                    # 分析圖像
                    stats = self.analyze_image(image)
                    print(f"  統計: 平均={stats.get('mean', 0):.1f}, "
                          f"對比度={stats.get('contrast', 0):.1f}, "
                          f"過曝={stats.get('overexposed_pct', 0):.2f}%")
                    
                    # 保存原始圖像（無覆蓋層）
                    filename_base = f"exp{int(exposure)}_gain{gain:.1f}"
                    raw_path = os.path.join(output_dir, f"{filename_base}_raw.png")
                    
                    # 應用旋轉和翻轉（如果需要）
                    image_to_save = image.copy()
                    if rotation == 90:
                        image_to_save = cv2.rotate(image_to_save, cv2.ROTATE_90_CLOCKWISE)
                    elif rotation == 180:
                        image_to_save = cv2.rotate(image_to_save, cv2.ROTATE_180)
                    elif rotation == 270:
                        image_to_save = cv2.rotate(image_to_save, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    
                    if flip_horizontal:
                        image_to_save = cv2.flip(image_to_save, 1)
                    
                    if flip_vertical:
                        image_to_save = cv2.flip(image_to_save, 0)
                    
                    cv2.imwrite(raw_path, image_to_save)
                    print(f"  ✓ 保存原始圖像: {raw_path}")
                    
                    # 創建帶覆蓋層的圖像用於預覽
                    display_image = self.add_info_overlay(
                        image_to_save, exposure, gain, stats, current_index, total_combinations
                    )
                    
                    # 保存帶標註的圖像
                    annotated_path = os.path.join(output_dir, f"{filename_base}_annotated.png")
                    cv2.imwrite(annotated_path, display_image)
                    print(f"  ✓ 保存標註圖像: {annotated_path}")
                    
                    # 顯示預覽
                    if show_preview:
                        # 自動縮放
                        h, w = display_image.shape[:2]
                        max_h, max_w = 1000, 1900
                        if h > max_h or w > max_w:
                            scale = min(max_h / h, max_w / w)
                            new_w, new_h = int(w * scale), int(h * scale)
                            display_image = cv2.resize(display_image, (new_w, new_h))
                        
                        cv2.imshow("Parameter Iterator", display_image)
                        key = cv2.waitKey(100)
                        
                        # 按 'q' 提前退出
                        if key == ord('q') or key == ord('Q'):
                            print("\n用戶中斷")
                            break
                    
                    # 保存結果記錄
                    results.append({
                        'index': current_index,
                        'exposure_us': int(exposure),
                        'gain_db': float(gain),
                        'raw_image': filename_base + '_raw.png',
                        'annotated_image': filename_base + '_annotated.png',
                        'stats': stats,
                        'timestamp': datetime.now().isoformat()
                    })
                
                # 檢查是否提前退出
                if show_preview and cv2.waitKey(1) == ord('q'):
                    break
        
        finally:
            # 停止採集
            self.cam.EndAcquisition()
            cv2.destroyAllWindows()
        
        # 保存結果摘要
        summary_path = os.path.join(output_dir, 'capture_summary.yaml')
        summary = {
            'total_images': len(results),
            'exposure_list': [int(e) for e in exposure_list],
            'gain_list': [float(g) for g in gain_list],
            'rotation': rotation,
            'flip_horizontal': flip_horizontal,
            'flip_vertical': flip_vertical,
            'output_directory': output_dir,
            'capture_time': datetime.now().isoformat(),
            'results': results
        }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            yaml.dump(summary, f, default_flow_style=False, allow_unicode=True)
        
        print(f"\n✓ 保存結果摘要: {summary_path}")
        
        # 生成對比網格圖
        self.generate_comparison_grid(results, output_dir)
        
        return results
    
    def generate_comparison_grid(self, results, output_dir):
        """生成對比網格圖"""
        if len(results) == 0:
            return
        
        print("\n正在生成對比網格圖...")
        
        try:
            # 讀取所有標註圖像
            images = []
            for result in results:
                img_path = os.path.join(output_dir, result['annotated_image'])
                if os.path.exists(img_path):
                    img = cv2.imread(img_path)
                    if img is not None:
                        # 縮小圖像 - 使用更大的尺寸保持清晰度
                        h, w = img.shape[:2]
                        # 根據圖像數量自動調整目標大小
                        n_total = len(results)
                        if n_total <= 9:
                            target_size = 800  # 少量圖像用大尺寸
                        elif n_total <= 36:
                            target_size = 600  # 中等數量
                        else:
                            target_size = 450  # 大量圖像用較小尺寸
                        
                        scale = min(target_size / h, target_size / w)
                        new_w, new_h = int(w * scale), int(h * scale)
                        # 使用 INTER_AREA 獲得更好的縮小效果
                        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                        images.append(img)
            
            if len(images) == 0:
                return
            
            # 計算網格大小
            n_images = len(images)
            n_cols = min(4, n_images)  # 最多4列
            n_rows = (n_images + n_cols - 1) // n_cols
            
            # 統一所有圖像大小
            max_h = max(img.shape[0] for img in images)
            max_w = max(img.shape[1] for img in images)
            
            # 創建網格
            grid_rows = []
            for row in range(n_rows):
                row_images = []
                for col in range(n_cols):
                    idx = row * n_cols + col
                    if idx < len(images):
                        img = images[idx]
                        # 填充到統一大小
                        padded = np.zeros((max_h, max_w, 3), dtype=np.uint8)
                        h, w = img.shape[:2]
                        padded[:h, :w] = img
                        row_images.append(padded)
                    else:
                        # 空白圖像
                        row_images.append(np.zeros((max_h, max_w, 3), dtype=np.uint8))
                
                grid_rows.append(np.hstack(row_images))
            
            grid = np.vstack(grid_rows)
            
            # 保存網格圖
            grid_path = os.path.join(output_dir, 'comparison_grid.png')
            cv2.imwrite(grid_path, grid)
            print(f"✓ 保存對比網格圖: {grid_path}")
            
        except Exception as e:
            print(f"⚠️ 生成網格圖失敗: {e}")
    
    def cleanup(self):
        """清理資源"""
        try:
            if self.cam is not None:
                if self.cam.IsStreaming():
                    self.cam.EndAcquisition()
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


def parse_range(range_str):
    """解析範圍字符串，例如 '1000,2000,5000' 或 '1000:5000:1000'"""
    if ',' in range_str:
        # 逗號分隔的列表
        return [float(x.strip()) for x in range_str.split(',')]
    elif ':' in range_str:
        # 範圍格式 start:end:step
        parts = [float(x.strip()) for x in range_str.split(':')]
        if len(parts) == 2:
            start, end = parts
            step = (end - start) / 5  # 默認5步
        elif len(parts) == 3:
            start, end, step = parts
        else:
            raise ValueError("範圍格式錯誤")
        
        values = []
        current = start
        while current <= end:
            values.append(current)
            current += step
        return values
    else:
        # 單個值
        return [float(range_str)]


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description='自動迭代參數拍攝工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用範例:
  # 測試3組曝光和4組增益（共12張圖）
  python iterate_capture.py -e 1000,2000,5000 -g 0,3,6,9
  
  # 使用範圍格式（從1000到5000，每隔1000）
  python iterate_capture.py -e 1000:5000:1000 -g 0:9:3
  
  # 指定輸出目錄和延遲時間
  python iterate_capture.py -e 1000,2000,5000 -g 3,6,9 -o my_test -d 2
  
  # 加上旋轉和翻轉
  python iterate_capture.py -e 1000,2000 -g 3,6 --rotate 90 --flip
  
  # 不顯示預覽（更快）
  python iterate_capture.py -e 1000,2000,5000 -g 0,3,6,9 --no-preview
        ''')
    
    parser.add_argument('-e', '--exposure', type=str, required=True,
                       help='曝光值列表（微秒），格式: "1000,2000,5000" 或 "1000:5000:1000"')
    parser.add_argument('-g', '--gain', type=str, required=True,
                       help='增益值列表（分貝），格式: "0,3,6,9" 或 "0:9:3"')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='輸出目錄（預設: iterate_capture_YYYYMMDD_HHMMSS）')
    parser.add_argument('-d', '--delay', type=float, default=1.0,
                       help='每次拍攝間隔延遲（秒，預設: 1.0）')
    parser.add_argument('--no-preview', action='store_true',
                       help='不顯示預覽視窗（加快速度）')
    parser.add_argument('--rotate', type=int, choices=[0, 90, 180, 270], default=0,
                       help='旋轉圖像（度）')
    parser.add_argument('--flip', action='store_true',
                       help='水平翻轉圖像')
    parser.add_argument('--flip-v', action='store_true',
                       help='垂直翻轉圖像')
    
    args = parser.parse_args()
    
    # 解析參數範圍
    try:
        exposure_list = parse_range(args.exposure)
        gain_list = parse_range(args.gain)
    except Exception as e:
        print(f"❌ 解析參數錯誤: {e}")
        print("請使用格式: '1000,2000,5000' 或 '1000:5000:1000'")
        return 1
    
    # 設置輸出目錄
    if args.output:
        output_dir = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"iterate_capture_{timestamp}"
    
    print("="*70)
    print("自動迭代參數拍攝工具")
    print("="*70)
    print(f"\n曝光列表: {[int(e) for e in exposure_list]} μs")
    print(f"增益列表: {[float(g) for g in gain_list]} dB")
    print(f"總組合數: {len(exposure_list) * len(gain_list)}")
    print(f"輸出目錄: {output_dir}")
    print(f"拍攝延遲: {args.delay} 秒")
    print(f"顯示預覽: {'否' if args.no_preview else '是'}")
    if args.rotate != 0:
        print(f"旋轉: {args.rotate}度")
    if args.flip:
        print(f"翻轉: 水平")
    if args.flip_v:
        print(f"翻轉: 垂直")
    print("")
    
    # 創建迭代器
    iterator = ParameterIterator()
    
    try:
        # 初始化相機
        if not iterator.initialize_camera():
            return 1
        
        # 開始迭代拍攝
        results = iterator.iterate_and_capture(
            exposure_list=exposure_list,
            gain_list=gain_list,
            output_dir=output_dir,
            delay_seconds=args.delay,
            show_preview=not args.no_preview,
            rotation=args.rotate,
            flip_horizontal=args.flip,
            flip_vertical=args.flip_v
        )
        
        print("\n" + "="*70)
        print(f"✓ 完成！共拍攝 {len(results)} 張圖像")
        print(f"✓ 圖像保存在: {output_dir}")
        print(f"✓ 查看摘要: {os.path.join(output_dir, 'capture_summary.yaml')}")
        print(f"✓ 查看對比: {os.path.join(output_dir, 'comparison_grid.png')}")
        print("="*70)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n用戶中斷")
        return 1
    except Exception as e:
        print(f"\n錯誤: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        iterator.cleanup()


if __name__ == "__main__":
    sys.exit(main())
