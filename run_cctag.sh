#!/bin/bash
# CCTag Marker 偵測啟動腳本
# 用法: ./run_cctag.sh [參數]
#
# 範例:
#   ./run_cctag.sh --flir                              # FLIR 相機，預設參數
#   ./run_cctag.sh --flir --max-seeds 100 --no-lmdif   # FLIR + 速度調優
#   ./run_cctag.sh --flir --downscale 0.5              # FLIR + 縮小輸入
#   ./run_cctag.sh --image photo.jpg                   # 靜態圖片
#   ./run_cctag.sh --webcam                            # USB webcam
#   ./run_cctag.sh -h                                  # 查看所有參數

echo "正在啟動 CCTag Marker 偵測..."
echo "========================================"

# 激活 spinnaker conda 環境
source /home/gram424/miniconda3/bin/activate spinnaker

# 設置 Qt 平台插件（避免 wayland 警告）
export QT_QPA_PLATFORM=xcb

# 確保 CCTag library 可被載入
export LD_LIBRARY_PATH="$HOME/miniconda3/lib:$LD_LIBRARY_PATH"

# 運行偵測程式（傳遞所有參數）
cd /home/gram424/camera
python cctag_detector.py "$@"
