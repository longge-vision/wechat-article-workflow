#!/usr/bin/env python3
"""
创建论文工作目录结构
每篇论文使用独立文件夹存储相关素材
"""

from pathlib import Path
import json
import argparse


def create_paper_workspace(arxiv_id, base_dir="./papers"):
    """
    创建论文工作目录结构
    
    目录结构:
    papers/{arxiv_id}/
    ├── paper.pdf              # 论文原文
    ├── summary.json           # 论文总结
    ├── article.md             # 公众号文章
    ├── audio_script.txt       # 口播文案
    ├── content.txt            # PDF提取的文本内容
    └── figures/
        ├── pages/               # PDF转图片（每页一张）
        ├── extracted/           # 截取的图表
        └── analysis_template.json  # AI分析模板
    
    Args:
        arxiv_id: arXiv论文ID (如: 2504.06254)
        base_dir: 基础目录路径
    
    Returns:
        工作目录路径
    """
    # 创建主目录
    workspace = Path(base_dir) / arxiv_id
    figures_dir = workspace / "figures"
    pages_dir = figures_dir / "pages"
    extracted_dir = figures_dir / "extracted"
    
    # 创建所有子目录
    for dir_path in [workspace, figures_dir, pages_dir, extracted_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  📁 {dir_path}")
    
    # 创建空的 analysis_template.json
    template_path = figures_dir / "analysis_template.json"
    if not template_path.exists():
        template = {
            "arxiv_id": arxiv_id,
            "pages": [],
            "note": "AI分析后填写elements字段"
        }
        with open(template_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
        print(f"  📝 {template_path}")
    
    print(f"\n✅ 论文工作目录已创建: {workspace}")
    return workspace


def get_workspace_paths(arxiv_id, base_dir="./papers"):
    """
    获取论文工作目录中各文件的标准路径
    
    Args:
        arxiv_id: arXiv论文ID
        base_dir: 基础目录路径
    
    Returns:
        dict: 各文件的标准路径
    """
    workspace = Path(base_dir) / arxiv_id
    figures_dir = workspace / "figures"
    
    return {
        "workspace": workspace,
        "pdf": workspace / "paper.pdf",
        "summary": workspace / "summary.json",
        "article": workspace / "article.md",
        "audio_script": workspace / "audio_script.txt",
        "content": workspace / "content.txt",
        "figures_dir": figures_dir,
        "pages_dir": figures_dir / "pages",
        "extracted_dir": figures_dir / "extracted",
        "analysis_template": figures_dir / "analysis_template.json"
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="创建论文工作目录")
    parser.add_argument("arxiv_id", help="arXiv论文ID (如: 2504.06254)")
    parser.add_argument("-b", "--base-dir", default="./papers", help="基础目录路径")
    
    args = parser.parse_args()
    
    create_paper_workspace(args.arxiv_id, args.base_dir)
