#!/usr/bin/env python3
"""
重新生成對比網格圖 - 使用更好的質量
"""

import cv2
import numpy as np
import os
import sys
import yaml

def regenerate_comparison_grid(output_dir):
    """重新生成對比網格圖"""
    
    # 讀取結果摘要
    summary_path = os.path.join(output_dir, 'capture_summary.yaml')
    if not os.path.exists(summary_path):
        print(f"❌ 找不到結果摘要: {summary_path}")
        return False
    
    with open(summary_path, 'r', encoding='utf-8') as f:
        summary = yaml.safe_load(f)
    
    results = summary.get('results', [])
    if len(results) == 0:
        print("❌ 沒有找到結果")
        return False
    
    print(f"找到 {len(results)} 張圖像")
    print("正在重新生成對比網格圖...")
    
    try:
        # 讀取所有標註圖像
        images = []
        for result in results:
            img_path = os.path.join(output_dir, result['annotated_image'])
            if os.path.exists(img_path):
                img = cv2.imread(img_path)
                if img is not None:
                    # 縮小圖像 - 使用更大的尺寸保持清晰度
                    h, w = img.shape[:2]
                    # 根據圖像數量自動調整目標大小
                    n_total = len(results)
                    if n_total <= 9:
                        target_size = 800  # 少量圖像用大尺寸
                    elif n_total <= 36:
                        target_size = 600  # 中等數量
                    elif n_total <= 100:
                        target_size = 500  # 中大數量
                    else:
                        target_size = 400  # 大量圖像
                    
                    scale = min(target_size / h, target_size / w)
                    new_w, new_h = int(w * scale), int(h * scale)
                    # 使用 INTER_AREA 獲得更好的縮小效果
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    images.append(img)
                    print(f"  ✓ 處理: {result['annotated_image']} (縮放到 {new_w}x{new_h})")
        
        if len(images) == 0:
            print("❌ 沒有找到可用的圖像")
            return False
        
        print(f"\n共處理 {len(images)} 張圖像")
        print(f"目標大小: {target_size} 像素")
        
        # 計算網格大小
        n_images = len(images)
        
        # 自動調整列數
        if n_images <= 4:
            n_cols = 2
        elif n_images <= 9:
            n_cols = 3
        elif n_images <= 16:
            n_cols = 4
        elif n_images <= 36:
            n_cols = 6
        else:
            n_cols = 8  # 大量圖像用更多列
        
        n_rows = (n_images + n_cols - 1) // n_cols
        
        print(f"網格布局: {n_rows} 行 × {n_cols} 列")
        
        # 統一所有圖像大小
        max_h = max(img.shape[0] for img in images)
        max_w = max(img.shape[1] for img in images)
        
        print(f"單元格大小: {max_w}x{max_h}")
        
        # 創建網格
        grid_rows = []
        for row in range(n_rows):
            row_images = []
            for col in range(n_cols):
                idx = row * n_cols + col
                if idx < len(images):
                    img = images[idx]
                    # 填充到統一大小
                    padded = np.zeros((max_h, max_w, 3), dtype=np.uint8)
                    h, w = img.shape[:2]
                    padded[:h, :w] = img
                    row_images.append(padded)
                else:
                    # 空白圖像
                    row_images.append(np.zeros((max_h, max_w, 3), dtype=np.uint8))
            
            grid_rows.append(np.hstack(row_images))
        
        grid = np.vstack(grid_rows)
        
        # 保存網格圖
        grid_path = os.path.join(output_dir, 'comparison_grid.png')
        cv2.imwrite(grid_path, grid, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        
        # 獲取文件大小
        file_size_mb = os.path.getsize(grid_path) / (1024 * 1024)
        grid_h, grid_w = grid.shape[:2]
        
        print(f"\n✅ 成功生成對比網格圖！")
        print(f"  文件: {grid_path}")
        print(f"  尺寸: {grid_w} × {grid_h} 像素")
        print(f"  大小: {file_size_mb:.2f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ 生成網格圖失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函數"""
    if len(sys.argv) < 2:
        print("用法: python regenerate_grid.py <輸出目錄>")
        print("\n範例:")
        print("  python regenerate_grid.py fullrange_scan")
        print("  python regenerate_grid.py iterate_capture_20260209_201530")
        return 1
    
    output_dir = sys.argv[1]
    
    if not os.path.exists(output_dir):
        print(f"❌ 目錄不存在: {output_dir}")
        return 1
    
    print("="*70)
    print("重新生成對比網格圖")
    print("="*70)
    print(f"\n目錄: {output_dir}\n")
    
    if regenerate_comparison_grid(output_dir):
        print("\n" + "="*70)
        print("完成！")
        print("="*70)
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
