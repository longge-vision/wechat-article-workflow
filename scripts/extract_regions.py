#!/usr/bin/env python3
"""
从分析结果截取图表区域
支持从工作目录自动推断输出路径
"""

from PIL import Image
from pathlib import Path
import json
import sys
import re

# 添加脚本目录到路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
from create_paper_workspace import get_workspace_paths

def extract_regions(analysis_json, output_dir=None, arxiv_id=None):
    """
    根据分析结果截取图表
    
    Args:
        analysis_json: 包含 elements 的分析结果 JSON
        output_dir: 输出目录（默认从 analysis_json 路径推断）
        arxiv_id: arXiv ID（可选，用于自动推断工作目录）
    
    Returns:
        截取图片路径列表
    """
    analysis_path = Path(analysis_json)
    
    # 自动推断工作目录
    if output_dir is None and arxiv_id is None:
        # 尝试从路径推断 arxiv_id
        # 路径格式: papers/{arxiv_id}/figures/analysis_template.json
        match = re.search(r'papers[\\/](\d+\.\d+)[\\/]', str(analysis_path))
        if match:
            arxiv_id = match.group(1)
    
    if arxiv_id:
        paths = get_workspace_paths(arxiv_id)
        output_dir = paths["extracted_dir"]
        print(f"📁 使用工作目录: {paths['workspace']}")
    else:
        output_dir = Path(output_dir) if output_dir else Path("./extracted")
    
    with open(analysis_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    extracted = []
    
    for page_data in data.get('pages', []):
        page_num = page_data['page']
        image_path = page_data['image_path']
        
        for element in page_data.get('elements', []):
            elem_type = element['type']
            bbox = element['bbox']  # [x, y, width, height]
            desc = element.get('description', '')
            
            # 截取
            img = Image.open(image_path)
            region = img.crop((bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3]))
            
            # 保存
            safe_desc = desc[:30].replace(' ', '_').replace('/', '_')
            output_name = f"page{page_num:03d}_{elem_type}_{safe_desc}.png"
            output_path = output_dir / output_name
            region.save(output_path)
            
            extracted.append(str(output_path))
            print(f"✓ {output_name}")
    
    print(f"\n✅ 共截取 {len(extracted)} 个区域")
    print(f"📂 输出目录: {output_dir}")
    return extracted

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="截取图表区域")
    parser.add_argument("analysis_json", help="分析结果 JSON 文件 (支持工作目录结构)")
    parser.add_argument("-o", "--output", default=None, help="输出目录 (默认从 JSON 路径推断)")
    parser.add_argument("--id", dest="arxiv_id", default=None, help="arXiv ID (可选，用于推断工作目录)")
    
    args = parser.parse_args()
    extract_regions(args.analysis_json, args.output, args.arxiv_id)
