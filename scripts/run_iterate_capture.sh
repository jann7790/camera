#!/bin/bash
# 啟動參數迭代拍攝工具

echo "========================================================================"
echo "            自動迭代參數拍攝工具"
echo "========================================================================"
echo ""
echo "這個工具會自動測試多組曝光和增益參數組合"
echo "並保存每組參數的圖像，方便比較"
echo ""
echo "========================================================================"
echo ""

# 激活 spinnaker conda 環境
source /home/gram424/miniconda3/bin/activate spinnaker

# 設置 Qt 平台插件
export QT_QPA_PLATFORM=xcb

# 專案根目錄
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"
cd "$PROJECT_DIR"

# 檢查參數
if [ "$1" == "--help" ] || [ "$1" == "-h" ] || [ -z "$1" ]; then
    python src/iterate_capture.py --help
    exit 0
fi

# 運行工具
python src/iterate_capture.py "$@"

echo ""
echo "========================================================================"
echo "已完成參數迭代拍攝"
echo "========================================================================"
