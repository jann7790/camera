#!/usr/bin/env python3
"""
快速配置切換工具
用於快速切換不同的相機配置模式
"""
import yaml
import sys
import os

# 預設配置模式
PRESET_CONFIGS = {
    '1': {
        'name': '手電筒直射測試（避免過曝）',
        'description': '極短曝光，適合手電筒直接對準鏡頭',
        'config': {
            'exposure': {'mode': 'manual', 'time_us': 500},
            'gain': {'mode': 'manual', 'value_db': 0},
            'camera': {'pixel_format': 'Mono8'},
            'analysis': {'brightness_threshold': 250},
            'image': {'gamma': 1.0}
        }
    },
    '2': {
        'name': '小光圈手電筒測試（推薦）',
        'description': '平衡曝光，適合透過小光圈觀察',
        'config': {
            'exposure': {'mode': 'manual', 'time_us': 5000},
            'gain': {'mode': 'manual', 'value_db': 6},
            'camera': {'pixel_format': 'Mono8'},
            'analysis': {'brightness_threshold': 180},
            'image': {'gamma': 1.0}
        }
    },
    '3': {
        'name': '高動態範圍測試',
        'description': '16位深度，同時捕捉極亮和極暗',
        'config': {
            'camera': {'pixel_format': 'Mono16'},
            'exposure': {'mode': 'manual', 'time_us': 8000},
            'gain': {'mode': 'manual', 'value_db': 0},
            'image': {'gamma': 0.8},
            'analysis': {'brightness_threshold': 200}
        }
    },
    '4': {
        'name': '弱光檢測模式',
        'description': '長曝光高增益，檢測微弱光源',
        'config': {
            'exposure': {'mode': 'manual', 'time_us': 35000},
            'gain': {'mode': 'manual', 'value_db': 18},
            'camera': {'pixel_format': 'Mono8'},
            'image': {'gamma': 0.7},
            'analysis': {'brightness_threshold': 80}
        }
    },
    '5': {
        'name': '高速捕捉模式',
        'description': '快速幀率，適合運動物體',
        'config': {
            'frame_rate': {'enabled': True, 'target_fps': 22},
            'exposure': {'mode': 'manual', 'time_us': 2000},
            'gain': {'mode': 'manual', 'value_db': 12},
            'resolution': {'binning_vertical': 2}
        }
    },
    '0': {
        'name': '自動模式（默認）',
        'description': '相機自動調整曝光和增益',
        'config': {
            'exposure': {'mode': 'auto'},
            'gain': {'mode': 'auto'},
            'camera': {'pixel_format': 'BayerRG8'}
        }
    }
}

def load_current_config(config_file='camera_config.yaml'):
    """載入當前配置"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"配置文件 {config_file} 不存在")
        return None
    except Exception as e:
        print(f"載入配置文件錯誤: {e}")
        return None

def merge_config(base_config, preset_config):
    """合併預設配置到基礎配置"""
    if base_config is None:
        return preset_config
    
    result = base_config.copy()
    
    for section, values in preset_config.items():
        if section not in result:
            result[section] = {}
        if isinstance(values, dict):
            result[section].update(values)
        else:
            result[section] = values
    
    return result

def save_config(config, config_file='camera_config.yaml'):
    """保存配置文件"""
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        print(f"保存配置文件錯誤: {e}")
        return False

def show_menu():
    """顯示選單"""
    print("=" * 70)
    print("FLIR 相機配置切換工具")
    print("=" * 70)
    print("\n可用的預設配置:\n")
    
    for key in sorted(PRESET_CONFIGS.keys()):
        preset = PRESET_CONFIGS[key]
        print(f"  [{key}] {preset['name']}")
        print(f"      {preset['description']}\n")
    
    print("  [c] 顯示當前配置")
    print("  [b] 備份當前配置")
    print("  [r] 恢復默認配置")
    print("  [q] 退出")
    print("\n" + "=" * 70)

def show_current_config(config):
    """顯示當前配置的關鍵參數"""
    print("\n" + "=" * 70)
    print("當前配置:")
    print("=" * 70)
    
    if 'camera' in config and 'pixel_format' in config['camera']:
        print(f"像素格式: {config['camera']['pixel_format']}")
    
    if 'exposure' in config:
        print(f"曝光模式: {config['exposure'].get('mode', 'N/A')}")
        if config['exposure'].get('mode') == 'manual':
            time_us = config['exposure'].get('time_us', 0)
            print(f"曝光時間: {time_us} 微秒 ({time_us/1000:.2f} 毫秒)")
    
    if 'gain' in config:
        print(f"增益模式: {config['gain'].get('mode', 'N/A')}")
        if config['gain'].get('mode') == 'manual':
            print(f"增益值: {config['gain'].get('value_db', 0)} dB")
    
    if 'analysis' in config:
        print(f"亮點閾值: {config['analysis'].get('brightness_threshold', 200)}")
    
    if 'image' in config and config['image'].get('gamma'):
        print(f"Gamma: {config['image']['gamma']}")
    
    print("=" * 70 + "\n")

def backup_config(config_file='camera_config.yaml'):
    """備份配置文件"""
    import shutil
    from datetime import datetime
    
    if not os.path.exists(config_file):
        print("配置文件不存在，無法備份")
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"camera_config_backup_{timestamp}.yaml"
    
    try:
        shutil.copy(config_file, backup_file)
        print(f"✓ 配置已備份到: {backup_file}")
        return True
    except Exception as e:
        print(f"✗ 備份失敗: {e}")
        return False

def main():
    config_file = 'camera_config.yaml'
    
    while True:
        show_menu()
        
        choice = input("\n請選擇 [0-5/c/b/r/q]: ").strip().lower()
        
        if choice == 'q':
            print("退出")
            break
        
        elif choice == 'c':
            config = load_current_config(config_file)
            if config:
                show_current_config(config)
            input("按 Enter 繼續...")
        
        elif choice == 'b':
            backup_config(config_file)
            input("按 Enter 繼續...")
        
        elif choice == 'r':
            confirm = input("確定要恢復默認配置嗎？ [y/N]: ").strip().lower()
            if confirm == 'y':
                # 這裡可以實現恢復默認配置的邏輯
                print("請手動編輯配置文件或從備份恢復")
            input("按 Enter 繼續...")
        
        elif choice in PRESET_CONFIGS:
            preset = PRESET_CONFIGS[choice]
            print(f"\n正在應用配置: {preset['name']}")
            
            # 載入當前配置
            current_config = load_current_config(config_file)
            if current_config is None:
                print("無法載入當前配置，使用預設配置")
                current_config = {}
            
            # 合併配置
            new_config = merge_config(current_config, preset['config'])
            
            # 顯示將要應用的配置
            print("\n將應用以下配置:")
            for section, values in preset['config'].items():
                print(f"  {section}: {values}")
            
            confirm = input(f"\n確定要應用此配置嗎？ [Y/n]: ").strip().lower()
            if confirm in ['', 'y', 'yes']:
                if save_config(new_config, config_file):
                    print(f"✓ 配置已更新")
                    print(f"✓ 現在可以運行: ./run_camera.sh")
                    show_current_config(new_config)
                else:
                    print("✗ 配置保存失敗")
            else:
                print("已取消")
            
            input("按 Enter 繼續...")
        
        else:
            print("無效選擇，請重試")
            input("按 Enter 繼續...")
        
        # 清屏（可選）
        os.system('clear' if os.name == 'posix' else 'cls')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用戶中斷，退出")
        sys.exit(0)
