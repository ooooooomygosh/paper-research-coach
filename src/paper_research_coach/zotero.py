from __future__ import annotations

import html
import json
import re
import secrets
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from .models import Note, SyncState, now, uid
from .store import Store


class SyncError(ValueError):
    pass


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
        if tag in ("p", "div", "li"):
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
    match = re.search(r"<pre[^>]*>(.*?)</pre>", data.get("note", ""), re.S)
    return (
        html.unescape(match.group(1))
        if match
        else plain(data.get("note", "")) or "[空白笔记]"
    )


class ZoteroSync:
    def __init__(self, store: Store, client: httpx.Client | None = None):
        self.store = store
        self.client = client or httpx.Client(
            base_url="http://127.0.0.1:23119/api/", timeout=10, follow_redirects=False
        )
        self.keys = {}
        self.lock = threading.Lock()

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

    def request(self, method, path, sid, data=None):
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
                raise SyncError("本地内容已保存；请在同步设置中授权 Zotero 写入。")
            headers["Zotero-API-Key"] = key
        r = self.client.request(method, path, headers=headers, json=data)
        if r.status_code == 401:
            self.keys.pop(sid, None)
            try:
                import keyring

                keyring.delete_password("paper-research-coach-zotero", sid)
            except Exception:
                pass
            raise SyncError("Zotero 写入授权已失效；请重新授权。")
        if r.status_code == 412:
            raise SyncError("Zotero 版本或实例已变化，已停止本次写入。请重新同步。")
        if r.status_code == 403:
            raise SyncError("Zotero 拒绝了访问；本地笔记保持可用。")
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

    def mapped(self, sid, local_id=None, remote_key=None):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT * FROM sync_map WHERE server=? AND "
                + ("local_id=?" if local_id else "remote_key=?"),
                (sid, local_id or remote_key),
            ).fetchone()
        return dict(row) if row else None

    def map(self, sid, note, data):
        with self.store.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO sync_map VALUES (?,?,?,?,?,?)",
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
        values["discussed"] = False
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
            values["anchor"] = {
                "paper_id": p["id"],
                "source_version": p["source_version"],
                "page_index": pos.get("pageIndex"),
                "page_label": d.get("annotationPageLabel", ""),
                "quote": d.get("annotationText", ""),
                "rects": pos.get("rects", []),
                "status": (
                    "verified"
                    if self.store.check_source(p["id"])["status"] == "current"
                    else "stale"
                )
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

    def pull_note(self, sid, p, d):
        mapping = self.mapped(sid, remote_key=d["key"])
        if not mapping:
            note = self.store.put("note", self.decode(p, d), origin="zotero")
            self.map(sid, note, d)
            return
        note = self.store.get("note", mapping["local_id"])
        old_remote = json.loads(mapping["base_remote"])
        if d.get("deleted"):
            if not note["archived"]:
                self.conflict(sid, note, d, "remote-delete")
            return
        if d.get("version") == mapping["remote_version"]:
            return
        if note["revision"] != mapping["base_local_revision"]:
            encoded = self.encode(p, note, d["key"], d.get("version", 0))
            if remote_content(d) == note["content"] and all(
                d.get(k) == v for k, v in encoded.items() if k.startswith("annotation")
            ):
                self.map(sid, note, d)
            elif remote_content(d) == remote_content(old_remote) and all(
                d.get(k) == old_remote.get(k) for k in d if k.startswith("annotation")
            ):
                # A remote metadata-only change doesn't overwrite a local thought.
                with self.store.connect() as db:
                    db.execute(
                        "UPDATE sync_map SET remote_version=?,base_remote=? WHERE server=? AND local_id=?",
                        (d["version"], json.dumps(d), sid, note["id"]),
                    )
            else:
                self.conflict(sid, note, d, "both-edited")
            return
        updated = self.store.put(
            "note", self.decode(p, d, note), note["revision"], origin="zotero"
        )
        self.map(sid, updated, d)

    def push_note(self, sid, p, n, confirmed_delete=False):
        if n["read_only"]:
            return False
        mapping = self.mapped(sid, local_id=n["id"])
        if mapping and mapping["base_local_revision"] == n["revision"]:
            return True
        if n["archived"] and not confirmed_delete:
            if mapping:
                self.conflict(
                    sid, n, json.loads(mapping["base_remote"]), "local-delete"
                )
            return False
        if not mapping:
            key = "".join(
                secrets.choice("23456789ABCDEFGHIJKLMNPQRSTUVWXYZ") for _ in range(8)
            )
            with self.store.connect() as db:
                db.execute(
                    "INSERT INTO sync_map VALUES (?,?,?,?,?,?)",
                    (sid, n["id"], key, 0, 0, "{}"),
                )
            mapping = self.mapped(sid, local_id=n["id"])
        data = self.encode(p, n, mapping["remote_key"], mapping["remote_version"])
        previous = json.loads(mapping["base_remote"])
        if previous.get("itemType") and data["itemType"] != previous["itemType"]:
            self.conflict(sid, n, previous, "anchor-type-changed")
            return False
        if (
            data["itemType"] == "annotation"
            and self.store.check_source(p["id"])["status"] != "current"
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
        if not self.lock.acquire(blocking=False):
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
            for wrapped in parents:
                data = wrapped["data"]
                if data.get("itemType") in (
                    "note",
                    "attachment",
                    "annotation",
                ) or data.get("deleted"):
                    continue
                children = self.request(
                    "GET", f"users/0/items/{data['key']}/children?format=json", sid
                ).json()
                attachments = [
                    x["data"]
                    for x in children
                    if x["data"].get("itemType") == "attachment"
                    and x["data"].get("contentType") == "application/pdf"
                ]
                p = next(
                    (
                        p
                        for p in self.store.list("paper")
                        if p["zotero_server"] == sid and p["zotero_key"] == data["key"]
                    ),
                    None,
                )
                meta = {
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
                remote_notes = [
                    x["data"] for x in children if x["data"].get("itemType") == "note"
                ]
                if p["zotero_attachment"]:
                    annotations = self.request(
                        "GET",
                        f"users/0/items/{p['zotero_attachment']}/children?format=json",
                        sid,
                    ).json()
                    remote_notes += [
                        x["data"]
                        for x in annotations
                        if x["data"].get("itemType") == "annotation"
                    ]
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
        except (SyncError, httpx.HTTPError, ValueError, KeyError, TypeError) as e:
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
        with self.lock:
            c = next((x for x in self.conflicts() if x["id"] == conflict_id), None)
            if not c:
                raise KeyError("Conflict no longer exists")
            if self.probe() != c["server"]:
                raise SyncError("请连接产生此冲突的 Zotero 文献库。")
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
                    self.map(c["server"], n | {"revision": n["revision"] - 1}, remote)
                if not self.push_note(
                    c["server"], p, n, confirmed_delete=n["archived"]
                ):
                    raise SyncError("冲突期间内容再次变化，请重新同步并核对双方。")
            with self.store.connect() as db:
                db.execute(
                    "UPDATE sync_conflicts SET resolved=1 WHERE id=?", (conflict_id,)
                )
            return {"resolved": True}
