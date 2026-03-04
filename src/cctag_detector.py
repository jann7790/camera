#!/usr/bin/env python3
"""
CCTag Marker Detector
=====================
整合官方 CCTag C++ library（透過 _cctag_native pybind11 binding）。

支援模式：
  --flir     使用 FLIR 相機即時偵測
  --webcam   使用 USB webcam 即時偵測
  --image    對靜態圖片偵測

CCTag detection 參數可透過命令列調整，例如：
  python cctag_detector.py --flir --max-seeds 100 --no-arc-search
"""

import os
import sys
import cv2
import numpy as np
import time
import argparse
from pathlib import Path

# ── 確保 conda lib 和 lib/ 目錄在搜尋路徑中 ──────────────────────────────────
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LIB_DIR = os.path.join(_PROJECT_DIR, "lib")
_CONDA_LIB = os.path.expanduser("~/miniconda3/lib")
_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
if _LIB_DIR not in _ld_path:
    os.environ["LD_LIBRARY_PATH"] = f"{_LIB_DIR}:{_ld_path}"
    _ld_path = os.environ["LD_LIBRARY_PATH"]
if _CONDA_LIB not in _ld_path:
    os.environ["LD_LIBRARY_PATH"] = f"{_CONDA_LIB}:{_ld_path}"

# 確保 lib/ 在 Python 搜尋路徑中（for _cctag_native.so）
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

# ── 載入 _cctag_native ──────────────────────────────────────────────────────
_NATIVE_AVAILABLE = False
try:
    import _cctag_native as _cn
    _NATIVE_AVAILABLE = True
    print("[CCTag] 官方 CCTag C++ library 載入成功")
except Exception as _e:
    print(f"[CCTag] 官方 library 載入失敗（{_e}）")
    print("        請確認 _cctag_native.so 存在於 lib/ 目錄且 LD_LIBRARY_PATH 包含 ~/miniconda3/lib")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Detector 封裝
# ═══════════════════════════════════════════════════════════════════════════════

def create_detector(args):
    """根據命令列參數建立並設定 Detector。"""
    det = _cn.Detector(num_crowns=args.num_crowns)

    # Canny / Gradient
    if args.canny_low is not None:
        det.canny_thr_low = args.canny_low
    if args.canny_high is not None:
        det.canny_thr_high = args.canny_high
    if args.thr_gradient is not None:
        det.thr_gradient_mag = args.thr_gradient
    if args.max_edges is not None:
        det.max_edges = args.max_edges

    # Candidate search / Voting
    if args.max_seeds is not None:
        det.max_seeds = args.max_seeds
    if args.max_candidates is not None:
        det.max_candidates_loop2 = args.max_candidates
    if args.min_votes is not None:
        det.min_votes = args.min_votes
    if args.dist_search is not None:
        det.dist_search = args.dist_search

    # Ellipse
    if args.no_arc_search:
        det.search_another_segment = False

    # Multi-resolution
    if args.multires_layers is not None:
        det.num_multires_layers = args.multires_layers
        det.processed_multires_layers = args.multires_layers

    # Identification
    if args.cuts_trials is not None:
        det.cuts_selection_trials = args.cuts_trials
    if args.no_lmdif:
        det.use_lmdif = False
    if args.no_identification:
        det.do_identification = False

    return det


# ═══════════════════════════════════════════════════════════════════════════════
# 繪圖工具
# ═══════════════════════════════════════════════════════════════════════════════

# 預定義的 tag ID 顏色
_COLORS = [
    (0, 255, 0),    # ID 0: green
    (255, 0, 0),    # ID 1: blue
    (0, 0, 255),    # ID 2: red
    (0, 255, 255),  # ID 3: yellow
    (255, 0, 255),  # ID 4: magenta
    (255, 255, 0),  # ID 5: cyan
]


def _color_for_id(tag_id):
    if tag_id < 0:
        return (128, 128, 128)
    return _COLORS[tag_id % len(_COLORS)]


