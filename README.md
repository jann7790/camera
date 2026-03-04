# Camera Project

FLIR 相機拍攝與 CCTag / Barcode 偵測專案。

---

## Shell 腳本說明

### 主要入口

| 腳本 | 功能 |
|------|------|
| `run_camera.sh` | 啟動 FLIR 相機預覽程式，可傳入 `--exposure`、`--gain`、`--format` 等參數 |
| `run_cctag.sh` | 啟動 CCTag marker 偵測，支援 FLIR 相機、靜態圖片、webcam，可透過命令列調整所有 detection 參數 |
| `barcode_tools_menu.sh` | 互動式選單，整合所有 barcode 相關工具的入口（選項 1~7） |

### 參數調整與拍攝

| 腳本 | 功能 |
|------|------|
| `run_live_tuner.sh` | 即時調參工具，用鍵盤即時調整曝光/增益，觀察 barcode 清晰度 |
| `run_iterate_capture.sh` | 自動迭代拍攝工具，批次測試多組曝光＋增益組合並儲存影像供比較 |
| `quick_barcode_test.sh` | 快速跑 4 組預設參數配置（短曝光低增益、中曝光中增益、較長曝光、16bit 高精度） |

### 設定與報告

| 腳本 | 功能 |
|------|------|
| `apply_best_config.sh` | 讀取 `results/best_config.yaml`，將最佳參數合併套用到 `camera_config.yaml`（會先自動備份） |
| `view_report.sh` | 在本地啟動 HTTP server（port 8000），用瀏覽器開啟 HTML 分析報告 |

---

## 建議使用流程

1. **找參數**：執行 `run_live_tuner.sh` 或透過 `barcode_tools_menu.sh` 互動選單
2. **批次驗證**：執行 `run_iterate_capture.sh` 批次拍攝多組參數
3. **套用設定**：執行 `apply_best_config.sh` 將最佳參數寫入 `camera_config.yaml`
4. **正式運行**：執行 `run_camera.sh` 或 `run_cctag.sh`

---

## 鍵盤控制（`run_live_tuner.sh`）

| 按鍵 | 功能 |
|------|------|
| `W` / `S` | 曝光 +/- 大步進（1000 μs） |
| `A` / `D` | 增益 +/- 大步進（3 dB） |
| `I` / `K` | 曝光 +/- 小步進（100 μs） |
| `J` / `L` | 增益 +/- 小步進（0.5 dB） |
| `SPACE` | 儲存當前配置 |
| `R` | 重置為預設值 |
| `Q` | 退出 |

---

## run_cctag.sh 用法

```bash
# FLIR 相機，預設參數
./run_cctag.sh --flir

# FLIR + 速度調優（只有少數 tag 時）
./run_cctag.sh --flir --max-seeds 100 --max-candidates 10 \
    --cuts-trials 100 --no-arc-search --multires-layers 2 --no-lmdif

# FLIR + 輸入圖像縮小 50%（最直接的加速方式）
./run_cctag.sh --flir --downscale 0.5

# 對靜態圖片偵測
./run_cctag.sh --image photo.jpg

# 使用 webcam
./run_cctag.sh --webcam --cam-index 0

# 查看所有參數
./run_cctag.sh -h
```

### 所有命令列參數

| 參數 | 說明 | 預設值 |
|------|------|--------|
| **模式選擇** | | |
| `--flir` | 使用 FLIR 相機 | |
| `--image PATH` | 對靜態圖片偵測 | |
| `--webcam` | 使用 USB webcam | |
| `--cam-index N` | webcam 索引 | 0 |
| `--config PATH` | FLIR 相機設定檔 | camera_config.yaml |
| **輸入前處理** | | |
| `--downscale F` | 偵測前縮小倍率（0.5=縮小一半） | 無（原始大小） |
| **CCTag 基本** | | |
| `--num-crowns N` | CCTag 環數（3 或 4） | 3 |
| **Canny / 梯度** | | |
| `--canny-low F` | Canny 低閾值 | 0.01 |
| `--canny-high F` | Canny 高閾值 | 0.04 |
| `--thr-gradient N` | 梯度強度門檻 | 2500 |
| `--max-edges N` | 最大邊緣點數 | 20000 |
| **候選搜尋** | | |
| `--max-seeds N` | 最多種子候選點數 | 500 |
| `--max-candidates N` | 第二輪最多候選數 | 40 |
| `--min-votes N` | 成為種子的最低票數 | 3 |
| `--dist-search N` | 搜尋最大距離（px） | 30 |
| **橢圓擬合** | | |
| `--no-arc-search` | 關閉多弧段組合 | 開啟 |
| **多解析度** | | |
| `--multires-layers N` | pyramid 處理層數 | 4 |
| **ID 識別** | | |
| `--cuts-trials N` | 切割選取試驗次數 | 500 |
| `--no-lmdif` | 關閉 LM 精煉 | 開啟 |
| `--no-identification` | 跳過 ID 識別（只定位） | 開啟 |

