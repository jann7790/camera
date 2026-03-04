#!/bin/bash
# 啟動實時 Barcode 參數調整工具

echo "========================================================================"
echo "            實時 Barcode 參數調整工具"
echo "========================================================================"
echo ""
echo "這個工具可以讓您即時調整曝光和增益參數"
echo "用肉眼觀察 Barcode 清晰度，找到最佳設定"
echo ""
echo "鍵盤控制："
echo "  W/S: 曝光 +/- (大步進: 1000 μs)"
echo "  A/D: 增益 +/- (大步進: 3 dB)"
echo "  I/K: 曝光 +/- (小步進: 100 μs)"
echo "  J/L: 增益 +/- (小步進: 0.5 dB)"
echo ""
echo "  SPACE: 保存當前配置"
echo "  R: 重置為默認值"
echo "  Q: 退出"
echo ""
echo "顏色提示："
echo "  🟢 綠色 = 理想範圍"
echo "  🟠 橙色 = 可接受"
echo "  🔴 紅色 = 需要調整"
echo ""
echo "常用參數："
echo "  --rotate 90           向右旋轉90度"
echo "  --rotate 180          旋轉180度"
echo "  --rotate 270          向左旋轉90度"
echo "  --flip                水平翻轉（鏡像）"
echo "  --flip-v              垂直翻轉（上下翻轉）"
echo "  --exposure 5000       設定初始曝光（微秒）"
echo "  --gain 6              設定初始增益（分貝）"
echo ""
echo "========================================================================"
echo ""

# 激活 spinnaker conda 環境
source /home/gram424/miniconda3/bin/activate spinnaker

# 設置 Qt 平台插件
export QT_QPA_PLATFORM=xcb

# 進入相機目錄
cd /home/gram424/camera

# 檢查參數
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    python live_barcode_tuner.py --help
    exit 0
fi

# 運行工具
if [ -z "$1" ]; then
    # 使用默認值
    python live_barcode_tuner.py
else
    # 傳遞所有參數
    python live_barcode_tuner.py "$@"
fi

echo ""
echo "========================================================================"
echo "已退出實時調參工具"
echo "========================================================================"