def draw_detections(frame, detections):
    """
    在圖像上繪製 CCTag 偵測結果。

    Parameters
    ----------
    frame      : BGR 圖像（會被直接修改）
    detections : detect() 回傳的 list of dict
    """
    for d in detections:
        tag_id = d["id"]
        cx, cy = int(d["x"]), int(d["y"])
        color = _color_for_id(tag_id)

        # 畫橢圓
        a = d["ellipse_a"]
        b = d["ellipse_b"]
        if a > 0 and b > 0:
            ecx = int(d["ellipse_cx"])
            ecy = int(d["ellipse_cy"])
            angle_deg = np.degrees(d["ellipse_angle_rad"])
            axes = (int(a), int(b))
            cv2.ellipse(frame, (ecx, ecy), axes, angle_deg, 0, 360, color, 2)

        # 畫中心十字
        size = 8
        cv2.line(frame, (cx - size, cy), (cx + size, cy), color, 2)
        cv2.line(frame, (cx, cy - size), (cx, cy + size), color, 2)

        # 標籤文字
        label = f"ID:{tag_id}" if tag_id >= 0 else "ID:?"
        conf = d["quality"]
        text = f"{label} conf:{conf:.2f}"
        cv2.putText(frame, text, (cx + 12, cy - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    return frame


# ═══════════════════════════════════════════════════════════════════════════════
# OSD（On-Screen Display）
# ═══════════════════════════════════════════════════════════════════════════════

def draw_osd(frame, fps, detect_ms, num_detections, det):
    """繪製左上角的即時資訊。"""
    lines = [
        f"FPS: {fps:.1f}  detect: {detect_ms:.1f}ms",
        f"CCTag detected: {num_detections}",
    ]
    y = 25
    for line in lines:
        cv2.putText(frame, line, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y += 22

    # 底部顯示當前參數概要
    params_text = (
        f"seeds:{det.max_seeds} cand:{det.max_candidates_loop2} "
        f"cuts:{det.cuts_selection_trials} "
        f"layers:{det.processed_multires_layers} "
        f"arc:{'Y' if det.search_another_segment else 'N'} "
        f"LM:{'Y' if det.use_lmdif else 'N'}"
    )
    h = frame.shape[0]
    cv2.putText(frame, params_text, (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    return frame


# ═══════════════════════════════════════════════════════════════════════════════
# 自動縮放
# ═══════════════════════════════════════════════════════════════════════════════

def auto_scale(frame, max_width=1280, max_height=800):
    """如果圖像超過指定大小就等比縮小。"""
    h, w = frame.shape[:2]
    if w <= max_width and h <= max_height:
        return frame
    scale = min(max_width / w, max_height / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)


# ═══════════════════════════════════════════════════════════════════════════════
# 模式一：FLIR 相機
# ═══════════════════════════════════════════════════════════════════════════════

def run_with_flir_camera(det, args):
    """使用 FLIR 相機即時偵測 CCTag。"""
    try:
        import PySpin
    except ImportError:
        print("[ERROR] PySpin 未安裝，無法使用 FLIR 相機。")
        print("        請改用 --image 或 --webcam 測試。")
        return

    import yaml

    # 載入 camera_config.yaml
    config_path = args.config
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print(f"[CCTag] 載入設定: {config_path}")
    else:
        print(f"[WARN] 找不到 {config_path}，使用預設設定")
        config = None

    # 初始化相機（複用 flir_camera_preview.py）
    from flir_camera_preview import FLIRCameraPreview

    cam_preview = FLIRCameraPreview(config)
    if not cam_preview.initialize_camera():
        print("[ERROR] 相機初始化失敗")
        return
    if not cam_preview.configure_camera():
        print("[ERROR] 相機配置失敗")
        return
    if not cam_preview.start_acquisition():
        print("[ERROR] 開始擷取失敗")
        return

    print("CCTag 偵測中... 按 'q' 退出，'s' 儲存目前畫面")
    _print_detector_config(det)

    window_name = "CCTag Detection - FLIR Camera"
    fps = 0.0
    fps_counter = 0
    fps_timer = time.time()
    frame_id = 0
    timeout_ms = config["performance"]["image_timeout_ms"] if config else 1000

    try:
        while True:
            try:
                image_result = cam_preview.cam.GetNextImage(timeout_ms)
                if image_result.IsIncomplete():
                    image_result.Release()
                    continue

                # 取得灰階影像
                img_data = image_result.GetNDArray()
                image_result.Release()

                if img_data is None:
                    continue

                # 確保是灰階
                if len(img_data.shape) == 3:
                    gray = cv2.cvtColor(img_data, cv2.COLOR_BGR2GRAY)
                else:
                    gray = img_data

                # 如果指定了 downscale
                detect_gray = _maybe_downscale(gray, args.downscale)

                # 偵測
                t0 = time.perf_counter()
                results = det.detect(detect_gray, frame_id=frame_id)
                detect_ms = (time.perf_counter() - t0) * 1000.0

                # 座標映射回原始大小
                if args.downscale and args.downscale != 1.0:
                    results = _scale_results(results, 1.0 / args.downscale)

                frame_id += 1

                # 繪製結果
                if len(gray.shape) == 2:
                    display = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                else:
                    display = gray.copy()

                draw_detections(display, results)

                # FPS 計算
                fps_counter += 1
                elapsed = time.time() - fps_timer
                if elapsed >= 1.0:
                    fps = fps_counter / elapsed
                    fps_counter = 0
                    fps_timer = time.time()

                draw_osd(display, fps, detect_ms, len(results), det)
                display = auto_scale(display)
                cv2.imshow(window_name, display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("s"):
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    fname = f"cctag_capture_{ts}.jpg"
                    cv2.imwrite(fname, display)
                    print(f"[SAVE] {fname}")

            except Exception as e:
                print(f"[ERROR] {e}")
                continue

    except KeyboardInterrupt:
        print("\n偵測結束")
    finally:
        cv2.destroyAllWindows()
        cam_preview.cam.EndAcquisition()
        cam_preview.cam.DeInit()
        del cam_preview.cam
        cam_preview.cam_list.Clear()
        cam_preview.system.ReleaseInstance()
        print("[CCTag] 相機資源已釋放")


# ═══════════════════════════════════════════════════════════════════════════════
# 模式二：Webcam
# ═══════════════════════════════════════════════════════════════════════════════

def run_on_webcam(det, args):
    """使用 USB webcam 即時偵測 CCTag。"""
    cap = cv2.VideoCapture(args.cam_index)
    if not cap.isOpened():
        print(f"[ERROR] 無法開啟 webcam index={args.cam_index}")
        return

    print(f"CCTag webcam 偵測中... 按 'q' 退出")
    _print_detector_config(det)

    window_name = "CCTag Detection - Webcam"
    fps = 0.0
    fps_counter = 0
    fps_timer = time.time()
    frame_id = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detect_gray = _maybe_downscale(gray, args.downscale)

            t0 = time.perf_counter()
            results = det.detect(detect_gray, frame_id=frame_id)
            detect_ms = (time.perf_counter() - t0) * 1000.0

            if args.downscale and args.downscale != 1.0:
                results = _scale_results(results, 1.0 / args.downscale)

            frame_id += 1

            draw_detections(frame, results)

            fps_counter += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                fps = fps_counter / elapsed
                fps_counter = 0
                fps_timer = time.time()

            draw_osd(frame, fps, detect_ms, len(results), det)
            display = auto_scale(frame)
            cv2.imshow(window_name, display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("s"):
                ts = time.strftime("%Y%m%d_%H%M%S")
                fname = f"cctag_capture_{ts}.jpg"
                cv2.imwrite(fname, frame)
                print(f"[SAVE] {fname}")

    except KeyboardInterrupt:
        print("\n偵測結束")
    finally:
        cap.release()
        cv2.destroyAllWindows()


# ═══════════════════════════════════════════════════════════════════════════════
# 模式三：靜態圖片
# ═══════════════════════════════════════════════════════════════════════════════

def run_on_image(det, args):
    """對靜態圖片執行 CCTag 偵測並顯示結果。"""
    image_path = args.image
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"[ERROR] 無法讀取圖片: {image_path}")
        return

    print(f"[CCTag] 圖片: {image_path} ({frame.shape[1]}x{frame.shape[0]})")
    _print_detector_config(det)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detect_gray = _maybe_downscale(gray, args.downscale)

    t0 = time.perf_counter()
    results = det.detect(detect_gray)
    detect_ms = (time.perf_counter() - t0) * 1000.0

    if args.downscale and args.downscale != 1.0:
        results = _scale_results(results, 1.0 / args.downscale)

    print(f"[CCTag] 偵測到 {len(results)} 個 marker，耗時 {detect_ms:.1f}ms")
    for d in results:
        tag_id = d["id"]
        cx, cy = d["x"], d["y"]
        conf = d["quality"]
        print(f"  ID:{tag_id}  center=({cx:.1f}, {cy:.1f})  conf={conf:.3f}")

    draw_detections(frame, results)

    # 加上偵測資訊文字
    info = f"Detected: {len(results)}  Time: {detect_ms:.1f}ms"
    cv2.putText(frame, info, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    display = auto_scale(frame)
    window_name = "CCTag Detection"
    cv2.imshow(window_name, display)
    print("按任意鍵關閉視窗，'s' 儲存結果圖")

    while True:
        key = cv2.waitKey(0) & 0xFF
        if key == ord("s"):
            base = Path(image_path).stem
            ext = Path(image_path).suffix
            out_path = f"{base}_cctag_result{ext}"
            cv2.imwrite(out_path, frame)
            print(f"[SAVE] {out_path}")
        else:
            break

    cv2.destroyAllWindows()


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函式
# ═══════════════════════════════════════════════════════════════════════════════

def _maybe_downscale(gray, downscale):
    """如果指定了 downscale 因子就縮小偵測用灰階圖。"""
    if downscale is None or downscale == 1.0:
        return gray
    h, w = gray.shape[:2]
    new_w = int(w * downscale)
    new_h = int(h * downscale)
    return cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_LINEAR)


def _scale_results(results, scale):
    """將偵測結果座標按比例映射回原始解析度。"""
    scaled = []
    for d in results:
        sd = dict(d)
        sd["x"] = d["x"] * scale
        sd["y"] = d["y"] * scale
        sd["ellipse_cx"] = d["ellipse_cx"] * scale
        sd["ellipse_cy"] = d["ellipse_cy"] * scale
        sd["ellipse_a"] = d["ellipse_a"] * scale
        sd["ellipse_b"] = d["ellipse_b"] * scale
        scaled.append(sd)
    return scaled


def _print_detector_config(det):
    """印出當前 Detector 參數。"""
    print(f"  num_crowns             = 3 (CCTag3)")
    print(f"  max_seeds              = {det.max_seeds}")
    print(f"  max_candidates_loop2   = {det.max_candidates_loop2}")
    print(f"  cuts_selection_trials   = {det.cuts_selection_trials}")
    print(f"  processed_multires     = {det.processed_multires_layers}")
    print(f"  search_another_segment = {det.search_another_segment}")
    print(f"  use_lmdif              = {det.use_lmdif}")
    print(f"  do_identification      = {det.do_identification}")
    print(f"  canny_thr              = {det.canny_thr_low:.4f} / {det.canny_thr_high:.4f}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser():
    parser = argparse.ArgumentParser(
        description="CCTag Marker Detector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例：
  # 使用 FLIR 相機（預設參數）
  python cctag_detector.py --flir

  # FLIR + 速度調優（只有少數 tag）
  python cctag_detector.py --flir --max-seeds 100 --max-candidates 10 \\
      --cuts-trials 100 --no-arc-search --multires-layers 2 --no-lmdif

  # FLIR + 輸入圖像縮小 50%
  python cctag_detector.py --flir --downscale 0.5

  # 對靜態圖片偵測
  python cctag_detector.py --image photo.jpg

  # 使用 webcam
  python cctag_detector.py --webcam --cam-index 0
""")

    # ── 模式選擇 ─────────────────────────────────────────────────────────────
    mode = parser.add_argument_group("模式選擇（擇一）")
    mode.add_argument("--flir", action="store_true",
                       help="使用 FLIR 相機（需 PySpin）")
    mode.add_argument("--image", type=str, metavar="PATH",
                       help="對靜態圖片偵測")
    mode.add_argument("--webcam", action="store_true",
                       help="使用 USB webcam")
    mode.add_argument("--cam-index", type=int, default=0,
                       help="webcam 索引（預設 0）")
    mode.add_argument("--config", type=str, default="camera_config.yaml",
                       help="FLIR 相機設定檔路徑（預設 camera_config.yaml）")

    # ── 輸入前處理 ───────────────────────────────────────────────────────────
    pre = parser.add_argument_group("輸入前處理")
    pre.add_argument("--downscale", type=float, default=None,
                      help="偵測前縮小倍率（如 0.5 = 縮小一半），可大幅加速")

    # ── CCTag 基本設定 ───────────────────────────────────────────────────────
    basic = parser.add_argument_group("CCTag 基本設定")
    basic.add_argument("--num-crowns", type=int, default=3,
                        help="CCTag 環數：3=CCTag3, 4=CCTag4（預設 3）")

    # ── Canny / Gradient ─────────────────────────────────────────────────────
    canny = parser.add_argument_group("Canny / 梯度參數")
    canny.add_argument("--canny-low", type=float, default=None,
                        help="Canny 低閾值（預設 0.01）")
    canny.add_argument("--canny-high", type=float, default=None,
                        help="Canny 高閾值（預設 0.04）")
    canny.add_argument("--thr-gradient", type=int, default=None,
                        help="投票梯度強度門檻（預設 2500）")
    canny.add_argument("--max-edges", type=int, default=None,
                        help="最大邊緣點數（預設 20000）")

    # ── 候選搜尋 / 投票 ─────────────────────────────────────────────────────
    vote = parser.add_argument_group("候選搜尋 / 投票參數")
    vote.add_argument("--max-seeds", type=int, default=None,
                       help="最多種子候選點數（預設 500）。tag 少時建議調低到 50-100")
    vote.add_argument("--max-candidates", type=int, default=None,
                       help="第二輪最多候選數（預設 40）。tag 少時建議調低到 10-15")
    vote.add_argument("--min-votes", type=int, default=None,
                       help="邊緣點成為種子的最低票數（預設 3）")
    vote.add_argument("--dist-search", type=int, default=None,
                       help="邊緣點搜尋最大距離 pixels（預設 30）")

    # ── 橢圓擬合 ─────────────────────────────────────────────────────────────
    ell = parser.add_argument_group("橢圓擬合參數")
    ell.add_argument("--no-arc-search", action="store_true",
                      help="關閉多弧段組合（search_another_segment=False），可加速")

    # ── 多解析度 ─────────────────────────────────────────────────────────────
    multi = parser.add_argument_group("多解析度參數")
    multi.add_argument("--multires-layers", type=int, default=None,
                        help="處理的 pyramid 層數（預設 4）。調到 2-3 可加速")

    # ── ID 識別 ──────────────────────────────────────────────────────────────
    ident = parser.add_argument_group("ID 識別參數")
    ident.add_argument("--cuts-trials", type=int, default=None,
                        help="切割選取試驗次數（預設 500）。ID 少時建議調低到 50-100")
    ident.add_argument("--no-lmdif", action="store_true",
                        help="關閉 LM 非線性精煉（加速，精度略降）")
    ident.add_argument("--no-identification", action="store_true",
                        help="完全跳過 ID 識別（只做定位）")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # 檢查是否指定了模式
    if not args.flir and not args.image and not args.webcam:
        print("CCTag Detector - 請指定模式：")
        print("  --flir    使用 FLIR 相機")
        print("  --image   靜態圖片")
        print("  --webcam  USB webcam")
        print()
        print("速度調優範例：")
        print("  python cctag_detector.py --flir --max-seeds 100 --no-arc-search --no-lmdif")
        print()
        print("使用 -h 查看所有參數")
        return

    # 建立 Detector
    det = create_detector(args)

    # 執行對應模式
    if args.image:
        run_on_image(det, args)
    elif args.webcam:
        run_on_webcam(det, args)
    elif args.flir:
        run_with_flir_camera(det, args)


if __name__ == "__main__":
    main()
