#!/usr/bin/env python3
"""
生成口播字幕
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

def generate_audio_script(summary_data, output_path=None, arxiv_id=None):
    """
    生成口播字幕
    
    格式要求：
    1. 开头开场白："大家好，我是视觉龙哥，专注工业视觉检测。"
    2. 每一段不要换行，不要有空格，不要空一行，保持连续
    
    Args:
        summary_data: 论文总结数据（dict 或 JSON 文件路径）
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
            output_path = paths["audio_script"]
        print(f"📁 使用工作目录: {paths['workspace']}")
    elif output_path is None:
        output_path = "./audio_script.txt"
    
    # 开场白
    opening = "大家好，我是视觉龙哥，专注工业视觉检测。"
    
    # 构建连续的字幕内容（无换行、无空行）
    sections = [
        opening,
        summary_data.get('title', ''),
        summary_data.get('insight', ''),
        '核心设计包括三个部分：' + summary_data.get('method', '').replace('\n', ' '),
        '实验结果表明：' + summary_data.get('experiment', '').replace('\n', ' '),
        summary_data.get('conclusion', '')
    ]
    
    # 过滤空内容并合并为一段连续文本
    script = ' '.join([s for s in sections if s])
    
    # 清理多余空格
    script = ' '.join(script.split())
    
    # 保存
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(script)
    
    print(f"✅ 口播字幕已生成: {output_path}")
    print(f"   格式: 连续文本，无换行")
    return str(output_path)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="生成口播字幕")
    parser.add_argument("summary", help="论文总结 JSON 文件 (支持工作目录结构)")
    parser.add_argument("-o", "--output", default=None, help="输出文件 (默认保存到工作目录)")
    parser.add_argument("--id", dest="arxiv_id", default=None, help="arXiv ID (可选，用于推断工作目录)")
    
    args = parser.parse_args()
    
    generate_audio_script(args.summary, args.output, args.arxiv_id)
