#!/bin/bash
# FLIR 相機預覽程式啟動腳本
# 用法: ./run_camera.sh [參數]
# 範例: ./run_camera.sh --exposure 1000 --gain 10 --format Mono16

echo "正在啟動 FLIR 相機預覽程式..."
echo "========================================"

# 激活 spinnaker conda 環境
source /home/gram424/miniconda3/bin/activate spinnaker

# 設置 Qt 平台插件（避免 wayland 警告）
export QT_QPA_PLATFORM=xcb

# 運行預覽程式（傳遞所有參數）
cd /home/gram424/camera
python flir_camera_preview.py "$@"
