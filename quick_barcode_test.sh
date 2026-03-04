#!/bin/bash
# Barcode 快速測試套件
# 預定義幾組適合 Barcode 識別的參數配置

echo "========================================================================"
echo "                    Barcode 快速測試套件"
echo "========================================================================"
echo ""
echo "這個腳本會依序測試 4 組預設配置，幫助您快速找到最佳參數"
echo ""
echo "測試組合："
echo "  1. 短曝光低增益 (防過曝) - 適合高亮度 LCD"
echo "  2. 中曝光中增益 (平衡)   - 大多數情況推薦"
echo "  3. 較長曝光中增益        - 較暗 LCD 或小孔徑"
echo "  4. 16位高精度           - 需要最佳對比度"
echo ""
echo "========================================================================"
echo ""

# 激活 spinnaker conda 環境
source /home/gram424/miniconda3/bin/activate spinnaker

# 設置 Qt 平台插件
export QT_QPA_PLATFORM=xcb

# 進入相機目錄
cd /home/gram424/camera

# 測試函數
run_test() {
    local test_num=$1
    local description=$2
    local exposure=$3
    local gain=$4
    local format=$5
    
    echo ""
    echo "------------------------------------------------------------------------"
    echo "測試 $test_num: $description"
    echo "------------------------------------------------------------------------"
    echo "參數: 曝光=${exposure}μs, 增益=${gain}dB, 格式=${format}"
    echo ""
    echo "按下 's' 鍵保存圖像並分析"
    echo "按下 'q' 鍵結束此測試並繼續下一個"
    echo "按下 Ctrl+C 退出所有測試"
    echo ""
    read -p "按 Enter 開始測試 $test_num..."
    
    python flir_camera_preview.py --exposure $exposure --gain $gain --format $format
    
    echo ""
    echo "測試 $test_num 完成"
    echo ""
}

# 執行測試
echo "準備開始測試..."
sleep 1

# 測試 1: 短曝光低增益 (防過曝)
run_test 1 "短曝光低增益 (防過曝)" 1000 0 Mono8

# 測試 2: 中曝光中增益 (平衡) - 推薦作為起點
run_test 2 "中曝光中增益 (平衡) ⭐" 2000 3 Mono8

# 測試 3: 較長曝光中增益
run_test 3 "較長曝光中增益" 3000 6 Mono8

# 測試 4: 16位高精度
run_test 4 "16位高精度 (最佳對比)" 2000 3 Mono16

# 完成
echo "========================================================================"
echo "                        所有測試完成！"
echo "========================================================================"
echo ""
echo "根據您的觀察結果："
echo ""
echo "如果畫面..."
echo "  - 太亮/過曝 → 減少曝光時間或增益"
echo "  - 太暗       → 增加曝光時間或增益"
echo "  - 對比度不足 → 調整 Gamma 或使用 Mono16"
echo "  - 噪點太多   → 減少增益，增加曝光時間"
echo ""
echo "建議下一步："
echo "  1. 如果找到合適的參數，可以編輯 camera_config.yaml 永久保存"
echo "  2. 或使用: ./run_camera.sh --exposure <值> --gain <值>"
echo "  3. 如果需要更精確的參數，運行自動搜索:"
echo "     python barcode_search.py"
echo ""
echo "========================================================================"
