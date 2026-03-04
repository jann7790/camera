# Barcode 參數搜索工具套件

針對透過小孔觀察 LCD 螢幕上 Barcode 的場景，自動搜索最佳的相機曝光和增益參數。

## 📦 工具清單

### 核心工具

1. **`barcode_search.py`** - 自動參數搜索器
   - 自動測試多組曝光/增益組合
   - 針對 Barcode 優化的評分算法
   - 生成完整的測試結果

2. **`quick_barcode_test.sh`** - 快速測試腳本
   - 4 組預設配置快速測試
   - 即時視覺反饋
   - 手動選擇最佳參數

3. **`visualize_results.py`** - 結果可視化
   - 生成精美的 HTML 報告
   - 圖像對比和指標分析
   - 互動式結果查看

4. **`apply_best_config.sh`** - 一鍵應用配置
   - 自動應用最佳參數到配置文件
   - 自動備份原配置
   - 安全的配置管理

## 🚀 快速開始

### 方案 A：自動搜索（推薦）

適合想要找到最優參數的用戶。

```bash
# 1. 運行自動搜索（5-10 分鐘）
python barcode_search.py

# 2. 查看 HTML 報告
python visualize_results.py
firefox results/report.html

# 3. 應用最佳配置
./apply_best_config.sh

# 4. 運行相機驗證
./run_camera.sh
```

### 方案 B：快速手動測試

適合想要快速嘗試幾組預設的用戶。

```bash
# 運行快速測試（依序測試 4 組預設）
./quick_barcode_test.sh

# 根據視覺效果選擇最佳的一組
# 然後手動設置：
./run_camera.sh --exposure <選定的值> --gain <選定的值>
```

## 📖 詳細使用說明

### 1. 自動參數搜索

**基本用法：**
```bash
# 快速搜索（預設：24 組測試）
python barcode_search.py

# 精細搜索（更多測試點）
python barcode_search.py --fine

# 自定義搜索範圍
python barcode_search.py --exposure 500,1000,2000,5000 --gain 0,3,6,9
```

**輸出：**
- `results/images/` - 所有測試圖像
- `results/search_results.json` - 完整測試數據
- `results/best_config.yaml` - 最佳配置

**評分指標：**
- **對比度** (40%)：白條與黑條的亮度差
- **範圍評分** (30%)：白條和黑條是否在理想範圍
- **邊緣清晰度** (20%)：條碼邊界的清晰程度
- **曝光懲罰** (10%)：過曝和欠曝的懲罰

### 2. 結果可視化

```bash
# 生成 HTML 報告
python visualize_results.py

# 指定輸出位置
python visualize_results.py --output my_report.html

# 在瀏覽器中查看
firefox results/report.html
```

**報告內容：**
- 搜索概覽（測試數量、參數範圍）
- Top 5 最佳配置詳情
- 每組配置的圖像和指標
- 完整結果表格
- 一鍵應用命令

### 3. 應用配置

```bash
# 自動應用最佳配置
./apply_best_config.sh

# 配置會自動備份到 camera_config_backup_<時間戳>.yaml
```

### 4. 快速測試

```bash
# 依序測試 4 組預設配置
./quick_barcode_test.sh
```

測試組合：
1. **短曝光低增益** (1000μs, 0dB) - 高亮度 LCD
2. **中曝光中增益** (2000μs, 3dB) - 平衡配置 ⭐
3. **長曝光中增益** (3000μs, 6dB) - 較暗場景
4. **16位高精度** (2000μs, 3dB, Mono16) - 最佳對比度

## 🎯 參數調整指南

### 曝光時間 (Exposure Time)
- **範圍**: 9 - 11526 μs
- **效果**: 越大越亮，但會降低幀率
- **建議**: 
  - 亮 LCD: 500-2000 μs
  - 普通 LCD: 2000-5000 μs
  - 暗 LCD: 5000-10000 μs

### 增益 (Gain)
- **範圍**: 0 - 24 dB
- **效果**: 越大越亮，但噪點增加
- **建議**:
  - 優先畫質: 0-6 dB
  - 平衡模式: 6-12 dB
  - 極暗環境: 12-18 dB

### 像素格式 (Pixel Format)
- **Mono8**: 8位灰階，速度快，適合大多數情況 ⭐
- **Mono16**: 16位灰階，動態範圍更大，適合高對比度需求

