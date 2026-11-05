"""Publish a complete offline learning bundle from reviewed canonical data.

Usage: python scripts/finalize.py page.json --knowledge-base topic.learnkb
       --output-dir delivery --name learning
New output names are required; source knowledge bases are never overwritten.
"""
import argparse
import hashlib
import json
import shutil
import time
import uuid
import zipfile
from pathlib import Path

from source_presentation import validate_labels
from delivery import check_canonical, export_readable, verify_readable
from methods import bind, read, validate_library
from methodology import validate as validate_model, markdown
from render_page import render, validate as validate_page
from verify_coverage import verify
from verify_static import verify as verify_static
from verify_relations import check_page as check_relations
from action_rules import load_and_validate
from content_review import validate_file as validate_content_review
from workflow_io import skill_metadata


def publish_move(source, destination, stage, output_dir):
    """Move a validated artifact within the delivery directory, without overwrite.

    Windows scanners can briefly lock a newly written directory. Retry only
    that reported lock/access condition, at most five attempts over one second.
    """
    source, destination = Path(source), Path(destination)
    if not source.resolve().is_relative_to(Path(stage).resolve()) or not destination.resolve().is_relative_to(Path(output_dir).resolve()):
        raise ValueError('Delivery move escaped its staging or output directory')
    for attempt in range(5):
        if destination.exists():
            raise ValueError('A delivery target already exists; choose another name.')
        try:
            source.rename(destination)
            return
        except PermissionError as error:
            if getattr(error, 'winerror', None) not in (5, 32) or attempt == 4:
                raise
            time.sleep(.1 * (attempt + 1))


