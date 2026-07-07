#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


API_ROOT = "https://api.weixin.qq.com"
TOKEN_CACHE = Path.home() / ".wechat-publisher" / "token_cache.json"
REPORT_DIR = Path.home() / "wechat-publisher" / "reports"


class WeChatError(RuntimeError):
    pass


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    data = None
    headers = {"User-Agent": "wechat-ops/1.0"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise WeChatError(f"HTTP {exc.code}: {raw}") from exc
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WeChatError(f"Non-JSON response: {raw[:500]}") from exc
    errcode = result.get("errcode")
    if errcode not in (None, 0):
        raise WeChatError(f"{errcode}: {result.get('errmsg', result)}")
    return result


def get_access_token(force: bool = False) -> str:
    appid = os.environ.get("WECHAT_APP_ID", "").strip()
    secret = os.environ.get("WECHAT_APP_SECRET", "").strip()
    if not appid or not secret:
        raise WeChatError("WECHAT_APP_ID and WECHAT_APP_SECRET are required in environment.")

    cache = read_json(TOKEN_CACHE, {})
    now = int(time.time())
    cache_key = appid
    token_data = cache.get(cache_key) or {}
    if not force and token_data.get("access_token") and int(token_data.get("expires_at", 0)) > now + 300:
        return str(token_data["access_token"])

    query = urllib.parse.urlencode(
        {"grant_type": "client_credential", "appid": appid, "secret": secret}
    )
    result = http_json(f"{API_ROOT}/cgi-bin/token?{query}", timeout=30)
    token = result.get("access_token")
    if not token:
        raise WeChatError(f"Missing access_token: {result}")
    cache[cache_key] = {
        "access_token": token,
        "expires_at": now + int(result.get("expires_in", 7200)),
    }
    write_json(TOKEN_CACHE, cache)
    return str(token)


def api_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = get_access_token()
    url = f"{API_ROOT}{path}?access_token={urllib.parse.quote(token)}"
    return http_json(url, payload=payload)


def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = get_access_token()
    merged = {"access_token": token}
    if params:
        merged.update(params)
    query = urllib.parse.urlencode(merged)
    return http_json(f"{API_ROOT}{path}?{query}")


def fetch_drafts(offset: int = 0, count: int = 20, content: bool = False) -> dict[str, Any]:
    payload = {"offset": offset, "count": count, "no_content": 0 if content else 1}
    return api_post("/cgi-bin/draft/batchget", payload)


def summarize_drafts(result: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for item in result.get("item", []):
        media_id = item.get("media_id", "")
        content = item.get("content") or {}
        news = content.get("news_item") or []
        first = news[0] if news else {}
        items.append(
            {
                "media_id": media_id,
                "title": first.get("title", ""),
                "author": first.get("author", ""),
                "update_time": item.get("update_time"),
                "article_count": len(news),
            }
        )
    return items


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def format_ts(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def duplicate_groups_from_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_title: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        title = item.get("title") or ""
        if not title:
            continue
        by_title.setdefault(title, []).append(item)
    groups = []
    for title, group in by_title.items():
        if len(group) <= 1:
            continue
        group = sorted(group, key=lambda x: int(x.get("update_time") or 0), reverse=True)
        groups.append({"title": title, "keep": group[0], "delete_candidates": group[1:]})
    return groups


def cmd_draft_list(args: argparse.Namespace) -> None:
    result = fetch_drafts(args.offset, args.count, args.content)
    if args.raw:
        print_json(result)
    else:
        print_json(
            {
                "total_count": result.get("total_count"),
                "item_count": result.get("item_count"),
                "items": summarize_drafts(result),
            }
        )


def cmd_draft_get(args: argparse.Namespace) -> None:
    print_json(api_post("/cgi-bin/draft/get", {"media_id": args.media_id}))


def cmd_draft_delete(args: argparse.Namespace) -> None:
    if not args.yes:
        raise WeChatError("Refusing to delete without --yes.")
    print_json(api_post("/cgi-bin/draft/delete", {"media_id": args.media_id}))


def cmd_draft_update_settings(args: argparse.Namespace) -> None:
    current = api_post("/cgi-bin/draft/get", {"media_id": args.media_id})
    news_items = ((current.get("news_item") or []) if "news_item" in current else ((current.get("content") or {}).get("news_item") or []))
    if not news_items:
        raise WeChatError(f"Draft has no article content: {args.media_id}")
    if args.index < 0 or args.index >= len(news_items):
        raise WeChatError(f"Article index out of range: {args.index}")

    article = dict(news_items[args.index])
    required_fields = ("title", "content", "thumb_media_id")
    missing = [name for name in required_fields if not article.get(name)]
    if missing:
        raise WeChatError(f"Draft article is missing required fields for update: {', '.join(missing)}")

    if args.author is not None:
        article["author"] = args.author
    if args.digest is not None:
        article["digest"] = args.digest
    if args.clear_source_url:
        article["content_source_url"] = ""
    elif args.source_url is not None:
        article["content_source_url"] = args.source_url
    if args.need_open_comment is not None:
        article["need_open_comment"] = int(args.need_open_comment)
    if args.only_fans_can_comment is not None:
        article["only_fans_can_comment"] = int(args.only_fans_can_comment)

    allowed = {
        "title",
        "author",
        "digest",
        "content",
        "content_source_url",
        "thumb_media_id",
        "need_open_comment",
        "only_fans_can_comment",
        "pic_crop_235_1",
        "pic_crop_1_1",
    }
    update_article = {key: article.get(key, "") for key in allowed if key in article}
    payload = {"media_id": args.media_id, "index": args.index, "articles": update_article}
    response = api_post("/cgi-bin/draft/update", payload)
    print_json(
        {
            "updated": True,
            "media_id": args.media_id,
            "index": args.index,
            "applied": {
                "author": update_article.get("author", ""),
                "digest": update_article.get("digest", ""),
                "content_source_url": update_article.get("content_source_url", ""),
                "need_open_comment": update_article.get("need_open_comment"),
                "only_fans_can_comment": update_article.get("only_fans_can_comment"),
            },
            "response": response,
        }
    )


def cmd_draft_duplicates(args: argparse.Namespace) -> None:
    result = fetch_drafts(0, args.count, content=False)
    items = summarize_drafts(result)
    groups = duplicate_groups_from_items(items)
    print_json({"duplicate_group_count": len(groups), "groups": groups})


def cmd_draft_delete_duplicates(args: argparse.Namespace) -> None:
    if not args.yes:
        raise WeChatError("Refusing to delete duplicate drafts without --yes.")
    result = fetch_drafts(0, args.count, content=False)
    items = summarize_drafts(result)
    by_title: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        title = item.get("title") or ""
        if not title:
            continue
        by_title.setdefault(title, []).append(item)
    deleted = []
    for group in by_title.values():
        if len(group) <= 1:
            continue
        group = sorted(group, key=lambda x: int(x.get("update_time") or 0), reverse=True)
        for item in group[1:]:
            media_id = item.get("media_id")
            if not media_id:
                continue
            response = api_post("/cgi-bin/draft/delete", {"media_id": media_id})
            deleted.append({"media_id": media_id, "title": item.get("title"), "response": response})
            if args.limit and len(deleted) >= args.limit:
                print_json({"deleted_count": len(deleted), "deleted": deleted, "stopped_at_limit": args.limit})
                return
    print_json({"deleted_count": len(deleted), "deleted": deleted})


def cmd_preview(args: argparse.Namespace) -> None:
    payload = {
        "towxname": args.wxname,
        "mpnews": {"media_id": args.media_id},
        "msgtype": "mpnews",
    }
    print_json(api_post("/cgi-bin/message/mass/preview", payload))


def cmd_user_list(args: argparse.Namespace) -> None:
    params = {}
    if args.next_openid:
        params["next_openid"] = args.next_openid
    result = api_get("/cgi-bin/user/get", params)
    openids = ((result.get("data") or {}).get("openid") or [])
    if args.raw:
        print_json(result)
    else:
        print_json(
            {
                "total": result.get("total"),
                "count": result.get("count"),
                "next_openid": result.get("next_openid"),
                "openid_sample": openids[: args.sample],
            }
        )


def cmd_user_info(args: argparse.Namespace) -> None:
    user_list = [{"openid": openid, "lang": args.lang} for openid in args.openid]
    print_json(api_post("/cgi-bin/user/info/batchget", {"user_list": user_list}))


def cmd_material_list(args: argparse.Namespace) -> None:
    payload = {"type": args.type, "offset": args.offset, "count": args.count}
    print_json(api_post("/cgi-bin/material/batchget_material", payload))


def cmd_material_count(_: argparse.Namespace) -> None:
    print_json(api_get("/cgi-bin/material/get_materialcount"))


def cmd_publish_list(args: argparse.Namespace) -> None:
    payload = {"offset": args.offset, "count": args.count, "no_content": 0 if args.content else 1}
    print_json(api_post("/cgi-bin/freepublish/batchget", payload))


def cmd_publish_article(args: argparse.Namespace) -> None:
    print_json(api_post("/cgi-bin/freepublish/getarticle", {"article_id": args.article_id}))


def cmd_stats(args: argparse.Namespace) -> None:
    endpoints = {
        "user-summary": "/datacube/getusersummary",
        "user-cumulate": "/datacube/getusercumulate",
        "article-summary": "/datacube/getarticlesummary",
        "article-total": "/datacube/getarticletotal",
    }
    payload = {"begin_date": args.begin, "end_date": args.end}
    print_json(api_post(endpoints[args.kind], payload))


def cmd_menu_get(_: argparse.Namespace) -> None:
    print_json(api_get("/cgi-bin/get_current_selfmenu_info"))


def cmd_menu_create(args: argparse.Namespace) -> None:
    if not args.yes:
        raise WeChatError("Refusing to update menu without --yes.")
    payload = read_json(Path(args.file), None)
    if not isinstance(payload, dict):
        raise WeChatError(f"Invalid menu JSON file: {args.file}")
    print_json(api_post("/cgi-bin/menu/create", payload))


def cmd_menu_delete(args: argparse.Namespace) -> None:
    if not args.yes:
        raise WeChatError("Refusing to delete menu without --yes.")
    print_json(api_get("/cgi-bin/menu/delete"))


def safe_call(name: str, func, *args, **kwargs) -> dict[str, Any]:
    try:
        return {"ok": True, "data": func(*args, **kwargs)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def render_daily_report(report: dict[str, Any]) -> str:
    lines = [
        f"# 公众号运营日报 {report['date']}",
        "",
        f"- 服务器出口 IP: `{report.get('server_ip', '')}`",
        f"- 生成时间: {report.get('generated_at', '')}",
        "",
        "## 粉丝",
    ]
    user_summary = report.get("user_summary") or {}
    if user_summary.get("ok"):
        items = user_summary.get("data", {}).get("list", [])
        new_user = sum(int(x.get("new_user", 0)) for x in items)
        cancel_user = sum(int(x.get("cancel_user", 0)) for x in items)
        lines += [f"- 新增关注: {new_user}", f"- 取消关注: {cancel_user}"]
    else:
        lines.append(f"- 获取失败: {user_summary.get('error')}")
    user_cumulate = report.get("user_cumulate") or {}
    if user_cumulate.get("ok"):
        items = user_cumulate.get("data", {}).get("list", [])
        if items:
            lines.append(f"- 累计关注: {items[-1].get('cumulate_user')}")

    lines += ["", "## 草稿"]
    draft = report.get("drafts") or {}
    if draft.get("ok"):
        data = draft.get("data", {})
        items = data.get("items", [])
        lines += [
            f"- 草稿总数: {data.get('total_count')}",
            f"- 最近检查: {len(items)} 篇",
        ]
        for item in items[:5]:
            lines.append(f"- {item.get('title')} ({format_ts(item.get('update_time'))})")
    else:
        lines.append(f"- 获取失败: {draft.get('error')}")

    duplicates = report.get("duplicate_drafts") or {}
    lines += ["", "## 重复草稿"]
    groups = duplicates.get("groups") or []
    lines.append(f"- 重复标题组: {len(groups)}")
    for group in groups[:10]:
        lines.append(
            f"- {group.get('title')}：保留 1 篇，可删 {len(group.get('delete_candidates') or [])} 篇"
        )

    lines += ["", "## 素材库"]
    material = report.get("material_count") or {}
    if material.get("ok"):
        data = material.get("data", {})
        lines += [
            f"- 图片: {data.get('image_count')}",
            f"- 图文: {data.get('news_count')}",
            f"- 视频: {data.get('video_count')}",
            f"- 音频: {data.get('voice_count')}",
        ]
    else:
        lines.append(f"- 获取失败: {material.get('error')}")

    lines += ["", "## 菜单"]
    menu = report.get("menu") or {}
    if menu.get("ok"):
        data = menu.get("data", {})
        lines.append(f"- 自定义菜单开启: {data.get('is_menu_open')}")
    else:
        lines.append(f"- 获取失败: {menu.get('error')}")

    lines += ["", "## 已发布文章"]
    published = report.get("published") or {}
    if published.get("ok"):
        data = published.get("data", {})
        lines += [f"- 接口返回总数: {data.get('total_count')}", f"- 本次返回: {data.get('item_count')}"]
        for item in data.get("item", [])[:5]:
            news = ((item.get("content") or {}).get("news_item") or [])
            title = news[0].get("title") if news else ""
            lines.append(f"- {title} ({format_ts(item.get('update_time'))})")
    else:
        lines.append(f"- 获取失败: {published.get('error')}")

    lines += ["", "## 图文数据"]
    article_summary = report.get("article_summary") or {}
    if article_summary.get("ok"):
        items = article_summary.get("data", {}).get("list", [])
        if not items:
            lines.append("- 昨日无图文统计数据或接口未返回。")
        for item in items[:20]:
            title = item.get("title") or item.get("msgid") or "未命名图文"
            lines.append(
                f"- {title}: 阅读 {item.get('int_page_read_count', 0)}, 分享 {item.get('share_count', 0)}, 收藏 {item.get('add_to_fav_count', 0)}"
            )
    else:
        lines.append(f"- 获取失败: {article_summary.get('error')}")

    lines.append("")
    return "\n".join(lines)


def cmd_daily_report(args: argparse.Namespace) -> None:
    target_date = args.date
    if not target_date:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    server_ip = ""
    try:
        with urllib.request.urlopen("https://ifconfig.me/ip", timeout=15) as resp:
            server_ip = resp.read().decode("utf-8", errors="replace").strip()
    except Exception:
        server_ip = ""

    draft_result = safe_call("drafts", fetch_drafts, 0, args.draft_count, False)
    draft_items = summarize_drafts(draft_result["data"]) if draft_result.get("ok") else []
    duplicate_groups = duplicate_groups_from_items(draft_items)

    payload = {"begin_date": target_date, "end_date": target_date}
    report = {
        "date": target_date,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "server_ip": server_ip,
        "user_summary": safe_call("user_summary", api_post, "/datacube/getusersummary", payload),
        "user_cumulate": safe_call("user_cumulate", api_post, "/datacube/getusercumulate", payload),
        "article_summary": safe_call("article_summary", api_post, "/datacube/getarticlesummary", payload),
        "drafts": {
            "ok": draft_result.get("ok"),
            "data": {
                "total_count": draft_result.get("data", {}).get("total_count") if draft_result.get("ok") else None,
                "item_count": draft_result.get("data", {}).get("item_count") if draft_result.get("ok") else None,
                "items": draft_items,
            },
            "error": draft_result.get("error"),
        },
        "duplicate_drafts": {
            "duplicate_group_count": len(duplicate_groups),
            "groups": duplicate_groups,
        },
        "material_count": safe_call("material_count", api_get, "/cgi-bin/material/get_materialcount"),
        "menu": safe_call("menu", api_get, "/cgi-bin/get_current_selfmenu_info"),
        "published": safe_call(
            "published",
            api_post,
            "/cgi-bin/freepublish/batchget",
            {"offset": 0, "count": args.publish_count, "no_content": 1},
        ),
    }
    markdown = render_daily_report(report)

    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"wechat-report-{target_date}.json"
    md_path = out_dir / f"wechat-report-{target_date}.md"
    write_json(json_path, report)
    md_path.write_text(markdown, encoding="utf-8")

    if args.format == "json":
        print_json({"json": str(json_path), "markdown": str(md_path), "report": report})
    else:
        print(markdown)
        print(f"\nSaved JSON: {json_path}")
        print(f"Saved Markdown: {md_path}")


def cmd_publish_submit(args: argparse.Namespace) -> None:
    print_json(api_post("/cgi-bin/freepublish/submit", {"media_id": args.media_id}))


def cmd_publish_status(args: argparse.Namespace) -> None:
    print_json(api_post("/cgi-bin/freepublish/get", {"publish_id": args.publish_id}))


def cmd_publish_delete(args: argparse.Namespace) -> None:
    payload: dict[str, Any] = {"article_id": args.article_id}
    if args.index is not None:
        payload["index"] = args.index
    if not args.yes:
        raise WeChatError("Refusing to delete published article without --yes.")
    print_json(api_post("/cgi-bin/freepublish/delete", payload))


def cmd_token(args: argparse.Namespace) -> None:
    token = get_access_token(force=args.force)
    print_json({"access_token_prefix": token[:12], "cache": str(TOKEN_CACHE)})


def cmd_ip(_: argparse.Namespace) -> None:
    with urllib.request.urlopen("https://ifconfig.me/ip", timeout=15) as resp:
        print(resp.read().decode("utf-8", errors="replace").strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WeChat Official Account operations.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("token", help="Fetch/cache access token.")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_token)

    p = sub.add_parser("ip", help="Show current server public IP.")
    p.set_defaults(func=cmd_ip)

    p = sub.add_parser("draft-list", help="List draft articles.")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--content", action="store_true", help="Include full draft content from API.")
    p.add_argument("--raw", action="store_true")
    p.set_defaults(func=cmd_draft_list)

    p = sub.add_parser("draft-get", help="Get one draft by media_id.")
    p.add_argument("media_id")
    p.set_defaults(func=cmd_draft_get)

    p = sub.add_parser("draft-delete", help="Delete one draft by media_id.")
    p.add_argument("media_id")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_draft_delete)

    p = sub.add_parser("draft-update-settings", help="Update publish-related settings on an existing draft.")
    p.add_argument("media_id")
    p.add_argument("--index", type=int, default=0)
    p.add_argument("--author")
    p.add_argument("--digest")
    p.add_argument("--source-url")
    p.add_argument("--clear-source-url", action="store_true")
    p.add_argument("--need-open-comment", type=int, choices=(0, 1))
    p.add_argument("--only-fans-can-comment", type=int, choices=(0, 1))
    p.set_defaults(func=cmd_draft_update_settings)

    p = sub.add_parser("draft-duplicates", help="Find drafts with duplicate titles.")
    p.add_argument("--count", type=int, default=50)
    p.set_defaults(func=cmd_draft_duplicates)

    p = sub.add_parser("draft-delete-duplicates", help="Delete duplicate-title drafts, keeping newest per title.")
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--limit", type=int, default=0, help="Maximum number of drafts to delete.")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_draft_delete_duplicates)

    p = sub.add_parser("preview", help="Send a draft preview to a WeChat account.")
    p.add_argument("media_id")
    p.add_argument("--wxname", required=True, help="WeChat ID that receives the preview.")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("user-list", help="List follower OpenIDs.")
    p.add_argument("--next-openid", default="")
    p.add_argument("--sample", type=int, default=10)
    p.add_argument("--raw", action="store_true")
    p.set_defaults(func=cmd_user_list)

    p = sub.add_parser("user-info", help="Get follower details by OpenID.")
    p.add_argument("openid", nargs="+")
    p.add_argument("--lang", default="zh_CN")
    p.set_defaults(func=cmd_user_info)

    p = sub.add_parser("material-count", help="Get material library counts.")
    p.set_defaults(func=cmd_material_count)

    p = sub.add_parser("material-list", help="List permanent materials.")
    p.add_argument("type", choices=("image", "voice", "video", "news"))
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--count", type=int, default=20)
    p.set_defaults(func=cmd_material_list)

    p = sub.add_parser("publish-list", help="List published articles.")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--content", action="store_true")
    p.set_defaults(func=cmd_publish_list)

    p = sub.add_parser("publish-article", help="Get a published article by article_id.")
    p.add_argument("article_id")
    p.set_defaults(func=cmd_publish_article)

    p = sub.add_parser("stats", help="Get basic account/article statistics.")
    p.add_argument("kind", choices=("user-summary", "user-cumulate", "article-summary", "article-total"))
    p.add_argument("--begin", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("menu-get", help="Get current custom menu.")
    p.set_defaults(func=cmd_menu_get)

    p = sub.add_parser("menu-create", help="Create/update custom menu from JSON.")
    p.add_argument("file")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_menu_create)

    p = sub.add_parser("menu-delete", help="Delete custom menu.")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_menu_delete)

    p = sub.add_parser("daily-report", help="Generate an operations daily report.")
    p.add_argument("--date", default="", help="Report date, default yesterday. Format: YYYY-MM-DD")
    p.add_argument("--draft-count", type=int, default=50)
    p.add_argument("--publish-count", type=int, default=10)
    p.add_argument("--output-dir", default="")
    p.add_argument("--format", choices=("markdown", "json"), default="markdown")
    p.set_defaults(func=cmd_daily_report)

    p = sub.add_parser("publish-submit", help="Submit a draft for publishing.")
    p.add_argument("media_id")
    p.set_defaults(func=cmd_publish_submit)

    p = sub.add_parser("publish-status", help="Get publishing status.")
    p.add_argument("publish_id")
    p.set_defaults(func=cmd_publish_status)

    p = sub.add_parser("publish-delete", help="Delete a published article.")
    p.add_argument("article_id")
    p.add_argument("--index", type=int)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_publish_delete)

    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except WeChatError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
