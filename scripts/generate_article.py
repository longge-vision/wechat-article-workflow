#!/usr/bin/env python3
"""
生成公众号文章 Markdown
支持从工作目录自动读取和输出
"""

from pathlib import Path
import json
import sys
import re

# 添加脚本目录到路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
from create_paper_workspace import get_workspace_paths

ARTICLE_TEMPLATE = """---
title: {title}
author: {author}
---

# {title}

> **{venue} | {institution}**

![封面图]({cover_image})

---

## 0. 核心洞察

{insight}

---

## 1. 方法介绍

{method}

---

## 2. 实验结果

{experiment}

---

## 3. 总结与展望

{conclusion}

---

**论文信息**
- 标题：{paper_title}
- 作者：{authors}
- 机构：{institution}
- 论文链接：{paper_url}
- 代码链接：{code_url}

---

*本文仅做学术分享，如有侵权，请联系删除。*

**关注 {author}，获取更多前沿技术解读**
"""

def generate_article(summary_data, cover_image, figures, output_path=None, arxiv_id=None):
    """
    生成公众号文章
    
    Args:
        summary_data: 论文总结数据（dict 或 JSON 文件路径）
        cover_image: 封面图路径
        figures: 正文配图路径列表
        output_path: 输出文件路径（默认保存到工作目录）
        arxiv_id: arXiv ID（可选，用于自动推断工作目录）
    """
    # 如果 summary_data 是路径，读取 JSON
    if isinstance(summary_data, (str, Path)):
        summary_path = Path(summary_data)
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary_data = json.load(f)
        
        # 自动推断工作目录
        if output_path is None and arxiv_id is None:
            match = re.search(r'papers[\\/](\d+\.\d+)[\\/]', str(summary_path))
            if match:
                arxiv_id = match.group(1)
    
    # 自动推断工作目录
    if arxiv_id:
        paths = get_workspace_paths(arxiv_id)
        if output_path is None:
            output_path = paths["article"]
        print(f"📁 使用工作目录: {paths['workspace']}")
    elif output_path is None:
        output_path = "./article.md"
    
    # 构建文章内容
    content = ARTICLE_TEMPLATE.format(
        title=summary_data.get('title', ''),
        author=summary_data.get('author', 'LabVIEW视觉'),
        venue=summary_data.get('venue', ''),
        institution=summary_data.get('institution', ''),
        cover_image=cover_image,
        insight=summary_data.get('insight', ''),
        method=summary_data.get('method', ''),
        experiment=summary_data.get('experiment', ''),
        conclusion=summary_data.get('conclusion', ''),
        paper_title=summary_data.get('paper_title', ''),
        authors=summary_data.get('authors', ''),
        paper_url=summary_data.get('paper_url', ''),
        code_url=summary_data.get('code_url', '')
    )
    
    # 插入正文配图
    lines = content.split('\n')
    new_lines = []
    figure_idx = 0
    
    for line in lines:
        new_lines.append(line)
        # 在特定章节后插入配图
        if line.startswith('## 1.') and figure_idx < len(figures):
            new_lines.append(f"\n![方法图]({figures[figure_idx]})\n")
            figure_idx += 1
        elif line.startswith('## 2.') and figure_idx < len(figures):
            new_lines.append(f"\n![实验图]({figures[figure_idx]})\n")
            figure_idx += 1
    
    final_content = '\n'.join(new_lines)
    
    # 保存
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    
    print(f"✅ 文章已生成: {output_path}")
    return str(output_path)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="生成公众号文章")
    parser.add_argument("summary", help="论文总结 JSON 文件 (支持工作目录结构)")
    parser.add_argument("cover", help="封面图路径")
    parser.add_argument("figures", nargs='+', help="正文配图路径")
    parser.add_argument("-o", "--output", default=None, help="输出文件 (默认保存到工作目录)")
    parser.add_argument("--id", dest="arxiv_id", default=None, help="arXiv ID (可选，用于推断工作目录)")
    
    args = parser.parse_args()
    
    generate_article(args.summary, args.cover, args.figures, args.output, args.arxiv_id)
