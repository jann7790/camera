# 自動定時保存功能

## 功能說明

相機預覽程式現在支援**自動定時保存**功能，可以每隔指定的秒數自動保存當前圖像，無需手動按 's' 鍵。

## 使用方法

### 方法 1: 配置文件

編輯 `camera_config.yaml`:

```yaml
save:
  auto_save_interval: 5  # 每5秒自動保存一次
  # auto_save_interval: 0  # 0 = 禁用自動保存（預設）
```

### 方法 2: 命令行參數

```bash
# 每5秒自動保存一次
./run_camera.sh --auto-save 5

# 每10秒自動保存一次
./run_camera.sh --auto-save 10

# 每1秒自動保存一次（快速連續保存）
./run_camera.sh --auto-save 1

# 禁用自動保存
./run_camera.sh --auto-save 0
```

### 完整使用示例

```bash
# 每5秒自動保存 + 旋轉90度 + 自動縮放
./run_camera.sh --auto-save 5 -r 90 -e 5000 -g 0

# 每3秒自動保存 + Mono16格式 + 8秒曝光
./run_camera.sh --auto-save 3 -f Mono16 -e 8000

# 快速保存測試（每秒保存）
./run_camera.sh --auto-save 1 -e 5000
```

## 保存的內容

### 每次自動保存會創建 4 個文件：

1. **`flir_preview_YYYYMMDD_HHMMSS.jpg`** - 預覽圖像（有損壓縮）
2. **`flir_raw_YYYYMMDD_HHMMSS.png`** 或 `.tiff` - 原始數據（無損）
3. **`flir_raw_YYYYMMDD_HHMMSS.npy`** - NumPy 數組（完整數據）
4. **`flir_meta_YYYYMMDD_HHMMSS.txt`** - 元數據信息

### 可選：分析報告

如果配置文件中啟用了 `auto_analyze_on_save: true`，還會生成：

5. **`flir_analysis_YYYYMMDD_HHMMSS.txt`** - 像素分析報告

配置方式：
```yaml
analysis:
  auto_analyze_on_save: true  # 自動保存時生成分析報告
  brightness_threshold: 200
```

## 運行時提示

啟動時會顯示：
```
✓ 自動保存已啟用: 每 5 秒保存一次
按下 'q' 鍵退出，'s' 鍵保存圖像並分析像素值，'a' 鍵分析當前幀
```

每次自動保存時會顯示：
```
[自動保存 #1] 正在保存圖像...
✓ 預覽圖像: saved_images/flir_preview_20260205_123456.jpg
✓ 原始數據 (PNG 8-bit): saved_images/flir_raw_20260205_123456.png
✓ NumPy 數組: saved_images/flir_raw_20260205_123456.npy
✓ 元數據: saved_images/flir_meta_20260205_123456.txt

[自動保存 #2] 正在保存圖像...
✓ 預覽圖像: saved_images/flir_preview_20260205_123501.jpg
...
```

## 實用場景

### 場景 1: 長時間監控
```bash
# 每10分鐘保存一次，持續監控
./run_camera.sh --auto-save 600 -e 5000
```

### 場景 2: 快速序列拍攝
```bash
# 每秒保存一次，快速捕捉變化
./run_camera.sh --auto-save 1 -e 3000
```

### 場景 3: 定時採樣
```bash
# 每30秒保存一次，長期數據採集
./run_camera.sh --auto-save 30 -f Mono16 -e 8000
```

### 場景 4: 實驗記錄
```bash
# 每5秒保存 + 自動分析
./run_camera.sh --auto-save 5 -e 5000 -g 0
# 確保 camera_config.yaml 中 auto_analyze_on_save: true
```

## 注意事項

### 1. 磁碟空間
- 每次保存約 4-9 MB（取決於像素格式）
- 每秒保存 = 每分鐘 240-540 MB
- 每5秒保存 = 每分鐘 48-108 MB
- 每10秒保存 = 每分鐘 24-54 MB

**建議：** 根據可用磁碟空間選擇合適的間隔

### 2. 性能影響
- 自動保存會在後台執行
- 保存 4 個文件需要約 0.1-0.3 秒
- 如果間隔太短（如 1 秒），可能會影響預覽流暢度
- **建議最小間隔：** 2-3 秒

### 3. 文件命名
- 使用時間戳命名，確保不會覆蓋
- 格式：`YYYYMMDD_HHMMSS`（年月日_時分秒）
- 例如：`flir_raw_20260205_143025.npy`

### 4. 手動保存仍可用
- 自動保存不會禁用手動保存
- 隨時可以按 's' 鍵立即保存當前幀
- 手動保存和自動保存的文件格式相同