### 鍵盤控制（即時偵測模式）

| 按鍵 | 功能 |
|------|------|
| `Q` | 退出 |
| `S` | 儲存當前畫面 |

---

## CCTag Detection 參數說明

### Python API

```python
import _cctag_native as cn

# 建立 Detector（Parameters 和 MarkersBank 只初始化一次，後續每幀複用）
det = cn.Detector(num_crowns=3)

# 調整參數（建立後、呼叫 detect 前設定）
det.max_seeds = 100                  # 預設 500，只有少數 tag 可大幅調低
det.max_candidates_loop2 = 10        # 預設 40
det.cuts_selection_trials = 100      # 預設 500，ID 少時可調低
det.search_another_segment = False   # 預設 True，關閉可跳過耗時弧段組合
det.num_multires_layers = 2          # 預設 4
det.processed_multires_layers = 2    # 預設 4
det.use_lmdif = False                # 預設 True，關閉 LM 精煉可加速
det.canny_thr_low = 0.01            # 預設 0.01
det.canny_thr_high = 0.04           # 預設 0.04

# 執行偵測
results = det.detect(gray_numpy_uint8, pipe_id=0, frame_id=0)
```

### 全部參數一覽

#### 邊緣偵測（Canny / Gradient）

| 參數 | Python 屬性 | 預設值 | 說明 |
|------|-------------|--------|------|
| `_cannyThrLow` | `canny_thr_low` | 0.01 | Canny 低閾值，調高可減少雜訊邊緣 |
| `_cannyThrHigh` | `canny_thr_high` | 0.04 | Canny 高閾值，調高可進一步過濾弱邊緣 |
| `_thrGradientMagInVote` | `thr_gradient_mag` | 2500 | 投票時梯度強度最低門檻，調高可減少噪訊候選點 |
| `_maxEdges` | `max_edges` | 20000 | 最大邊緣點數，影響記憶體分配 |

#### 候選點搜尋 / 投票

| 參數 | Python 屬性 | 預設值 | 說明 |
|------|-------------|--------|------|
| `_distSearch` | `dist_search` | 30 | 邊緣點間搜尋最大距離（pixels） |
| `_angleVoting` | `angle_voting` | 0.0 | 相鄰邊緣點梯度方向最大角度差（0=不限） |
| `_ratioVoting` | `ratio_voting` | 4.0 | 相鄰邊緣點距離比最大值 |
| `_maximumNbSeeds` | `max_seeds` | 500 | 最多處理幾個種子候選點。**tag 少時應大幅調低** |
| `_maximumNbCandidatesLoopTwo` | `max_candidates_loop2` | 40 | 第二輪最多候選數。**tag 少時應調低** |
| `_minVotesToSelectCandidate` | `min_votes` | 3 | 邊緣點成為種子的最低票數 |
| `_averageVoteMin` | `average_vote_min` | 0.0 | 平均投票最低值 |

#### 橢圓擬合

