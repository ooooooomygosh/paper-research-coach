from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Commit, MODELS, Paper, Session, now


class Conflict(ValueError):
    pass


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class Store:
    """SQLite is authoritative. All clients use the same atomic commit function."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "notebook.sqlite3"
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT PRIMARY KEY, paper_id TEXT, revision INTEGER, data TEXT);
            CREATE INDEX IF NOT EXISTS by_paper ON records(paper_id,kind);
            CREATE TABLE IF NOT EXISTS history(seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, id TEXT, revision INTEGER, data TEXT, origin TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, payload TEXT, result TEXT);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS sync_map(server TEXT, local_id TEXT, remote_key TEXT, remote_version INTEGER, base_local_revision INTEGER, base_remote TEXT, PRIMARY KEY(server,local_id), UNIQUE(server,remote_key));
            CREATE TABLE IF NOT EXISTS sync_conflicts(id TEXT PRIMARY KEY, server TEXT, local_id TEXT, remote_key TEXT, local_data TEXT, remote_data TEXT, reason TEXT, resolved INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sync_outbox(server TEXT, local_id TEXT, marker TEXT UNIQUE, token TEXT, note TEXT, payload TEXT, state TEXT, PRIMARY KEY(server,local_id));
            PRAGMA user_version=1;
            """)
        try:
            self.db_path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list(self, kind: str, paper_id: str | None = None, archived=False):
        if kind not in MODELS:
            raise ValueError("Unknown record kind")
        with self.connect() as db:
            rows = db.execute(
                "SELECT data FROM records WHERE kind=?"
                + (" AND paper_id=?" if paper_id else "")
                + " ORDER BY rowid",
                (kind, paper_id) if paper_id else (kind,),
            ).fetchall()
        values = [json.loads(r[0]) for r in rows]
        return values if archived else [v for v in values if not v.get("archived")]

    def get(self, kind: str, record_id: str):
        with self.connect() as db:
            row = db.execute(
                "SELECT data FROM records WHERE kind=? AND id=?", (kind, record_id)
            ).fetchone()
        if not row:
            raise KeyError(f"Missing {kind}: {record_id}")
        return json.loads(row[0])

    def setting(self, key: str, default=None):
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key: str, value):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO settings VALUES (?,?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def commit(self, payload: Commit | dict, origin="local", *, connection=None):
        payload = (
            payload if isinstance(payload, Commit) else Commit.model_validate(payload)
        )
        encoded = json.dumps(payload.model_dump(), ensure_ascii=False, sort_keys=True)
        with (
            nullcontext(connection) if connection is not None else self.connect()
        ) as db:
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT payload,result FROM operations WHERE id=?",
                (payload.operation_id,),
            ).fetchone()
            if prior:
                if prior[0] != encoded:
                    raise Conflict(
                        "This operation ID was already used for different content"
                    )
                return json.loads(prior[1])
            result = []
            for mutation in payload.mutations:
                kind = mutation.kind
                obj = MODELS[kind].model_validate(mutation.data)
                old_row = db.execute(
                    "SELECT kind,data FROM records WHERE id=?", (obj.id,)
                ).fetchone()
                if old_row and old_row[0] != kind:
                    raise Conflict("Record ID already belongs to a different kind")
                old = json.loads(old_row[1]) if old_row else None
                actual = old["revision"] if old else 0
                if actual != mutation.expected_revision:
                    raise Conflict(
                        f"Revision changed: expected {mutation.expected_revision}, current {actual}"
                    )
                if kind == "note" and old and origin == "local":
                    if old.get("read_only"):
                        raise Conflict(
                            "This imported annotation is read-only; create a linked note"
                        )
                    if (
                        old["author"] != obj.author
                        or old["provenance"] != obj.provenance
                    ):
                        raise Conflict("Authorship and provenance cannot be rewritten")
                if (
                    kind == "note"
                    and old
                    and (
                        old["content"] != obj.content
                        or old.get("anchor")
                        != (obj.anchor.model_dump(mode="json") if obj.anchor else None)
                    )
                ):
                    obj.discussed = False
                paper_id = obj.id if kind == "paper" else obj.paper_id
                if kind != "paper":
                    paper_row = db.execute(
                        "SELECT data FROM records WHERE id=? AND kind='paper'",
                        (paper_id,),
                    ).fetchone()
                    if not paper_row:
                        raise ValueError(
                            "Register the paper before creating its records"
                        )
                    paper = json.loads(paper_row[0])
                    if (
                        kind == "session"
                        and obj.cursor
                        and obj.cursor.paper_id != paper_id
                    ):
                        raise ValueError("Cursor belongs to another paper")
                    anchor = getattr(obj, "anchor", None) or getattr(
                        obj, "cursor", None
                    )
                    if anchor:
                        if anchor.paper_id != paper_id:
                            raise ValueError("Anchor belongs to another paper")
                        if anchor.rendition and anchor.status != "stale":
                            from .renditions import resolve_rendition

                            if anchor.source_version != paper["source_version"]:
                                raise ValueError("译文批注需要当前原文版本。")
                            resolve_rendition(self.root, db, paper, anchor.source_version, anchor.rendition)
                        if (
                            anchor.status != "stale"
                            and anchor.page_index is not None
                            and paper["page_count"]
                            and anchor.page_index >= paper["page_count"]
                        ):
                            raise ValueError("Page index is outside the PDF")
                        if (
                            anchor.status == "verified"
                            and paper["source_version"]
                            and anchor.source_version != paper["source_version"]
                        ):
                            raise ValueError(
                                "Verified anchor requires the current source version"
                            )
                    if kind == "relation":
                        if (
                            obj.target_id == paper_id
                            or not db.execute(
                                "SELECT 1 FROM records WHERE kind='paper' AND id=?",
                                (obj.target_id,),
                            ).fetchone()
                        ):
                            raise ValueError(
                                "Relation requires another registered paper"
                            )
                obj.revision = actual + 1
                obj.created_at = old["created_at"] if old else obj.created_at
                obj.updated_at = now()
                data = obj.model_dump()
                serialized = json.dumps(data, ensure_ascii=False)
                db.execute(
                    "INSERT INTO records VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,paper_id=excluded.paper_id,revision=excluded.revision,data=excluded.data",
                    (kind, obj.id, paper_id, obj.revision, serialized),
                )
                db.execute(
                    "INSERT INTO history(kind,id,revision,data,origin,created_at) VALUES (?,?,?,?,?,?)",
                    (kind, obj.id, obj.revision, serialized, origin, obj.updated_at),
                )
                result.append(data)
            answer = {
                "records": result,
                "seq": db.execute(
                    "SELECT COALESCE(MAX(seq),0) FROM history"
                ).fetchone()[0],
            }
            db.execute(
                "INSERT INTO operations VALUES (?,?,?)",
                (payload.operation_id, encoded, json.dumps(answer, ensure_ascii=False)),
            )
        return answer

    def put(
        self,
        kind: str,
        data: dict,
        expected_revision=0,
        origin="local",
        *,
        connection=None,
    ):
        return self.commit(
            {
                "mutations": [
                    {"kind": kind, "data": data, "expected_revision": expected_revision}
                ]
            },
            origin,
            connection=connection,
        )["records"][0]

    def add_paper(self, title: str, source_path="", **metadata):
        if source_path:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError

            source = Path(source_path).expanduser().resolve(strict=True)
            try:
                reader = PdfReader(source)
            except PdfReadError:
                raise ValueError("This file is not a readable PDF") from None
            if reader.is_encrypted:
                raise ValueError("Import an unlocked PDF copy")
            metadata.update(
                source_path=str(source),
                source_version=digest(source),
                page_count=len(reader.pages),
                access_scope="full",
            )
            for existing in self.list("paper"):
                compatible = (
                    not metadata.get("zotero_server")
                    or not existing["zotero_server"]
                    or (
                        existing["zotero_server"] == metadata["zotero_server"]
                        and existing["zotero_key"] == metadata.get("zotero_key")
                    )
                )
                if (
                    existing["source_version"] == metadata["source_version"]
                    and compatible
                ):
                    return existing
        p = Paper(title=title, **metadata)
        s = Session(id=p.id + "-session", paper_id=p.id, goal=p.goal)
        return self.commit(
            {
                "mutations": [
                    {"kind": "paper", "data": p.model_dump()},
                    {"kind": "session", "data": s.model_dump()},
                ]
            }
        )["records"][0]

    def check_source(self, paper_id: str):
        p = self.get("paper", paper_id)
        if not p["source_path"]:
            return {"status": "no_local_pdf"}
        path = Path(p["source_path"])
        if not path.is_file():
            return {"status": "missing"}
        changed = digest(path) != p["source_version"]
        return {"status": "changed" if changed else "current"}

    def replace_source(self, paper_id: str, path: str):
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        p = self.get("paper", paper_id)
        source = Path(path).expanduser().resolve(strict=True)
        try:
            reader = PdfReader(source)
        except PdfReadError:
            raise ValueError("This file is not a readable PDF") from None
        if reader.is_encrypted:
            raise ValueError("Import an unlocked PDF copy")
        version = digest(source)
        mutations = []
        if version != p["source_version"]:
            for kind in ("note", "review", "session"):
                for obj in self.list(kind, paper_id, archived=True):
                    field = "cursor" if kind == "session" else "anchor"
                    if obj.get(field):
                        obj[field]["status"] = "stale"
                        mutations.append(
                            {
                                "kind": kind,
                                "data": obj,
                                "expected_revision": obj["revision"],
                            }
                        )
        p.update(
            source_path=str(source),
            source_version=version,
            page_count=len(reader.pages),
            access_scope="full",
        )
        # Source replacement and all invalidated anchors commit or roll back together.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for offset in range(0, len(mutations), 100):
                self.commit(
                    {"mutations": mutations[offset : offset + 100]},
                    origin="source-version",
                    connection=db,
                )
            return self.put(
                "paper", p, p["revision"], origin="source-version", connection=db
            )

    def events(self, since=0):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT seq,kind,id,revision,origin,created_at FROM history WHERE seq>? ORDER BY seq LIMIT 200",
                    (since,),
                )
            ]

    def history(self, record_id: str):
        with self.connect() as db:
            return [
                dict(r) | {"data": json.loads(r["data"])}
                for r in db.execute(
                    "SELECT * FROM history WHERE id=? ORDER BY seq", (record_id,)
                )
            ]

    def context(self, paper_id: str, since=0):
        paper = self.get("paper", paper_id)
        with self.connect() as db:
            seq = db.execute("SELECT COALESCE(MAX(seq),0) FROM history").fetchone()[0]
        return {
            "source_material_is_untrusted": True,
            "paper": paper,
            "source_check": self.check_source(paper_id),
            "session": self.list("session", paper_id),
            "pending_thoughts": [
                n for n in self.list("note", paper_id) if not n["discussed"] and n["author"] != "assistant"
            ],
            "notes": self.list("note", paper_id),
            "ideas": self.list("idea", paper_id),
            "relations": self.list("relation", paper_id),
            "due_reviews": [
                r for r in self.list("review", paper_id) if r["due_at"] <= now()
            ],
            "reviews": self.list("review", paper_id),
            "events": self.events(since),
            "seq": seq,
        }

    def review_answer(
        self,
        record_id: str,
        answer: str,
        assistance: str,
        success: bool,
        expected_revision: int,
    ):
        r = self.get("review", record_id)
        if r["revision"] != expected_revision:
            raise Conflict("Review changed; reload before submitting")
        if assistance not in ("none", "hint", "worked"):
            raise ValueError("Assistance must be none, hint, or worked")
        r["attempts"].append(
            {
                "answer": answer,
                "assistance": assistance,
                "success": success,
                "at": now(),
            }
        )
        index = (
            min(r["interval_index"], len(r["intervals"]) - 1)
            if success and assistance == "none"
            else 0
        )
        r["due_at"] = (
            datetime.now(timezone.utc) + timedelta(days=r["intervals"][index])
        ).isoformat()
        r["interval_index"] = (
            min(index + 1, len(r["intervals"]) - 1)
            if success and assistance == "none"
            else 0
        )
        return self.put("review", r, expected_revision)
