#!/bin/bash
# CCTag Marker 偵測啟動腳本

show_help() {
    cat << 'EOF'
用法:
  ./scripts/run_cctag.sh [參數]

常用範例:
  ./scripts/run_cctag.sh --flir
  ./scripts/run_cctag.sh --flir --flip                    # 只左右翻轉 preview
  ./scripts/run_cctag.sh --flir --fast                    # 速度最優 preset
  ./scripts/run_cctag.sh --flir --fast --downscale 0.5   # 速度最優 + 縮圖偵測
  ./scripts/run_cctag.sh --flir --max-seeds 100 --no-lmdif
  ./scripts/run_cctag.sh --flir --downscale 0.5
  ./scripts/run_cctag.sh --flir --display-skip 3         # 每 3 幀才更新視窗
  ./scripts/run_cctag.sh --image photo.jpg
  ./scripts/run_cctag.sh --webcam

速度優化說明:
  --fast              自動套用速度最優參數組合：
                        --max-seeds 80 --max-candidates 10 --cuts-trials 80
                        --multires-layers 2
  --flip              只將 preview 左右翻轉（鏡像），不影響實際偵測。
  --display-skip N    每 N 幀才更新視窗（預設 2）。detect 每幀跑，
                      只有顯示降頻，可降低 X11/GPU 負擔。
  --downscale F       偵測前縮小倍率（如 0.5），可大幅加速 CCTag 本身。

說明:
  此腳本會啟動 conda 環境並轉呼叫 src/cctag_detector.py。
  其餘參數皆原樣傳遞給 cctag_detector.py。
  FLIR 預設設定讀取 camera_config.yaml（預設手動增益為 15 dB）。

完整參數:
  ./scripts/run_cctag.sh --help
  ./scripts/run_cctag.sh --flir --help
EOF
}

# ── 解析 --fast，展開為具體參數 ───────────────────────────────────────────────
FAST_FLAGS=""
PASS_ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        show_help
        exit 0
    elif [[ "$arg" == "--fast" ]]; then
        FAST_FLAGS="--max-seeds 80 --max-candidates 10 --cuts-trials 80 --multires-layers 2"
    else
        PASS_ARGS+=("$arg")
    fi
done

echo "正在啟動 CCTag Marker 偵測..."
if [[ -n "$FAST_FLAGS" ]]; then
    echo "[fast] 套用速度最優參數: $FAST_FLAGS"
fi
echo "========================================"

# 激活 spinnaker conda 環境
source /home/gram424/miniconda3/bin/activate spinnaker

# 設置 Qt 平台插件（避免 wayland 警告）
export QT_QPA_PLATFORM=xcb

# 專案根目錄
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# 確保 CCTag library 和 Python binding 可被載入
export LD_LIBRARY_PATH="$PROJECT_DIR/lib:$HOME/miniconda3/lib:$LD_LIBRARY_PATH"
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"

# 運行偵測程式（--fast 已展開，其餘參數原樣傳遞）
cd "$PROJECT_DIR"
python src/cctag_detector.py "${PASS_ARGS[@]}" $FAST_FLAGS