| 參數 | Python 屬性 | 預設值 | 說明 |
|------|-------------|--------|------|
| `_minPointsSegmentCandidate` | `min_points_segment` | 10 | 外橢圓上最少點數才考慮內段候選 |
| `_thrMedianDistanceEllipse` | `thr_median_dist_ellipse` | 3.0 | 橢圓擬合中位數距離門檻（pixels） |
| `_threshRobustEstimationOfOuterEllipse` | `thresh_robust_ellipse` | 30.0 | 外橢圓 LMeDs 估計閾值 |
| `_ellipseGrowingEllipticHullWidth` | `ellipse_hull_width` | 2.3 | 橢圓擴展寬度（pixels） |
| `_windowSizeOnInnerEllipticSegment` | `window_inner_segment` | 20 | 內橢圓段的視窗大小 |
| `_searchForAnotherSegment` | `search_another_segment` | true | **是否組合多個弧段**。設 false 可跳過耗時組合步驟 |

#### 多解析度（Image Pyramid）

| 參數 | Python 屬性 | 預設值 | 說明 |
|------|-------------|--------|------|
| `_numberOfMultiresLayers` | `num_multires_layers` | 4 | 建立幾層 image pyramid |
| `_numberOfProcessedMultiresLayers` | `processed_multires_layers` | 4 | **實際處理幾層**。調低到 2-3 可大幅加速 |

#### ID 識別

| 參數 | Python 屬性 | 預設值 | 說明 |
|------|-------------|--------|------|
| `_nSamplesOuterEllipse` | `n_samples_outer` | 150 | 識別時在外橢圓上取幾個點 |
| `_numCutsInIdentStep` | `num_cuts_ident` | 22 | 識別步驟的切割數 |
| `_numSamplesOuterEdgePointsRefinement` | `num_samples_refinement` | 20 | 邊緣點精煉取樣數 |
| `_cutsSelectionTrials` | `cuts_selection_trials` | 500 | 切割選取試驗次數。**ID 少時應大幅調低** |
| `_sampleCutLength` | `sample_cut_length` | 100 | 每個切割的取樣長度 |
| `_imagedCenterNGridSample` | `center_grid_sample` | 5 | 中心網格取樣（5 = 5x5 = 25 個點），須為奇數 |
| `_imagedCenterNeighbourSize` | `center_neighbour_size` | 0.20 | 鄰域大小（相對外橢圓長軸比例） |
| `_minIdentProba` | `min_ident_proba` | 1e-6 | 識別概率最低門檻 |
| `_useLMDif` | `use_lmdif` | true | 是否用 LM 非線性最佳化精煉，設 false 可加速 |
| `_doIdentification` | `do_identification` | true | 是否執行 ID 識別步驟 |

### 只有少數 tag 時的建議配置

如果場景中只有 1-2 個 tag（例如只用 ID=0），建議調整以下參數以大幅提速：

```python
det = cn.Detector(num_crowns=3)
det.max_seeds = 100                  # 500 → 100
det.max_candidates_loop2 = 10        # 40 → 10
det.cuts_selection_trials = 100      # 500 → 100
det.search_another_segment = False   # 跳過弧段組合
det.processed_multires_layers = 2    # 4 → 2（tag 夠大時）
det.use_lmdif = False                # 不做 LM 精煉
```

---

## 目錄結構

```
camera/
├── run_camera.sh            # 相機預覽
├── run_cctag.sh             # CCTag 偵測（支援命令列調參）
├── cctag_detector.py        # CCTag 偵測主程式
├── cctag_binding.cpp        # CCTag C++ pybind11 binding（含 Detector class）
├── _cctag_native.*.so       # 編譯後的 CCTag binding
├── run_live_tuner.sh        # 即時調參
├── run_iterate_capture.sh   # 迭代拍攝
├── barcode_tools_menu.sh    # 工具選單
├── quick_barcode_test.sh    # 快速測試
├── apply_best_config.sh     # 套用最佳設定
├── flir_camera_preview.py   # FLIR 相機擷取核心
├── camera_config.yaml       # 相機設定檔
├── binding_build/           # CMake 編譯目錄
├── requirements.txt         # Python 依賴套件
├── results/                 # 搜索結果與最佳配置
├── indoor/                  # 室內拍攝資料
├── outdoor/                 # 室外拍攝資料
├── fullrange_scan/          # 全範圍曝光/增益掃描結果
├── iterate_capture_*/       # 迭代拍攝實驗結果
├── analysis_plots/          # 分析圖表
└── focal_analysis/          # 焦距分析資料
```
