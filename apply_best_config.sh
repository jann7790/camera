#!/bin/bash
# 一鍵應用最佳配置
# 讀取搜索結果並將最佳參數應用到 camera_config.yaml

echo "========================================================================"
echo "            應用最佳 Barcode 參數配置"
echo "========================================================================"
echo ""

# 檢查結果文件是否存在
BEST_CONFIG="results/best_config.yaml"
CURRENT_CONFIG="camera_config.yaml"

if [ ! -f "$BEST_CONFIG" ]; then
    echo "❌ 找不到最佳配置文件: $BEST_CONFIG"
    echo ""
    echo "請先運行參數搜索:"
    echo "  python barcode_search.py"
    echo ""
    exit 1
fi

# 備份當前配置
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="camera_config_backup_${TIMESTAMP}.yaml"

echo "1. 備份當前配置..."
cp "$CURRENT_CONFIG" "$BACKUP_FILE"
echo "   ✓ 已備份到: $BACKUP_FILE"
echo ""

# 顯示最佳配置
echo "2. 最佳配置內容:"
echo "------------------------------------------------------------------------"
cat "$BEST_CONFIG"
echo "------------------------------------------------------------------------"
echo ""

# 詢問確認
read -p "是否要應用此配置？[Y/n] " -r REPLY
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo "❌ 已取消"
    exit 0
fi

# 應用配置
echo "3. 應用配置..."

# 使用 Python 合併配置（保留其他設定）
python3 << 'EOF'
import yaml
import sys

try:
    # 載入最佳配置
    with open('results/best_config.yaml', 'r', encoding='utf-8') as f:
        best_config = yaml.safe_load(f)
    
    # 載入當前配置
    with open('camera_config.yaml', 'r', encoding='utf-8') as f:
        current_config = yaml.safe_load(f)
    
    # 合併配置（最佳配置覆蓋當前配置）
    for section, values in best_config.items():
        if section not in current_config:
            current_config[section] = {}
        if isinstance(values, dict):
            current_config[section].update(values)
        else:
            current_config[section] = values
    
    # 保存更新後的配置
    with open('camera_config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(current_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print("   ✓ 配置已更新")
    
    # 顯示關鍵參數
    print("\n4. 已應用的參數:")
    print(f"   曝光時間: {best_config['exposure']['time_us']} μs")
    print(f"   增益值: {best_config['gain']['value_db']} dB")
    print(f"   像素格式: {best_config['camera']['pixel_format']}")
    
except Exception as e:
    print(f"   ❌ 錯誤: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 應用配置失敗，正在恢復備份..."
    cp "$BACKUP_FILE" "$CURRENT_CONFIG"
    echo "   ✓ 已恢復原配置"
    exit 1
fi

echo ""
echo "========================================================================"
echo "✓ 配置應用成功！"
echo "========================================================================"
echo ""
echo "下一步："
echo "  運行相機查看效果:"
echo "    ./run_camera.sh"
echo ""
echo "  如果需要恢復原配置:"
echo "    cp $BACKUP_FILE camera_config.yaml"
echo ""
echo "========================================================================"