def finalize(page_file, kb, output_dir, name, legacy_rule_ledger=False, compatibility=None):
    kb, out = Path(kb).resolve(), Path(output_dir).resolve()
    if not name or Path(name).name != name or any(c in name for c in '/\\:') or name in ('.', '..'):
        raise ValueError('name must be a filename stem, not a path')
    page = read(Path(page_file))
    if compatibility not in (None, '1.03'):
        raise ValueError('Unsupported compatibility contract; use explicit 1.03 for existing deliveries')
    if legacy_rule_ledger and compatibility:
        raise ValueError('Choose one explicit compatibility route, not both')
    records = [read(p) for p in sorted((kb / 'unit-records').glob('*.json'))]
    modern_records = any(r.get('schemaVersion') == 'learn-from-materials/unit-record-v2' for r in records)
    has_relations = (kb / 'relation-ledger.json').is_file()
    if (legacy_rule_ledger or compatibility) and (modern_records or has_relations):
        raise ValueError('New relation/unit artifacts cannot fall back to an older publication contract')
    if page['meta']['mode'] != 'overview':
        raise ValueError('finalize.py currently accepts overview pages; topic/unit pages use render_page.py')
    # Fail before publishing anything if either canonical file is missing.
    library = validate_library(read(kb / 'methods.json'), kb)
    model = read(kb / 'methodology.json')
    page = bind(page, library)
    validate_model(model, page, kb)
    page['methodology'] = model
    validate_page(page)
    label_errors = []
    validate_labels(page, label_errors, require_complete=not legacy_rule_ledger)
    if label_errors:
        raise ValueError("Source presentation validation failed: " + "; ".join(label_errors))
    exports = check_canonical(page, kb)
    ledger = None
    content_review = None
    relations = None
    if page['meta']['learningDepth'] == 'systematic' and not legacy_rule_ledger:
        ledger = load_and_validate(page, kb)
        review_path = kb / 'content-review.json'
        if not review_path.is_file():
            raise ValueError('content-review.json is required for new systematic deliveries')
        review_errors = validate_content_review(review_path, page, kb)
        if review_errors:
            raise ValueError('Content review validation failed: ' + '; '.join(review_errors))
        content_review = json.loads(review_path.read_text(encoding='utf-8'))
        if compatibility is None:
            from relation_ledger import load_and_validate as validate_relation_inventory
            relations = validate_relation_inventory(page, kb)
            if not records or not all(r.get('schemaVersion') == 'learn-from-materials/unit-record-v2' for r in records):
                raise ValueError('New 1.04 systematic delivery requires unit-record-v2 for every unit')
            if content_review.get('schemaVersion') != 'learn-from-materials/content-review-v3':
                raise ValueError('New 1.04 systematic delivery requires content-review-v3 and both source-first structure review passes')
            isolated = {r['frameworkId'] for r in relations['isolatedFrameworks']}
            if isolated != {r['frameworkId'] for r in ledger['independentFrameworks']}:
                raise ValueError('Action-rule and relation ledgers disagree on isolated frameworks')
    target_kb = out / (name + '.learnkb')
    if target_kb == kb or target_kb.is_relative_to(kb):
        raise ValueError('Choose an output directory outside the source knowledge base')
    targets = {k: out / (name + suffix) for k, suffix in [('page','.page.json'),('html','.html'),('markdown','.md'),('methodologyExport','.methodology.md'),('manifest','.delivery.json'),('archive','.zip')]}
    if any(p.exists() for p in [target_kb, *targets.values()]):
        raise ValueError('A delivery target already exists. Choose a new name/directory to preserve the prior output.')
    relation_report = check_relations(page, ledger=ledger, allow_empty=legacy_rule_ledger)
    if relation_report.errors:
        raise ValueError('Relationship graph validation failed: ' + '; '.join(relation_report.errors))
    out.mkdir(parents=True, exist_ok=True)
    stage = out / ('.' + name + '-staging-' + uuid.uuid4().hex)
    stage.mkdir()
    staged_kb = stage / target_kb.name
    staged = {key: stage / path.name for key, path in targets.items()}
    published = []
    try:
        # Extraction caches are rebuildable working data, not provenance.
        # Their digest filenames plus a staging path can also exceed Windows
        # path limits. Keep them in the source KB, outside the delivery ZIP.
        shutil.copytree(kb, staged_kb, ignore=shutil.ignore_patterns('__pycache__','*.pyc','.extraction-cache','.pipeline'))
        export_readable(staged_kb, exports)
        staged['methodologyExport'].write_bytes((staged_kb / 'methodology.md').read_bytes())
        page['meta']['knowledgeBase'] = target_kb.name + '/INDEX.md'
        staged['page'].write_text(json.dumps(page,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        errors = verify(staged['page'], staged_kb,
                        require_heading_index=page['meta']['learningDepth'] == 'systematic' and not legacy_rule_ledger,
                        require_claim_mapping=page['meta']['learningDepth'] == 'systematic' and not legacy_rule_ledger)
        if errors:
            raise ValueError('Coverage validation failed: ' + '; '.join(errors))
        render(page, staged['html'], staged['markdown'])
        with staged['markdown'].open('a',encoding='utf-8') as f:
            f.write('\n' + markdown(model, source_labels=page.get('sourceLabels')))
        errors, warnings, _ = verify_static(staged['html'])
        if errors:
            raise ValueError('Static validation failed: ' + '; '.join(errors))
        verify_readable(staged_kb, exports)
        files = [staged['page'],staged['html'],staged['markdown'],staged['methodologyExport'],*sorted(p for p in staged_kb.rglob('*') if p.is_file())]
        heading_file = staged_kb / 'source-heading-index.json'
        heading_entries = json.loads(heading_file.read_text(encoding='utf-8')).get('entries', []) if heading_file.is_file() else []
        visual_heading_count = sum(item.get('verification') == 'visual' for item in heading_entries if isinstance(item, dict))
        # Content review cannot attest a render that does not yet exist. Browser
        # geometry is recorded separately against this exact HTML hash.
        en = page['meta'].get('language') == 'en'
        skill = skill_metadata()
        manifest = {'skillVersion':skill['version'],'skillRevision':skill['revision'],'status':'static-only','pageId':page['meta']['pageId'],
            'checks':['canonical-evidence','coverage','snapshot-equality','derived-files','static-html','relations'] + (['action-rule-ledger','content-review'] if ledger else []) + (['relation-candidates','structure-reviews'] if relations else []) + (['pdf-heading-index'] if (staged_kb/'source-heading-index.json').is_file() else []),
            'relations':relation_report.as_dict(),
            'headingIndex':{'textEntries':len(heading_entries)-visual_heading_count,'visualEntries':visual_heading_count},
            'contentValidation':'passed',
            'semanticReview':'recorded-not-machine-proven' if content_review else 'not-recorded',
            'relationReviewContract':'1.04' if relations else ('1.03-compatibility-not-upgraded' if compatibility else ('legacy-not-run' if legacy_rule_ledger else 'not-applicable')),
            'relationInventory':{'candidates':len(relations['candidates']),'scopes':len(relations['scopes']),'integratorId':relations['integratorId']} if relations else None,
            'layoutCheck':'not-run','visualReview':'not-run',
            'methodologyExport':targets['methodologyExport'].name,
            'warnings':[*warnings,*relation_report.warnings] + (['PDF headings include manual visual evidence; their text was not machine-verified' if en else 'PDF 标题索引含人工视觉核验条目，程序未验证其文字'] if visual_heading_count else []) + ['Browser visual checks were not run; this delivery passed static validation only' if en else '视觉检查未运行；此交付仅完成静态校验'],
            'files':[{'path':p.relative_to(stage).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
        staged['manifest'].write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with zipfile.ZipFile(staged['archive'],'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for p in [*files,staged['manifest']]:archive.write(p,p.relative_to(stage))
        with zipfile.ZipFile(staged['archive']) as archive:
            if archive.testzip() is not None:raise ValueError('Archive integrity check failed')
        if any(p.exists() for p in [target_kb, *targets.values()]):
            raise ValueError('A delivery target appeared during validation; choose another name.')
        for source, destination in [(staged_kb, target_kb), *[(staged[key], path) for key, path in targets.items()]]:
            publish_move(source, destination, stage, out)
            published.append(destination)
    except Exception:
        for path in reversed(published):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    result={k:str(v) for k,v in targets.items()}
    result['methodology']=str(target_kb/'methodology.md')
    result['methodologyData']=str(target_kb/'methodology.json')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('page',type=Path);p.add_argument('--knowledge-base',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--name',required=True)
    p.add_argument('--legacy-rule-ledger',action='store_true',help='Only for re-delivering an existing overview created before the rule ledger')
    p.add_argument('--compatibility',choices=('1.03',),help='Explicit existing 1.03 re-delivery; does not claim the 1.04 relation review contract')
    a=p.parse_args()
    try:print(json.dumps(finalize(a.page,a.knowledge_base,a.output_dir,a.name,a.legacy_rule_ledger,a.compatibility),ensure_ascii=False,indent=2))
    except (OSError,ValueError,KeyError,TypeError) as exc:p.exit(2,str(exc)+'\n')


if __name__ == '__main__':
    from cli_output import configure_output
    configure_output()
    main()
