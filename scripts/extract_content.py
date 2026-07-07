#!/usr/bin/env python3
"""
提取 PDF 文本内容
支持从工作目录自动推断输出路径
"""

import fitz  # PyMuPDF
import sys
import re
from pathlib import Path

# 添加脚本目录到路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
from create_paper_workspace import get_workspace_paths

def extract_text_from_pdf(pdf_path, output_path=None, arxiv_id=None):
    """
    提取 PDF 文本内容
    
    Args:
        pdf_path: PDF 文件路径
        output_path: 可选，保存文本的文件路径（默认保存到工作目录）
        arxiv_id: arXiv ID（可选，用于自动推断工作目录）
    
    Returns:
        提取的文本内容
    """
    pdf_path = Path(pdf_path)
    
    # 自动推断工作目录
    if output_path is None and arxiv_id is None:
        match = re.search(r'papers[\\/](\d+\.\d+)[\\/]', str(pdf_path))
        if match:
            arxiv_id = match.group(1)
    
    if arxiv_id:
        paths = get_workspace_paths(arxiv_id)
        output_path = paths["content"]
        print(f"📁 使用工作目录: {paths['workspace']}")
    
    doc = fitz.open(pdf_path)
    
    text_content = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        text_content.append(f"=== Page {page_num + 1} ===\n{text}")
    
    doc.close()
    
    full_text = "\n\n".join(text_content)
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"✅ 文本已保存: {output_path}")
    
    return full_text

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="提取 PDF 文本")
    parser.add_argument("pdf", help="PDF 文件路径 (支持工作目录结构 papers/{id}/paper.pdf)")
    parser.add_argument("-o", "--output", default=None, help="输出文本文件路径 (默认保存到工作目录)")
    parser.add_argument("--id", dest="arxiv_id", default=None, help="arXiv ID (可选，用于推断工作目录)")
    
    args = parser.parse_args()
    extract_text_from_pdf(args.pdf, args.output, args.arxiv_id)
