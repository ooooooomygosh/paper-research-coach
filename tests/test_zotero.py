import copy
import json

import httpx
import pytest
from paper_research_coach.zotero import ZoteroSync, SyncError
from paper_research_coach.store import Store


class LocalAPI:
    def __init__(self, pdf):
        self.sid = "instance-A"
        self.version = 1
        self.auth = True
        self.denied = False
        self.offline = False
        self.writes = []
        self.fail_after_write = False
        self.pdf = pdf
        self.items = {
            "PARENT01": {
                "key": "PARENT01",
                "version": 1,
                "itemType": "journalArticle",
                "title": "Synthetic Zotero paper",
                "creators": [],
                "date": "2026",
                "collections": ["COLLECT1"],
            },
            "ATTACH01": {
                "key": "ATTACH01",
                "version": 1,
                "itemType": "attachment",
                "parentItem": "PARENT01",
                "contentType": "application/pdf",
            },
        }

    def handle(self, request):
        if self.offline:
            raise httpx.ConnectError("offline", request=request)
        path = request.url.path.removeprefix("/api/")
        method = request.method
        headers = {"Zotero-Server-ID": self.sid}

        def response(code=200, data=None, body=None):
            return (
                httpx.Response(code, json=data, headers=headers)
                if body is None
                else httpx.Response(code, text=body, headers=headers)
            )

        if path == "":
            return response(data={})
        if request.headers.get("Zotero-Server-ID") != self.sid:
            return response(412, {})
        if path == "local/authorize":
            return (
                response(403, {"denied": True})
                if self.denied
                else response(data={"key": "test-key", "remember": False})
            )
        if method == "POST":
            if not self.auth or request.headers.get("Zotero-API-Key") != "test-key":
                return response(401, {})
            assert path == "users/0/items"
            data = json.loads(request.content)[0]
            old = self.items.get(data["key"])
            if old and old["version"] != data["version"]:
                return response(data={"failed": {"0": {"code": 412}}})
            self.version += 1
            data = copy.deepcopy(data)
            data["version"] = self.version
            self.items[data["key"]] = data
            self.writes.append(copy.deepcopy(data))
            if self.fail_after_write:
                self.fail_after_write = False
                raise httpx.ReadError(
                    "connection lost after successful commit", request=request
                )
            return response(
                data={
                    "successful": {"0": {"data": data}},
                    "failed": {},
                    "unchanged": {},
                }
            )
        if path == "users/0/collections":
            return response(
                data=[{"key": "COLLECT1", "data": {"name": "Isolated synthetic test"}}]
            )
        if path == "users/0/collections/COLLECT1/items/top":
            return response(data=[{"data": self.items["PARENT01"]}])
        if path.endswith("/file/view/url"):
            return response(body=self.pdf.as_uri())
        if path.endswith("/children"):
            parent = path.split("/")[-2]
            return response(
                data=[
                    {"data": d}
                    for d in self.items.values()
                    if d.get("parentItem") == parent and not d.get("deleted")
                ]
            )
        key = path.split("/")[-1]
        return (
            response(data={"data": self.items[key]})
            if key in self.items
            else response(404, {})
        )

    def mutate(self, key, **changes):
        self.version += 1
        self.items[key].update(changes, version=self.version)


@pytest.fixture
def synced(store, pdf, monkeypatch):
    import keyring

    monkeypatch.setattr(keyring, "get_password", lambda *a: None)
    monkeypatch.setattr(keyring, "delete_password", lambda *a: None)
    fake = LocalAPI(pdf)
    sync = ZoteroSync(
        store,
        httpx.Client(
            base_url="http://127.0.0.1:23119/api/",
            transport=httpx.MockTransport(fake.handle),
        ),
    )
    sync.configure("instance-A", "COLLECT1")
    sync.keys[fake.sid] = "test-key"
    assert sync.run()["state"] == "connected"
    return sync, fake, store.list("paper")[0]


