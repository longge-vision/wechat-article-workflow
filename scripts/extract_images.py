#!/usr/bin/env python3
"""
一键提取论文图片（整合 pdf_to_pages + AI分析 + extract）
支持从工作目录自动读取和输出
"""

import fitz
from PIL import Image
import json
import os
import sys
import re
from pathlib import Path

# 添加脚本目录到路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
from create_paper_workspace import get_workspace_paths

def extract_figures_from_pdf(pdf_path, output_dir=None, dpi=200, arxiv_id=None):
    """
    从 PDF 提取图表（完整流程）
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（如果为 None，则从 pdf_path 推断工作目录）
        dpi: 分辨率
        arxiv_id: arXiv ID（可选，用于自动推断工作目录）
    
    Returns:
        提取的图片路径列表和元数据
    """
    pdf_path = Path(pdf_path)
    
    # 自动推断工作目录
    if output_dir is None and arxiv_id is None:
        # 尝试从路径推断 arxiv_id
        # 路径格式: papers/{arxiv_id}/paper.pdf
        match = re.search(r'papers[\\/](\d+\.\d+)[\\/]', str(pdf_path))
        if match:
            arxiv_id = match.group(1)
    
    if arxiv_id:
        paths = get_workspace_paths(arxiv_id)
        output_dir = paths["figures_dir"]
        print(f"📁 使用工作目录: {paths['workspace']}")
    else:
        output_dir = Path(output_dir) if output_dir else Path("./figures")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: PDF 转图片
    print("📄 Step 1: 将 PDF 转为图片...")
    doc = fitz.open(pdf_path)
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(exist_ok=True)
    
    page_images = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        page_path = pages_dir / f"page_{page_num + 1:03d}.png"
        pix.save(str(page_path))
        page_images.append(str(page_path))
        print(f"  ✓ Page {page_num + 1}/{len(doc)}")
    
    doc.close()
    
    # Step 2: 创建/更新分析模板
    print("\n🔍 Step 2: 创建分析模板...")
    analysis_path = output_dir / "analysis_template.json"
    
    # 如果已有模板，保留用户填写的 elements
    existing_elements = {}
    if analysis_path.exists():
        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                for page_data in old_data.get("pages", []):
                    page_num = page_data.get("page")
                    if page_num and page_data.get("elements"):
                        existing_elements[page_num] = page_data["elements"]
            print(f"  ℹ️ 保留已存在的 elements 数据")
        except:
            pass
    
    analysis_data = {
        "pdf": str(pdf_path),
        "arxiv_id": arxiv_id,
        "total_pages": len(page_images),
        "pages": []
    }
    
    for i, img_path in enumerate(page_images, 1):
        with Image.open(img_path) as img:
            w, h = img.size
        
        page_data = {
            "page": i,
            "image_path": img_path,
            "width": w,
            "height": h,
            "elements": existing_elements.get(i, [])
        }
        analysis_data["pages"].append(page_data)
    
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False)
    
    print(f"  ✓ 分析模板: {analysis_path}")
    if not existing_elements:
        print(f"\n💡 下一步: 使用 AI 视觉分析每页图片，填写 elements 字段")
        print(f"   然后运行: extract_regions.py batch {analysis_path}")
    else:
        print(f"\n✅ 已保留 {len(existing_elements)} 页的 elements 数据")
    
    return page_images, str(analysis_path)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="提取论文图片")
    parser.add_argument("pdf", help="PDF 文件路径 (支持工作目录结构 papers/{id}/paper.pdf)")
    parser.add_argument("-o", "--output", default=None, help="输出目录 (默认从 PDF 路径推断)")
    parser.add_argument("--dpi", type=int, default=200, help="分辨率")
    parser.add_argument("--id", dest="arxiv_id", default=None, help="arXiv ID (可选，用于推断工作目录)")
    
    args = parser.parse_args()
    extract_figures_from_pdf(args.pdf, args.output, args.dpi, args.arxiv_id)
