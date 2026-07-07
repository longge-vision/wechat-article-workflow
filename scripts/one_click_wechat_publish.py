#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DEFAULT_KEY = Path(r"C:\Users\User\.ssh\codex_server_generated")
DEFAULT_HOST = "175.178.71.163"
DEFAULT_USER = "deploy"
REMOTE_BASE = "/home/deploy/wechat-publisher/jobs"
REMOTE_NODE = "/home/deploy/tools/node-v24.11.1-linux-x64/bin/node"
REMOTE_WENYAN = "/home/deploy/.npm-global/lib/node_modules/@wenyan-md/cli/dist/cli.js"
REMOTE_OPS = "/home/deploy/wechat-publisher/tools/wechat_ops.py"
REMOTE_REPLY = "/home/deploy/wechat-publisher/tools/wechat_reply_server.py"


IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
COVER_RE = re.compile(r"^cover:\s*(.+?)\s*$", re.M)
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)(?:\n---\s*\n)", re.S)
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
BARE_URL_RE = re.compile(r"(?<!\]\()https?://[^\s)）>]+")
DEFAULT_AUTHOR = "LabVIEW"
DEFAULT_THEME = "phycat"
DEFAULT_KEYWORD_PREFIX = "论文"
DEFAULT_SETTINGS_PATH = Path(__file__).with_name("wechat_publish_settings.json")
DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": DEFAULT_THEME,
    "author": DEFAULT_AUTHOR,
    "digest": "",
    "source_url": "",
    "clear_source_url": True,
    "footnote": False,
    "strip_resource_links": True,
    "keyword_prefix": DEFAULT_KEYWORD_PREFIX,
    "need_open_comment": True,
    "only_fans_can_comment": False,
    "apply_draft_settings_update": True,
    "require_manual_publish_confirmation": True,
    "original_declaration": {
        "enabled": True,
        "type": "original",
        "note": "发布前在公众号后台勾选原创声明，并按实际情况确认转载/引用规则。",
    },
    "insert_ads": {
        "enabled": True,
        "type": "traffic_ad",
        "note": "发布前在公众号后台确认流量主广告/文中广告位置。",
    },
    "manual_settings": {
        "publisher": "在公众号后台最终发布时确认操作人",
        "original_declaration": "必须确认：在公众号后台勾选原创声明",
        "insert_ads": "必须确认：在公众号后台插入/确认广告设置",
        "appreciation": "如需赞赏，在公众号后台发布前手动确认",
        "cover_display": "封面图和封面裁剪在公众号后台发布前最终确认",
        "collection_or_topic": "如需合集、话题或专辑，在公众号后台发布前选择",
    },
}
RESOURCE_HINT = (
    "\n\n> 获取论文原文和代码链接：关注公众号后，在后台回复关键词「{keyword}」。\n"
)


def run(cmd: list[str], *, timeout: int = 300, show: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
    if show and result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"command failed: {' '.join(cmd)}")
    return result


def merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_publish_settings(path: str | None) -> dict[str, Any]:
    if not path:
        settings_path = DEFAULT_SETTINGS_PATH
    else:
        settings_path = Path(path).expanduser()
    settings = dict(DEFAULT_SETTINGS)
    if settings_path.exists():
        loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise RuntimeError(f"Invalid settings file: {settings_path}")
        settings = merge_dict(settings, loaded)
    settings["_path"] = str(settings_path)
    return settings


def coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "是", "开"}
    return bool(value)