def test_roundtrip_note_and_native_annotation(synced, store):
    sync, fake, p = synced
    n = store.put("note", {"paper_id": p["id"], "content": "  我的原话\n第二行  "})
    assert sync.run()["state"] == "connected"
    m = sync.mapped(fake.sid, local_id=n["id"])
    assert m and m["remote_version"] > 0
    assert len(fake.writes) == 1
    sync.run()
    assert len(fake.writes) == 1
    fake.mutate(m["remote_key"], note="<div><pre>Zotero changed\nline 2</pre></div>")
    sync.run()
    n = store.get("note", n["id"])
    assert n["content"] == "Zotero changed\nline 2" and n["author"] == "user"
    assert store.history(n["id"])[0]["data"]["content"] == "  我的原话\n第二行  "
    a = {
        "paper_id": p["id"],
        "source_version": p["source_version"],
        "page_index": 0,
        "page_label": "i",
        "quote": "Synthetic",
        "rects": [[60, 715, 120, 735]],
        "status": "verified",
    }
    n2 = store.put("note", {"paper_id": p["id"], "content": "批注", "anchor": a})
    sync.run()
    m = sync.mapped(fake.sid, local_id=n2["id"])
    d = fake.items[m["remote_key"]]
    assert d["itemType"] == "annotation" and d["parentItem"] == "ATTACH01"
    assert json.loads(d["annotationPosition"])["rects"] == a["rects"]
    fake.mutate(
        d["key"], annotationComment="changed annotation", annotationColor="#ff6666"
    )
    sync.run()
    assert store.get("note", n2["id"])["content"] == "changed annotation"
    assert store.get("note", n2["id"])["color"] == "#ff6666"


def test_concurrent_edits_preserve_both_and_resolve(synced, store):
    sync, fake, p = synced
    n = store.put("note", {"paper_id": p["id"], "content": "base"})
    sync.run()
    m = sync.mapped(fake.sid, local_id=n["id"])
    store.put("note", n | {"content": "local change"}, n["revision"])
    fake.mutate(m["remote_key"], note="<p>remote change</p>")
    sync.run()
    c = sync.conflicts()[0]
    assert (
        c["local_data"]["content"] == "local change"
        and "remote change" in c["remote_data"]["note"]
    )
    assert len(fake.writes) == 1
    sync.resolve(c["id"], "remote")
    assert not sync.conflicts()
    assert store.get("note", n["id"])["content"] == "remote change"
    assert [x["data"]["content"] for x in store.history(n["id"])] == [
        "base",
        "local change",
        "remote change",
    ]


def test_remote_and_local_deletion_need_explicit_resolution(synced, store):
    sync, fake, p = synced
    n = store.put("note", {"paper_id": p["id"], "content": "keep me"})
    sync.run()
    m = sync.mapped(fake.sid, local_id=n["id"])
    fake.mutate(m["remote_key"], deleted=1)
    sync.run()
    assert not store.get("note", n["id"])["archived"]
    assert sync.conflicts()[0]["reason"] == "remote-delete"
    sync.resolve(sync.conflicts()[0]["id"], "remote")
    assert store.get("note", n["id"])["archived"]
    n = store.put("note", {"paper_id": p["id"], "content": "local archive"})
    sync.run()
    m = sync.mapped(fake.sid, local_id=n["id"])
    n = store.put("note", n | {"archived": True}, n["revision"])
    sync.run()
    assert not fake.items[m["remote_key"]].get("deleted")
    assert sync.conflicts()[0]["reason"] == "local-delete"
    sync.resolve(sync.conflicts()[0]["id"], "local")
    assert fake.items[m["remote_key"]]["deleted"] == 1
    assert store.get("paper", p["id"])["source_path"] and fake.pdf.is_file()


def test_unknown_write_outcome_reconnect_is_idempotent(synced, store):
    sync, fake, p = synced
    n = store.put("note", {"paper_id": p["id"], "content": "do not duplicate"})
    fake.fail_after_write = True
    assert sync.run()["state"] == "attention"
    restarted = ZoteroSync(Store(store.root), sync.client)
    restarted.keys[fake.sid] = "test-key"
    assert restarted.run()["state"] == "connected"
    assert len(fake.writes) == 1 and len(store.list("note")) == 1
    fake.offline = True
    store.put("note", n | {"content": "offline thought"}, n["revision"])
    assert restarted.run()["state"] == "attention"
    fake.offline = False
    assert restarted.run()["state"] == "connected"
    assert len(fake.writes) == 2