### 5. 停止自動保存
- 按 'q' 鍵退出程式即可
- 或重啟程式時設置 `--auto-save 0`

## 文件管理建議

### 定期清理
```bash
# 查看 saved_images 目錄大小
du -sh saved_images/

# 刪除舊文件（保留最近7天）
find saved_images/ -name "flir_*" -mtime +7 -delete
```

### 按日期整理
```bash
# 創建日期子目錄並移動文件
mkdir -p saved_images/2026-02-05
mv saved_images/flir_*20260205* saved_images/2026-02-05/
```

### 只保留 NPY 文件（節省空間）
```bash
# 如果不需要預覽圖像，可以刪除 JPG 和 PNG/TIFF
cd saved_images
rm flir_preview_*.jpg
rm flir_raw_*.png
rm flir_raw_*.tiff
# 只保留 NPY 和 metadata
```

## 時間間隔參考表

| 間隔（秒） | 每分鐘保存 | 每小時保存 | 每小時磁碟用量（8-bit） | 每小時磁碟用量（16-bit） |
|-----------|----------|-----------|----------------------|----------------------|
| 1         | 60       | 3,600     | ~14 GB               | ~32 GB               |
| 2         | 30       | 1,800     | ~7 GB                | ~16 GB               |
| 5         | 12       | 720       | ~2.8 GB              | ~6.5 GB              |
| 10        | 6        | 360       | ~1.4 GB              | ~3.2 GB              |
| 30        | 2        | 120       | ~470 MB              | ~1.1 GB              |
| 60        | 1        | 60        | ~235 MB              | ~540 MB              |
| 300 (5分) | 0.2      | 12        | ~47 MB               | ~108 MB              |
| 600 (10分)| 0.1      | 6         | ~23 MB               | ~54 MB               |

## 示例：長時間實驗

```bash
# 啟動相機，每10秒保存一次，旋轉90度，自動縮放
./run_camera.sh --auto-save 10 -r 90 -s auto -e 8000 -g 0 -f Mono16

# 運行3小時後停止（按 q 退出）
# 預計文件數量：3×360 = 1,080 組（4,320 個文件）
# 預計磁碟用量：~9.6 GB
```

## 驗證自動保存的數據

```bash
# 自動保存完成後，驗證最新的數據
python verify_saved_data.py

# 或指定具體文件
python verify_saved_data.py saved_images/flir_raw_20260205_123456
```

## 故障排除

### 問題：自動保存沒有觸發
**原因：** 配置文件中 `auto_save_interval: 0` 或未設置命令行參數  
**解決：** 使用 `--auto-save 5` 或修改配置文件

### 問題：保存太頻繁導致預覽卡頓
**原因：** 間隔太短（如 1 秒）  
**解決：** 增加間隔到 3-5 秒或更長

### 問題：磁碟空間不足
**原因：** 間隔太短或運行時間太長  
**解決：** 
1. 增加保存間隔
2. 定期清理舊文件
3. 只保留 NPY 文件，刪除其他格式

### 問題：想暫時停止自動保存
**解決：** 
- 重啟程式時設置 `--auto-save 0`
- 或修改配置文件後重啟

## 高級功能組合

### 1. 自動保存 + 分析報告
```bash
# 配置文件中設置
analysis:
  auto_analyze_on_save: true

# 啟動
./run_camera.sh --auto-save 10
```

### 2. 自動保存 + 16-bit 高精度
```bash
./run_camera.sh --auto-save 5 -f Mono16 -e 8000
```

### 3. 自動保存 + 自定義保存目錄
```yaml
# 配置文件
save:
  directory: ./experiment_data
  auto_save_interval: 10
```

### 4. 快速連續拍攝
```bash
# 每秒保存，持續1分鐘，然後手動停止
./run_camera.sh --auto-save 1 -e 3000
```

## 總結

✅ **已實現功能：**
- 自動定時保存（可配置間隔）
- 多格式保存（JPG, PNG/TIFF, NPY, TXT）
- 保存計數器（顯示 #1, #2, ...）
- 命令行和配置文件兩種設置方式
- 與手動保存共存（按 's' 仍可用）
- 可選自動分析報告

✅ **適用場景：**
- 長時間監控
- 定時採樣
- 快速序列拍攝
- 實驗數據記錄
- 時間序列分析

✅ **數據完整性：**
- 所有保存的數據都是無損的（NPY, PNG/TIFF）
- 可以完全恢復原始像素值
- 包含完整的元數據信息

開始使用：`./run_camera.sh --auto-save 5`
