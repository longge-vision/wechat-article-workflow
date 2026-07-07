#!/usr/bin/env python3
"""
发送口播字幕和文章图片给用户
支持从工作目录自动推断路径
"""

import subprocess
import os
import sys
import re
from pathlib import Path

# 添加脚本目录到路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
from create_paper_workspace import get_workspace_paths

def send_files(audio_script=None, figure_dir=None, arxiv_id=None, user_id=None):
    """
    发送口播字幕和文章图片
    
    Args:
        audio_script: 口播字幕文件路径（默认从工作目录推断）
        figure_dir: 图片目录路径（默认从工作目录推断）
        arxiv_id: arXiv ID（可选，用于自动推断工作目录）
        user_id: 可选，指定用户ID
    """
    # 自动推断工作目录
    if arxiv_id or (audio_script is None and figure_dir is None):
        # 尝试从 audio_script 路径推断 arxiv_id
        if arxiv_id is None and audio_script:
            match = re.search(r'papers[\\/](\d+\.\d+)[\\/]', str(audio_script))
            if match:
                arxiv_id = match.group(1)
        
        # 尝试从 figure_dir 路径推断 arxiv_id
        if arxiv_id is None and figure_dir:
            match = re.search(r'papers[\\/](\d+\.\d+)[\\/]', str(figure_dir))
            if match:
                arxiv_id = match.group(1)
        
        if arxiv_id:
            paths = get_workspace_paths(arxiv_id)
            if audio_script is None:
                audio_script = paths["audio_script"]
            if figure_dir is None:
                figure_dir = paths["extracted_dir"]
            print(f"📁 使用工作目录: {paths['workspace']}")
    
    # 检查文件是否存在
    if audio_script is None or not Path(audio_script).exists():
        print(f"❌ 口播字幕文件不存在: {audio_script}")
        return
    
    figure_dir = Path(figure_dir) if figure_dir else Path("./extracted")
    if not figure_dir.exists():
        print(f"❌ 图片目录不存在: {figure_dir}")
        return
    
    # 发送口播字幕
    print("📤 发送口播字幕...")
    cmd = ['bash', '/root/.openclaw/workspace/skills/send-file/scripts/send.sh', str(audio_script)]
    if user_id:
        cmd.append(user_id)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ 口播字幕发送成功")
    else:
        print(f"❌ 口播字幕发送失败: {result.stderr}")
    
    # 发送所有图片
    print("\n📤 发送文章图片...")
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
    images = [f for f in figure_dir.iterdir() if f.suffix.lower() in image_extensions]
    
    for img_path in sorted(images):
        print(f"  发送: {img_path.name}")
        cmd = ['bash', '/root/.openclaw/workspace/skills/send-file/scripts/send.sh', str(img_path)]
        if user_id:
            cmd.append(user_id)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ {img_path.name}")
        else:
            print(f"  ❌ {img_path.name} 失败")
    
    print(f"\n✅ 共发送 {len(images)} 张图片")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="发送口播字幕和图片")
    parser.add_argument("audio_script", nargs='?', default=None, help="口播字幕文件路径 (支持工作目录结构)")
    parser.add_argument("figure_dir", nargs='?', default=None, help="图片目录路径 (支持工作目录结构)")
    parser.add_argument("--id", dest="arxiv_id", default=None, help="arXiv ID (可选，用于推断工作目录)")
    parser.add_argument("--user-id", help="指定用户ID")
    
    args = parser.parse_args()
    
    send_files(args.audio_script, args.figure_dir, args.arxiv_id, args.user_id)
