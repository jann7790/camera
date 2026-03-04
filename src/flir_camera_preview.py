#!/usr/bin/env python3
"""
FLIR Grasshopper 相機即時預覽程式
使用 PySpin SDK 和 OpenCV 來顯示相機畫面
支持通過 YAML 配置文件自定義相機參數
"""

import PySpin
import cv2
import numpy as np
import sys
import os
import time
from pathlib import Path
import yaml

class FLIRCameraPreview:
    def __init__(self, config=None):
        self.system = None
        self.cam_list = None
        self.cam = None
        self.is_running = False
        self.image_processor = PySpin.ImageProcessor()
        self.config = config or self.load_default_config()
        
    def load_default_config(self):
        """加載默認配置"""
        return {
            'camera': {'index': 0, 'pixel_format': 'BayerRG8'},
            'exposure': {'mode': 'auto', 'time_us': 10000},
            'gain': {'mode': 'auto', 'value_db': 0},
            'frame_rate': {'enabled': False, 'target_fps': 30},
            'white_balance': {'mode': 'auto', 'red_ratio': 1.0, 'blue_ratio': 1.0},
            'image': {'gamma': None, 'sharpness': None, 'saturation': None},
            'display': {
                'window_title': 'FLIR Grasshopper Camera Preview',
                'show_fps': True,
                'show_resolution': True,
                'show_exposure_gain': True,
                'scale': 1.0,
                'fullscreen': False
            },
            'save': {
                'directory': '.',
                'filename_prefix': 'flir_image',
                'format': 'jpg',
                'jpeg_quality': 95,
                'add_timestamp': True
            },
            'performance': {
                'image_timeout_ms': 1000,
                'use_threading': False,
                'buffer_count': 10
            },
            'advanced': {
                'trigger_mode': False,
                'trigger_source': 'Software',
                'enable_roi': False,
                'roi': {'x': 0, 'y': 0, 'width': 1920, 'height': 1200}
            },
            'debug': {
                'verbose': False,
                'show_camera_info': True,
                'save_log': False,
                'log_file': 'camera_debug.log'
            }
        }
        
    def initialize_camera(self):
        """初始化相機系統"""
        try:
            # 獲得系統實例
            self.system = PySpin.System.GetInstance()
            
            # 獲得相機列表
            self.cam_list = self.system.GetCameras()
            
            # 檢查是否有可用的相機
            num_cameras = self.cam_list.GetSize()
            if num_cameras == 0:
                print("沒有找到相機")
                return False
            
            if self.config['debug']['verbose']:
                print(f"找到 {num_cameras} 個相機")
            
            # 使用配置指定的相機索引
            cam_index = self.config['camera']['index']
            if cam_index >= num_cameras:
                print(f"相機索引 {cam_index} 超出範圍，使用第一個相機")
                cam_index = 0
                
            self.cam = self.cam_list[cam_index]
            
            # 初始化相機
            self.cam.Init()
            
            # 設置緩衝區數量
            try:
                buffer_count = self.config['performance']['buffer_count']
                self.cam.TLStream.StreamBufferCountMode.SetValue(PySpin.StreamBufferCountMode_Manual)
                self.cam.TLStream.StreamBufferCountManual.SetValue(buffer_count)
                if self.config['debug']['verbose']:
                    print(f"設置緩衝區數量: {buffer_count}")
            except:
                pass
            
            print("相機初始化成功")
            return True
            
        except PySpin.SpinnakerException as ex:
            print(f"相機初始化錯誤: {ex}")
            return False
    
    def configure_camera(self):
        """配置相機參數"""
        try:
            # 設置獲取模式為連續模式（除非使用觸發模式）
            if not self.config['advanced']['trigger_mode']:
                if self.cam.AcquisitionMode.GetAccessMode() == PySpin.RW:
                    self.cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
                    if self.config['debug']['verbose']:
                        print("設置獲取模式為連續模式")
            else:
                # 配置觸發模式
                self.configure_trigger_mode()
            
            # 設置像素格式
            self.configure_pixel_format()
            
            # 設置曝光
            self.configure_exposure()
            
            # 設置增益
            self.configure_gain()
            
            # 設置幀率
            self.configure_frame_rate()
            
            # 設置白平衡
            self.configure_white_balance()
            
            # 設置圖像處理參數
            self.configure_image_processing()
            
            # 設置 ROI（如果啟用）
            if self.config['advanced']['enable_roi']:
                self.configure_roi()
            
            return True
            
        except PySpin.SpinnakerException as ex:
            print(f"相機配置錯誤: {ex}")
            return False
    
    def configure_pixel_format(self):
        """配置像素格式"""
        try:
            if self.cam.PixelFormat.GetAccessMode() != PySpin.RW:
                return
                
            pixel_format = self.config['camera']['pixel_format']
            format_map = {
                'BayerRG8': PySpin.PixelFormat_BayerRG8,
                'RGB8': PySpin.PixelFormat_RGB8,
                'Mono8': PySpin.PixelFormat_Mono8,
                'BayerRG12': PySpin.PixelFormat_BayerRG12,
            }
            
            if pixel_format == 'auto':
                # 自動選擇：BayerRG8 -> RGB8 -> Mono8
                for fmt_name, fmt_value in format_map.items():
                    try:
                        self.cam.PixelFormat.SetValue(fmt_value)
                        print(f"設置像素格式為 {fmt_name}")
                        return
                    except:
                        continue
                print("使用相機默認像素格式")
            else:
                # 使用指定格式
                if pixel_format in format_map:
                    try:
                        self.cam.PixelFormat.SetValue(format_map[pixel_format])
                        print(f"設置像素格式為 {pixel_format}")
                    except Exception as e:
                        print(f"無法設置像素格式 {pixel_format}: {e}")
                else:
                    print(f"不支持的像素格式: {pixel_format}")
                    
        except Exception as e:
            if self.config['debug']['verbose']:
                print(f"像素格式設置警告: {e}")
    
    def configure_exposure(self):
        """配置曝光設置"""
        try:
            mode = self.config['exposure']['mode']
            
            if self.cam.ExposureAuto.GetAccessMode() == PySpin.RW:
                if mode == 'auto':
                    self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Continuous)
                    print("設置自動曝光")
                elif mode == 'off':
                    self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                    print("關閉自動曝光")
                    time.sleep(0.1)  # 等待設置生效
                elif mode == 'manual':
                    self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                    time.sleep(0.1)  # 等待設置生效
                    if self.cam.ExposureTime.GetAccessMode() == PySpin.RW:
                        exposure_time = self.config['exposure']['time_us']
                        self.cam.ExposureTime.SetValue(min(max(exposure_time, 
                                                          self.cam.ExposureTime.GetMin()),
                                                          self.cam.ExposureTime.GetMax()))
                        print(f"設置手動曝光: {exposure_time} μs")
                        time.sleep(0.05)  # 等待設置生效
                        
        except Exception as e:
            if self.config['debug']['verbose']:
                print(f"曝光設置警告: {e}")
    
    def configure_gain(self):
        """配置增益設置"""
        try:
            mode = self.config['gain']['mode']
            
            if self.cam.GainAuto.GetAccessMode() == PySpin.RW:
                if mode == 'auto':
                    self.cam.GainAuto.SetValue(PySpin.GainAuto_Continuous)
                    print("設置自動增益")
                elif mode == 'off':
                    self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
                    print("關閉自動增益")
                    time.sleep(0.1)  # 等待設置生效
                elif mode == 'manual':
                    self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
                    time.sleep(0.1)  # 等待設置生效
                    if self.cam.Gain.GetAccessMode() == PySpin.RW:
                        gain_value = self.config['gain']['value_db']
                        self.cam.Gain.SetValue(min(max(gain_value,
                                                   self.cam.Gain.GetMin()),
                                                   self.cam.Gain.GetMax()))
                        print(f"設置手動增益: {gain_value} dB")
                        time.sleep(0.05)  # 等待設置生效
                        
        except Exception as e:
            if self.config['debug']['verbose']:
                print(f"增益設置警告: {e}")
    
    def configure_frame_rate(self):
        """配置幀率"""
        try:
            if not self.config['frame_rate']['enabled']:
                return
                
            if self.cam.AcquisitionFrameRateEnable.GetAccessMode() == PySpin.RW:
                self.cam.AcquisitionFrameRateEnable.SetValue(True)
                
                if self.cam.AcquisitionFrameRate.GetAccessMode() == PySpin.RW:
                    target_fps = self.config['frame_rate']['target_fps']
                    self.cam.AcquisitionFrameRate.SetValue(min(max(target_fps,
                                                               self.cam.AcquisitionFrameRate.GetMin()),
                                                               self.cam.AcquisitionFrameRate.GetMax()))
                    print(f"設置幀率: {target_fps} FPS")
                    
        except Exception as e:
            if self.config['debug']['verbose']:
                print(f"幀率設置警告: {e}")
    
    def configure_white_balance(self):
        """配置白平衡"""
        try:
            mode = self.config['white_balance']['mode']
            
            if self.cam.BalanceWhiteAuto.GetAccessMode() == PySpin.RW:
                if mode == 'auto':
                    self.cam.BalanceWhiteAuto.SetValue(PySpin.BalanceWhiteAuto_Continuous)
                    if self.config['debug']['verbose']:
                        print("設置自動白平衡")
                elif mode == 'off':
                    self.cam.BalanceWhiteAuto.SetValue(PySpin.BalanceWhiteAuto_Off)
                elif mode == 'manual':
                    self.cam.BalanceWhiteAuto.SetValue(PySpin.BalanceWhiteAuto_Off)
                    # 這裡可以添加手動白平衡設置
                    if self.config['debug']['verbose']:
                        print("設置手動白平衡")
                        
        except Exception as e:
            if self.config['debug']['verbose']:
                print(f"白平衡設置警告: {e}")
    
    def configure_image_processing(self):
        """配置圖像處理參數"""
        try:
            # Gamma
            if self.config['image']['gamma'] is not None:
                if self.cam.Gamma.GetAccessMode() == PySpin.RW:
                    self.cam.Gamma.SetValue(self.config['image']['gamma'])
                    if self.config['debug']['verbose']:
                        print(f"設置 Gamma: {self.config['image']['gamma']}")
            
            # Sharpness
            if self.config['image']['sharpness'] is not None:
                if self.cam.Sharpness.GetAccessMode() == PySpin.RW:
                    self.cam.Sharpness.SetValue(self.config['image']['sharpness'])
                    if self.config['debug']['verbose']:
                        print(f"設置銳化: {self.config['image']['sharpness']}")
                        
        except Exception as e:
            if self.config['debug']['verbose']:
                print(f"圖像處理設置警告: {e}")
    
    def configure_trigger_mode(self):
        """配置觸發模式"""
        try:
            if self.cam.TriggerMode.GetAccessMode() == PySpin.RW:
                self.cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
                if self.cam.TriggerSource.GetAccessMode() == PySpin.RW:
                    trigger_source = self.config['advanced']['trigger_source']
                    source_map = {
                        'Software': PySpin.TriggerSource_Software,
                        'Line0': PySpin.TriggerSource_Line0,
                        'Line1': PySpin.TriggerSource_Line1,
                        'Line2': PySpin.TriggerSource_Line2,
                        'Line3': PySpin.TriggerSource_Line3,
                    }
                    if trigger_source in source_map:
                        self.cam.TriggerSource.SetValue(source_map[trigger_source])
                        print(f"啟用觸發模式: {trigger_source}")
        except Exception as e:
            print(f"觸發模式設置警告: {e}")
    
    def configure_roi(self):
        """配置 ROI（感興趣區域）"""
        try:
            roi = self.config['advanced']['roi']
            if self.cam.Width.GetAccessMode() == PySpin.RW:
                self.cam.OffsetX.SetValue(0)
                self.cam.OffsetY.SetValue(0)
                self.cam.Width.SetValue(roi['width'])
                self.cam.Height.SetValue(roi['height'])
                self.cam.OffsetX.SetValue(roi['x'])
                self.cam.OffsetY.SetValue(roi['y'])
                print(f"設置 ROI: {roi['width']}x{roi['height']} @ ({roi['x']}, {roi['y']})")
        except Exception as e:
            print(f"ROI 設置警告: {e}")
    
    def start_acquisition(self):
        """開始圖像獲取"""
        try:
            # 在開始獲取前稍等，確保所有配置都已生效
            time.sleep(0.2)
            self.cam.BeginAcquisition()
            self.is_running = True
            
            # 丟棄前幾幀（這些幀通常是不完整的）
            print("正在初始化相機緩衝區...")
            for i in range(5):
                try:
                    image_result = self.cam.GetNextImage(2000)
                    if image_result.IsIncomplete():
                        if self.config['debug']['verbose']:
                            print(f"  丟棄不完整的初始幀 {i+1}/5")
                    else:
                        if self.config['debug']['verbose']:
                            print(f"  丟棄初始幀 {i+1}/5")
                    image_result.Release()
                except:
                    pass
            
            print("相機就緒")
            if self.config['debug']['verbose']:
                print("開始圖像獲取")
            return True
        except PySpin.SpinnakerException as ex:
            print(f"開始獲取錯誤: {ex}")
            return False
    
    def stop_acquisition(self):
        """停止圖像獲取"""
        try:
            if self.is_running:
                self.cam.EndAcquisition()
                self.is_running = False
                print("停止圖像獲取")
        except PySpin.SpinnakerException as ex:
            print(f"停止獲取錯誤: {ex}")
    
    def get_camera_info(self):
        """獲取相機資訊"""
        try:
            device_info = self.cam.GetTLDeviceNodeMap()
            
            # 獲取設備資訊
            device_serial_number = PySpin.CStringPtr(device_info.GetNode("DeviceSerialNumber"))
            device_vendor_name = PySpin.CStringPtr(device_info.GetNode("DeviceVendorName"))
            device_model_name = PySpin.CStringPtr(device_info.GetNode("DeviceModelName"))
            
            info = {
                'serial': device_serial_number.GetValue() if PySpin.IsReadable(device_serial_number) else "Unknown",
                'vendor': device_vendor_name.GetValue() if PySpin.IsReadable(device_vendor_name) else "Unknown",
                'model': device_model_name.GetValue() if PySpin.IsReadable(device_model_name) else "Unknown"
            }
            
            return info
            
        except PySpin.SpinnakerException as ex:
            print(f"獲取相機資訊錯誤: {ex}")
            return None
    
    def save_image_multiple_formats(self, raw_data, display_image, pixel_format_str, timestamp):
        """
        保存圖像為多種格式
        
        參數:
            raw_data: 原始未轉換的圖像數據 (numpy array)
            display_image: 處理後的顯示圖像 (BGR8, 已旋轉/翻轉)
            pixel_format_str: 像素格式字符串 (e.g., 'Mono8', 'Mono16')
            timestamp: 時間戳字符串
            
        返回:
            保存的文件路徑列表
        """
        import os
        save_dir = "saved_images"
        os.makedirs(save_dir, exist_ok=True)
        
        saved_files = []
        
        # 1. 保存預覽圖像 (JPG) - 經過旋轉/翻轉的顯示圖像
        preview_path = os.path.join(save_dir, f"flir_preview_{timestamp}.jpg")
        try:
            cv2.imwrite(preview_path, display_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
            saved_files.append(('preview', preview_path))
            print(f"✓ 預覽圖像: {preview_path}")
        except Exception as e:
            print(f"✗ 保存預覽失敗: {e}")
        
        # 2. 保存原始數據 (無損格式) - 未經旋轉/翻轉
        # 根據像素格式選擇合適的保存方式
        if 'Mono8' in pixel_format_str or 'BayerRG8' in pixel_format_str:
            # 8-bit 格式 - 使用 PNG 無損壓縮
            raw_path = os.path.join(save_dir, f"flir_raw_{timestamp}.png")
            try:
                # 如果是 Bayer 格式，保存為灰度
                if len(raw_data.shape) == 2:
                    cv2.imwrite(raw_path, raw_data)
                else:
                    # 如果是多通道，保存第一個通道
                    cv2.imwrite(raw_path, raw_data[:,:,0] if raw_data.shape[2] > 0 else raw_data)
                saved_files.append(('raw_png', raw_path))
                print(f"✓ 原始數據 (PNG 8-bit): {raw_path}")
            except Exception as e:
                print(f"✗ 保存PNG失敗: {e}")
                
        elif 'Mono16' in pixel_format_str or 'BayerRG16' in pixel_format_str:
            # 16-bit 格式 - 使用 TIFF 保存完整精度
            raw_path = os.path.join(save_dir, f"flir_raw_{timestamp}.tiff")
            try:
                # TIFF 支持 16-bit
                if len(raw_data.shape) == 2:
                    cv2.imwrite(raw_path, raw_data)
                else:
                    cv2.imwrite(raw_path, raw_data[:,:,0] if raw_data.shape[2] > 0 else raw_data)
                saved_files.append(('raw_tiff', raw_path))
                print(f"✓ 原始數據 (TIFF 16-bit): {raw_path}")
            except Exception as e:
                print(f"✗ 保存TIFF失敗: {e}")
        
        # 3. 保存 NumPy 數組 (NPY) - 完整保留所有信息
        npy_path = os.path.join(save_dir, f"flir_raw_{timestamp}.npy")
        try:
            np.save(npy_path, raw_data)
            saved_files.append(('raw_npy', npy_path))
            print(f"✓ NumPy 數組: {npy_path}")
        except Exception as e:
            print(f"✗ 保存NPY失敗: {e}")
        
        # 4. 保存元數據信息
        meta_path = os.path.join(save_dir, f"flir_meta_{timestamp}.txt")
        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                f.write("FLIR 圖像元數據\n")
                f.write("=" * 60 + "\n")
                f.write(f"時間戳: {timestamp}\n")
                f.write(f"像素格式: {pixel_format_str}\n")
                f.write(f"數據形狀: {raw_data.shape}\n")
                f.write(f"數據類型: {raw_data.dtype}\n")
                f.write(f"位深度: {'16-bit' if raw_data.dtype == np.uint16 else '8-bit'}\n")
                
                # 統計信息
                f.write(f"\n像素值統計:\n")
                f.write(f"  最小值: {np.min(raw_data)}\n")
                f.write(f"  最大值: {np.max(raw_data)}\n")
                f.write(f"  平均值: {np.mean(raw_data):.2f}\n")
                f.write(f"  標準差: {np.std(raw_data):.2f}\n")
                
                # 相機配置
                if 'exposure' in self.config:
                    f.write(f"\n相機配置:\n")
                    f.write(f"  曝光模式: {self.config['exposure'].get('mode', 'N/A')}\n")
                    if self.config['exposure'].get('mode') == 'manual':
                        f.write(f"  曝光時間: {self.config['exposure'].get('time_us', 0)} μs\n")
                
                if 'gain' in self.config:
                    f.write(f"  增益模式: {self.config['gain'].get('mode', 'N/A')}\n")
                    if self.config['gain'].get('mode') == 'manual':
                        f.write(f"  增益值: {self.config['gain'].get('value_db', 0)} dB\n")
                
                f.write(f"\n保存的文件:\n")
                for file_type, file_path in saved_files:
                    f.write(f"  [{file_type}] {os.path.basename(file_path)}\n")
                
                f.write("\n" + "=" * 60 + "\n")
                f.write("如何讀取保存的數據:\n")
                f.write(f"  PNG/TIFF: 使用任何圖像查看器或 cv2.imread()\n")
                f.write(f"  NPY: import numpy as np; data = np.load('{os.path.basename(npy_path)}')\n")
            
            saved_files.append(('metadata', meta_path))
            print(f"✓ 元數據: {meta_path}")
        except Exception as e:
            print(f"✗ 保存元數據失敗: {e}")
        
        return saved_files
    
    def analyze_image_pixels(self, image, threshold=200):
        """
        分析圖像的像素值
        
        參數:
            image: numpy 數組格式的圖像
            threshold: 亮點檢測閾值（默認200）
            
        返回:
            包含統計信息的字典
        """
        analysis = {}
        
        # 檢查是彩色還是灰度圖像
        if len(image.shape) == 3:
            # 彩色圖像 - 計算亮度（取最大通道值或轉換為灰度）
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            analysis['color_space'] = 'BGR'
            
            # 分析每個通道
            b, g, r = cv2.split(image)
            analysis['channels'] = {
                'blue': {
                    'max': int(np.max(b)),
                    'min': int(np.min(b)),
                    'mean': float(np.mean(b)),
                    'std': float(np.std(b))
                },
                'green': {
                    'max': int(np.max(g)),
                    'min': int(np.min(g)),
                    'mean': float(np.mean(g)),
                    'std': float(np.std(g))
                },
                'red': {
                    'max': int(np.max(r)),
                    'min': int(np.min(r)),
                    'mean': float(np.mean(r)),
                    'std': float(np.std(r))
                }
            }
        else:
            # 灰度圖像
            gray = image
            analysis['color_space'] = 'Grayscale'
        
        # 整體亮度統計
        analysis['brightness'] = {
            'max': int(np.max(gray)),
            'min': int(np.min(gray)),
            'mean': float(np.mean(gray)),
            'std': float(np.std(gray))
        }
        
        # 找到最亮點的位置
        max_val = np.max(gray)
        max_loc = np.unravel_index(np.argmax(gray), gray.shape)
        analysis['brightest_point'] = {
            'value': int(max_val),
            'location': (int(max_loc[1]), int(max_loc[0])),  # (x, y)
            'coords': f"({max_loc[1]}, {max_loc[0]})"
        }
        
        # 找到最暗點的位置
        min_val = np.min(gray)
        min_loc = np.unravel_index(np.argmin(gray), gray.shape)
        analysis['darkest_point'] = {
            'value': int(min_val),
            'location': (int(min_loc[1]), int(min_loc[0])),  # (x, y)
            'coords': f"({min_loc[1]}, {min_loc[0]})"
        }
        
        # 檢測亮點區域（像素值 > 閾值）
        bright_pixels = gray > threshold
        num_bright_pixels = np.sum(bright_pixels)
        analysis['bright_region'] = {
            'threshold': threshold,
            'pixel_count': int(num_bright_pixels),
            'percentage': float(num_bright_pixels / gray.size * 100)
        }
        
        # 如果有亮點，計算亮點的質心（中心位置）
        if num_bright_pixels > 0:
            y_indices, x_indices = np.where(bright_pixels)
            centroid_x = int(np.mean(x_indices))
            centroid_y = int(np.mean(y_indices))
            analysis['bright_region']['centroid'] = (centroid_x, centroid_y)
            analysis['bright_region']['centroid_coords'] = f"({centroid_x}, {centroid_y})"
        else:
            analysis['bright_region']['centroid'] = None
        
        # 圖像尺寸
        analysis['resolution'] = {
            'width': image.shape[1],
            'height': image.shape[0]
        }
        
        return analysis
    
    def print_pixel_analysis(self, analysis, save_to_file=None):
        """
        打印像素分析結果
        
        參數:
            analysis: analyze_image_pixels 返回的分析結果
            save_to_file: 如果指定，將結果保存到文件
        """
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("圖像像素值分析報告")
        report_lines.append("=" * 60)
        
        # 基本信息
        report_lines.append(f"\n【基本信息】")
        report_lines.append(f"  解析度: {analysis['resolution']['width']}x{analysis['resolution']['height']}")
        report_lines.append(f"  顏色空間: {analysis['color_space']}")
        
        # 整體亮度統計
        report_lines.append(f"\n【整體亮度統計】")
        report_lines.append(f"  最大值: {analysis['brightness']['max']}")
        report_lines.append(f"  最小值: {analysis['brightness']['min']}")
        report_lines.append(f"  平均值: {analysis['brightness']['mean']:.2f}")
        report_lines.append(f"  標準差: {analysis['brightness']['std']:.2f}")
        
        # 通道統計（如果是彩色圖像）
        if 'channels' in analysis:
            report_lines.append(f"\n【RGB 通道統計】")
            for channel_name, channel_data in analysis['channels'].items():
                report_lines.append(f"  {channel_name.capitalize()} 通道:")
                report_lines.append(f"    最大值: {channel_data['max']}, 最小值: {channel_data['min']}, "
                                  f"平均值: {channel_data['mean']:.2f}")
        
        # 最亮點
        report_lines.append(f"\n【最亮點】")
        report_lines.append(f"  像素值: {analysis['brightest_point']['value']}")
        report_lines.append(f"  位置 (x, y): {analysis['brightest_point']['coords']}")
        
        # 最暗點
        report_lines.append(f"\n【最暗點】")
        report_lines.append(f"  像素值: {analysis['darkest_point']['value']}")
        report_lines.append(f"  位置 (x, y): {analysis['darkest_point']['coords']}")
        
        # 亮點區域
        report_lines.append(f"\n【亮點區域分析】（閾值 > {analysis['bright_region']['threshold']}）")
        report_lines.append(f"  亮點像素數: {analysis['bright_region']['pixel_count']}")
        report_lines.append(f"  佔比: {analysis['bright_region']['percentage']:.3f}%")
        if analysis['bright_region']['centroid']:
            report_lines.append(f"  亮點質心 (x, y): {analysis['bright_region']['centroid_coords']}")
        else:
            report_lines.append(f"  沒有檢測到亮點（所有像素值 <= {analysis['bright_region']['threshold']}）")
        
        report_lines.append("=" * 60)
        
        # 打印到控制台
        report = "\n".join(report_lines)
        print(report)
        
        # 保存到文件（如果指定）
        if save_to_file:
            try:
                with open(save_to_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                print(f"\n分析報告已保存至: {save_to_file}")
            except Exception as e:
                print(f"保存報告失敗: {e}")
        
        return report
    
    def capture_and_display(self):
        """捕獲並顯示圖像"""
        fps_counter = 0
        fps_start_time = time.time()
        current_fps = 0.0
        
        # 自動保存計時器
        auto_save_interval = self.config.get('save', {}).get('auto_save_interval', 0)
        last_auto_save_time = time.time()
        auto_save_count = 0
        
        if auto_save_interval > 0:
            print(f"✓ 自動保存已啟用: 每 {auto_save_interval} 秒保存一次")
        
        print("按下 'q' 鍵退出，'s' 鍵保存圖像並分析像素值，'a' 鍵分析當前幀")
        print("如果看不到窗口，請檢查 DISPLAY 環境變數和 X11 forwarding")
        
        while self.is_running:
            try:
                # 獲取下一張圖像
                image_result = self.cam.GetNextImage(2000)  # 2秒超時
                
                if image_result.IsIncomplete():
                    print(f"圖像不完整，狀態: {image_result.GetImageStatus()}")
                    image_result.Release()
                    continue
                
                # 轉換圖像格式
                width = image_result.GetWidth()
                height = image_result.GetHeight()
                pixel_format = image_result.GetPixelFormat()
                
                # 保存原始圖像數據（未轉換）用於保存
                raw_image_data = image_result.GetNDArray()
                
                # 將所有格式轉換為 BGR8 以便顯示
                try:
                    image_converted = self.image_processor.Convert(image_result, PySpin.PixelFormat_BGR8)
                    
                    # 使用 GetData() 獲取原始數據並手動創建 numpy 數組
                    image_data = image_converted.GetData()
                    temp_array = np.frombuffer(image_data, dtype=np.uint8)
                    temp_array = temp_array.reshape((height, width, 3))
                    
                    # 創建一個新的 numpy 數組來避免兼容性問題
                    display_image = np.array(temp_array, dtype=np.uint8, order='C', copy=True)
                    
                    # 應用旋轉（如果配置中有設置）
                    if 'display' in self.config and 'rotation' in self.config['display']:
                        rotation = self.config['display']['rotation']
                        if rotation == 90:
                            display_image = cv2.rotate(display_image, cv2.ROTATE_90_CLOCKWISE)
                        elif rotation == 180:
                            display_image = cv2.rotate(display_image, cv2.ROTATE_180)
                        elif rotation == 270:
                            display_image = cv2.rotate(display_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    
                    # 應用水平翻轉（如果配置中有設置）
                    if 'display' in self.config and self.config['display'].get('flip_horizontal', False):
                        display_image = cv2.flip(display_image, 1)  # 1 = 水平翻轉
                    
                    # 應用垂直翻轉（如果配置中有設置）
                    if 'display' in self.config and self.config['display'].get('flip_vertical', False):
                        display_image = cv2.flip(display_image, 0)  # 0 = 垂直翻轉（上下翻轉）
                    
                    # 應用顯示縮放（自動適應螢幕或使用配置值）
                    if 'display' in self.config:
                        scale = self.config['display'].get('scale', 'auto')
                        
                        if scale == 'auto':
                            # 自動計算縮放比例以適應螢幕
                            # 假設螢幕可用高度約為 1000 像素（留空間給任務欄等）
                            max_display_height = 1000
                            max_display_width = 1900
                            
                            img_height = display_image.shape[0]
                            img_width = display_image.shape[1]
                            
                            # 計算縮放比例（取較小的比例以確保整個圖像都能顯示）
                            scale_height = max_display_height / img_height if img_height > max_display_height else 1.0
                            scale_width = max_display_width / img_width if img_width > max_display_width else 1.0
                            scale = min(scale_height, scale_width)
                            
                            # 只有在需要縮小時才縮放
                            if scale < 1.0:
                                new_width = int(img_width * scale)
                                new_height = int(img_height * scale)
                                display_image = cv2.resize(display_image, (new_width, new_height), 
                                                          interpolation=cv2.INTER_LINEAR)
                        elif isinstance(scale, (int, float)) and scale != 1.0 and scale > 0:
                            # 使用配置中的固定縮放比例
                            new_width = int(display_image.shape[1] * scale)
                            new_height = int(display_image.shape[0] * scale)
                            display_image = cv2.resize(display_image, (new_width, new_height), 
                                                      interpolation=cv2.INTER_LINEAR)
                    
                except Exception as e:
                    print(f"圖像轉換錯誤: {e}")
                    import traceback
                    traceback.print_exc()
                    image_result.Release()
                    continue
                
                # 快速分析當前幀的亮度
                try:
                    gray = cv2.cvtColor(display_image, cv2.COLOR_BGR2GRAY)
                    max_brightness = int(np.max(gray))
                    mean_brightness = float(np.mean(gray))
                    max_loc = np.unravel_index(np.argmax(gray), gray.shape)
                    max_loc_xy = (int(max_loc[1]), int(max_loc[0]))
                    
                    # 在圖像上標記最亮點
                    cv2.circle(display_image, max_loc_xy, 10, (0, 0, 255), 2)
                    cv2.circle(display_image, max_loc_xy, 3, (0, 255, 255), -1)
                except:
                    max_brightness = 0
                    mean_brightness = 0.0
                    max_loc_xy = (0, 0)
                
                # 計算 FPS
                fps_counter += 1
                current_time = time.time()
                if current_time - fps_start_time >= 1.0:
                    current_fps = fps_counter / (current_time - fps_start_time)
                    fps_counter = 0
                    fps_start_time = current_time
                
                # 在圖像上顯示信息
                try:
                    text_y = 30
                    line_height = 35
                    
                    # FPS
                    cv2.putText(display_image, f"FPS: {current_fps:.1f}", (10, text_y), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    text_y += line_height
                    
                    # 解析度
                    cv2.putText(display_image, f"Resolution: {width}x{height}", (10, text_y), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    text_y += line_height
                    
                    # 最大亮度
                    cv2.putText(display_image, f"Max Brightness: {max_brightness}", (10, text_y), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    text_y += line_height
                    
                    # 平均亮度
                    cv2.putText(display_image, f"Mean Brightness: {mean_brightness:.1f}", (10, text_y), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    text_y += line_height
                    
                    # 最亮點位置
                    cv2.putText(display_image, f"Brightest: ({max_loc_xy[0]}, {max_loc_xy[1]})", (10, text_y), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    
                except Exception as e:
                    pass  # 跳過文字添加錯誤
                
                # 顯示圖像
                try:
                    cv2.imshow("FLIR Grasshopper Camera Preview", display_image)
                except Exception as e:
                    pass  # 跳過顯示錯誤但繼續運行
                
                # 檢查是否需要自動保存
                current_time = time.time()
                if auto_save_interval > 0 and (current_time - last_auto_save_time) >= auto_save_interval:
                    auto_save_count += 1
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    
                    # 將 PySpin 像素格式枚舉轉換為字符串
                    pixel_format_map = {
                        PySpin.PixelFormat_Mono8: 'Mono8',
                        PySpin.PixelFormat_Mono16: 'Mono16',
                        PySpin.PixelFormat_BayerRG8: 'BayerRG8',
                        PySpin.PixelFormat_BayerRG16: 'BayerRG16',
                        PySpin.PixelFormat_RGB8: 'RGB8',
                        PySpin.PixelFormat_BayerRG12: 'BayerRG12',
                    }
                    pixel_format_str = pixel_format_map.get(pixel_format, f'Unknown_{pixel_format}')
                    
                    print(f"\n[自動保存 #{auto_save_count}] 正在保存圖像...")
                    saved_files = self.save_image_multiple_formats(
                        raw_image_data, 
                        display_image, 
                        pixel_format_str, 
                        timestamp
                    )
                    
                    # 如果啟用了自動分析，生成分析報告
                    if self.config.get('analysis', {}).get('auto_analyze_on_save', False):
                        import os
                        save_dir = "saved_images"
                        report_filename = os.path.join(save_dir, f"flir_analysis_{timestamp}.txt")
                        analysis = self.analyze_image_pixels(display_image, threshold=200)
                        self.print_pixel_analysis(analysis, save_to_file=report_filename)
                    
                    last_auto_save_time = current_time
                
                # 處理按鍵
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("用戶退出")
                    break
                elif key == ord('s'):
                    # 保存圖像並進行詳細分析（多種格式）
                    import os
                    
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    
                    # 將 PySpin 像素格式枚舉轉換為字符串
                    pixel_format_map = {
                        PySpin.PixelFormat_Mono8: 'Mono8',
                        PySpin.PixelFormat_Mono16: 'Mono16',
                        PySpin.PixelFormat_BayerRG8: 'BayerRG8',
                        PySpin.PixelFormat_BayerRG16: 'BayerRG16',
                        PySpin.PixelFormat_RGB8: 'RGB8',
                        PySpin.PixelFormat_BayerRG12: 'BayerRG12',
                    }
                    pixel_format_str = pixel_format_map.get(pixel_format, f'Unknown_{pixel_format}')
                    
                    # 保存多種格式
                    print("\n正在保存圖像...")
                    saved_files = self.save_image_multiple_formats(
                        raw_image_data, 
                        display_image, 
                        pixel_format_str, 
                        timestamp
                    )
                    
                    # 生成分析報告
                    save_dir = "saved_images"
                    report_filename = os.path.join(save_dir, f"flir_analysis_{timestamp}.txt")
                    print("\n正在分析像素值...")
                    analysis = self.analyze_image_pixels(display_image, threshold=200)
                    self.print_pixel_analysis(analysis, save_to_file=report_filename)
                elif key == ord('a'):
                    # 分析當前幀但不保存
                    print("\n正在分析當前幀的像素值...")
                    analysis = self.analyze_image_pixels(display_image, threshold=200)
                    self.print_pixel_analysis(analysis)
                
                # 釋放圖像
                image_result.Release()
                
            except PySpin.SpinnakerException as ex:
                print(f"獲取圖像錯誤: {ex}")
                break
            except KeyboardInterrupt:
                print("\n用戶中斷")
                break
    
    def cleanup(self):
        """清理資源"""
        try:
            if self.is_running:
                self.stop_acquisition()
            
            if hasattr(self, 'cam') and self.cam is not None:
                try:
                    self.cam.DeInit()
                except:
                    pass
                del self.cam
            
            if hasattr(self, 'cam_list') and self.cam_list is not None:
                self.cam_list.Clear()
            
            if hasattr(self, 'system') and self.system is not None:
                self.system.ReleaseInstance()
            
            cv2.destroyAllWindows()
            print("資源清理完成")
            
        except PySpin.SpinnakerException as ex:
            print(f"清理錯誤: {ex}")
        except Exception as ex:
            print(f"清理錯誤: {ex}")
    
    def run(self):
        """主執行函數"""
        # 初始化相機
        if not self.initialize_camera():
            return False
        
        # 顯示相機資訊
        camera_info = self.get_camera_info()
        if camera_info:
            print(f"相機資訊:")
            print(f"  廠商: {camera_info['vendor']}")
            print(f"  型號: {camera_info['model']}")
            print(f"  序號: {camera_info['serial']}")
        
        # 配置相機
        if not self.configure_camera():
            return False
        
        # 開始獲取
        if not self.start_acquisition():
            return False
        
        # 顯示畫面
        self.capture_and_display()
        
        return True

def main():
    """主函數"""
    import argparse
    
    # 解析命令行參數
    parser = argparse.ArgumentParser(
        description='FLIR Grasshopper 相機預覽程式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
範例:
  %(prog)s                              # 使用配置文件
  %(prog)s --exposure 1000 --gain 10    # 覆蓋曝光和增益
  %(prog)s --format Mono16 --gamma 1.2  # 使用16位格式
  %(prog)s --preset 1                   # 使用預設模式1
  %(prog)s --help-params                # 顯示所有可用參數
        ''')
    
    # 基本參數
    parser.add_argument('--exposure', '-e', type=float, metavar='μs',
                        help='曝光時間 (微秒), 範圍: 9-11526')
    parser.add_argument('--gain', '-g', type=float, metavar='dB',
                        help='增益值 (dB), 範圍: 0-24')
    parser.add_argument('--format', '-f', type=str, metavar='FMT',
                        choices=['Mono8', 'Mono16', 'BayerRG8', 'BayerRG16', 'RGB8'],
                        help='像素格式: Mono8, Mono16, BayerRG8, BayerRG16, RGB8')
    
    # 圖像質量參數
    parser.add_argument('--gamma', type=float, metavar='VAL',
                        help='Gamma校正 (0.5-4.0), <1暗部提亮, >1亮部壓暗')
    parser.add_argument('--black-level', type=float, metavar='VAL',
                        help='黑電平 (0-12.48), 降低可減少噪點')
    parser.add_argument('--threshold', '-t', type=int, metavar='VAL',
                        help='亮點檢測閾值 (0-255)')
    
    # ROI參數
    parser.add_argument('--width', type=int, metavar='PX',
                        help='圖像寬度 (32-1920)')
    parser.add_argument('--height', type=int, metavar='PX',
                        help='圖像高度 (2-1200)')
    parser.add_argument('--offset-x', type=int, metavar='PX',
                        help='X偏移')
    parser.add_argument('--offset-y', type=int, metavar='PX',
                        help='Y偏移')
    
    # Binning
    parser.add_argument('--binning', type=int, choices=[1, 2],
                        help='垂直像素合併 (1=正常, 2=靈敏度4倍但解析度減半)')
    
    # 顯示旋轉
    parser.add_argument('--rotate', '-r', type=int, choices=[0, 90, 180, 270],
                        help='旋轉畫面: 0=不旋轉, 90=向右旋轉90度, 180=旋轉180度, 270=向左旋轉90度')
    
    # 水平翻轉
    parser.add_argument('--flip', action='store_true',
                        help='水平翻轉畫面（鏡像，左右翻轉）')
    
    # 垂直翻轉
    parser.add_argument('--flip-v', action='store_true',
                        help='垂直翻轉畫面（上下翻轉）')
    
    # 顯示縮放
    parser.add_argument('--scale', '-s', type=str, metavar='VAL',
                        help='顯示縮放: auto=自動適應螢幕(預設), 或數字如0.5, 1.0, 1.5')
    
    # 自動保存
    parser.add_argument('--auto-save', type=int, metavar='SEC',
                        help='自動保存間隔（秒），例如 5 表示每5秒自動保存一次，0 = 禁用')
    
    # 預設模式
    parser.add_argument('--preset', '-p', type=int, choices=[0, 1, 2, 3, 4, 5],
                        help='預設模式: 0=自動, 1=直射, 2=小孔, 3=HDR, 4=弱光, 5=高速')
    
    # 自動模式
    parser.add_argument('--auto', '-a', action='store_true',
                        help='使用自動曝光和增益')
    
    # 其他
    parser.add_argument('--config', '-c', type=str, metavar='FILE',
                        default='camera_config.yaml',
                        help='配置文件路徑 (默認: camera_config.yaml)')
    parser.add_argument('--help-params', action='store_true',
                        help='顯示所有可調參數說明')
    
    args = parser.parse_args()
    
    # 顯示參數說明
    if args.help_params:
        print("=" * 70)
        print("FLIR Grasshopper3 可調參數說明")
        print("=" * 70)
        print("\n📸 曝光和增益:")
        print("  --exposure    曝光時間 (μs), 越大越亮, 範圍: 9-11526")
        print("  --gain        增益值 (dB), 越大越亮但噪點增加, 範圍: 0-24")
        print("  --auto        使用自動曝光和增益")
        print("\n🎨 像素格式:")
        print("  --format Mono8       8位灰階 (0-255), 最快最簡單 ⭐")
        print("  --format Mono16      16位灰階 (0-65535), 超高精度")
        print("  --format BayerRG8    8位彩色原始")
        print("  --format RGB8        8位RGB彩色")
        print("\n🎛️ 圖像質量:")
        print("  --gamma          Gamma校正 (0.5-4.0)")
        print("                   < 1.0 = 暗部提亮 (弱光用)")
        print("                   > 1.0 = 亮部壓暗 (避免過曝)")
        print("  --black-level    黑電平 (0-12.48), 降低可減少噪點")
        print("  --threshold      亮點檢測閾值 (0-255)")
        print("\n📐 ROI裁切 (提高速度):")
        print("  --width          圖像寬度 (32-1920)")
        print("  --height         圖像高度 (2-1200)")
        print("  --offset-x       X偏移")
        print("  --offset-y       Y偏移")
        print("\n⚡ 靈敏度增強:")
        print("  --binning 2      垂直像素合併, 靈敏度提升4倍但解析度減半")
        print("\n🔄 顯示調整:")
        print("  --rotate 90      向右旋轉90度 (橫向相機變豎向)")
        print("  --rotate 180     旋轉180度 (畫面上下顛倒)")
        print("  --rotate 270     向左旋轉90度 (豎向相機變橫向)")
        print("  --flip           水平翻轉（鏡像效果）")
        print("\n🎯 快速預設模式:")
        print("  --preset 0       自動模式")
        print("  --preset 1       手電筒直射 (500μs, 0dB)")
        print("  --preset 2       小光圈測試 (5000μs, 6dB) ⭐")
        print("  --preset 3       高動態範圍 (Mono16, 8000μs)")
        print("  --preset 4       弱光檢測 (35000μs, 18dB)")
        print("  --preset 5       高速捕捉 (2000μs, 22fps)")
        print("\n" + "=" * 70)
        return
    
    print("FLIR Grasshopper 相機預覽程式")
    print("=" * 40)
    
    # 檢查是否安裝了必要的庫
    try:
        import PySpin
        import cv2
        print("所需庫已安裝")
    except ImportError as e:
        print(f"缺少必要的庫: {e}")
        print("請安裝:")
        print("  pip install opencv-python")
        print("  並從FLIR官網下載並安裝PySpin")
        return
    
    # 載入配置文件
    config = None
    config_file = args.config
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"✓ 已載入配置文件: {config_file}")
        except Exception as e:
            print(f"⚠ 載入配置文件失敗: {e}")
            print("  將使用默認配置")
            config = None
    else:
        if config_file != 'camera_config.yaml':
            print(f"⚠ 未找到配置文件 {config_file}")
            return
        print(f"⚠ 未找到配置文件 {config_file}，使用默認配置")
    
    # 如果沒有配置，創建默認配置
    if config is None:
        config = {
            'camera': {'pixel_format': 'Mono8'},
            'exposure': {'mode': 'auto'},
            'gain': {'mode': 'auto'},
            'analysis': {'brightness_threshold': 200},
            'image': {},
            'resolution': {},
        }
    
    # 應用預設模式
    if args.preset is not None:
        from switch_config import PRESET_CONFIGS
        preset_key = str(args.preset)
        if preset_key in PRESET_CONFIGS:
            preset = PRESET_CONFIGS[preset_key]
            print(f"✓ 使用預設模式 [{args.preset}]: {preset['name']}")
            # 合併預設配置
            for section, values in preset['config'].items():
                if section not in config:
                    config[section] = {}
                if isinstance(values, dict):
                    config[section].update(values)
                else:
                    config[section] = values
    
    # 應用命令行參數（覆蓋配置文件和預設模式）
    if args.auto:
        config['exposure']['mode'] = 'auto'
        config['gain']['mode'] = 'auto'
        print("✓ 使用自動曝光和增益")
    
    if args.exposure is not None:
        config['exposure']['mode'] = 'manual'
        config['exposure']['time_us'] = args.exposure
        print(f"✓ 覆蓋曝光時間: {args.exposure} μs")
    
    if args.gain is not None:
        config['gain']['mode'] = 'manual'
        config['gain']['value_db'] = args.gain
        print(f"✓ 覆蓋增益值: {args.gain} dB")
    
    if args.format is not None:
        config['camera']['pixel_format'] = args.format
        print(f"✓ 覆蓋像素格式: {args.format}")
    
    if args.gamma is not None:
        if 'image' not in config:
            config['image'] = {}
        config['image']['gamma'] = args.gamma
        print(f"✓ 設置 Gamma: {args.gamma}")
    
    if args.black_level is not None:
        if 'image' not in config:
            config['image'] = {}
        config['image']['black_level'] = args.black_level
        print(f"✓ 設置黑電平: {args.black_level}")
    
    if args.threshold is not None:
        if 'analysis' not in config:
            config['analysis'] = {}
        config['analysis']['brightness_threshold'] = args.threshold
        print(f"✓ 設置亮點閾值: {args.threshold}")
    
    if args.width is not None or args.height is not None:
        if 'resolution' not in config:
            config['resolution'] = {}
        if 'roi' not in config['resolution']:
            config['resolution']['roi'] = {'enabled': True}
        if args.width:
            config['resolution']['roi']['width'] = args.width
        if args.height:
            config['resolution']['roi']['height'] = args.height
        if args.offset_x:
            config['resolution']['roi']['x'] = args.offset_x
        if args.offset_y:
            config['resolution']['roi']['y'] = args.offset_y
        print(f"✓ 設置 ROI")
    
    if args.binning is not None:
        if 'resolution' not in config:
            config['resolution'] = {}
        config['resolution']['binning_vertical'] = args.binning
        print(f"✓ 設置 Binning: {args.binning}")
    
    if args.rotate is not None:
        if 'display' not in config:
            config['display'] = {}
        config['display']['rotation'] = args.rotate
        rotation_text = {0: '不旋轉', 90: '向右旋轉90度', 180: '旋轉180度', 270: '向左旋轉90度'}
        print(f"✓ 設置旋轉: {rotation_text.get(args.rotate, str(args.rotate))}")
    
    if args.flip:
        if 'display' not in config:
            config['display'] = {}
        config['display']['flip_horizontal'] = True
        print(f"✓ 設置水平翻轉（左右翻轉）")
    
    if args.flip_v:
        if 'display' not in config:
            config['display'] = {}
        config['display']['flip_vertical'] = True
        print(f"✓ 設置垂直翻轉（上下翻轉）")
    
    if args.scale is not None:
        if 'display' not in config:
            config['display'] = {}
        # 判斷是 'auto' 還是數字
        if args.scale.lower() == 'auto':
            config['display']['scale'] = 'auto'
            print(f"✓ 設置縮放: 自動適應螢幕")
        else:
            try:
                scale_val = float(args.scale)
                if scale_val > 0:
                    config['display']['scale'] = scale_val
                    print(f"✓ 設置縮放: {scale_val}x")
                else:
                    print(f"⚠ 縮放值必須大於0，忽略")
            except ValueError:
                print(f"⚠ 無效的縮放值: {args.scale}，使用 auto 或數字如 0.5, 1.0")
    
    if args.auto_save is not None:
        if 'save' not in config:
            config['save'] = {}
        if args.auto_save >= 0:
            config['save']['auto_save_interval'] = args.auto_save
            if args.auto_save > 0:
                print(f"✓ 設置自動保存: 每 {args.auto_save} 秒保存一次")
            else:
                print(f"✓ 禁用自動保存")
        else:
            print(f"⚠ 自動保存間隔必須 >= 0，忽略")
    
    # 顯示最終配置
    print("\n當前配置:")
    if 'exposure' in config:
        exp_mode = config['exposure'].get('mode', 'N/A')
        print(f"  曝光模式: {exp_mode}")
        if exp_mode == 'manual':
            time_us = config['exposure'].get('time_us', 0)
            print(f"  曝光時間: {time_us} 微秒 ({time_us/1000:.2f} 毫秒)")
    
    if 'gain' in config:
        gain_mode = config['gain'].get('mode', 'N/A')
        print(f"  增益模式: {gain_mode}")
        if gain_mode == 'manual':
            gain_db = config['gain'].get('value_db', 0)
            print(f"  增益值: {gain_db} dB")
    
    if 'camera' in config:
        pixel_format = config['camera'].get('pixel_format', 'N/A')
        print(f"  像素格式: {pixel_format}")
    
    if 'image' in config and 'gamma' in config['image']:
        print(f"  Gamma: {config['image']['gamma']}")
    
    if 'display' in config and 'rotation' in config['display']:
        print(f"  旋轉: {config['display']['rotation']}度")
    
    if 'display' in config and config['display'].get('flip_horizontal', False):
        print(f"  水平翻轉: 是")
    
    # 創建並運行相機預覽
    camera_preview = FLIRCameraPreview(config)
    
    try:
        camera_preview.run()
    except KeyboardInterrupt:
        print("\n用戶中斷程式")
    except Exception as e:
        print(f"程式執行錯誤: {e}")
    finally:
        camera_preview.cleanup()

if __name__ == "__main__":
    main()
