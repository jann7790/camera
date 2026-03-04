#!/bin/bash
# Barcode 參數搜索工具 - 快速入門
# 這個腳本會引導您完成整個流程

# 專案根目錄
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$PROJECT_DIR/scripts"
cd "$PROJECT_DIR"

clear

cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║              🎯 Barcode 參數搜索工具套件 - 快速入門                    ║
║                                                                       ║
║   針對透過小孔觀察 LCD 螢幕 Barcode 的場景                             ║
║   自動找到最佳的相機曝光和增益參數                                      ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝

EOF

echo ""
echo "請選擇您想要的操作："
echo ""
echo "  1) 👁️  實時調參（用肉眼找最佳參數）⭐ 推薦！"
echo "  2) 🚀 自動參數搜索（全自動，5-10分鐘）"
echo "  3) ⚡ 快速手動測試（4組預設配置）"
echo "  4) 📊 查看上次搜索結果"
echo "  5) ✅ 應用最佳配置到相機"
echo "  6) 📖 查看完整使用說明"
echo "  7) ❌ 退出"
echo ""

read -p "請輸入選項 [1-7]: " choice

case $choice in
    1)
        echo ""
        echo "========================================================================="
        echo "  實時參數調整工具"
        echo "========================================================================="
        echo ""
        echo "這個工具讓您即時調整曝光和增益，用肉眼觀察 Barcode 清晰度"
        echo ""
        echo "鍵盤控制："
        echo "  W/S: 曝光 +/- (大步進)"
        echo "  A/D: 增益 +/- (大步進)"
        echo "  I/K: 曝光 +/- (小步進)"
        echo "  J/L: 增益 +/- (小步進)"
        echo "  SPACE: 保存配置"
        echo "  Q: 退出"
        echo ""
        read -p "按 Enter 開始..."
        
        "$SCRIPT_DIR/run_live_tuner.sh"
        ;;
        
    2)
        echo ""
        echo "========================================================================="
        echo "  運行自動參數搜索"
        echo "========================================================================="
        echo ""
        echo "即將測試 24 組參數組合："
        echo "  - 曝光時間：500, 1000, 2000, 3000, 5000, 8000 μs"
        echo "  - 增益：0, 3, 6, 9 dB"
        echo ""
        echo "預計耗時：5-10 分鐘"
        echo ""
        read -p "按 Enter 開始，或 Ctrl+C 取消..."
        
        # 激活環境
        source /home/gram424/miniconda3/bin/activate spinnaker
        export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"
        
        # 運行搜索
        python src/barcode_search.py
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "========================================================================="
            echo "✓ 搜索完成！"
            echo "========================================================================="
            echo ""
            read -p "是否要查看 HTML 報告？[Y/n] " view_report
            
            if [[ ! $view_report =~ ^[Nn]$ ]]; then
                python src/visualize_results.py
                
                # 嘗試打開瀏覽器
                if command -v firefox &> /dev/null; then
                    firefox results/report.html &
                elif command -v google-chrome &> /dev/null; then
                    google-chrome results/report.html &
                else
                    echo "請手動打開: results/report.html"
                fi
            fi
            
            echo ""
            read -p "是否要立即應用最佳配置？[Y/n] " apply_config
            
            if [[ ! $apply_config =~ ^[Nn]$ ]]; then
                "$SCRIPT_DIR/apply_best_config.sh"
            fi
        fi
        ;;
    
    3)
        echo ""
        echo "========================================================================="
        echo "  快速手動測試"
        echo "========================================================================="
        echo ""
        echo "即將依序測試 4 組預設配置"
        echo "請觀察每組的效果，選擇最佳的一組"
        echo ""
        read -p "按 Enter 開始..."
        
        "$SCRIPT_DIR/quick_barcode_test.sh"
        ;;
        
    4)
        echo ""
        echo "========================================================================="
        echo "  查看搜索結果"
        echo "========================================================================="
        echo ""
        
        if [ -f "results/search_results.json" ]; then
            echo "正在生成 HTML 報告..."
            source /home/gram424/miniconda3/bin/activate spinnaker
            export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"
            python src/visualize_results.py
            
            # 嘗試打開瀏覽器
            if command -v firefox &> /dev/null; then
                firefox results/report.html &
                echo "已在 Firefox 中打開報告"
            elif command -v google-chrome &> /dev/null; then
                google-chrome results/report.html &
                echo "已在 Chrome 中打開報告"
            else
                echo "請手動打開: results/report.html"
            fi
        else
            echo "❌ 找不到搜索結果"
            echo "請先運行: python barcode_search.py"
        fi
        
        echo ""
        read -p "按 Enter 繼續..."
        ;;
        
    5)
        echo ""
        echo "========================================================================="
        echo "  應用最佳配置"
        echo "========================================================================="
        echo ""
        
        if [ -f "results/best_config.yaml" ]; then
            "$SCRIPT_DIR/apply_best_config.sh"
        else
            echo "❌ 找不到最佳配置"
            echo "請先運行參數搜索: python barcode_search.py"
        fi
        
        echo ""
        read -p "按 Enter 繼續..."
        ;;
        
    6)
        echo ""
        echo "========================================================================="
        echo "  使用說明"
        echo "========================================================================="
        echo ""
        
        if [ -f "docs/README_barcode_tools.md" ]; then
            if command -v less &> /dev/null; then
                less docs/README_barcode_tools.md
            else
                cat docs/README_barcode_tools.md | more
            fi
        else
            echo "❌ 找不到說明文件"
        fi
        ;;
        
    7)
        echo ""
        echo "再見！"
        exit 0
        ;;
        
    *)
        echo ""
        echo "❌ 無效選項"
        exit 1
        ;;
esac

echo ""
echo "操作完成！"
