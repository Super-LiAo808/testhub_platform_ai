#!/usr/bin/env python3
"""Import a Markdown file as Feishu docx and move it under a wiki parent node.

Reads user access token from Cursor mcp.json (-u arg). Never prints the token.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path


def _http_json(method: str, url: str, token: str | None = None, data=None, raw_body=None, headers=None):
    h = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        h.update(headers)
    if token:
        h["Authorization"] = f"Bearer {token}"
    body = raw_body
    if body is None and data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        try:
            return json.loads(err)
        except Exception:
            return {"_http_error": e.code, "_body": err}


def _load_mcp_user_token(mcp_json: Path) -> str:
    cfg = json.loads(mcp_json.read_text(encoding="utf-8"))
    servers = cfg.get("mcpServers") or {}
    for name in ("lark-mcp", "user-lark-mcp"):
        block = servers.get(name) or {}
        args = block.get("args") or []
        if "-u" in args:
            idx = args.index("-u")
            if idx + 1 < len(args):
                tok = args[idx + 1]
                if tok.count(".") == 2 and len(tok) > 80:
                    return tok
    raise SystemExit(f"No valid -u user token in {mcp_json}")


def _load_skill_config(skill_dir: Path) -> dict:
    for name in ("config.json", "config.example.json"):
        p = skill_dir / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _root_folder_token(user_token: str) -> str:
    root = _http_json(
        "GET",
        "https://open.feishu.cn/open-apis/drive/explorer/v2/root_folder/meta",
        token=user_token,
    )
    if root.get("code") != 0:
        raise SystemExit(f"root folder meta failed: {root}")
    return (root.get("data") or {}).get("token") or ""


def _upload_md(user_token: str, md_bytes: bytes, file_name: str, folder_token: str) -> str:
    boundary = "----feishu" + uuid.uuid4().hex
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file_name\"\r\n\r\n{file_name}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"parent_type\"\r\n\r\nexplorer\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"parent_node\"\r\n\r\n{folder_token}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"size\"\r\n\r\n{len(md_bytes)}\r\n".encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_name}\"\r\n"
        f"Content-Type: text/markdown\r\n\r\n".encode()
        + md_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    upload = _http_json(
        "POST",
        "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all",
        token=user_token,
        raw_body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    token = (upload.get("data") or {}).get("file_token")
    if not token:
        raise SystemExit(f"upload failed: {upload}")
    return token


def _import_docx(user_token: str, file_token: str, title: str, folder_token: str) -> str:
    imp = _http_json(
        "POST",
        "https://open.feishu.cn/open-apis/drive/v1/import_tasks",
        token=user_token,
        data={
            "file_extension": "md",
            "file_token": file_token,
            "type": "docx",
            "file_name": title[:27],
            "point": {"mount_type": 1, "mount_key": folder_token},
        },
    )
    ticket = (imp.get("data") or {}).get("ticket")
    if not ticket:
        raise SystemExit(f"import create failed: {imp}")
    for _ in range(60):
        time.sleep(1)
        st = _http_json(
            "GET",
            f"https://open.feishu.cn/open-apis/drive/v1/import_tasks/{ticket}",
            token=user_token,
        )
        result = (st.get("data") or {}).get("result") or {}
        if result.get("job_status") == 0 and result.get("token"):
            return result["token"]
        if result.get("job_status") not in (0, 1, 2, None):
            raise SystemExit(f"import failed: {st}")
    raise SystemExit("import timeout")


def _move_to_wiki(user_token: str, space_id: str, parent_node: str, doc_token: str) -> dict:
    return _http_json(
        "POST",
        f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes/move_docs_to_wiki",
        token=user_token,
        data={
            "parent_wiki_token": parent_node,
            "obj_type": "docx",
            "obj_token": doc_token,
        },
    )


def _find_wiki_node(user_token: str, space_id: str, parent_node: str, doc_token: str) -> str | None:
    # direct get by obj token
    node = _http_json(
        "GET",
        f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={doc_token}&obj_type=docx",
        token=user_token,
    )
    if node.get("code") == 0:
        nt = ((node.get("data") or {}).get("node") or {}).get("node_token")
        if nt:
            return nt
    children = _http_json(
        "GET",
        f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes?parent_node_token={parent_node}&page_size=50",
        token=user_token,
    )
    for item in (children.get("data") or {}).get("items") or []:
        if item.get("obj_token") == doc_token:
            return item.get("node_token")
    return None


def main() -> int:
    skill_dir = Path(__file__).resolve().parent.parent
    cfg = _load_skill_config(skill_dir)

    parser = argparse.ArgumentParser(description="Publish markdown changelog to Feishu wiki")
    parser.add_argument("--md", required=True, help="Path to markdown file")
    parser.add_argument("--title", default="", help="Document title (default: md stem)")
    parser.add_argument("--space-id", default=os.environ.get("FEISHU_WIKI_SPACE_ID") or cfg.get("space_id", ""))
    parser.add_argument(
        "--parent-node",
        default=os.environ.get("FEISHU_WIKI_PARENT_NODE") or cfg.get("parent_node", ""),
    )
    parser.add_argument(
        "--mcp-json",
        default=cfg.get("mcp_json_path")
        or os.environ.get("CURSOR_MCP_JSON")
        or str(Path.home() / ".cursor" / "mcp.json"),
    )
    args = parser.parse_args()

    if not args.space_id or not args.parent_node:
        print("ERROR: space_id / parent_node required (config.json or env)", file=sys.stderr)
        return 2

    md_path = Path(args.md)
    if not md_path.is_file():
        print(f"ERROR: md not found: {md_path}", file=sys.stderr)
        return 2

    title = args.title or cfg.get("title_prefix", "迭代说明")
    if title == cfg.get("title_prefix", "迭代说明"):
        # include date from filename if present
        title = f"{title} {md_path.stem}"[:80]

    user_token = _load_mcp_user_token(Path(args.mcp_json))
    md_bytes = md_path.read_bytes()
    folder = _root_folder_token(user_token)
    print("upload…")
    file_token = _upload_md(user_token, md_bytes, f"{md_path.stem}.md", folder)
    print("import…")
    doc_token = _import_docx(user_token, file_token, title, folder)
    print(f"docx={doc_token}")
    print("move to wiki…")
    move = _move_to_wiki(user_token, args.space_id, args.parent_node, doc_token)
    if move.get("code") != 0:
        print(f"ERROR move failed: {move.get('code')} {move.get('msg')}", file=sys.stderr)
        print(f"cloud_doc=https://my.feishu.cn/docx/{doc_token}")
        return 1

    # async task may need a moment
    time.sleep(2)
    wiki_token = None
    data = move.get("data") or {}
    wiki_token = data.get("wiki_token") or (data.get("node") or {}).get("node_token")
    if not wiki_token:
        for _ in range(10):
            wiki_token = _find_wiki_node(user_token, args.space_id, args.parent_node, doc_token)
            if wiki_token:
                break
            time.sleep(1)

    if wiki_token:
        url = f"https://my.feishu.cn/wiki/{wiki_token}"
        print(f"OK wiki_url={url}")
    else:
        print(f"OK moved (node pending) docx=https://my.feishu.cn/docx/{doc_token}")
        print(f"parent=https://my.feishu.cn/wiki/{args.parent_node}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
