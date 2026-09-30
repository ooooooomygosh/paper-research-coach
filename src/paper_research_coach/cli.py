from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from platformdirs import user_data_path

from .exports import export, import_markdown
from .store import Store


def output(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parser():
    p = argparse.ArgumentParser(
        prog="prc", description="Paper Research Coach — 本地论文阅读与笔记"
    )
    p.add_argument(
        "--data-dir",
        default=os.environ.get("PRC_DATA_DIR")
        or str(user_data_path("paper-research-coach")),
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("list")
    imp = sub.add_parser("import", help="导入 PDF 或论文书目")
    imp.add_argument("path", nargs="?", default="")
    imp.add_argument("--title", required=True)
    imp.add_argument("--goal", default="")
    imp.add_argument("--type", default="empirical", dest="paper_type")
    for cmd in ("context", "resume"):
        c = sub.add_parser(cmd)
        c.add_argument("paper_id")
        c.add_argument("--since", type=int, default=0)
    c = sub.add_parser("commit", help="从 JSON 文件或标准输入提交事务")
    c.add_argument("file", nargs="?", default="-")
    t = sub.add_parser("text")
    t.add_argument("paper_id")
    t.add_argument("page_index", type=int, help="PDF 页索引，从 0 开始")
    h = sub.add_parser("history")
    h.add_argument("record_id")
    r = sub.add_parser("replace-source")
    r.add_argument("paper_id")
    r.add_argument("path")
    m = sub.add_parser("import-markdown")
    m.add_argument("paper_id")
    m.add_argument("path")
    e = sub.add_parser("export")
    e.add_argument("kind", choices=["paper", "ideas", "talk", "comparison", "pdf"])
    e.add_argument("--paper", dest="paper_id")
    e.add_argument("--output")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-open", action="store_true")
    z = sub.add_parser("sync")
    z.add_argument(
        "action",
        choices=[
            "status",
            "collections",
            "configure",
            "authorize",
            "run",
            "conflicts",
            "resolve",
        ],
        default="status",
        nargs="?",
    )
    z.add_argument("--server")
    z.add_argument("--collection")
    z.add_argument("--conflict")
    z.add_argument("--choice", choices=["local", "remote"])
    v = sub.add_parser("vault", help="连接 OneDrive / Obsidian 文献目录")
    v.add_argument(
        "action", choices=["status", "configure", "scan", "conflicts", "resolve"]
    )
    v.add_argument("--path")
    v.add_argument("--conflict")
    v.add_argument("--choice", choices=["file", "local", "both"])
    bg = sub.add_parser("service", help="macOS 登录后持续运行工作台与目录同步")
    bg.add_argument("action", choices=["install", "status", "stop"])
    bg.add_argument("--port", type=int, default=8765)
    meta = sub.add_parser("metadata", help="核实 PDF 书目或设置 OpenAlex（不上传全文）")
    meta.add_argument("action", choices=["status", "resolve", "openalex-key"])
    meta.add_argument("--paper")
    meta.add_argument("--refresh", action="store_true")
    i = sub.add_parser("install-skill")
    i.add_argument("--host", choices=["codex", "claude", "pi"], required=True)
    i.add_argument("--force", action="store_true")
    return p


def main():
    args = parser().parse_args()
    try:
        if args.command == "install-skill":
            base = {
                "codex": ".agents/skills",
                "claude": ".claude/skills",
                "pi": ".pi/agent/skills",
            }[args.host]
            dest = Path.home() / base / "paper-research-coach"
            src = Path(__file__).parent / "skill"
            if not src.exists():
                src = (
                    Path(__file__).resolve().parents[2]
                    / "skills"
                    / "paper-research-coach"
                )
            if dest.exists() and not args.force:
                raise ValueError("Skill 已存在；检查差异后使用 --force 更新。")
            shutil.copytree(src, dest, dirs_exist_ok=args.force)
            output(
                {"installed": str(dest), "next": "在新会话中启用 paper-research-coach"}
            )
            return
        store = Store(args.data_dir)
        cmd = args.command
        if cmd == "doctor":
            from .zotero import ZoteroSync

            try:
                server = ZoteroSync(store).probe()
                zotero = {"available": True, "server_id": server}
            except Exception:
                zotero = {
                    "available": False,
                    "next": "启动 Zotero 10 并在高级设置中启用本地应用通信",
                }
            output(
                {
                    "python": sys.version.split()[0],
                    "data_dir": str(store.root),
                    "frontend": (Path(__file__).parent / "static/index.html").exists(),
                    "zotero": zotero,
                    "ai": "由 Codex / Claude Code / Pi 当前宿主提供",
                }
            )
        elif cmd == "list":
            output(store.list("paper"))
        elif cmd == "import":
            output(
                store.add_paper(
                    args.title, args.path, goal=args.goal, paper_type=args.paper_type
                )
            )
        elif cmd in ("context", "resume"):
            output(store.context(args.paper_id, args.since))
        elif cmd == "commit":
            payload = (
                json.load(sys.stdin)
                if args.file == "-"
                else json.loads(Path(args.file).read_text())
            )
            output(store.commit(payload))
        elif cmd == "history":
            output(store.history(args.record_id))
        elif cmd == "replace-source":
            output(store.replace_source(args.paper_id, args.path))
        elif cmd == "import-markdown":
            output(import_markdown(store, args.paper_id, args.path))
        elif cmd == "text":
            from pypdf import PdfReader

            paper = store.get("paper", args.paper_id)
            if (
                store.check_source(args.paper_id)["status"] != "current"
                or not 0 <= args.page_index < paper["page_count"]
            ):
                raise ValueError("当前 PDF 不可用，或页索引超出范围。")
            reader = PdfReader(paper["source_path"])
            text = reader.pages[args.page_index].extract_text() or ""
            output(
                {
                    "text": text,
                    "page_index": args.page_index,
                    "page_label": reader.page_labels[args.page_index],
                    "source_version": paper["source_version"],
                    "untrusted_source": True,
                    "needs_visual_reading": not bool(text.strip()),
                }
            )
        elif cmd == "export":
            output(export(store, args.kind, args.paper_id, args.output))
        elif cmd == "serve":
            import uvicorn
            from .server import create_app, session_token

            token = session_token(store)
            url = f"http://127.0.0.1:{args.port}/#token={token}"
            print(
                f"本地阅读工作台：{url}\n此地址含本机访问凭证，请勿分享。", flush=True
            )
            if not args.no_open:
                import threading, webbrowser

                threading.Timer(1.5, lambda: webbrowser.open(url)).start()
            uvicorn.run(
                create_app(store, token),
                host="127.0.0.1",
                port=args.port,
                access_log=False,
            )
        elif cmd == "service":
            from .service import manage

            output(manage(args.action, store, args.port))
        elif cmd == "metadata":
            from .metadata import MetadataResolver

            if args.action == "openalex-key":
                import getpass, keyring

                value = getpass.getpass("OpenAlex API key（不回显）：").strip()
                if not value:
                    raise ValueError("API key 不能为空")
                keyring.set_password("paper-research-coach-metadata", "openalex", value)
                output({"saved": True, "location": "system keyring"})
            elif args.action == "resolve":
                if not args.paper:
                    raise ValueError("指定 --paper 论文 ID")
                output(
                    MetadataResolver(store).resolve(
                        store.get("paper", args.paper), force=args.refresh
                    )
                )
            else:
                output(
                    [
                        {
                            "paper_id": p["id"],
                            "title": p["title"],
                            "bibliography": store.setting(
                                "bibliography:" + p["id"], {}
                            ),
                        }
                        for p in store.list("paper")
                    ]
                )
        elif cmd == "vault":
            from .vault import VaultSync
            from .zotero import ZoteroSync

            sync = ZoteroSync(store)
            vault = VaultSync(store, sync)
            if args.action == "configure":
                output(
                    vault.configure(
                        args.path, sync.state()["collection"], sync.state()["server_id"]
                    )
                )
            elif args.action == "scan":
                output(vault.run())
            elif args.action == "conflicts":
                output(vault.conflicts())
            elif args.action == "resolve":
                output(vault.resolve(args.conflict, args.choice))
            else:
                output(vault.state())
        elif cmd == "sync":
            from .zotero import ZoteroSync

            sync = ZoteroSync(store)
            if args.action == "status":
                output(sync.state())
            elif args.action == "collections":
                output(sync.collections())
            elif args.action == "configure":
                output(sync.configure(args.server, args.collection))
            elif args.action == "authorize":
                output(sync.authorize(args.server))
            elif args.action == "run":
                output(sync.run())
            elif args.action == "conflicts":
                output(sync.conflicts())
            elif args.action == "resolve":
                output(sync.resolve(args.conflict, args.choice))
    except (ValueError, KeyError, OSError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
