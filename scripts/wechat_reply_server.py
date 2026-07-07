#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DEFAULT_STORE = Path.home() / "wechat-publisher" / "keyword_resources.json"


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sha1_signature(token: str, timestamp: str, nonce: str) -> str:
    pieces = sorted([token, timestamp, nonce])
    return hashlib.sha1("".join(pieces).encode("utf-8")).hexdigest()


def xml_text(root: ET.Element, name: str) -> str:
    node = root.find(name)
    return node.text if node is not None and node.text is not None else ""


def cdata(value: str) -> str:
    return f"<![CDATA[{value}]]>"


def make_text_reply(to_user: str, from_user: str, content: str) -> bytes:
    now = int(time.time())
    xml = (
        "<xml>"
        f"<ToUserName>{cdata(to_user)}</ToUserName>"
        f"<FromUserName>{cdata(from_user)}</FromUserName>"
        f"<CreateTime>{now}</CreateTime>"
        f"<MsgType>{cdata('text')}</MsgType>"
        f"<Content>{cdata(content)}</Content>"
        "</xml>"
    )
    return xml.encode("utf-8")


def normalize_keyword(value: str) -> str:
    return "".join((value or "").strip().split()).upper()


def resource_text(keyword: str, store: dict) -> str:
    normalized = normalize_keyword(keyword)
    item = None
    for key, value in store.get("keywords", {}).items():
        if normalize_keyword(key) == normalized:
            item = value
            break
    if not item:
        return "没有找到这个关键词对应的资料。请检查关键词，或回复“目录”查看可用资料。"
    lines = [item.get("title") or f"关键词：{keyword}", ""]
    for idx, resource in enumerate(item.get("resources", []), 1):
        label = resource.get("label") or f"资料 {idx}"
        url = resource.get("url") or ""
        if url:
            lines.append(f"{idx}. {label}\n{url}")
    if item.get("note"):
        lines += ["", item["note"]]
    return "\n".join(lines).strip()


def catalog_text(store: dict) -> str:
    keywords = store.get("keywords", {})
    if not keywords:
        return "资料目录暂时为空。"
    lines = ["可回复以下关键词获取资料："]
    for key, value in keywords.items():
        title = value.get("title") or key
        lines.append(f"- {key}：{title}")
    return "\n".join(lines)


class WeChatHandler(BaseHTTPRequestHandler):
    token = ""
    store_path = DEFAULT_STORE

    def log_message(self, format, *args):  # noqa: A003
        return

    def verify(self) -> tuple[bool, str]:
        query = parse_qs(urlparse(self.path).query)
        signature = (query.get("signature") or [""])[0]
        timestamp = (query.get("timestamp") or [""])[0]
        nonce = (query.get("nonce") or [""])[0]
        echostr = (query.get("echostr") or [""])[0]
        expected = sha1_signature(self.token, timestamp, nonce)
        return signature == expected, echostr

    def do_GET(self):  # noqa: N802
        ok, echostr = self.verify()
        if not ok:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"forbidden")
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(echostr.encode("utf-8"))

    def do_POST(self):  # noqa: N802
        ok, _ = self.verify()
        if not ok:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"forbidden")
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length)
        try:
            root = ET.fromstring(body)
            to_user = xml_text(root, "ToUserName")
            from_user = xml_text(root, "FromUserName")
            msg_type = xml_text(root, "MsgType")
            content = xml_text(root, "Content")
            store = read_json(self.store_path, {"keywords": {}})
            if msg_type != "text":
                reply = "请发送文字关键词获取资料。回复“目录”查看可用资料。"
            elif normalize_keyword(content) in {"目录", "ML", "CATALOG"}:
                reply = catalog_text(store)
            else:
                reply = resource_text(content, store)
            payload = make_text_reply(from_user, to_user, reply)
            self.send_response(200)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.end_headers()
            self.wfile.write(payload)
        except Exception:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"success")


def cmd_add(args: argparse.Namespace) -> None:
    store = read_json(Path(args.store), {"keywords": {}})
    resources = []
    for item in args.resource:
        if "=" in item:
            label, url = item.split("=", 1)
        else:
            label, url = "资料链接", item
        resources.append({"label": label.strip(), "url": url.strip()})
    store.setdefault("keywords", {})[args.keyword] = {
        "title": args.title or args.keyword,
        "resources": resources,
        "note": args.note,
    }
    write_json(Path(args.store), store)
    print(json.dumps({"store": args.store, "keyword": args.keyword, "resources": len(resources)}, ensure_ascii=False))


def cmd_import(args: argparse.Namespace) -> None:
    data = read_json(Path(args.file), {})
    keyword = args.keyword or data.get("keyword")
    if not keyword:
        raise SystemExit("keyword is required")
    store = read_json(Path(args.store), {"keywords": {}})
    store.setdefault("keywords", {})[keyword] = {
        "title": args.title or keyword,
        "resources": data.get("resources", []),
        "note": args.note,
    }
    write_json(Path(args.store), store)
    print(json.dumps({"store": args.store, "keyword": keyword, "resources": len(data.get("resources", []))}, ensure_ascii=False))


def cmd_list(args: argparse.Namespace) -> None:
    print(json.dumps(read_json(Path(args.store), {"keywords": {}}), ensure_ascii=False, indent=2))


def cmd_serve(args: argparse.Namespace) -> None:
    token = args.token or os.environ.get("WECHAT_REPLY_TOKEN", "")
    if not token:
        raise SystemExit("WECHAT_REPLY_TOKEN or --token is required")
    WeChatHandler.token = token
    WeChatHandler.store_path = Path(args.store)
    server = ThreadingHTTPServer((args.host, args.port), WeChatHandler)
    print(f"wechat reply server listening on {args.host}:{args.port}, store={args.store}", flush=True)
    server.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WeChat keyword auto-reply server.")
    parser.add_argument("--store", default=str(DEFAULT_STORE))
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add")
    p.add_argument("keyword")
    p.add_argument("--title", default="")
    p.add_argument("--resource", action="append", default=[], help="label=url or url")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("import-resources")
    p.add_argument("file")
    p.add_argument("--keyword", default="")
    p.add_argument("--title", default="")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("list")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9088)
    p.add_argument("--token", default="")
    p.set_defaults(func=cmd_serve)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