def apply_publish_settings(args: argparse.Namespace, settings: dict[str, Any]) -> None:
    string_defaults = {
        "theme": DEFAULT_THEME,
        "author": DEFAULT_AUTHOR,
        "digest": "",
        "source_url": "",
        "keyword_prefix": DEFAULT_KEYWORD_PREFIX,
        "resource_title": "",
    }
    for name, fallback in string_defaults.items():
        if getattr(args, name, None) is None:
            setattr(args, name, str(settings.get(name, fallback) or ""))

    bool_defaults = {
        "clear_source_url": True,
        "strip_resource_links": True,
        "footnote": False,
        "need_open_comment": True,
        "only_fans_can_comment": False,
        "apply_draft_settings_update": True,
        "manual_publish_confirmed": False,
    }
    for name, fallback in bool_defaults.items():
        if getattr(args, name, None) is None:
            setattr(args, name, coerce_bool(settings.get(name), fallback))

    if args.title is None:
        args.title = str(settings.get("title", "") or "")
    if args.cover is None:
        args.cover = str(settings.get("cover", "") or "")
    if args.keyword is None:
        args.keyword = str(settings.get("keyword", "") or "")
    args.publish_settings = settings


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "data:"))


def clean_link(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    return value


def resolve_asset(link: str, md_dir: Path) -> Path | None:
    link = clean_link(link)
    if not link or is_url(link):
        return None
    link = link.split("#", 1)[0].split("?", 1)[0]
    candidate = Path(link)
    if not candidate.is_absolute():
        candidate = md_dir / candidate
    try:
        candidate = candidate.resolve()
    except OSError:
        candidate = candidate.absolute()
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def unique_name(path: Path, used: set[str]) -> str:
    name = path.name
    if name not in used:
        used.add(name)
        return name
    stem = path.stem
    suffix = path.suffix
    idx = 2
    while True:
        candidate = f"{stem}_{idx}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        idx += 1


def collect_assets(markdown: str, md_dir: Path) -> tuple[dict[Path, str], str | None]:
    assets: dict[Path, str] = {}
    used: set[str] = set()

    def add(path: Path) -> str:
        existing = assets.get(path)
        if existing:
            return existing
        name = unique_name(path, used)
        assets[path] = name
        return name

    cover_remote_name: str | None = None
    cover_match = COVER_RE.search(markdown)
    if cover_match:
        cover_path = resolve_asset(cover_match.group(1), md_dir)
        if cover_path:
            cover_remote_name = add(cover_path)

    for match in IMAGE_RE.finditer(markdown):
        img_path = resolve_asset(match.group(1), md_dir)
        if img_path:
            add(img_path)

    return assets, cover_remote_name


def split_front_matter(markdown: str) -> tuple[dict[str, str], str]:
    match = FRONT_MATTER_RE.match(markdown)
    if not match:
        return {}, markdown
    meta: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, markdown[match.end() :]


def dump_front_matter(meta: dict[str, str]) -> str:
    lines = ["---"]
    primary_keys = (
        "title",
        "cover",
        "author",
        "digest",
        "description",
        "source_url",
        "need_open_comment",
        "only_fans_can_comment",
    )
    for key in primary_keys:
        if key in meta and meta[key] != "":
            lines.append(f"{key}: {meta[key]}")
    for key in sorted(k for k in meta if k not in set(primary_keys)):
        if meta[key] != "":
            lines.append(f"{key}: {meta[key]}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def first_heading(markdown: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", markdown, re.M)
    return match.group(1).strip() if match else ""


def derive_keyword(markdown: str, fallback: str, prefix: str) -> str:
    title = first_heading(markdown) or fallback
    if "REF+CFA" in title or "Residual Fields" in markdown or "Anomaly-Related Residual Fields" in markdown:
        return f"{prefix}REF"
    words = re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", title)
    stop = {"CVPR", "AUROC", "AUPRC", "IEEE", "arXiv"}
    for word in words:
        if word not in stop:
            return f"{prefix}{word[:16]}"
    chinese = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", title)
    return (prefix + chinese[:8]) if chinese else f"{prefix}{datetime.now().strftime('%m%d')}"


def is_wechat_article_url(url: str) -> bool:
    lower = url.lower()
    return "mp.weixin.qq.com/s" in lower


def strip_resource_links(markdown: str, keyword: str, keep_http_images: bool = True) -> tuple[str, list[dict[str, str]]]:
    resources: list[dict[str, str]] = []

    def remember(label: str, url: str) -> None:
        lower = url.lower()
        label_lower = label.lower()
        if any(token in lower for token in ("arxiv.org", "openaccess.thecvf.com", "github.com", "gitlab.com", "huggingface.co")) or any(
            token in label_lower for token in ("论文", "pdf", "代码", "github", "开源", "paper", "code")
        ):
            if not any(item["url"] == url for item in resources):
                resources.append({"label": label.strip(), "url": url.strip()})

    def replace_md_link(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        if is_wechat_article_url(url):
            return match.group(0)
        remember(label, url)
        return label

    markdown = LINK_RE.sub(replace_md_link, markdown)

    def replace_bare_url(match: re.Match[str]) -> str:
        url = match.group(0)
        if is_wechat_article_url(url):
            return url
        if keep_http_images and re.search(r"\.(png|jpg|jpeg|gif|webp)(\?|$)", url, flags=re.I):
            return url
        remember("资源链接", url)
        return "后台回复关键词获取"

    markdown = BARE_URL_RE.sub(replace_bare_url, markdown)

    lines = []
    skip_section = False
    for line in markdown.splitlines():
        heading = re.match(r"^#{2,3}\s+(.+)$", line)
        if heading:
            title = heading.group(1)
            skip_section = any(token in title for token in ("扩展阅读", "技术工具", "资源", "资料", "发布时隐藏", "相关研究"))
            if skip_section:
                continue
        if skip_section:
            if re.match(r"^##\s+", line):
                skip_section = False
            else:
                continue
        if any(token in line for token in ("论文链接", "PDF", "开源地址", "官方代码仓库")):
            remember(line, "")
            continue
        lines.append(line)
    markdown = "\n".join(lines).strip() + "\n"
    if "后台回复关键词" not in markdown:
        markdown += RESOURCE_HINT.format(keyword=keyword)
    return markdown, [item for item in resources if item.get("url")]


def prepare_markdown(markdown: str, args: argparse.Namespace) -> tuple[str, str, list[dict[str, str]]]:
    meta, body = split_front_matter(markdown)
    title = args.title or meta.get("title") or first_heading(body)
    if not title:
        raise RuntimeError("Article title not found. Add a first-level heading or --title.")
    keyword = args.keyword or meta.get("keyword") or derive_keyword(body, title, args.keyword_prefix)
    if args.strip_resource_links:
        body, resources = strip_resource_links(body, keyword)
    else:
        resources = []
    meta["title"] = title
    meta["author"] = args.author or meta.get("author") or DEFAULT_AUTHOR
    if args.cover:
        meta["cover"] = args.cover
    if args.digest:
        meta["digest"] = args.digest
        meta["description"] = args.digest
    if args.source_url:
        meta["source_url"] = args.source_url
    elif args.clear_source_url:
        meta.pop("source_url", None)
    meta["need_open_comment"] = "true" if args.need_open_comment else "false"
    meta["only_fans_can_comment"] = "true" if args.only_fans_can_comment else "false"
    meta["keyword"] = keyword
    return dump_front_matter(meta) + body.lstrip(), keyword, resources


def render_publish_checklist(
    args: argparse.Namespace,
    *,
    keyword: str,
    media_id: str = "",
    remote_job: str = "",
    assets_count: int = 0,
    resources_count: int = 0,
) -> str:
    settings = getattr(args, "publish_settings", {}) or {}
    manual = settings.get("manual_settings") or {}
    original = settings.get("original_declaration") or {}
    ads = settings.get("insert_ads") or {}
    lines = [
        "# 公众号发布设置检查清单",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 配置文件: {settings.get('_path', '')}",
        f"- 草稿 Media ID: {media_id or '未发布，仅预处理'}",
        f"- 远程任务目录: {remote_job or '未上传'}",
        f"- 资源关键词: {keyword}",
        f"- 图片素材数量: {assets_count}",
        f"- 已隐藏资源链接数量: {resources_count}",
        "",
        "## 已自动设置",
        "",
        f"- 样式主题: {args.theme}",
        f"- 作者: {args.author}",
        f"- 摘要/description: {args.digest or '未单独设置，由公众号后台/正文摘要处理'}",
        f"- 原文链接 source_url: {'已清空' if args.clear_source_url and not args.source_url else args.source_url}",
        f"- 引用脚注: {'保留' if args.footnote else '关闭'}",
        f"- 论文/PDF/代码链接: {'已从正文隐藏，改为后台关键词回复' if args.strip_resource_links else '保留在正文'}",
        f"- 留言评论: {'开启' if args.need_open_comment else '关闭'}",
        f"- 仅粉丝可评论: {'是' if args.only_fans_can_comment else '否'}",
        f"- 草稿二次设置校准: {'开启' if args.apply_draft_settings_update else '关闭'}",
        "",
        "## 必须后台确认",
        "",
        f"- 原创声明: {'需要' if coerce_bool(original.get('enabled'), True) else '不要求'}；{original.get('note', '在公众号后台发布前确认')}",
        f"- 广告插入: {'需要' if coerce_bool(ads.get('enabled'), True) else '不要求'}；{ads.get('note', '在公众号后台发布前确认')}",
        f"- API 直接正式发布: {'已允许' if args.manual_publish_confirmed else '未允许，需先后台确认原创和广告'}",
        "",
        "## 发布前手动确认",
        "",
    ]
    if manual:
        for key, value in manual.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.extend(
            [
                "- 原创声明: 在公众号后台发布前确认",
                "- 广告插入: 在公众号后台发布前确认",
                "- 发布人/操作人: 在公众号后台确认",
                "- 封面裁剪和是否展示封面: 在公众号后台确认",
            ]
        )
    lines.extend(
        [
            "",
            "## 当前限制",
            "",
            "- 微信草稿 API 可以写入作者、摘要、原文链接、评论权限等字段。",
            "- 原创声明、广告插入、赞赏、合集/话题、最终发布操作人通常属于公众号后台发布页控制项，本脚本不默认代替人工确认。",
            "",
        ]
    )
    return "\n".join(lines)


def render_backend_reply(keyword: str, resources: list[dict[str, str]], title: str = "") -> str:
    heading = title or f"{keyword} 相关资料"
    lines = [heading, "", f"关键词：{keyword}", ""]
    if not resources:
        lines.append("资料链接暂未整理。")
        return "\n".join(lines).strip() + "\n"
    for idx, item in enumerate(resources, 1):
        url = item.get("url") or ""
        if not url:
            continue
        label = item.get("label") or f"资料 {idx}"
        lower = url.lower()
        if "github.com" in lower or "gitlab.com" in lower:
            label = "GitHub 代码" if "github.com" in lower else "代码仓库"
        elif lower.endswith(".pdf") or "/papers/" in lower or "/pdf/" in lower:
            label = "PDF 原文"
        elif "openaccess.thecvf.com" in lower or "arxiv.org/abs" in lower:
            label = "论文主页"
        lines.append(f"{idx}. {label}")
        lines.append(url)
        lines.append("")
    lines.append("如果链接打不开，可以复制到浏览器访问。")
    return "\n".join(lines).strip() + "\n"


def rewrite_markdown(markdown: str, md_dir: Path, assets: dict[Path, str], remote_job: str, cover_name: str | None) -> str:
    by_resolved = {path: name for path, name in assets.items()}

    if cover_name:
        markdown = COVER_RE.sub(f"cover: {remote_job}/images/{cover_name}", markdown, count=1)

    def replace_image(match: re.Match[str]) -> str:
        original = match.group(1)
        img_path = resolve_asset(original, md_dir)
        if not img_path:
            return match.group(0)
        name = by_resolved.get(img_path)
        if not name:
            return match.group(0)
        return match.group(0).replace(original, f"../images/{name}")

    return IMAGE_RE.sub(replace_image, markdown)


def scp_file(key: Path, local: Path, user: str, host: str, remote: str) -> None:
    run(["scp", "-i", str(key), str(local), f"{user}@{host}:{remote}"], timeout=180)


def ssh(key: Path, user: str, host: str, remote_cmd: str, *, timeout: int = 300, show: bool = False) -> subprocess.CompletedProcess[str]:
    return run(["ssh", "-i", str(key), f"{user}@{host}", remote_cmd], timeout=timeout, show=show)


def quote_sh(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def publish(args: argparse.Namespace) -> int:
    md_path = Path(args.markdown).expanduser().resolve()
    if not md_path.exists():
        raise FileNotFoundError(md_path)
    if not os.environ.get("WECHAT_APP_ID") or not os.environ.get("WECHAT_APP_SECRET"):
        raise RuntimeError("WECHAT_APP_ID and WECHAT_APP_SECRET must be set locally.")

    key = Path(args.key).expanduser()
    user = args.user
    host = args.host
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_name = args.job_name or f"{md_path.stem}-{stamp}"
    job_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", job_name).strip("-")[:120]
    remote_job = f"{args.remote_base.rstrip('/')}/{job_name}"

    markdown = md_path.read_text(encoding="utf-8")
    markdown, keyword, resources = prepare_markdown(markdown, args)
    assets, cover_name = collect_assets(markdown, md_path.parent)

    if args.dry_run:
        out = md_path.with_suffix(md_path.suffix + ".prepared.md")
        out.write_text(markdown, encoding="utf-8")
        resource_out = md_path.with_suffix(md_path.suffix + ".resources.json")
        resource_out.write_text(
            json.dumps({"keyword": keyword, "resources": resources}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        reply_out = md_path.with_suffix(md_path.suffix + ".reply.txt")
        reply_out.write_text(render_backend_reply(keyword, resources, args.resource_title or keyword), encoding="utf-8")
        checklist_out = md_path.with_suffix(md_path.suffix + ".publish_checklist.md")
        checklist_out.write_text(
            render_publish_checklist(
                args,
                keyword=keyword,
                assets_count=len(assets),
                resources_count=len(resources),
            ),
            encoding="utf-8",
        )
        print(f"Prepared Markdown: {out}")
        print(f"Resource JSON: {resource_out}")
        print(f"Backend Reply Text: {reply_out}")
        print(f"Publish Checklist: {checklist_out}")
        print(f"Keyword: {keyword}")
        print(f"Assets: {len(assets)}")
        return 0

    with tempfile.TemporaryDirectory(prefix="wechat_publish_") as tmpdir:
        tmp = Path(tmpdir)
        outputs = tmp / "outputs"
        images = tmp / "images"
        outputs.mkdir()
        images.mkdir()
        rewritten = rewrite_markdown(markdown, md_path.parent, assets, remote_job, cover_name)
        staged_md = outputs / "article.md"
        staged_md.write_text(rewritten, encoding="utf-8")
        for src, name in assets.items():
            shutil.copy2(src, images / name)

        ssh(key, user, host, f"mkdir -p {quote_sh(remote_job + '/outputs')} {quote_sh(remote_job + '/images')}", timeout=60)
        scp_file(key, staged_md, user, host, f"{remote_job}/outputs/article.md")
        for item in images.iterdir():
            scp_file(key, item, user, host, f"{remote_job}/images/{item.name}")

        resource_file = tmp / "resources.json"
        resource_file.write_text(json.dumps({"keyword": keyword, "resources": resources}, ensure_ascii=False, indent=2), encoding="utf-8")
        scp_file(key, resource_file, user, host, f"{remote_job}/resources.json")

    appid = quote_sh(os.environ["WECHAT_APP_ID"])
    secret = quote_sh(os.environ["WECHAT_APP_SECRET"])
    footnote_flag = "" if args.footnote else " --no-footnote"
    remote_publish = (
        f"cd {quote_sh(remote_job + '/outputs')} && "
        f"export WECHAT_APP_ID={appid} WECHAT_APP_SECRET={secret} && "
        f"{REMOTE_NODE} {REMOTE_WENYAN} publish --file article.md --theme {quote_sh(args.theme)} "
        f"--app-id {appid}{footnote_flag}"
    )
    result = ssh(key, user, host, remote_publish, timeout=300)
    output = (result.stdout or "").strip()
    print(output)
    media_match = re.search(r"Media ID:\s*([A-Za-z0-9_-]+)", output)
    media_id = media_match.group(1) if media_match else ""

    draft_update_output = ""
    if media_id and args.apply_draft_settings_update:
        remote_update_parts = [
            f"export WECHAT_APP_ID={appid} WECHAT_APP_SECRET={secret} &&",
            f"python3 {REMOTE_OPS} draft-update-settings {quote_sh(media_id)}",
            f"--author {quote_sh(args.author)}",
            f"--need-open-comment {1 if args.need_open_comment else 0}",
            f"--only-fans-can-comment {1 if args.only_fans_can_comment else 0}",
        ]
        if args.digest:
            remote_update_parts.append(f"--digest {quote_sh(args.digest)}")
        if args.source_url:
            remote_update_parts.append(f"--source-url {quote_sh(args.source_url)}")
        elif args.clear_source_url:
            remote_update_parts.append("--clear-source-url")
        updated = ssh(key, user, host, " ".join(remote_update_parts), timeout=120)
        draft_update_output = updated.stdout.strip()
        print(draft_update_output)

    resource_import_output = ""
    if resources:
        remote_import = (
            f"python3 {REMOTE_REPLY} import-resources {quote_sh(remote_job + '/resources.json')} "
            f"--keyword {quote_sh(keyword)} --title {quote_sh(args.resource_title or keyword)}"
        )
        imported = ssh(key, user, host, remote_import, timeout=60)
        resource_import_output = imported.stdout.strip()
        print(resource_import_output)

    preview_output = ""
    if args.preview_wxname:
        if not media_id:
            raise RuntimeError("publish succeeded but media_id was not detected; cannot preview.")
        remote_preview = (
            f"export WECHAT_APP_ID={appid} WECHAT_APP_SECRET={secret} && "
            f"python3 {REMOTE_OPS} preview {quote_sh(media_id)} --wxname {quote_sh(args.preview_wxname)}"
        )
        preview = ssh(key, user, host, remote_preview, timeout=120)
        preview_output = preview.stdout.strip()
        print(preview_output)

    submit_output = ""
    if args.submit:
        if not args.yes:
            raise RuntimeError("--submit requires --yes to avoid accidental formal publishing.")
        if (getattr(args, "publish_settings", {}) or {}).get("require_manual_publish_confirmation", True) and not args.manual_publish_confirmed:
            raise RuntimeError(
                "--submit is blocked because original declaration/ad insertion require WeChat backend confirmation. "
                "Confirm them in the backend first, then rerun with --manual-publish-confirmed."
            )
        if not media_id:
            raise RuntimeError("publish succeeded but media_id was not detected; cannot submit.")
        remote_submit = (
            f"export WECHAT_APP_ID={appid} WECHAT_APP_SECRET={secret} && "
            f"python3 {REMOTE_OPS} publish-submit {quote_sh(media_id)}"
        )
        submitted = ssh(key, user, host, remote_submit, timeout=120)
        submit_output = submitted.stdout.strip()
        print(submit_output)

    summary = {
        "markdown": str(md_path),
        "remote_job": remote_job,
        "media_id": media_id,
        "assets": len(assets),
        "keyword": keyword,
        "resources": resources,
        "resource_import_output": resource_import_output,
        "preview": bool(args.preview_wxname),
        "submitted": bool(args.submit),
        "settings": {
            "settings_file": (getattr(args, "publish_settings", {}) or {}).get("_path", ""),
            "theme": args.theme,
            "author": args.author,
            "digest": args.digest,
            "source_url": args.source_url,
            "clear_source_url": args.clear_source_url,
            "footnote": args.footnote,
            "strip_resource_links": args.strip_resource_links,
            "need_open_comment": args.need_open_comment,
            "only_fans_can_comment": args.only_fans_can_comment,
            "apply_draft_settings_update": args.apply_draft_settings_update,
            "manual_publish_confirmed": args.manual_publish_confirmed,
            "original_declaration": (getattr(args, "publish_settings", {}) or {}).get("original_declaration", {}),
            "insert_ads": (getattr(args, "publish_settings", {}) or {}).get("insert_ads", {}),
        },
        "draft_update_output": draft_update_output,
        "preview_output": preview_output,
        "submit_output": submit_output,
    }
    summary_path = md_path.with_suffix(md_path.suffix + ".publish.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    reply_path = md_path.with_suffix(md_path.suffix + ".reply.txt")
    reply_path.write_text(render_backend_reply(keyword, resources, args.resource_title or keyword), encoding="utf-8")
    checklist_path = md_path.with_suffix(md_path.suffix + ".publish_checklist.md")
    checklist_path.write_text(
        render_publish_checklist(
            args,
            keyword=keyword,
            media_id=media_id,
            remote_job=remote_job,
            assets_count=len(assets),
            resources_count=len(resources),
        ),
        encoding="utf-8",
    )
    print(f"Saved publish summary: {summary_path}")
    print(f"Saved backend reply text: {reply_path}")
    print(f"Saved publish checklist: {checklist_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One-click WeChat draft publishing through Tencent Cloud fixed IP.")
    parser.add_argument("markdown", help="Local markdown file to publish.")
    parser.add_argument("--settings", default=str(DEFAULT_SETTINGS_PATH), help="JSON publish settings file.")
    parser.add_argument("--theme")
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--cover")
    parser.add_argument("--digest")
    parser.add_argument("--source-url")
    parser.add_argument("--clear-source-url", action="store_true", default=None)
    parser.add_argument("--keep-source-url", action="store_false", dest="clear_source_url")
    parser.add_argument("--keyword")
    parser.add_argument("--keyword-prefix")
    parser.add_argument("--resource-title")
    parser.add_argument("--strip-resource-links", action="store_true", default=None)
    parser.add_argument("--keep-resource-links", action="store_false", dest="strip_resource_links")
    parser.add_argument("--footnote", action="store_true", default=None, help="Keep WenYan footnote references. Default: disabled.")
    parser.add_argument("--no-footnote", action="store_false", dest="footnote")
    parser.add_argument("--need-open-comment", type=int, choices=(0, 1), default=None, help="1 opens comments, 0 closes comments.")
    parser.add_argument("--only-fans-can-comment", type=int, choices=(0, 1), default=None, help="1 restricts comments to fans.")
    parser.add_argument("--apply-draft-settings-update", action="store_true", default=None)
    parser.add_argument("--no-draft-settings-update", action="store_false", dest="apply_draft_settings_update")
    parser.add_argument("--preview-wxname", default="", help="Send a preview to this WeChat ID after draft upload.")
    parser.add_argument("--submit", action="store_true", help="Submit the generated draft for formal publishing.")
    parser.add_argument("--yes", action="store_true", help="Required with --submit.")
    parser.add_argument("--manual-publish-confirmed", action="store_true", default=None, help="Confirm backend-only settings such as original declaration and ads were checked manually.")
    parser.add_argument("--job-name", default="")
    parser.add_argument("--dry-run", action="store_true", help="Prepare cleaned files locally without publishing.")
    parser.add_argument("--key", default=str(DEFAULT_KEY))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--remote-base", default=REMOTE_BASE)
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    settings = load_publish_settings(args.settings)
    apply_publish_settings(args, settings)
    return publish(args)


if __name__ == "__main__":
    raise SystemExit(main())
