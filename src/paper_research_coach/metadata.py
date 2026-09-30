"""Resolve bibliographic identity against the PDF, never guess from a filename.

Only identifiers and titles go to Crossref/OpenAlex/arXiv. PDFs stay local.
Credentials live in the OS keyring; remote exceptions are deliberately redacted.
"""

from __future__ import annotations

import html
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

import httpx
from pypdf import PdfReader

from .store import digest


class MetadataPending(ValueError):
    pass


def normalized(value):
    text = unicodedata.normalize("NFKD", html.unescape(value)).casefold()
    return "".join(c for c in text if c.isalnum())


def matches_title(title, paper_title, first_page):
    target = normalized(title)
    page = normalized(first_page)
    if len(target) < 16 or target not in page:
        return False
    # Main title before the abstract, or a filename/title independently matching it.
    header = re.split(r"\babstract\b", first_page, flags=re.I)[0][:2500]
    return (
        target in normalized(header)
        or SequenceMatcher(None, target, normalized(paper_title)).ratio() >= 0.88
    )


def crossref_payload(data):
    item_type = {
        "journal-article": "journalArticle",
        "proceedings-article": "conferencePaper",
        "posted-content": "preprint",
        "book-chapter": "bookSection",
    }.get(data.get("type"))
    if not item_type:
        return None
    creators = []
    for a in data.get("author", []):
        if a.get("family"):
            creators.append(
                dict(
                    creatorType="author",
                    firstName=html.unescape(a.get("given", "")),
                    lastName=html.unescape(
                        a["family"] + (" " + a["suffix"] if a.get("suffix") else "")
                    ),
                )
            )
        elif a.get("name"):
            creators.append(dict(creatorType="author", name=html.unescape(a["name"])))
    if not creators:
        return None
    p = dict(
        itemType=item_type,
        title=html.unescape(data["title"][0]),
        creators=creators,
        DOI=data["DOI"],
        url="https://doi.org/" + data["DOI"],
    )
    container_field = {
        "journalArticle": "publicationTitle",
        "conferencePaper": "proceedingsTitle",
        "bookSection": "bookTitle",
        "preprint": "repository",
    }[item_type]
    if data.get("container-title"):
        p[container_field] = html.unescape(data["container-title"][0])
    dates = data.get("published", {}).get("date-parts", [[]])[0]
    if dates:
        p["date"] = "-".join(
            str(x) if i == 0 else str(x).zfill(2) for i, x in enumerate(dates)
        )
    fields = {"page": "pages"}
    if item_type == "journalArticle":
        fields |= {"volume": "volume", "issue": "issue"}
        if data.get("ISSN"):
            p["ISSN"] = data["ISSN"][0]
    if item_type in ("conferencePaper", "bookSection") and data.get("publisher"):
        p["publisher"] = data["publisher"]
    for src, dest in fields.items():
        if data.get(src) and item_type != "preprint":
            p[dest] = str(data[src])
    return p