def test_instance_switch_never_writes_previous_library(synced, store):
    sync, fake, p = synced
    store.put("note", {"paper_id": p["id"], "content": "belongs to A"})
    fake.sid = "instance-B"
    assert sync.run()["state"] == "attention" and not fake.writes
    sync.configure("instance-B", "COLLECT1")
    sync.keys[fake.sid] = "test-key"
    sync.run()
    assert not fake.writes
    assert len(store.list("paper")) == 2


def test_denied_and_expired_auth_keep_local_data(synced, store):
    sync, fake, p = synced
    fake.denied = True
    assert sync.authorize(fake.sid) == {"authorized": False, "remembered": False}
    n = store.put("note", {"paper_id": p["id"], "content": "safe locally"})
    fake.auth = False
    assert sync.run()["state"] == "attention"
    assert store.get("note", n["id"])["content"] == "safe locally"
    assert fake.sid not in sync.keys
    assert "test-key" not in json.dumps(store.setting("zotero"))
    fake.auth = True
    fake.denied = False
    sync.authorize(fake.sid)
    sync.run()
    assert len(fake.writes) == 1


def test_external_annotation_preserved_and_not_overwritten(synced, store):
    sync, fake, p = synced
    fake.items["EXTERNAL"] = {
        "key": "EXTERNAL",
        "version": 5,
        "itemType": "annotation",
        "parentItem": "ATTACH01",
        "annotationType": "ink",
        "annotationComment": "original external",
        "annotationPosition": json.dumps({"pageIndex": 0, "paths": [[1, 2, 3, 4]]}),
        "annotationIsExternal": True,
    }
    sync.run()
    n = store.list("note")[0]
    assert n["read_only"] and not fake.writes
    store.put(
        "note",
        {"paper_id": p["id"], "content": "my linked thought", "links": [n["id"]]},
    )
    sync.run()
    assert (
        len(fake.writes) == 1
        and fake.items["EXTERNAL"]["annotationComment"] == "original external"
    )


def test_failed_conflict_resolution_stays_unresolved(synced, store):
    sync, fake, p = synced
    n = store.put("note", {"paper_id": p["id"], "content": "base"})
    sync.run()
    m = sync.mapped(fake.sid, local_id=n["id"])
    store.put("note", n | {"content": "local"}, 1)
    fake.mutate(m["remote_key"], note="<p>remote</p>")
    sync.run()
    fake.auth = False
    with pytest.raises(SyncError):
        sync.resolve(sync.conflicts()[0]["id"], "local")
    assert sync.conflicts() and store.get("note", n["id"])["content"] == "local"


def test_discussed_flag_does_not_rewrite_remote(synced, store):
    sync, fake, p = synced
    n = store.put("note", {"paper_id": p["id"], "content": "original"})
    sync.run()
    n = store.put("note", n | {"discussed": True}, n["revision"])
    sync.run()
    assert len(fake.writes) == 1


def test_pdf_changed_in_place_stops_position_writes(synced, store):
    sync, fake, p = synced
    a = {
        "paper_id": p["id"],
        "source_version": p["source_version"],
        "page_index": 0,
        "rects": [[60, 700, 100, 720]],
        "status": "verified",
    }
    store.put("note", {"paper_id": p["id"], "content": "geometry", "anchor": a})
    fake.pdf.write_bytes(b"changed source")
    assert sync.run()["state"] == "attention" and not fake.writes


def test_existing_metadata_item_gets_later_downloaded_pdf(synced, store):
    sync, fake, p = synced
    store.put(
        "paper",
        p
        | {
            "source_path": "",
            "source_version": "",
            "page_count": 0,
            "access_scope": "metadata",
        },
        p["revision"],
    )
    assert sync.run()["state"] == "connected"
    assert store.get("paper", p["id"])["page_count"] == 2
