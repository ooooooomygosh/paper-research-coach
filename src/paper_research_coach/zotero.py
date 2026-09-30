from __future__ import annotations

import html
import json
import re
import secrets
import sqlite3
from contextlib import nullcontext
from filelock import FileLock, Timeout
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from .models import Note, SyncState, now, uid
from .store import Store, digest


class SyncError(ValueError):
    def __init__(self, message, *, rejected=False):
        super().__init__(message)
        self.rejected = rejected


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("p", "div", "li", "pre", "blockquote", "tr", "h1", "h2", "h3"):
            self.parts.append("\n")


def plain(value):
    parser = PlainText()
    parser.feed(value)
    return "".join(parser.parts).strip()


def remote_content(data):
    if data.get("itemType") == "annotation":
        return (
            data.get("annotationComment", "")
            or data.get("annotationText", "")
            or "[区域批注]"
        )
    markup = data.get("note", "")
    # Extract verbatim words only from the complete envelope we own. Extra paragraphs
    # (including ones added in Zotero) must never disappear behind the first pre block.
    match = re.fullmatch(
        r"<div><p>Paper Research Coach · (?:USER|PAPER|EXTERNAL|INFERENCE|IDEA)</p><pre>(.*?)</pre><p>PRC-ID: [a-zA-Z0-9_-]+</p><p>(.*?)</p></div>",
        markup,
        re.S,
    )
    if match:
        metadata = html.unescape(match.group(2))
        try:
            valid = metadata == "unresolved" or isinstance(json.loads(metadata), dict)
        except ValueError:
            valid = False
        if valid:
            parser = PlainText()
            parser.feed(match.group(1))
            return "".join(parser.parts)
    return plain(markup) or "[空白笔记]"


