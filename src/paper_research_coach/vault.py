"""Local folder adapter. Original PDFs/cards are read-only; exports are versioned."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import re

import httpx
import time
from pathlib import Path

import yaml
from filelock import FileLock, Timeout

from .models import uid, now
from .store import Store

MANAGED = "06_PRC阅读记录"


def stable_bytes(path: Path):
    before = path.stat()
    if time.time() - before.st_mtime < 2:
        raise OSError("File is still changing")
    value = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError("File changed during read")
    return value


def fingerprint(value: bytes):
    return hashlib.sha256(value).hexdigest()


def metadata(text):
    if not text.startswith("---\n"):
        return {}
    parts = text.split("\n---", 1)
    if len(parts) != 2:
        return {}
    value = yaml.safe_load(parts[0][4:])
    return value if isinstance(value, dict) else {}


class VaultSync:
    def __init__(self, store: Store, zotero=None):
        self.store = store
        self.zotero = zotero
        self.lock = FileLock(str(store.root / "vault-sync.lock"), timeout=0)
        with store.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS vault_files(root TEXT, path TEXT, kind TEXT, hash TEXT, paper_id TEXT, record_id TEXT, base_revision INTEGER, PRIMARY KEY(root,path));
            CREATE TABLE IF NOT EXISTS vault_conflicts(id TEXT PRIMARY KEY, root TEXT, path TEXT, note_id TEXT, file_content TEXT, file_hash TEXT, local_revision INTEGER, resolved INTEGER DEFAULT 0);
            """)

    def state(self):
        return self.store.setting(
            "vault", {"enabled": False, "root": "", "state": "off", "message": ""}
        )

    def configure(self, root, collection="", server=""):
        with self.lock.acquire(timeout=10):
            path = Path(root).expanduser().resolve(strict=True)
            if not path.is_dir():
                raise ValueError("Choose a literature folder")
            if server:
                for link in self.files(path).values():
                    paper = self.store.get("paper", link["paper_id"])
                    if paper["zotero_server"] and paper["zotero_server"] != server:
                        raise ValueError(
                            "此目录已关联另一 Zotero 实例，请保留原绑定或使用独立目录。"
                        )
            state = dict(
                enabled=True,
                root=str(path),
                collection=collection,
                server=server,
                state="ready",
                message="",
                last_scan="",
            )
            self.store.set_setting("vault", state)
            return state

    def files(self, root):
        with self.store.connect() as db:
            return {
                r["path"]: dict(r)
                for r in db.execute(
                    "SELECT * FROM vault_files WHERE root=?", (str(root),)
                )
            }

    def bind(
        self,
        root,
        path,
        kind,
        hash_value,
        paper_id,
        record_id="",
        revision=0,
        connection=None,
    ):
        from contextlib import nullcontext

        with nullcontext(connection) if connection else self.store.connect() as db:
            db.execute(
                "INSERT INTO vault_files VALUES (?,?,?,?,?,?,?) ON CONFLICT(root,path) DO UPDATE SET kind=excluded.kind,hash=excluded.hash,paper_id=excluded.paper_id,record_id=excluded.record_id,base_revision=excluded.base_revision",
                (str(root), str(path), kind, hash_value, paper_id, record_id, revision),
            )

    def conflicts(self):
        with self.store.connect() as db:
            return [
                dict(r)
                for r in db.execute("SELECT * FROM vault_conflicts WHERE resolved=0")
            ]

    def conflict(self, root, relative, note, text, hash_value):
        with self.store.connect() as db:
            found = db.execute(
                "SELECT id FROM vault_conflicts WHERE root=? AND path=? AND resolved=0",
                (str(root), relative),
            ).fetchone()
            if found:
                db.execute(
                    "UPDATE vault_conflicts SET file_content=?,file_hash=?,local_revision=? WHERE id=?",
                    (text, hash_value, note["revision"], found[0]),
                )
            else:
                db.execute(
                    "INSERT INTO vault_conflicts VALUES (?,?,?,?,?,?,?,0)",
                    (
                        uid(),
                        str(root),
                        relative,
                        note["id"],
                        text,
                        hash_value,
                        note["revision"],
                    ),
                )

    def resolve(self, conflict_id, choice):
        if choice not in ("file", "local", "both"):
            raise ValueError("Choose file, local or both")
        with self.lock.acquire(timeout=10):
            c = next((c for c in self.conflicts() if c["id"] == conflict_id), None)
            if not c:
                raise KeyError("Conflict no longer exists")
            path = (Path(c["root"]) / c["path"]).resolve()
            if not path.is_relative_to(Path(c["root"])):
                raise ValueError("Path outside literature folder")
            data = stable_bytes(path)
            if fingerprint(data) != c["file_hash"]:
                raise ValueError("Markdown changed again; scan before resolving")
            n = self.store.get("note", c["note_id"])
            if n["revision"] != c["local_revision"]:
                raise ValueError("Note changed again; scan before resolving")
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                if choice == "file":
                    if n["read_only"] or n["author"] == "assistant":
                        raise ValueError(
                            "Keep an edited external/AI source as a separate note"
                        )
                    n = self.store.put(
                        "note",
                        n | {"content": c["file_content"]},
                        n["revision"],
                        origin="vault",
                        connection=db,
                    )
                elif choice == "both":
                    self.store.put(
                        "note",
                        dict(
                            paper_id=n["paper_id"],
                            content=c["file_content"],
                            author="external",
                            provenance="EXTERNAL",
                            links=[n["id"]],
                            tags=["Markdown 冲突保留"],
                        ),
                        origin="vault",
                        connection=db,
                    )
                if choice in ("local", "both"):
                    # Publish a fresh complete revision even if an interrupted export
                    # already occupies the old filename. Keep the conflicting file intact.
                    n = self.store.put(
                        "note",
                        n,
                        n["revision"],
                        origin="vault-resolution",
                        connection=db,
                    )
                self.bind(
                    c["root"],
                    c["path"],
                    "note",
                    c["file_hash"],
                    n["paper_id"],
                    n["id"],
                    n["revision"],
                    connection=db,
                )
                db.execute(
                    "UPDATE vault_conflicts SET resolved=1 WHERE id=?", (conflict_id,)
                )
            return {"resolved": True}

    def run(self):
        try:
            self.lock.acquire(timeout=0)
        except Timeout:
            return self.state()
        state = self.state()
        try:
            if not state["enabled"]:
                return state
            root = Path(state["root"])
            if not root.is_dir():
                raise OSError("Literature folder unavailable")
            files = self.files(root)
            skipped = 0
            # Parse only paper-card metadata. All values are data, never instructions.
            cards = []
            for path in sorted((root / "01_论文卡片").glob("*.md")):
                try:
                    if path.is_symlink() or not path.resolve().is_relative_to(root):
                        continue
                    text = stable_bytes(path).decode("utf-8")
                    meta = metadata(text)
                    value = str(meta.get("原文PDF路径") or meta.get("原文PDF") or "")
                    value = value.removeprefix("[[").removesuffix("]]").split("|")[0]
                    pdf_path = (root / value).resolve()
                    if (
                        value
                        and pdf_path.is_relative_to(root)
                        and pdf_path.suffix.lower() == ".pdf"
                    ):
                        cards.append((path, text, meta, pdf_path))
                except (OSError, ValueError, yaml.YAMLError):
                    skipped += 1
            card_by_pdf = {str(c[3]): c for c in cards}
            pdf_paths = [
                p
                for p in root.rglob("*")
                if p.suffix.lower() == ".pdf"
                and not p.is_symlink()
                and MANAGED not in p.relative_to(root).parts
                and not any(x.startswith(".") for x in p.relative_to(root).parts)
            ]
            for path in sorted(pdf_paths):
                try:
                    if not path.resolve().is_relative_to(root):
                        continue
                    raw = stable_bytes(path)
                    h = fingerprint(raw)
                    rel = str(path.relative_to(root))
                    old = files.get(rel)
                    if old and old["hash"] == h:
                        continue
                    if old:
                        paper = self.store.get("paper", old["paper_id"])
                        # A renamed duplicate path may already bind this exact version.
                        if paper["source_version"] != h:
                            paper = self.store.replace_source(paper["id"], str(path))
                    else:
                        card = card_by_pdf.get(str(path.resolve()))
                        meta = card[2] if card else {}
                        aliases = meta.get("aliases", [])
                        title = next(
                            (str(x) for x in aliases if len(str(x)) > 12),
                            str(meta.get("title") or path.stem),
                        )
                        paper = self.store.add_paper(
                            title,
                            str(path),
                            doi=str(meta.get("DOI", "")).removeprefix(
                                "https://doi.org/"
                            ),
                            authors=str(meta.get("作者", "")),
                            year=str(meta.get("年份", "")),
                            zotero_server=state.get("server", ""),
                        )
                    if (
                        paper["source_path"] != str(path)
                        and not Path(paper["source_path"]).is_file()
                    ):
                        paper = self.store.replace_source(paper["id"], str(path))
                    self.bind(root, rel, "pdf", h, paper["id"])
                    files[rel] = dict(paper_id=paper["id"], hash=h, kind="pdf")
                except (OSError, ValueError):
                    skipped += 1
            # Import existing cards as attributed, read-only external material.
            for path, text, meta, pdf_path in cards:
                link = files.get(str(pdf_path.relative_to(root)))
                if not link:
                    continue
                rel = str(path.relative_to(root))
                h = fingerprint(text.encode())
                old = files.get(rel)
                if old and old["hash"] == h:
                    continue
                with self.store.connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    n = (
                        self.store.get("note", old["record_id"])
                        if old and old["paper_id"] == link["paper_id"]
                        else dict(
                            paper_id=link["paper_id"],
                            author="external",
                            provenance="EXTERNAL",
                            read_only=True,
                            tags=["现有论文卡 · 外部资料"],
                        )
                    )
                    n = self.store.put(
                        "note",
                        n | {"content": text},
                        n.get("revision", 0),
                        origin="vault-source",
                        connection=db,
                    )
                    self.bind(
                        root,
                        rel,
                        "card",
                        h,
                        link["paper_id"],
                        n["id"],
                        n["revision"],
                        connection=db,
                    )
            # Managed note revisions are append-only exports. Editing one is an input;
            # we never replace a file that an external editor might still be writing.
            managed = root / MANAGED
            if managed.is_symlink():
                raise ValueError("Managed note directory cannot be a symlink")
            managed.mkdir(exist_ok=True)
            papers = {p["id"]: p for p in self.store.list("paper")}
            for path in sorted(managed.glob("*/*.md")):
                if (
                    path.name == "README.md"
                    or path.is_symlink()
                    or not path.resolve().is_relative_to(managed.resolve())
                ):
                    continue
                pid = path.parent.name
                if pid not in papers:
                    continue
                try:
                    raw = stable_bytes(path)
                    h = fingerprint(raw)
                    text = raw.decode("utf-8")
                    rel = str(path.relative_to(root))
                    old = files.get(rel)
                    if not old:
                        match = re.fullmatch(
                            r"([a-zA-Z0-9_-]+)-r([0-9]+)\.md", path.name
                        )
                        if match:
                            try:
                                candidate = self.store.get("note", match[1])
                                history = next(
                                    x["data"]
                                    for x in self.store.history(match[1])
                                    if x["revision"] == int(match[2])
                                )
                                if (
                                    candidate["paper_id"] == pid
                                    and fingerprint(history["content"].encode()) != h
                                ):
                                    self.conflict(root, rel, candidate, text, h)
                                    continue
                                if candidate["paper_id"] == pid:
                                    old = dict(
                                        record_id=candidate["id"],
                                        base_revision=history["revision"],
                                        hash=fingerprint(history["content"].encode()),
                                    )
                                    self.bind(
                                        root,
                                        rel,
                                        "note",
                                        old["hash"],
                                        pid,
                                        candidate["id"],
                                        old["base_revision"],
                                    )
                            except (KeyError, StopIteration):
                                pass
                    if old and old["hash"] == h:
                        continue
                    if not text.strip():
                        continue
                    if old:
                        n = self.store.get("note", old["record_id"])
                        if text == n["content"]:
                            self.bind(root, rel, "note", h, pid, n["id"], n["revision"])
                            continue
                        if (
                            n["revision"] != old["base_revision"]
                            or n["read_only"]
                            or n["author"] == "assistant"
                        ):
                            self.conflict(root, rel, n, text, h)
                            continue
                        value = n | {"content": text}
                        revision = n["revision"]
                    else:
                        value = dict(
                            paper_id=pid,
                            content=text,
                            author="external",
                            provenance="EXTERNAL",
                            tags=["从 Markdown 导入 · 作者待确认"],
                        )
                        revision = 0
                    with self.store.connect() as db:
                        db.execute("BEGIN IMMEDIATE")
                        n = self.store.put(
                            "note", value, revision, origin="vault", connection=db
                        )
                        self.bind(
                            root,
                            rel,
                            "note",
                            h,
                            pid,
                            n["id"],
                            n["revision"],
                            connection=db,
                        )

                except (OSError, ValueError):
                    skipped += 1
            linked_papers = {
                v["paper_id"] for v in self.files(root).values() if v["kind"] == "pdf"
            }
            for pid in linked_papers:
                if pid not in papers:
                    continue
                folder = managed / pid
                folder.mkdir(exist_ok=True)
                if folder.is_symlink():
                    raise ValueError("Managed note directory cannot be a symlink")
                readme = folder / "README.md"
                if readme.is_symlink():
                    raise ValueError("Managed README cannot be a symlink")
                if not readme.exists():
                    with readme.open("x", encoding="utf-8") as out:
                        out.write(
                            f"# {papers[pid]['title']}\n\n原文：{papers[pid]['source_path']}\n\n笔记按修订版本保存，r 后数字越大越新。可编辑自己的原话文件，工作台会读入；双方同时修改时保留冲突。新建 Markdown 也会导入，初始标为外部资料，作者身份可在带读时确认。\n\n原始论文卡和 PDF 保持只读。\n"
                        )
                for n in self.store.list("note", pid):
                    if n["read_only"]:
                        continue
                    filename = f"{n['id']}-r{n['revision']}.md"
                    path = folder / filename
                    if path.exists():
                        continue
                    data = n["content"].encode("utf-8")
                    # Publish a complete inode without replacing an editor's file.
                    handle, temp = tempfile.mkstemp(
                        prefix=".prc-", suffix=".tmp", dir=folder
                    )
                    try:
                        with os.fdopen(handle, "wb") as out:
                            out.write(data)
                            out.flush()
                            os.fsync(out.fileno())
                        try:
                            os.link(temp, path)
                        except FileExistsError:
                            continue
                        except OSError:
                            # Some cloud filesystems reject links. Exclusive write is
                            # recoverable: an unbound partial file is always a conflict.
                            with path.open("xb") as out:
                                out.write(data)
                                out.flush()
                                os.fsync(out.fileno())
                    finally:
                        Path(temp).unlink(missing_ok=True)
                    self.bind(
                        root,
                        str(path.relative_to(root)),
                        "note",
                        fingerprint(data),
                        pid,
                        n["id"],
                        n["revision"],
                    )
            pending_metadata = []
            if self.zotero and state.get("collection"):
                from .metadata import MetadataPending

                if self.zotero.probe() != state["server"]:
                    raise ValueError(
                        "Zotero library changed; folder binding remains isolated"
                    )
                self.zotero._attachment_inventory = None
                for pid in sorted(linked_papers):
                    p = self.store.get("paper", pid)
                    if p["zotero_key"] and p["zotero_server"] != state["server"]:
                        raise ValueError(
                            "目录中的论文属于另一 Zotero 实例，已停止绑定。"
                        )
                    if (
                        not p["zotero_key"]
                        or p.get("zotero_collection") != state["collection"]
                    ):
                        try:
                            self.zotero.bind_local_paper(
                                p, state["collection"], state["server"]
                            )
                        except MetadataPending:
                            pending_metadata.append(
                                {"paper_id": pid, "title": p["title"]}
                            )
            state.update(
                state="attention"
                if skipped or self.conflicts() or pending_metadata
                else "connected",
                message="；".join(
                    filter(
                        None,
                        [
                            f"{skipped} 个文件等待下载或稳定" if skipped else "",
                            f"{len(pending_metadata)} 篇书目信息待核实，已保留本地 PDF"
                            if pending_metadata
                            else "",
                        ],
                    )
                ),
                pending_metadata=pending_metadata,
                last_scan=now(),
                pdf_count=len(pdf_paths),
                card_count=len(cards),
                conflicts=len(self.conflicts()),
            )
        except httpx.HTTPError:
            state.update(
                state="attention", message="网络暂不可用，文件与待同步内容已保留"
            )
        except (OSError, ValueError) as e:
            state.update(state="attention", message=str(e))
        finally:
            self.store.set_setting("vault", state)
            self.lock.release()
        return state
