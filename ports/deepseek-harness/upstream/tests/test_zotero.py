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
            if "key" not in data:
                data["key"] = f"TEST{len(self.items):04d}"
                data["version"] = 0
            old = self.items.get(data["key"])
            if old and old["version"] != data["version"]:
                return response(data={"failed": {"0": {"code": 412}}})
            self.version += 1
            data = copy.deepcopy((old or {}) | data)
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
            from pathlib import Path

            item = self.items.get(path.split("/")[-4], {})
            return response(body=Path(item.get("path", str(self.pdf))).as_uri())
        if path == "users/0/items":
            kind = request.url.params.get("itemType")
            return response(
                data=[
                    {"data": d}
                    for d in self.items.values()
                    if not kind or d["itemType"] == kind
                ]
            )
        if path.endswith("/children"):
            parent = path.split("/")[-2]
            return response(
                data=[
                    {"data": d}
                    for d in self.items.values()
                    if d.get("parentItem") == parent
                    and (
                        not d.get("deleted")
                        or request.url.params.get("includeTrashed") == "1"
                    )
                    and (
                        d.get("itemType") != "annotation"
                        or request.url.params.get("itemType") == "annotation"
                    )
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


def test_rich_note_and_empty_highlight_survive_discussion(synced, store):
    sync, fake, p = synced
    rich = "<p>Important finding</p><pre>code</pre><p>Critical caveat</p>"
    fake.items["RICHNOTE"] = dict(
        key="RICHNOTE",
        version=2,
        itemType="note",
        parentItem="PARENT01",
        note=rich,
        tags=[],
    )
    fake.items["HIGHLITE"] = dict(
        key="HIGHLITE",
        version=2,
        itemType="annotation",
        parentItem="ATTACH01",
        annotationType="highlight",
        annotationComment="",
        annotationText="Original excerpt",
        annotationColor="#ffda75",
        annotationPageLabel="1",
        annotationSortIndex="00000|000000|00000",
        annotationPosition=json.dumps({"pageIndex": 0, "rects": [[60, 700, 200, 720]]}),
        tags=[],
    )
    sync.run()
    notes = store.list("note")
    assert notes[0]["content"] == "Important finding\ncode\nCritical caveat"
    for n in notes:
        store.put("note", n | {"discussed": True}, n["revision"])
    sync.run()
    assert not fake.writes
    assert fake.items["RICHNOTE"]["note"] == rich
    assert fake.items["HIGHLITE"]["annotationComment"] == ""


def test_replaced_pdf_never_writes_regions_to_old_zotero_attachment(
    synced, store, tmp_path
):
    from pypdf import PdfWriter

    sync, fake, p = synced
    new = tmp_path / "new.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    writer.write(new)
    p = store.replace_source(p["id"], str(new))
    anchor = dict(
        paper_id=p["id"],
        source_version=p["source_version"],
        page_index=0,
        rects=[[50, 600, 200, 620]],
        status="verified",
    )
    store.put("note", dict(paper_id=p["id"], content="new region", anchor=anchor))
    assert sync.run()["state"] == "attention"
    assert not fake.writes


@pytest.mark.parametrize(
    "local_change", [{"content": "local text"}, {"archived": True}]
)
def test_remote_tags_are_part_of_conflict_detection(synced, store, local_change):
    sync, fake, p = synced
    n = store.put("note", dict(paper_id=p["id"], content="base", tags=["old"]))
    sync.run()
    m = sync.mapped(fake.sid, local_id=n["id"])
    store.put("note", n | local_change, n["revision"])
    fake.mutate(m["remote_key"], tags=[{"tag": "remote tag"}])
    sync.run()
    assert len(sync.conflicts()) == 1 and len(fake.writes) == 1
    assert fake.items[m["remote_key"]]["tags"] == [{"tag": "remote tag"}]
    assert not fake.items[m["remote_key"]].get("deleted")


def test_concurrent_first_pull_creates_one_local_record(synced, store, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    sync, fake, p = synced
    data = dict(
        key="RACENOTE",
        version=3,
        itemType="note",
        parentItem="PARENT01",
        note="<p>one thought</p>",
        tags=[],
    )
    fake.items[data["key"]] = data
    other = ZoteroSync(Store(store.root), sync.client)
    barrier = threading.Barrier(2)
    for obj in (sync, other):
        original = obj.mapped

        def mapped(sid, local_id=None, remote_key=None, _original=original):
            result = _original(sid, local_id, remote_key)
            if remote_key == "RACENOTE" and result is None:
                barrier.wait(timeout=5)
            return result

        monkeypatch.setattr(obj, "mapped", mapped)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda obj: obj.pull_note(fake.sid, p, data), [sync, other]))
    assert len(store.list("note")) == 1
    sync.run()
    assert not fake.writes


def test_parent_deletion_resolution_keeps_notes_and_ignores_restored_parent(
    synced, store
):
    sync, fake, p = synced
    n = store.put("note", dict(paper_id=p["id"], content="preserve"))
    sync.run()
    fake.mutate("PARENT01", deleted=1)
    sync.run()
    c = sync.conflicts()[0]
    assert (
        c["reason"] == "paper-remote-delete"
        and not store.get("paper", p["id"])["archived"]
    )
    fake.mutate("PARENT01", deleted=0)
    sync.resolve(c["id"], "remote")
    assert not store.get("paper", p["id"])["archived"]
    fake.mutate("PARENT01", deleted=1)
    sync.run()
    sync.resolve(sync.conflicts()[0]["id"], "remote")
    assert (
        store.get("paper", p["id"])["archived"]
        and store.get("note", n["id"])["content"] == "preserve"
    )
    fake.mutate("PARENT01", deleted=0)
    sync.run()
    assert len(store.list("paper", archived=True)) == 1 and fake.pdf.is_file()


def test_explicit_local_conflict_choice_survives_discussion_revision(synced, store):
    sync, fake, p = synced
    n = store.put("note", dict(paper_id=p["id"], content="base"))
    sync.run()
    key = sync.mapped(fake.sid, local_id=n["id"])["remote_key"]
    n = store.put("note", n | {"content": "LOCAL CHOICE"}, n["revision"])
    fake.mutate(key, note="<p>REMOTE CHOICE</p>")
    sync.run()
    n = store.put("note", n | {"discussed": True}, n["revision"])
    sync.resolve(sync.conflicts()[0]["id"], "local")
    sync.run()
    from paper_research_coach.zotero import remote_content

    assert remote_content(fake.items[key]) == "LOCAL CHOICE"
    assert not sync.conflicts()


def test_unkeyed_create_keeps_persistent_marker(synced, store):
    sync, fake, p = synced
    n = store.put("note", dict(paper_id=p["id"], content="new"))
    sync.run()
    assert fake.writes[0]["relations"]["owl:sameAs"].startswith(
        "urn:paper-research-coach:"
    )
    assert sync.mapped(fake.sid, local_id=n["id"])["remote_key"].startswith("TEST")


def test_unknown_create_is_not_blindly_replayed(synced, store):
    sync, fake, p = synced
    n = store.put("note", dict(paper_id=p["id"], content="keep pending"))

    def timeout(request):
        if request.method == "POST":
            raise httpx.ReadTimeout("unknown", request=request)
        return fake.handle(request)

    sync.client = httpx.Client(
        base_url="http://127.0.0.1:23119/api/", transport=httpx.MockTransport(timeout)
    )
    assert sync.run()["state"] == "attention"
    sync.client = httpx.Client(
        base_url="http://127.0.0.1:23119/api/",
        transport=httpx.MockTransport(fake.handle),
    )
    assert sync.run()["state"] == "attention" and not fake.writes
    assert store.get("note", n["id"])["content"] == "keep pending"


def test_folder_binding_checks_instance_and_actual_attachment_bytes(
    synced, store, tmp_path, monkeypatch
):
    from paper_research_coach.metadata import MetadataResolver

    monkeypatch.setattr(
        MetadataResolver,
        "resolve",
        lambda self, p: {
            "payload": {
                "itemType": "journalArticle",
                "title": p["title"],
                "creators": [
                    {"creatorType": "author", "name": "Synthetic Test Author"}
                ],
            }
        },
    )
    from pypdf import PdfWriter

    sync, fake, linked = synced
    # Warm A's cache using another local record with identical source bytes.
    p = store.put(
        "paper",
        {
            k: v
            for k, v in linked.items()
            if k
            not in (
                "id",
                "revision",
                "zotero_key",
                "zotero_attachment",
                "zotero_server",
                "zotero_collection",
            )
        },
    )
    bound = sync.bind_local_paper(p, "COLLECT1", fake.sid)
    assert bound["zotero_attachment"] == "ATTACH01"
    different = tmp_path / "different.pdf"
    w = PdfWriter()
    w.add_blank_page(width=700, height=800)
    w.write(different)
    fake.sid = "instance-B"
    fake.pdf = different
    sync.keys[fake.sid] = "test-key"
    p = store.put(
        "paper",
        {
            k: v
            for k, v in linked.items()
            if k
            not in (
                "id",
                "revision",
                "zotero_key",
                "zotero_attachment",
                "zotero_server",
                "zotero_collection",
            )
        },
    )
    bound = sync.bind_local_paper(p, "COLLECT1", fake.sid)
    assert bound["zotero_attachment"] != "ATTACH01"
    assert sync.attachment_version(bound) == bound["source_version"]


def test_rejected_object_creation_can_use_new_collection(synced):
    sync, fake, _ = synced
    payload = {"itemType": "journalArticle", "title": "new", "collections": ["OLD"]}
    fake.auth = False
    with pytest.raises(SyncError):
        sync.create_object(fake.sid, "object", payload)
    fake.auth = True
    sync.keys[fake.sid] = "test-key"
    result = sync.create_object(fake.sid, "object", payload | {"collections": ["NEW"]})
    assert result["collections"] == ["NEW"]


def test_unknown_create_recovery_preserves_edits_during_disconnect(synced, store):
    sync, fake, p = synced
    n = store.put("note", {"paper_id": p["id"], "content": "submitted"})
    fake.fail_after_write = True
    sync.run()
    n = store.put("note", n | {"content": "typed after sending"}, n["revision"])
    key = fake.writes[0]["key"]
    fake.mutate(key, note="<p>remote edit too</p>")
    sync.run()
    assert store.get("note", n["id"])["content"] == "typed after sending"
    assert (
        fake.items[key]["note"] == "<p>remote edit too</p>"
        and len(sync.conflicts()) == 1
    )
    assert len(store.list("note")) == 1


def test_new_parent_requires_verified_metadata_before_any_write(
    synced, store, tmp_path, monkeypatch
):
    from paper_research_coach.metadata import MetadataResolver, MetadataPending
    from pypdf import PdfWriter

    sync, fake, _ = synced
    file = tmp_path / "unknown.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=700, height=700)
    writer.write(file)
    p = store.add_paper("Unverified paper", str(file), authors="None, Author et al.")

    def pending(*a, **kw):
        raise MetadataPending("needs verification")

    monkeypatch.setattr(MetadataResolver, "resolve", pending)
    with pytest.raises(MetadataPending):
        sync.bind_local_paper(p, "COLLECT1", fake.sid)
    assert not fake.writes and not store.get("paper", p["id"])["zotero_key"]


def test_unknown_legacy_parent_recovers_then_repairs_without_duplicate(
    synced, store, tmp_path, monkeypatch
):
    from paper_research_coach.metadata import MetadataResolver
    from pypdf import PdfWriter

    sync, fake, _ = synced
    file = tmp_path / "legacy.pdf"
    w = PdfWriter()
    w.add_blank_page(width=700, height=700)
    w.write(file)
    p = store.add_paper("Legacy paper", str(file))
    old = {"itemType": "document", "title": "Legacy paper", "collections": ["COLLECT1"]}
    fake.fail_after_write = True
    with pytest.raises(httpx.ReadError):
        sync.create_object(fake.sid, p["id"] + ":parent", old)
    key = fake.writes[-1]["key"]
    verified = {
        "itemType": "journalArticle",
        "title": "Verified legacy paper",
        "creators": [
            {"creatorType": "author", "firstName": "Ada", "lastName": "Example"}
        ],
    }
    monkeypatch.setattr(
        MetadataResolver, "resolve", lambda self, p: {"payload": verified}
    )
    bound = sync.bind_local_paper(p, "COLLECT1", fake.sid)
    assert (
        bound["zotero_key"] == key
        and fake.items[key]["creators"] == verified["creators"]
    )
    assert (
        sum(x.get("title") == "Verified legacy paper" for x in fake.items.values()) == 1
    )
    assert fake.items[bound["zotero_attachment"]]["parentItem"] == key


def test_sync_indexes_library_once_per_poll(synced, store, monkeypatch):
    sync, fake, first = synced
    parents = [{"data": fake.items["PARENT01"]}]
    for index in range(30):
        key = f"PARENT{index + 2:02d}"
        remote = dict(fake.items["PARENT01"], key=key, title=f"Paper {index}")
        fake.items[key] = remote
        parents.append({"data": remote})
        store.add_paper(
            remote["title"], zotero_server=fake.sid,
            zotero_key=key, zotero_collection="COLLECT1",
        )
    request = sync.request

    def respond(method, path, sid, *args, **kwargs):
        if "/collections/COLLECT1/items/top" in path:
            return httpx.Response(200, json=parents)
        return request(method, path, sid, *args, **kwargs)

    monkeypatch.setattr(sync, "request", respond)
    original_list, library_reads = store.list, []

    def list_records(kind, *args, **kwargs):
        if kind == "paper":
            library_reads.append(kind)
        return original_list(kind, *args, **kwargs)

    monkeypatch.setattr(store, "list", list_records)
    assert sync.run()["state"] == "connected"
    assert len(library_reads) == 1
    assert store.get("paper", first["id"])["zotero_key"] == "PARENT01"