class ZoteroSync:
    def __init__(self, store: Store, client: httpx.Client | None = None):
        self.store = store
        self.client = client or httpx.Client(
            base_url="http://127.0.0.1:23119/api/", timeout=10, follow_redirects=False
        )
        self.keys = {}
        self.lock = FileLock(str(store.root / "zotero-sync.lock"), timeout=0)

    def state(self):
        return SyncState.model_validate(self.store.setting("zotero", {})).model_dump()

    def set_state(self, **changes):
        s = self.state() | changes
        self.store.set_setting("zotero", SyncState.model_validate(s).model_dump())
        return self.state()

    def probe(self):
        try:
            r = self.client.get("")
        except httpx.RequestError:
            raise SyncError(
                "Zotero 未运行，或本地通信尚未开启。笔记已保存在本地。"
            ) from None
        if r.status_code == 403:
            raise SyncError("请在 Zotero 设置 → 高级中允许本机应用通信。")
        r.raise_for_status()
        sid = r.headers.get("Zotero-Server-ID", "")
        if not sid:
            raise SyncError("自动双向同步需要 Zotero 10+。当前接口没有实例标识。")
        return sid

    def request(self, method, path, sid, data=None, *, write_token=None):
        headers = {"Zotero-API-Version": "3", "Zotero-Server-ID": sid}
        if method != "GET":
            key = self.keys.get(sid)
            if not key:
                try:
                    import keyring

                    key = keyring.get_password("paper-research-coach-zotero", sid)
                except Exception:
                    pass
            if not key:
                raise SyncError(
                    "本地内容已保存；请在同步设置中授权 Zotero 写入。", rejected=True
                )
            headers["Zotero-API-Key"] = key
        if write_token:
            headers["Zotero-Write-Token"] = write_token
        r = self.client.request(method, path, headers=headers, json=data)
        if r.status_code == 401:
            self.keys.pop(sid, None)
            try:
                import keyring

                keyring.delete_password("paper-research-coach-zotero", sid)
            except Exception:
                pass
            raise SyncError("Zotero 写入授权已失效；请重新授权。", rejected=True)
        if r.status_code == 412:
            raise SyncError("Zotero 版本或实例已变化，已停止本次写入。请重新同步。")
        if r.status_code == 403:
            raise SyncError("Zotero 拒绝了访问；本地笔记保持可用。", rejected=True)
        if r.status_code not in (200, 201, 204, 404):
            raise SyncError(f"Zotero 返回 HTTP {r.status_code}，已保留待同步内容。")
        return r

    def authorize(self, expected_server=None):
        sid = self.probe()
        if expected_server and expected_server != sid:
            raise SyncError("Zotero 文献库已切换，请重新选择集合。")
        configured = self.state()["server_id"]
        if configured and configured != sid:
            raise SyncError("Zotero 文献库已切换，请重新选择集合后授权。")
        try:
            r = self.client.post(
                "local/authorize",
                headers={"Zotero-Server-ID": sid},
                json={"appName": "Paper Research Coach"},
                timeout=120,
            )
        except httpx.TimeoutException:
            raise SyncError("Zotero 授权等待已结束，可以稍后重新授权。") from None
        if r.status_code == 403:
            return {"authorized": False, "remembered": False}
        if r.status_code != 200:
            raise SyncError(f"Zotero 授权未完成（HTTP {r.status_code}）。")
        result = r.json()
        self.keys[sid] = result["key"]
        persisted = False
        if result.get("remember"):
            try:
                import keyring

                keyring.set_password("paper-research-coach-zotero", sid, result["key"])
                persisted = True
            except Exception:
                pass
        return {
            "authorized": True,
            "remembered": persisted,
            "session_only": not persisted,
        }

    def collections(self):
        sid = self.probe()
        r = self.request("GET", "users/0/collections?format=json", sid)
        return {
            "server_id": sid,
            "collections": [
                {"key": x["key"], "name": x["data"]["name"]} for x in r.json()
            ],
        }

    def configure(self, server_id, collection, enabled=True):
        try:
            guard = self.lock.acquire(timeout=10)
        except Timeout:
            raise SyncError("另一处正在同步，请稍后重试。") from None
        with guard:
            available = self.collections()
            if server_id and server_id != available["server_id"]:
                raise SyncError("Zotero 文献库已切换，请重新读取集合。")
            if collection not in [c["key"] for c in available["collections"]]:
                raise ValueError("Select a collection from the current Zotero library")
            return self.set_state(
                server_id=available["server_id"],
                collection=collection,
                enabled=enabled,
                state="ready",
                message="",
            )

    def create_object(self, sid, identity, payload):
        """Durable, marker-based creation for folder-linked parents and attachments."""
        setting = "zotero-create:" + sid + ":" + identity
        job = self.store.setting(setting)
        if job and job.get("remote_key"):
            response = self.request("GET", f"users/0/items/{job['remote_key']}", sid)
            if response.status_code != 200 or response.json()["data"].get("deleted"):
                raise SyncError("已关联的 Zotero 条目被删除；请先处理删除状态。")
            return response.json()["data"]
        if not job:
            marker = "urn:paper-research-coach:" + secrets.token_hex(16)
            payload = payload | {"relations": {"owl:sameAs": marker}}
            job = {
                "marker": marker,
                "payload": payload,
                "token": secrets.token_hex(16),
                "state": "prepared",
            }
            self.store.set_setting(setting, job)
        if job["state"] == "prepared" and job["payload"] != (
            payload | {"relations": {"owl:sameAs": job["marker"]}}
        ):
            job["payload"] = payload | {"relations": {"owl:sameAs": job["marker"]}}
            job["token"] = secrets.token_hex(16)
            self.store.set_setting(setting, job)
        if job["state"] == "unknown":
            items = self.request(
                "GET",
                f"users/0/items?itemType={job['payload']['itemType']}&includeTrashed=1",
                sid,
            ).json()
            matches = [
                x["data"]
                for x in items
                if job["marker"] in self.relation_markers(x["data"])
                and x["data"].get("parentItem") == job["payload"].get("parentItem")
            ]
            if len(matches) != 1:
                raise SyncError("正在核对新建文献的写入结果；确认前不会重复创建。")
            result = matches[0]
        else:
            job["state"] = "unknown"
            self.store.set_setting(setting, job)
            try:
                response = self.request(
                    "POST",
                    "users/0/items",
                    sid,
                    [job["payload"]],
                    write_token=job["token"],
                ).json()
            except (httpx.ConnectError, SyncError) as error:
                if isinstance(error, httpx.ConnectError) or error.rejected:
                    job["state"] = "prepared"
                    self.store.set_setting(setting, job)
                raise
            if response.get("failed"):
                job["state"] = "prepared"
                job["token"] = secrets.token_hex(16)
                self.store.set_setting(setting, job)
                raise SyncError("Zotero 未接受文献绑定，文件与原有条目已保留。")
            result = response.get("successful", {}).get("0", {}).get("data")
            if not result:
                raise SyncError("文献绑定结果待核对。")
        job["remote_key"] = result["key"]
        self.store.set_setting(setting, job)
        return result

    def bind_local_paper(self, paper, collection, sid):
        with self.lock.acquire(timeout=10):
            paper = self.store.get("paper", paper["id"])
            if self.probe() != sid:
                raise SyncError("Zotero 文献库已切换，停止绑定。")
            if paper["zotero_key"]:
                if paper["zotero_server"] != sid:
                    raise SyncError("论文属于另一 Zotero 实例。")
                parent = self.request(
                    "GET", f"users/0/items/{paper['zotero_key']}", sid
                )
                if parent.status_code != 200 or parent.json()["data"].get("deleted"):
                    raise SyncError("已关联条目被删除，请先处理删除状态。")
                data = parent.json()["data"]
                if collection not in data.get("collections", []):
                    response = self.request(
                        "POST",
                        "users/0/items",
                        sid,
                        [
                            {
                                "key": data["key"],
                                "version": data["version"],
                                "collections": [
                                    *data.get("collections", []),
                                    collection,
                                ],
                            }
                        ],
                    ).json()
                    if response.get("failed"):
                        raise SyncError("条目刚被修改，请重新同步后关联。")
                if paper.get("zotero_collection") != collection:
                    paper = self.store.put(
                        "paper",
                        paper | {"zotero_collection": collection},
                        paper["revision"],
                        origin="vault-link",
                    )
                return paper
            if self.store.check_source(paper["id"])["status"] != "current":
                raise SyncError("PDF 正在变化，等待稳定后再绑定。")
            # Existing stored PDFs stay intact. Match actual bytes before adding a link.
            cached = getattr(self, "_attachment_inventory", None)
            inventory = cached["rows"] if cached and cached["server"] == sid else None
            if inventory is None:
                inventory = []
                rows = self.request(
                    "GET", "users/0/items?itemType=attachment&format=json", sid
                ).json()
                for row in rows:
                    data = row["data"]
                    if data.get("contentType") != "application/pdf" or not data.get(
                        "parentItem"
                    ):
                        continue
                    path = self.attachment_path(sid, data["key"])
                    if path:
                        try:
                            inventory.append((digest(path), data))
                        except OSError:
                            pass
                self._attachment_inventory = {"server": sid, "rows": inventory}
            matches = []
            for h, d in inventory:
                if h != paper["source_version"]:
                    continue
                response = self.request("GET", f"users/0/items/{d['key']}", sid)
                if response.status_code != 200:
                    continue
                current = response.json()["data"]
                path = self.attachment_path(sid, d["key"])
                if (
                    current.get("itemType") == "attachment"
                    and not current.get("deleted")
                    and current.get("parentItem")
                    and path
                    and digest(path) == paper["source_version"]
                ):
                    matches.append(current)
            if len({d["parentItem"] for d in matches}) > 1:
                raise SyncError(
                    "同一 PDF 对应多个 Zotero 条目，请先在 Zotero 合并重复条目。"
                )
            if matches:
                attachment = matches[0]
                parent = self.request(
                    "GET", f"users/0/items/{attachment['parentItem']}", sid
                ).json()["data"]
                if collection not in parent.get("collections", []):
                    patch = {
                        "key": parent["key"],
                        "version": parent["version"],
                        "collections": [*parent.get("collections", []), collection],
                    }
                    result = self.request("POST", "users/0/items", sid, [patch]).json()
                    if result.get("failed"):
                        raise SyncError("Zotero 条目刚被修改，请重新同步后关联。")
            else:
                from .metadata import MetadataResolver

                identity = paper["id"] + ":parent"
                job = self.store.setting("zotero-create:" + sid + ":" + identity)
                recovered = None
                if job and (job.get("remote_key") or job.get("state") == "unknown"):
                    # First reconcile a possibly successful old create. Never turn
                    # a metadata failure into a duplicate Zotero parent.
                    recovered = self.create_object(sid, identity, job["payload"])
                verified = MetadataResolver(self.store).resolve(paper)
                if self.store.check_source(paper["id"])["status"] != "current":
                    raise SyncError("PDF 在书目核实期间变化，请重新扫描。")
                payload = verified["payload"] | {"collections": [collection]}
                parent = recovered or self.create_object(sid, identity, payload)
                if recovered and not recovered.get("creators"):
                    patch = verified["payload"] | {
                        "key": recovered["key"],
                        "version": recovered["version"],
                    }
                    result = self.request("POST", "users/0/items", sid, [patch]).json()
                    if result.get("failed"):
                        raise SyncError("旧条目的书目信息刚被修改，请重新同步后核对。")
                    parent = (
                        result.get("successful", {}).get("0", {}).get("data", recovered)
                    )
                if collection not in parent.get("collections", []):
                    result = self.request(
                        "POST",
                        "users/0/items",
                        sid,
                        [
                            {
                                "key": parent["key"],
                                "version": parent["version"],
                                "collections": [
                                    *parent.get("collections", []),
                                    collection,
                                ],
                            }
                        ],
                    ).json()
                    if result.get("failed"):
                        raise SyncError("条目集合刚被修改，请重新同步。")
                    parent = (
                        result.get("successful", {}).get("0", {}).get("data", parent)
                    )
                attachment = self.create_object(
                    sid,
                    paper["id"] + ":pdf",
                    {
                        "itemType": "attachment",
                        "parentItem": parent["key"],
                        "title": "PDF",
                        "linkMode": "linked_file",
                        "contentType": "application/pdf",
                        "path": paper["source_path"],
                    },
                )
                inventory.append((paper["source_version"], attachment))
            paper.update(
                publication=parent.get("publicationTitle")
                or parent.get("proceedingsTitle")
                or parent.get("repository")
                or paper.get("publication", ""),
                title=parent.get("title", paper["title"]),
                authors=", ".join(
                    a.get("name")
                    or " ".join(filter(None, [a.get("firstName"), a.get("lastName")]))
                    for a in parent.get("creators", [])
                ),
                doi=parent.get("DOI", paper["doi"]),
                year=parent.get("date", paper["year"]),
                url=parent.get("url", paper["url"]),
                zotero_key=parent["key"],
                zotero_attachment=attachment["key"],
                zotero_server=sid,
                zotero_collection=collection,
            )
            return self.store.put(
                "paper", paper, paper["revision"], origin="vault-link"
            )

    def mapped(self, sid, local_id=None, remote_key=None):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT * FROM sync_map WHERE server=? AND "
                + ("local_id=?" if local_id else "remote_key=?"),
                (sid, local_id or remote_key),
            ).fetchone()
        return dict(row) if row else None

    def map(self, sid, note, data, *, connection=None):
        with (
            nullcontext(connection) if connection is not None else self.store.connect()
        ) as db:
            db.execute(
                "INSERT INTO sync_map VALUES (?,?,?,?,?,?) ON CONFLICT(server,local_id) DO UPDATE SET remote_key=excluded.remote_key,remote_version=excluded.remote_version,base_local_revision=excluded.base_local_revision,base_remote=excluded.base_remote",
                (
                    sid,
                    note["id"],
                    data["key"],
                    data.get("version", 0),
                    note["revision"],
                    json.dumps(data, ensure_ascii=False),
                ),
            )

    def conflict(self, sid, note, remote, reason):
        key = remote.get("key", "")
        with self.store.connect() as db:
            exists = db.execute(
                "SELECT id FROM sync_conflicts WHERE server=? AND local_id=? AND resolved=0",
                (sid, note["id"]),
            ).fetchone()
            if exists:
                db.execute(
                    "UPDATE sync_conflicts SET local_data=?,remote_data=?,reason=? WHERE id=?",
                    (
                        json.dumps(note, ensure_ascii=False),
                        json.dumps(remote, ensure_ascii=False),
                        reason,
                        exists[0],
                    ),
                )
            else:
                db.execute(
                    "INSERT INTO sync_conflicts VALUES (?,?,?,?,?,?,?,0)",
                    (
                        uid(),
                        sid,
                        note["id"],
                        key,
                        json.dumps(note, ensure_ascii=False),
                        json.dumps(remote, ensure_ascii=False),
                        reason,
                    ),
                )

    def conflicts(self):
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT * FROM sync_conflicts WHERE resolved=0 ORDER BY rowid"
            ).fetchall()
        return [
            dict(r)
            | {
                "local_data": json.loads(r["local_data"]),
                "remote_data": json.loads(r["remote_data"]),
            }
            for r in rows
        ]

    def decode(self, p, remote, existing=None):
        d = remote
        values = (
            existing.copy()
            if existing
            else Note(
                paper_id=p["id"],
                author="external",
                provenance="EXTERNAL",
                content=remote_content(d),
            ).model_dump()
        )
        values["content"] = remote_content(d)
        values["discussed"] = existing.get("discussed", False) if existing else False
        values["archived"] = bool(d.get("deleted"))
        values["tags"] = [x["tag"] for x in d.get("tags", [])]
        if d.get("itemType") == "annotation":
            pos = json.loads(d.get("annotationPosition", "{}"))
            typ = d.get("annotationType", "")
            values.update(
                annotation_type=typ,
                color=d.get("annotationColor", "#ffda75"),
                read_only=bool(
                    d.get("annotationIsExternal")
                    or typ not in ("highlight", "underline", "note")
                ),
            )
            remote_version = self.attachment_version(p)
            values["anchor"] = {
                "paper_id": p["id"],
                "source_version": remote_version,
                "page_index": pos.get("pageIndex"),
                "page_label": d.get("annotationPageLabel", ""),
                "quote": d.get("annotationText", ""),
                "rects": pos.get("rects", []),
                "status": "verified"
                if remote_version
                and remote_version == p["source_version"]
                and self.store.check_source(p["id"])["status"] == "current"
                else "stale"
                if p["source_version"]
                else "unresolved",
            }
        return values

    def encode(self, p, n, remote_key, version):
        a = n.get("anchor")
        base = {
            "key": remote_key,
            "version": version,
            "tags": [{"tag": tag} for tag in n["tags"]],
        }
        if (
            a
            and a["status"] == "verified"
            and a["rects"]
            and a["source_version"] == p["source_version"]
            and p["zotero_attachment"]
        ):
            return base | {
                "itemType": "annotation",
                "parentItem": p["zotero_attachment"],
                "annotationType": n["annotation_type"]
                if n["annotation_type"] in ("highlight", "underline", "note")
                else "highlight",
                "annotationText": a["quote"],
                "annotationComment": n["content"],
                "annotationColor": n["color"],
                "annotationPageLabel": a["page_label"] or str(a["page_index"] + 1),
                "annotationSortIndex": f"{a['page_index']:05d}|000000|00000",
                "annotationPosition": json.dumps(
                    {"pageIndex": a["page_index"], "rects": a["rects"]}
                ),
            }
        anchor = html.escape(json.dumps(a, ensure_ascii=False)) if a else "unresolved"
        return base | {
            "itemType": "note",
            "parentItem": p["zotero_key"],
            "note": f"<div><p>Paper Research Coach · {n['provenance']}</p><pre>{html.escape(n['content'])}</pre><p>PRC-ID: {n['id']}</p><p>{anchor}</p></div>",
        }

    def base_note(self, mapping):
        if not mapping:
            return None
        with self.store.connect() as db:
            row = db.execute(
                "SELECT data FROM history WHERE kind='note' AND id=? AND revision=?",
                (mapping["local_id"], mapping["base_local_revision"]),
            ).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def local_fields(note):
        return {
            k: note.get(k)
            for k in (
                "content",
                "anchor",
                "tags",
                "annotation_type",
                "color",
                "archived",
            )
        }

    @staticmethod
    def remote_fields(data):
        keys = ["itemType", "parentItem", "tags"]
        keys += (
            ["note"]
            if data.get("itemType") == "note"
            else [
                "annotationType",
                "annotationText",
                "annotationComment",
                "annotationColor",
                "annotationPageLabel",
                "annotationPosition",
            ]
        )
        fields = {k: data.get(k, [] if k == "tags" else "") for k in keys}
        if fields.get("annotationPosition"):
            fields["annotationPosition"] = json.loads(fields["annotationPosition"])
        fields["tags"] = sorted(
            [{"tag": x["tag"], "type": x.get("type", 0)} for x in data.get("tags", [])],
            key=lambda x: (x["tag"], x["type"]),
        )
        if data.get("itemType") == "note":
            fields["note"] = remote_content(data)
        fields["deleted"] = bool(data.get("deleted"))
        return fields

    def attachment_path(self, sid, key):
        response = self.request("GET", f"users/0/items/{key}/file/view/url", sid)
        if response.status_code != 200:
            return None
        parsed = urlparse(response.text.strip())
        path = Path(unquote(parsed.path))
        return (
            path
            if parsed.scheme == "file"
            and parsed.netloc in ("", "localhost")
            and path.is_file()
            else None
        )

    def attachment_version(self, paper):
        if not paper.get("zotero_attachment"):
            return ""
        path = self.attachment_path(paper["zotero_server"], paper["zotero_attachment"])
        return digest(path) if path else ""

    def pull_note(self, sid, p, d):
        mapping = self.mapped(sid, remote_key=d["key"])
        if not mapping:
            values = self.decode(p, d)
            # The record, history, operation and mapping become durable together.
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT * FROM sync_map WHERE server=? AND remote_key=?",
                    (sid, d["key"]),
                ).fetchone()
                if row:
                    mapping = dict(row)
                else:
                    note = self.store.put(
                        "note", values, origin="zotero", connection=db
                    )
                    self.map(sid, note, d, connection=db)
                    return
        note = self.store.get("note", mapping["local_id"])
        old_remote = json.loads(mapping["base_remote"])
        if d.get("deleted"):
            if not note["archived"]:
                self.conflict(sid, note, d, "remote-delete")
            return
        if d.get("version") == mapping["remote_version"]:
            return
        baseline = self.base_note(mapping)
        dirty = baseline is None or self.local_fields(note) != self.local_fields(
            baseline
        )
        if dirty:
            encoded = self.encode(p, note, d["key"], d.get("version", 0))
            encoded["deleted"] = note["archived"]
            if self.remote_fields(d) == self.remote_fields(encoded):
                self.map(sid, note, d)
            elif self.remote_fields(d) == self.remote_fields(old_remote):
                with self.store.connect() as db:
                    db.execute(
                        "UPDATE sync_map SET remote_version=?,base_remote=? WHERE server=? AND local_id=?",
                        (d["version"], json.dumps(d), sid, note["id"]),
                    )
            else:
                self.conflict(sid, note, d, "both-edited")
            return
        if self.remote_fields(d) == self.remote_fields(old_remote):
            self.map(sid, note, d)
            return
        updated = self.store.put(
            "note", self.decode(p, d, note), note["revision"], origin="zotero"
        )
        self.map(sid, updated, d)

    @staticmethod
    def relation_markers(data):
        value = data.get("relations", {}).get("owl:sameAs", [])
        return [value] if isinstance(value, str) else value

    def recover_creates(self, sid, paper, remote_notes):
        with self.store.connect() as db:
            pending = [
                dict(r)
                for r in db.execute("SELECT * FROM sync_outbox WHERE server=?", (sid,))
            ]
        for job in pending:
            original = json.loads(job["note"])
            if original["paper_id"] != paper["id"]:
                continue
            submitted = json.loads(job["payload"])
            matches = [
                d
                for d in remote_notes
                if job["marker"] in self.relation_markers(d)
                and d.get("itemType") == submitted["itemType"]
                and d.get("parentItem") == submitted["parentItem"]
            ]
            if len(matches) > 1:
                raise SyncError(
                    "发现多个相同关联标记的 Zotero 笔记；已停止写入，请核对后再同步。"
                )
            if matches:
                with self.store.connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    base = json.loads(job["payload"]) | {
                        "key": matches[0]["key"],
                        "version": -1,
                    }
                    self.map(sid, original, base, connection=db)
                    db.execute(
                        "DELETE FROM sync_outbox WHERE server=? AND local_id=?",
                        (sid, original["id"]),
                    )

    def create_note(self, sid, paper, note):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT * FROM sync_outbox WHERE server=? AND local_id=?",
                (sid, note["id"]),
            ).fetchone()
        if row:
            job = dict(row)
            if job["state"] == "unknown":
                raise SyncError(
                    "正在核对一次结果未知的 Zotero 写入；已保留原文，确认前不会重复新建。"
                )
            payload = json.loads(job["payload"])
            original = json.loads(job["note"])
        else:
            payload = self.encode(paper, note, "", 0)
            payload.pop("key", None)
            payload.pop("version", None)
            marker = "urn:paper-research-coach:" + secrets.token_hex(16)
            payload["relations"] = {"owl:sameAs": marker}
            original = note
            job = {"marker": marker, "token": secrets.token_hex(16)}
            with self.store.connect() as db:
                db.execute(
                    "INSERT INTO sync_outbox VALUES (?,?,?,?,?,?,?)",
                    (
                        sid,
                        note["id"],
                        marker,
                        job["token"],
                        json.dumps(note),
                        json.dumps(payload),
                        "prepared",
                    ),
                )
        if payload["itemType"] == "annotation" and (
            self.store.check_source(paper["id"])["status"] != "current"
            or self.attachment_version(paper) != original["anchor"]["source_version"]
        ):
            raise SyncError("PDF 已换版或不可用，请先核实版本，再同步区域批注。")
        # Crash or timeout after this point is an unknown outcome. First reconcile by
        # persistent marker; never replay a possibly in-flight unkeyed create blindly.
        with self.store.connect() as db:
            db.execute(
                "UPDATE sync_outbox SET state='unknown' WHERE server=? AND local_id=?",
                (sid, note["id"]),
            )
        try:
            response = self.request(
                "POST", "users/0/items", sid, [payload], write_token=job["token"]
            )
        except (httpx.ConnectError, SyncError) as error:
            if isinstance(error, SyncError) and not error.rejected:
                raise
            with self.store.connect() as db:
                db.execute(
                    "UPDATE sync_outbox SET state='prepared' WHERE server=? AND local_id=?",
                    (sid, note["id"]),
                )
            raise
        data = response.json()
        if data.get("failed"):
            # A definite rejection permits a corrected request, with a new token.
            with self.store.connect() as db:
                db.execute(
                    "DELETE FROM sync_outbox WHERE server=? AND local_id=?",
                    (sid, note["id"]),
                )
            code = next(iter(data["failed"].values())).get("code")
            raise SyncError(f"Zotero 未接受此笔记（{code}），原文保留在本地。")
        result = data.get("successful", {}).get("0")
        if not result:
            raise SyncError("Zotero 写入结果待核对；不会重复新建此笔记。")
        remote = result.get("data", result)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.map(sid, original, remote, connection=db)
            db.execute(
                "DELETE FROM sync_outbox WHERE server=? AND local_id=?",
                (sid, note["id"]),
            )
        return True

    def push_note(self, sid, p, n, confirmed_delete=False, force_local=False):
        if n["read_only"]:
            return False
        mapping = self.mapped(sid, local_id=n["id"])
        if (
            not force_local
            and mapping
            and mapping["base_local_revision"] == n["revision"]
        ):
            return True
        baseline = None if force_local else self.base_note(mapping)
        if (
            baseline
            and self.local_fields(n) == self.local_fields(baseline)
            and not confirmed_delete
        ):
            self.map(sid, n, json.loads(mapping["base_remote"]))
            return True
        if n["archived"] and not confirmed_delete:
            if mapping:
                self.conflict(
                    sid, n, json.loads(mapping["base_remote"]), "local-delete"
                )
            return False
        if not mapping or not mapping["remote_version"]:
            return self.create_note(sid, p, n)
        data = self.encode(p, n, mapping["remote_key"], mapping["remote_version"])
        previous = json.loads(mapping["base_remote"])
        if baseline:
            if n["content"] == baseline["content"]:
                if data["itemType"] == "note" and "note" in previous:
                    data["note"] = previous["note"]
                elif data["itemType"] == "annotation":
                    data["annotationComment"] = previous.get("annotationComment", "")
            if n["tags"] == baseline["tags"] and "tags" in previous:
                data["tags"] = previous["tags"]
        if previous.get("itemType") and data["itemType"] != previous["itemType"]:
            self.conflict(sid, n, previous, "anchor-type-changed")
            return False
        if data["itemType"] == "annotation" and (
            self.store.check_source(p["id"])["status"] != "current"
            or self.attachment_version(p) != p["source_version"]
        ):
            raise SyncError("PDF 已换版或不可用，请先核实版本，再同步区域批注。")
        if (
            previous.get("annotationPosition") == data.get("annotationPosition")
            and "annotationSortIndex" in previous
        ):
            data["annotationSortIndex"] = previous["annotationSortIndex"]
        # A local discussion flag or history update is not an external content edit.
        if (
            previous
            and all(
                previous.get(k) == v
                for k, v in data.items()
                if k not in ("key", "version")
            )
            and not confirmed_delete
        ):
            self.map(sid, n, previous)
            return True
        data = previous | data
        if confirmed_delete:
            data["deleted"] = 1
        r = self.request("POST", "users/0/items", sid, [data])
        response = r.json()
        if response.get("failed"):
            code = next(iter(response["failed"].values())).get("code")
            if code == 412:
                remote = self.request(
                    "GET", f"users/0/items/{mapping['remote_key']}", sid
                )
                if remote.status_code == 200:
                    self.pull_note(sid, p, remote.json()["data"])
                return False
            raise SyncError(f"Zotero 未接受此笔记（{code}），原文保留在本地。")
        result = response.get("successful", {}).get("0")
        if result:
            self.map(sid, n, result.get("data", result))
            return True
        else:
            read = self.request("GET", f"users/0/items/{mapping['remote_key']}", sid)
            if read.status_code == 200:
                self.map(sid, n, read.json()["data"])
                return True
        return False

    def run(self):
        try:
            self.lock.acquire(timeout=0)
        except Timeout:
            return self.state()
        try:
            config = self.state()
            sid = self.probe()
            if not config["collection"]:
                raise SyncError("请先选择要同步的 Zotero 集合。")
            if sid != config["server_id"]:
                raise SyncError(
                    "检测到不同 Zotero 文献库，待同步内容已隔离。请重新选择集合。"
                )
            parents = self.request(
                "GET",
                f"users/0/collections/{config['collection']}/items/top?format=json",
                sid,
            ).json()
            active_keys = {
                x["data"]["key"] for x in parents if not x["data"].get("deleted")
            }
            # A poll used to re-open SQLite and decode the entire library once
            # for every parent. Index this poll's snapshot once instead.
            papers = self.store.list("paper", archived=True)
            by_zotero = {
                (p["zotero_server"], p["zotero_key"]): p for p in papers
                if p["zotero_key"]
            }
            for existing in papers:
                if existing["archived"]:
                    continue
                if (
                    existing.get("zotero_server") != sid
                    or existing.get("zotero_collection", config["collection"])
                    != config["collection"]
                ):
                    continue
                if existing["zotero_key"] in active_keys:
                    with self.store.connect() as db:
                        db.execute(
                            "UPDATE sync_conflicts SET resolved=1 WHERE server=? AND local_id=? AND reason='paper-remote-delete'",
                            (sid, existing["id"]),
                        )
                    continue
                response = self.request(
                    "GET", f"users/0/items/{existing['zotero_key']}", sid
                )
                remote = (
                    response.json().get("data", {})
                    if response.status_code == 200
                    else {"key": existing["zotero_key"], "deleted": 1}
                )
                if remote.get("deleted"):
                    self.conflict(sid, existing, remote, "paper-remote-delete")
            for wrapped in parents:
                data = wrapped["data"]
                if data.get("itemType") in (
                    "note",
                    "attachment",
                    "annotation",
                ) or data.get("deleted"):
                    continue
                children = self.request(
                    "GET",
                    f"users/0/items/{data['key']}/children?format=json&includeTrashed=1",
                    sid,
                ).json()
                attachments = [
                    x["data"]
                    for x in children
                    if x["data"].get("itemType") == "attachment"
                    and x["data"].get("contentType") == "application/pdf"
                ]
                p = by_zotero.get((sid, data["key"]))
                # Preserve the optimistic revision check if another client
                # changes a paper while network requests are in flight.
                if p:
                    p = self.store.get("paper", p["id"])
                if p and p["archived"]:
                    continue
                meta = {
                    "publication": data.get("publicationTitle")
                    or data.get("proceedingsTitle")
                    or data.get("repository")
                    or "",
                    "authors": ", ".join(
                        " ".join(
                            filter(
                                None,
                                [
                                    a.get("firstName"),
                                    a.get("lastName") or a.get("name"),
                                ],
                            )
                        )
                        for a in data.get("creators", [])
                    ),
                    "year": data.get("date", ""),
                    "doi": data.get("DOI", ""),
                    "url": data.get("url", ""),
                    "zotero_key": data["key"],
                    "zotero_server": sid,
                    "zotero_collection": config["collection"],
                }
                attachment_key = (
                    p["zotero_attachment"]
                    if p and p["zotero_attachment"]
                    else (attachments[0]["key"] if attachments else "")
                )
                meta["zotero_attachment"] = attachment_key
                path = ""
                if attachment_key and (p is None or not p["source_path"]):
                    file_response = self.request(
                        "GET", f"users/0/items/{attachment_key}/file/view/url", sid
                    )
                    if file_response.status_code == 200:
                        parsed = urlparse(file_response.text.strip())
                        candidate = Path(unquote(parsed.path))
                        if (
                            parsed.scheme == "file"
                            and parsed.netloc in ("", "localhost")
                            and candidate.is_file()
                        ):
                            path = str(candidate)
                if p is None:
                    try:
                        p = self.store.add_paper(
                            data.get("title") or "Untitled", source_path=path, **meta
                        )
                    except (OSError, ValueError):
                        p = self.store.add_paper(
                            data.get("title") or "Untitled", **meta
                        )
                    # A previously imported identical PDF gets linked to this item.
                    p.update(meta)
                    p = self.store.put("paper", p, p["revision"], origin="zotero")
                elif any(p.get(k) != v for k, v in meta.items()) or p[
                    "title"
                ] != data.get("title", p["title"]):
                    p.update(meta, title=data.get("title") or p["title"])
                    p = self.store.put("paper", p, p["revision"], origin="zotero")
                if path and not p["source_path"]:
                    p = self.store.replace_source(p["id"], path)
                by_zotero[(sid, data["key"])] = p
                remote_notes = [
                    x["data"] for x in children if x["data"].get("itemType") == "note"
                ]
                if p["zotero_attachment"]:
                    annotations = self.request(
                        "GET",
                        f"users/0/items/{p['zotero_attachment']}/children?format=json&itemType=annotation&includeTrashed=1",
                        sid,
                    ).json()
                    remote_notes += [
                        x["data"]
                        for x in annotations
                        if x["data"].get("itemType") == "annotation"
                    ]
                self.recover_creates(sid, p, remote_notes)
                for d in remote_notes:
                    self.pull_note(sid, p, d)
                remote_keys = {d["key"] for d in remote_notes}
                conflicts = {
                    c["local_id"] for c in self.conflicts() if c["server"] == sid
                }
                for n in self.store.list("note", p["id"], archived=True):
                    if n["id"] in conflicts:
                        continue
                    mapping = self.mapped(sid, local_id=n["id"])
                    if (
                        mapping
                        and mapping["remote_version"]
                        and mapping["remote_key"] not in remote_keys
                    ):
                        check = self.request(
                            "GET", f"users/0/items/{mapping['remote_key']}", sid
                        )
                        if check.status_code == 404 or check.json().get("data", {}).get(
                            "deleted"
                        ):
                            if not n["archived"]:
                                self.conflict(
                                    sid,
                                    n,
                                    {"key": mapping["remote_key"], "deleted": 1},
                                    "remote-delete",
                                )
                            continue
                    self.push_note(sid, p, n)
            return self.set_state(state="connected", message="", last_success=now())
        except (
            SyncError,
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            OSError,
            sqlite3.Error,
        ) as e:
            # HTTP exception strings may contain credential-bearing headers. Never log them.
            message = (
                str(e)
                if isinstance(e, SyncError)
                else "同步未完成，内容已保存在本地；请检查集合与本地接口。"
            )
            return self.set_state(state="attention", message=message)
        finally:
            self.lock.release()

    def resolve(self, conflict_id, choice):
        if choice not in ("local", "remote"):
            raise ValueError("Choose local or remote")
        try:
            guard = self.lock.acquire(timeout=10)
        except Timeout:
            raise SyncError("另一处正在同步，请稍后重试。") from None
        with guard:
            c = next((x for x in self.conflicts() if x["id"] == conflict_id), None)
            if not c:
                raise KeyError("Conflict no longer exists")
            if self.probe() != c["server"]:
                raise SyncError("请连接产生此冲突的 Zotero 文献库。")
            if c["reason"] == "paper-remote-delete":
                paper = self.store.get("paper", c["local_id"])
                check = self.request(
                    "GET", f"users/0/items/{c['remote_key']}", c["server"]
                )
                if check.status_code == 200 and not check.json()["data"].get("deleted"):
                    with self.store.connect() as db:
                        db.execute(
                            "UPDATE sync_conflicts SET resolved=1 WHERE id=?",
                            (conflict_id,),
                        )
                    return {
                        "resolved": True,
                        "message": "Zotero 条目已恢复，已取消过期的删除提示。",
                    }
                if choice == "remote":
                    paper["archived"] = True
                else:
                    # Keep the paper and its notes locally; never recreate a deleted parent implicitly.
                    paper.update(
                        zotero_key="",
                        zotero_server="",
                        zotero_attachment="",
                        zotero_collection="",
                    )
                with self.store.connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    self.store.put(
                        "paper",
                        paper,
                        paper["revision"],
                        origin="zotero-resolution",
                        connection=db,
                    )
                    db.execute(
                        "UPDATE sync_conflicts SET resolved=1 WHERE id=?",
                        (conflict_id,),
                    )
                return {"resolved": True}
            n = self.store.get("note", c["local_id"])
            p = self.store.get("paper", n["paper_id"])
            response = self.request(
                "GET", f"users/0/items/{c['remote_key']}", c["server"]
            )
            remote = (
                response.json()["data"]
                if response.status_code == 200
                else {"key": c["remote_key"], "deleted": 1}
            )
            if choice == "remote":
                updated = (
                    (n | {"archived": True})
                    if remote.get("deleted")
                    else self.decode(p, remote, n)
                )
                n = self.store.put(
                    "note", updated, n["revision"], origin="zotero-resolution"
                )
                self.map(c["server"], n, remote)
            else:
                if remote.get("deleted") or c["reason"] == "anchor-type-changed":
                    # Preserve the remote object; a new local-linked item is deliberate.
                    with self.store.connect() as db:
                        db.execute(
                            "DELETE FROM sync_map WHERE server=? AND local_id=?",
                            (c["server"], n["id"]),
                        )
                else:
                    with self.store.connect() as db:
                        db.execute(
                            "UPDATE sync_map SET remote_version=?,base_remote=? WHERE server=? AND local_id=?",
                            (
                                remote.get("version", 0),
                                json.dumps(remote),
                                c["server"],
                                n["id"],
                            ),
                        )
                if not self.push_note(
                    c["server"], p, n, confirmed_delete=n["archived"], force_local=True
                ):
                    raise SyncError("冲突期间内容再次变化，请重新同步并核对双方。")
            with self.store.connect() as db:
                db.execute(
                    "UPDATE sync_conflicts SET resolved=1 WHERE id=?", (conflict_id,)
                )
            return {"resolved": True}
