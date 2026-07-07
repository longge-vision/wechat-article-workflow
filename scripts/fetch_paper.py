#!/usr/bin/env python3
"""
从 arXiv 下载论文 PDF
自动创建论文工作目录
"""

import requests
import re
import os
import sys
from pathlib import Path

# 添加脚本目录到路径，以便导入 create_paper_workspace
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
from create_paper_workspace import create_paper_workspace, get_workspace_paths

def download_from_arxiv(url_or_id, base_dir="./papers"):
    """
    从 arXiv 下载论文 PDF 到工作目录
    
    Args:
        url_or_id: arXiv URL 或论文 ID (如 2603.07952)
        base_dir: 基础目录
    
    Returns:
        dict: 包含 PDF 路径和工作目录信息
    """
    # 提取 arXiv ID
    if "arxiv.org" in url_or_id:
        match = re.search(r'(\d+\.\d+)', url_or_id)
        if match:
            arxiv_id = match.group(1)
        else:
            raise ValueError(f"无法从 URL 提取 arXiv ID: {url_or_id}")
    else:
        arxiv_id = url_or_id
    
    print(f"📥 下载论文: {arxiv_id}")
    
    # 创建工作目录
    workspace = create_paper_workspace(arxiv_id, base_dir)
    paths = get_workspace_paths(arxiv_id, base_dir)
    
    # 下载 PDF 到工作目录
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    output_path = paths["pdf"]
    
    response = requests.get(pdf_url, stream=True)
    response.raise_for_status()
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"✅ 下载完成: {output_path}")
    print(f"📁 工作目录: {workspace}")
    
    return {
        "arxiv_id": arxiv_id,
        "pdf_path": str(output_path),
        "workspace": str(workspace),
        "paths": {k: str(v) for k, v in paths.items()}
    }

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="从 arXiv 下载论文")
    parser.add_argument("url_or_id", help="arXiv URL 或论文 ID")
    parser.add_argument("-b", "--base-dir", default="./papers", help="基础目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式的路径信息")
    
    args = parser.parse_args()
    result = download_from_arxiv(args.url_or_id, args.base_dir)
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