### Gamma
- **範圍**: 0.5 - 4.0
- **效果**:
  - < 1.0: 提亮暗部（暗處更清晰）
  - = 1.0: 線性（預設）
  - > 1.0: 壓暗亮部（防止過曝）

## 📊 理解評分結果

### 對比度 (Contrast)
- **理想值**: > 150
- **計算**: 白條平均值 - 黑條平均值
- **重要性**: 對比度越高，條碼越容易識別

### 白條平均 (White Mean)
- **理想範圍**: 180-240
- **過高** (>250): 可能過曝
- **過低** (<180): 亮度不足

### 黑條平均 (Black Mean)
- **理想範圍**: 20-60
- **過高** (>60): 對比度不足
- **過低** (<20): 可能欠曝

### 過曝率 (Overexposed Ratio)
- **理想值**: < 5%
- **含義**: 像素值 = 255 的比例
- **影響**: 過曝區域失去細節

### 邊緣評分 (Edge Score)
- **範圍**: 0-100
- **含義**: 邊緣清晰度
- **影響**: 影響條碼邊界識別

## 🔧 常見問題

### Q1: 搜索時間太長？
```bash
# 使用快速模式（預設已是快速模式）
python barcode_search.py

# 或手動指定更少的測試點
python barcode_search.py --exposure 1000,2000,5000 --gain 0,6
```

### Q2: 圖像太暗？
- 增加曝光時間：`--exposure 5000`
- 或增加增益：`--gain 12`
- 或兩者都增加

### Q3: 圖像太亮/過曝？
- 減少曝光時間：`--exposure 1000`
- 或減少增益：`--gain 0`

### Q4: 對比度不足？
- 嘗試 Mono16 格式：`--format Mono16`
- 調整 Gamma：`--gamma 0.8`

### Q5: 噪點太多？
- 減少增益，增加曝光時間
- 例如：從 `exposure=2000, gain=12` 改為 `exposure=5000, gain=6`

### Q6: 如何恢復原配置？
```bash
# 配置會自動備份為 camera_config_backup_<時間戳>.yaml
cp camera_config_backup_20260209_123456.yaml camera_config.yaml
```

## 📁 文件結構

```
camera/
├── barcode_search.py          # 自動搜索腳本
├── quick_barcode_test.sh      # 快速測試腳本
├── visualize_results.py       # 結果可視化
├── apply_best_config.sh       # 應用配置
├── README_barcode_tools.md    # 本文件
├── results/                   # 搜索結果目錄
│   ├── images/               # 測試圖像
│   ├── search_results.json   # 測試數據
│   ├── best_config.yaml      # 最佳配置
│   └── report.html           # HTML 報告
└── camera_config.yaml         # 主配置文件
```

## 🎓 進階技巧

### 針對特定場景優化

**高亮度 LCD：**
```bash
python barcode_search.py --exposure 500,1000,1500 --gain 0,3
```

**低亮度 LCD：**
```bash
python barcode_search.py --exposure 5000,8000,10000 --gain 6,9,12
```

**極小孔徑：**
```bash
python barcode_search.py --exposure 10000,15000,20000 --gain 12,15,18 --fine
```

### 二次精細搜索

如果粗搜索找到最佳值在 `exposure=2000, gain=3`，可以進行精細搜索：

```bash
python barcode_search.py --exposure 1500,1750,2000,2250,2500 --gain 2,3,4
```

### 批次測試不同場景

```bash
# 場景 1: 亮 LCD
python barcode_search.py --exposure 500,1000,2000 --gain 0,3 --output results_bright

# 場景 2: 暗 LCD
python barcode_search.py --exposure 5000,8000,10000 --gain 6,9 --output results_dim

# 比較結果
python visualize_results.py --input results_bright --output report_bright.html
python visualize_results.py --input results_dim --output report_dim.html
```

## 💡 最佳實踐

1. **先快速後精細**：使用預設快速搜索，再針對最佳值周圍精細搜索

2. **優先曝光時間**：在噪點可接受的前提下，優先使用較長曝光而非高增益

3. **記錄場景**：不同 LCD 亮度/孔徑大小可能需要不同配置，建議記錄

4. **定期驗證**：光源或環境變化時，重新運行搜索

5. **備份配置**：找到好的配置後，手動備份一份

## 📞 支援

如遇到問題：
1. 檢查相機連接：`./run_camera.sh --help-params`
2. 查看錯誤日誌
3. 確認 PySpin 和 OpenCV 已正確安裝

---

**Happy Parameter Tuning! 🎯📷**
