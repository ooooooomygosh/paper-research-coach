"""One-way, idempotent import from the earlier local JS prototype.

The old directory remains intact. Reading completion is kept as an archival
record rather than asserted under the stronger source-grounded state machine.
"""
import hashlib
import json
import shutil
from pathlib import Path

from .models import uid, now


def migrate(store, coach):
    legacy = store.root.parent / "paper-coach"
    if not (legacy / "papers").is_dir():
        return
    for folder in (legacy / "papers").iterdir():
        if not folder.is_dir() or not (folder / "paper.json").is_file():
            continue
        marker = "legacy-import:" + folder.name
        if store.setting(marker):
            continue
        try:
            metadata = json.loads((folder / "paper.json").read_text(encoding="utf-8"))
            source = folder / "source.pdf"
            if not source.is_file():
                source = Path(metadata.get("sourcePath", ""))
            if not source.is_file():
                continue
            imports = store.root / "imports"
            imports.mkdir(exist_ok=True)
            target = imports / ("legacy-" + hashlib.sha256(folder.name.encode()).hexdigest()[:20] + ".pdf")
            if not target.exists():
                shutil.copy2(source, target)
            paper = store.add_paper(metadata.get("title") or source.stem, str(target))
            pid = paper["id"]
            fields = {key: str(metadata.get(key, "")) for key in ("authors", "year", "doi", "url")}
            store.commit({"operation_id": "legacy-metadata-" + folder.name, "mutations": [{"kind": "paper", "expected_revision": paper["revision"], "data": {**paper, **fields}}]})
            for file in (folder / "notes").glob("*.json"):
                note = json.loads(file.read_text(encoding="utf-8"))
                if not note.get("content"):
                    continue
                anchor = note.get("anchor") or {}
                old_author = note.get("author", "user")
                author = old_author if old_author in ("user", "assistant", "external") else "external"
                provenance = "USER" if author == "user" else note.get("provenance", "INFERENCE")
                if provenance not in ("PAPER", "EXTERNAL", "INFERENCE", "IDEA", "USER") or (author != "user" and provenance == "USER"):
                    provenance = "EXTERNAL"
                converted = {"paper_id": pid, "source_version": paper["source_version"], "page_index": anchor.get("pageIndex"), "quote": anchor.get("quote", ""), "rects": anchor.get("rects", []), "status": "inferred"}
                data = {"id": "legacy_" + hashlib.sha256((folder.name + file.name).encode()).hexdigest()[:32], "paper_id": pid, "author": author, "provenance": provenance, "content": note["content"], "tags": note.get("tags", []), "anchor": converted if anchor else None}
                store.commit({"operation_id": "legacy-note-" + data["id"], "mutations": [{"kind": "note", "expected_revision": 0, "data": data}]})
            if (folder / "chat.json").is_file():
                messages = json.loads((folder / "chat.json").read_text(encoding="utf-8"))
                cid = coach.binding(pid)["conversation_id"]
                for index, message in enumerate(messages):
                    if message.get("role") not in ("user", "assistant") or not message.get("text"):
                        continue
                    coach.save_message({"id": "legacy_" + hashlib.sha256((folder.name + str(index)).encode()).hexdigest()[:32], "paper_id": pid, "conversation_id": cid, "role": message["role"], "content": message["text"], "status": "completed", "created_at": now(), "imported": True, "actions": []})
            archive = store.root / "legacy-archive" / folder.name
            archive.parent.mkdir(exist_ok=True)
            shutil.copytree(folder, archive, ignore=shutil.ignore_patterns("source.pdf", "pages"), dirs_exist_ok=True)
            store.set_setting(marker, {"paper_id": pid, "imported_at": now(), "archive": str(archive)})
        except (OSError, ValueError, KeyError):
            # A malformed legacy record never prevents opening the new workbench.
            # It stays available in the untouched original directory for repair.
            continue
