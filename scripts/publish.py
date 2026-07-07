#!/usr/bin/env python3
"""
发布文章到公众号草稿箱
"""

import subprocess
import os
from pathlib import Path

def publish_article(article_md, theme="phycat", app_id=None, app_secret=None):
    """
    发布文章到公众号草稿箱
    
    Args:
        article_md: Markdown 文章路径
        theme: 主题风格（默认 phycat）
        app_id: 公众号 AppID（可选，默认从环境变量读取）
        app_secret: 公众号 AppSecret（可选）
    """
    article_md = Path(article_md)
    
    # 设置环境变量
    env = os.environ.copy()
    if app_id:
        env['WECHAT_APP_ID'] = app_id
    if app_secret:
        env['WECHAT_APP_SECRET'] = app_secret
    
    # 执行发布命令
    cmd = ['wenyan', 'publish', '-f', str(article_md), '--theme', theme]
    
    print(f"📤 发布文章: {article_md.name}")
    print(f"🎨 主题: {theme}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    if result.returncode == 0:
        print(f"✅ 发布成功")
        print(result.stdout)
        return True
    else:
        print(f"❌ 发布失败")
        print(result.stderr)
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="发布文章到公众号")
    parser.add_argument("article", help="Markdown 文章路径")
    parser.add_argument("--theme", default="phycat", help="主题风格")
    parser.add_argument("--app-id", help="公众号 AppID")
    parser.add_argument("--app-secret", help="公众号 AppSecret")
    
    args = parser.parse_args()
    
    publish_article(args.article, args.theme, args.app_id, args.app_secret)