class MetadataResolver:
    def __init__(self, store, client=None):
        self.store = store
        self.client = client or httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "PaperResearchCoach/2.0 (bibliographic metadata)"},
        )

    def json(self, url, params=None):
        try:
            r = self.client.get(url, params=params)
            data = r.json() if r.status_code == 200 else {}
            return data if isinstance(data, dict) else {}
        except (httpx.HTTPError, ValueError):
            # Never persist str(error): an OpenAlex request URL contains the key.
            return {}

    def openalex(self, query):
        try:
            import keyring

            key = keyring.get_password("paper-research-coach-metadata", "openalex")
        except Exception:
            key = None
        if not key:
            return []
        data = self.json(
            "https://api.openalex.org/works",
            {"search": query[:500], "per_page": 5, "api_key": key},
        )
        return data.get("results", [])

    def resolve(self, paper, *, force=False):
        setting = "bibliography:" + paper["id"]
        cached = self.store.setting(setting, {})
        version = paper["source_version"]
        if not force and cached.get("source_version") == version:
            if cached.get("status") == "verified":
                return cached
            if time.time() - cached.get("checked_at", 0) < 900:
                raise MetadataPending(cached.get("message", "书目信息待核实"))
        try:
            before = digest(Path(paper["source_path"]))
            reader = PdfReader(paper["source_path"])
            first = reader.pages[0].extract_text() or ""
            second = (
                reader.pages[1].extract_text() or "" if len(reader.pages) > 1 else ""
            )
            # No reference-list mining: the first two pages identify the actual paper.
            dois = list(
                dict.fromkeys(
                    x.rstrip(".,;])}")
                    for x in re.findall(
                        r"10\.\d{4,9}/[^\s<>]+", first + "\n" + second, re.I
                    )
                )
            )[:8]
            if before != version:
                raise MetadataPending("PDF 版本已变化，书目信息等待重新核实")
        except (OSError, ValueError, IndexError):
            raise MetadataPending("无法读取 PDF 首页，书目信息等待核实") from None
        title_hint = paper["title"].replace("_", " ")
        title_meta = str((reader.metadata or {}).get("/Title", ""))
        if (
            title_meta
            and len(title_meta) > 16
            and normalized(title_meta) in normalized(first)
        ):
            title_hint = title_meta
        if paper.get("doi"):
            dois = list(dict.fromkeys([paper["doi"], *dois]))
        payload = None
        sources = []
        for doi in dois:
            data = self.json(
                "https://api.crossref.org/works/" + quote(doi, safe="/")
            ).get("message", {})
            title = (data.get("title") or [""])[0]
            if matches_title(title, title_hint, first):
                payload = crossref_payload(data)
                if payload:
                    sources = ["https://doi.org/" + data["DOI"], "PDF page 1"]
                    break
        if payload is None:
            # Title lookup also recovers a DOI absent from a publisher's first page.
            results = (
                self.json(
                    "https://api.crossref.org/works",
                    {"query.title": title_hint[:500], "rows": 3},
                )
                .get("message", {})
                .get("items", [])
            )
            for data in results:
                if matches_title((data.get("title") or [""])[0], title_hint, first):
                    payload = crossref_payload(data)
                    if payload:
                        sources = ["https://doi.org/" + data["DOI"], "PDF page 1"]
                        break
        if payload is None:
            for data in self.openalex(title_hint):
                if not matches_title(data.get("title") or "", title_hint, first):
                    continue
                authors = data.get("authorships", [])
                names = [
                    a.get("raw_author_name")
                    or a.get("author", {}).get("display_name", "")
                    for a in authors
                ]
                # Index author disambiguation can be wrong. Require every raw name on the PDF.
                if not names or not all(
                    normalized(n) and normalized(n) in normalized(first) for n in names
                ):
                    continue
                location = data.get("primary_location") or {}
                source = location.get("source") or {}
                kind = {
                    "journal": "journalArticle",
                    "conference": "conferencePaper",
                    "repository": "preprint",
                }.get(source.get("type"))
                if not kind:
                    continue
                payload = dict(
                    itemType=kind,
                    title=data["title"],
                    creators=[dict(creatorType="author", name=n) for n in names],
                    date=str(
                        data.get("publication_date")
                        or data.get("publication_year")
                        or ""
                    ),
                )
                doi = (data.get("doi") or "").removeprefix("https://doi.org/")
                if doi:
                    payload.update(DOI=doi, url="https://doi.org/" + doi)
                elif location.get("landing_page_url"):
                    payload["url"] = location["landing_page_url"]
                field = {
                    "journalArticle": "publicationTitle",
                    "conferencePaper": "proceedingsTitle",
                    "preprint": "repository",
                }[kind]
                if source.get("display_name"):
                    payload[field] = source["display_name"]
                if kind == "journalArticle":
                    biblio = data.get("biblio") or {}
                    for field in ("volume", "issue"):
                        if biblio.get(field):
                            payload[field] = biblio[field]
                    if biblio.get("first_page"):
                        payload["pages"] = biblio["first_page"] + (
                            "-" + biblio["last_page"] if biblio.get("last_page") else ""
                        )
                sources = [data["id"], "PDF page 1"]
                break
        if payload is None:
            arxiv = re.search(r"arXiv:\s*(\d{4}\.\d{4,5})(v\d+)?", first)
            if arxiv:
                try:
                    response = self.client.get(
                        "https://export.arxiv.org/api/query",
                        params={"id_list": arxiv[1]},
                    )
                    entry = ElementTree.fromstring(response.content).find(
                        "{http://www.w3.org/2005/Atom}entry"
                    )
                    if entry is not None:
                        ns = {"a": "http://www.w3.org/2005/Atom"}
                        title = " ".join(
                            entry.findtext("a:title", default="", namespaces=ns).split()
                        )
                        names = [
                            a.findtext("a:name", default="", namespaces=ns)
                            for a in entry.findall("a:author", ns)
                        ]
                        if (
                            matches_title(title, title_hint, first)
                            and names
                            and all(normalized(n) in normalized(first) for n in names)
                        ):
                            payload = dict(
                                itemType="preprint",
                                title=title,
                                creators=[
                                    dict(creatorType="author", name=n) for n in names
                                ],
                                repository="arXiv",
                                archiveID=arxiv[1],
                                url="https://arxiv.org/abs/" + arxiv[1],
                                date=entry.findtext(
                                    "a:published", default="", namespaces=ns
                                )[:10],
                            )
                            sources = [payload["url"], "PDF page 1"]
                except (httpx.HTTPError, ElementTree.ParseError):
                    pass
        if digest(Path(paper["source_path"])) != version:
            raise MetadataPending("核实期间 PDF 已变化，请重新扫描")
        result = dict(source_version=version, checked_at=time.time(), sources=sources)
        if payload:
            result.update(status="verified", payload=payload)
            self.store.set_setting(setting, result)
            return result
        message = "作者与正式书目信息待核实；PDF 已保留，可先在 Zotero 检索 PDF 元数据后重新扫描"
        self.store.set_setting(
            setting, result | {"status": "pending", "message": message}
        )
        raise MetadataPending(message)
