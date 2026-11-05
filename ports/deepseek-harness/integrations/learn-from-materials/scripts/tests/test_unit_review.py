"""Mutation tests for scoped review freshness and final integration gates.

The self-authored synthetic fixture's existing reviewed claims are reused here;
test construction is not a production helper for generating review judgments.
"""
import copy
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from authoring_fixture import fixture
from content_review import validate, validate_file
from unit_records import assemble
from unit_review import (GLOBAL_CHECKS, GLOBAL_SCHEMA, UNIT_SCHEMA, assemble_review,
                         cross_unit_relations, global_snapshot, snapshot, validate_global, validate_unit)
from workflow_io import json_text, read_json, write_changed


class UnitReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kb, self.project, self.paths, self.original = fixture(self.root, SCRIPTS.parent)
        self.old_review = read_json(self.kb / 'content-review.json')
        self.action = read_json(self.kb / 'action-rule-ledger.json')
        # Explicitly retain the synthetic fixture's reviewed source dispositions.
        for path in self.paths:
            record = read_json(path)
            record['ruleReview'] = next(copy.deepcopy(r) for r in self.action['units'] if r['unitId'] == record['unit']['id'])
            write_changed(path, json_text(record))
        project = read_json(self.project)
        project['coverage']['finalCheck'] = read_json(self.kb / 'coverage-audit.json')['finalCheck']
        project['summaryCheck'] = read_json(self.kb / 'summary-ledger.json')['finalCheck']
        write_changed(self.project, json_text(project))
        self.records = [read_json(p) for p in self.paths]
        self.reviews = [self.local_review(record) for record in self.records]

    def local_review(self, record):
        uid = record['unit']['id']; inputs = snapshot(record, self.kb)
        claims = {r['id'] for r in record['claims']}
        rules = {r['id'] for r in record['decisionRules']}
        enumerated = copy.deepcopy(self.old_review['enumeratedLists'])
        enumerated['sourceIds'] = [r['sourceId'] for r in record['sources'] if r['status'] == 'covered']
        enumerated['lists'] = [r for r in enumerated['lists'] if r['unitId'] == uid]
        return dict(schemaVersion=UNIT_SCHEMA, unitId=uid, executionMode='sequential',
                    authorId='fixture-writer-' + uid, reviewerId='fixture-reviewer-' + uid,
                    reviewedInputs=inputs,
                    sourceFirst=dict(status='completed', sourceIds=sorted(inputs['sources']),
                                     note='Synthetic fixture: original page passages were independently read before this comparison.'),
                    unitReview=next(copy.deepcopy(r) for r in self.old_review['unitReviews'] if r['unitId'] == uid),
                    claimReviews=[copy.deepcopy(r) for r in self.old_review['claimReviews'] if r['claimId'] in claims],
                    ruleReviews=[copy.deepcopy(r) for r in self.old_review['ruleReviews'] if r['ruleId'] in rules],
                    enumeratedLists=enumerated)

    def integration(self):
        target = self.root / 'page.json'; assemble(self.project, self.kb, target)
        page = read_json(target)
        relations = cross_unit_relations(page, self.kb)
        global_review = dict(schemaVersion=GLOBAL_SCHEMA, reviewerId='fixture-integrator', status='completed',
            reviewedInputs=global_snapshot(page, self.kb, self.reviews),
            checks={key: dict(status='completed', note='Synthetic integration scope checked: ' + key) for key in GLOBAL_CHECKS},
            relationReviews=[])
        for ident, actual in relations.items():
            # The existing source-first fixture contains these actual relations.
            local = next(r for r in self.reviews if r['unitId'] in actual['unitIds'])
            global_review['relationReviews'].append(dict(relationId=ident, status='supported',
                evidenceKind=actual['relation']['evidence'],
                note='Fixture provenance test: check this actual final cross-unit relation; not a semantic entailment proof.',
                evidence=copy.deepcopy(local['unitReview']['evidence'])))
        return page, global_review

    def test_local_review_does_not_require_full_assembly(self):
        for name in ('coverage-audit.json', 'summary-ledger.json', 'action-rule-ledger.json', 'methodology.json'):
            (self.kb / name).unlink()
        self.assertFalse((self.root / 'page.json').exists())
        self.assertEqual(validate_unit(self.reviews[0], self.records[0], self.kb), [])

    def test_historical_parallel_reviewer_must_differ_from_author(self):
        review = copy.deepcopy(self.reviews[0]); review['executionMode'] = 'parallel'; review['reviewerId'] = review['authorId']
        self.assertTrue(any('differ from author' in e for e in validate_unit(review, self.records[0], self.kb)))
        review['executionMode'] = 'sequential'
        self.assertEqual(validate_unit(review, self.records[0], self.kb), [])

    def test_assigned_and_method_dependent_source_first_scope_is_exact(self):
        review = copy.deepcopy(self.reviews[0]); review['sourceFirst']['sourceIds'] = []
        self.assertTrue(any('source-first' in e for e in validate_unit(review, self.records[0], self.kb)))

    def test_prose_entities_focus_and_rule_candidates_are_bound(self):
        for group in ('sections', 'frameworks', 'glossary', 'focusAreas', 'ruleCandidates'):
            with self.subTest(group=group):
                record = copy.deepcopy(self.records[0])
                if group == 'sections': record[group]['workedExamples'][0] += ' Changed explanation.'
                elif group == 'frameworks': record[group][0]['oneLine'] += ' Changed framework.'
                elif group == 'glossary': record[group][0]['definition'] += ' Changed definition.'
                elif group == 'focusAreas': record[group][0]['title'] += ' Changed focus.'
                else: record[group][0]['reason'] += ' Changed disposition reasoning.'
                errors = validate_unit(self.reviews[0], record, self.kb)
                self.assertTrue(any('stale local snapshot' in e for e in errors), errors)

    def test_unrelated_source_change_does_not_invalidate_local_review(self):
        own = set(self.reviews[0]['reviewedInputs']['sources'])
        blocks = read_json(self.kb / 'source_map.json')
        block = next(b for b in blocks if b['source_id'] not in own)
        raw = (self.kb / 'full_text.txt').read_text(encoding='utf-8')
        index = block['end_char'] - 1
        raw = raw[:index] + ('X' if raw[index] != 'X' else 'Y') + raw[index+1:]
        (self.kb / 'full_text.txt').write_text(raw, encoding='utf-8')
        block['content_sha256'] = hashlib.sha256(raw[block['start_char']:block['end_char']].encode()).hexdigest()
        write_changed(self.kb / 'source_map.json', json_text(blocks))
        self.assertEqual(validate_unit(self.reviews[0], self.records[0], self.kb), [])

    def test_offset_only_change_preserves_local_actual_passage_identity(self):
        blocks = read_json(self.kb / 'source_map.json')
        raw = (self.kb / 'full_text.txt').read_text(encoding='utf-8')
        (self.kb / 'full_text.txt').write_text('unrelated header\n' + raw, encoding='utf-8')
        for block in blocks:
            block['start_char'] += len('unrelated header\n'); block['end_char'] += len('unrelated header\n')
        write_changed(self.kb / 'source_map.json', json_text(blocks))
        self.assertEqual(validate_unit(self.reviews[0], self.records[0], self.kb), [])

    def test_local_actual_source_change_invalidates_review_even_with_valid_map_hash(self):
        blocks = read_json(self.kb / 'source_map.json'); sid = self.records[0]['sources'][0]['sourceId']
        block = next(b for b in blocks if b['source_id'] == sid)
        raw = (self.kb / 'full_text.txt').read_text(encoding='utf-8')
        index = block['end_char'] - 1
        raw = raw[:index] + ('X' if raw[index] != 'X' else 'Y') + raw[index+1:]
        (self.kb / 'full_text.txt').write_text(raw, encoding='utf-8')
        block['content_sha256'] = hashlib.sha256(raw[block['start_char']:block['end_char']].encode()).hexdigest()
        write_changed(self.kb / 'source_map.json', json_text(blocks))
        self.assertTrue(any('stale local snapshot' in e for e in validate_unit(self.reviews[0], self.records[0], self.kb)))

    def test_method_changes_are_scoped_and_additions_invalidate_associations(self):
        library = read_json(self.kb / 'methods.json')
        own_ids = {r['id'] for group in ('frameworks', 'decisionRules') for r in self.records[0][group]}
        unrelated = next(c for c in library['methods'] if c['id'] not in own_ids)
        unrelated['summary'] += ' Unrelated change.'
        write_changed(self.kb / 'methods.json', json_text(library))
        self.assertEqual(validate_unit(self.reviews[0], self.records[0], self.kb), [])
        linked = next(c for c in library['methods'] if c['id'] in own_ids)
        linked['limitations'].append('Changed material limitation.')
        write_changed(self.kb / 'methods.json', json_text(library))
        self.assertTrue(any('stale local snapshot' in e for e in validate_unit(self.reviews[0], self.records[0], self.kb)))
        (self.kb / 'methods.json').unlink()
        no_method_review = self.local_review(self.records[0])
        self.assertEqual(validate_unit(no_method_review, self.records[0], self.kb), [])
        write_changed(self.kb / 'methods.json', json_text(library))
        self.assertTrue(any('stale local snapshot' in e for e in validate_unit(no_method_review, self.records[0], self.kb)))

    def test_claim_rule_and_closed_list_gates_remain_required(self):
        for key in ('claimReviews', 'ruleReviews'):
            review = copy.deepcopy(self.reviews[0]); review[key].pop()
            self.assertTrue(any('cover every ID' in e for e in validate_unit(review, self.records[0], self.kb)))
        review = copy.deepcopy(self.reviews[0]); review['enumeratedLists']['sourceIds'] = []
        self.assertTrue(any('all covered sources' in e for e in validate_unit(review, self.records[0], self.kb)))
        review = copy.deepcopy(self.reviews[0]); review['enumeratedLists']['lists'][0]['items'] = []
        self.assertTrue(any('item count mismatch' in e for e in validate_unit(review, self.records[0], self.kb)))

    def test_wrong_unit_quote_and_visual_traversal_still_fail(self):
        review = copy.deepcopy(self.reviews[0])
        review['claimReviews'][0]['evidence'] = copy.deepcopy(self.reviews[1]['claimReviews'][0]['evidence'])
        self.assertTrue(any('wrong-unit' in e for e in validate_unit(review, self.records[0], self.kb)))
        review = copy.deepcopy(self.reviews[0])
        review['claimReviews'][0]['evidence'][0].update(kind='visual', artifact='../outside.png',
                                                       sha256='not-a-real-hash', note='Must reject traversal')
        self.assertTrue(any('unsafe visual artifact' in e for e in validate_unit(review, self.records[0], self.kb)))

    def test_complete_v2_dispatch_and_publication_destination_change(self):
        page, global_review = self.integration()
        complete = assemble_review(page, self.kb, self.reviews, global_review)
        self.assertEqual(validate(complete, page, self.kb), [])
        page['meta']['knowledgeBase'] = 'different-destination.learnkb/INDEX.md'
        self.assertEqual(validate(complete, page, self.kb), [])
        write_changed(self.kb / 'content-review.json', json_text(complete))
        self.assertEqual(validate_file(self.kb / 'content-review.json', page, self.kb), [])

    def test_global_change_preserves_unchanged_local_reviews(self):
        page, global_review = self.integration()
        page['relationships'][-1]['explanation'] += ' Changed integration explanation.'
        errors = validate_global(global_review, page, self.kb, self.reviews)
        self.assertTrue(any('stale global snapshot' in e for e in errors))
        for review, record in zip(self.reviews, self.records):
            self.assertEqual(validate_unit(review, record, self.kb), [])

    def test_methodology_or_review_record_change_invalidates_only_global(self):
        page, global_review = self.integration()
        methodology = read_json(self.kb / 'methodology.json')
        methodology['edges'][0]['why'] += ' Changed integration rationale.'
        write_changed(self.kb / 'methodology.json', json_text(methodology))
        self.assertTrue(any('stale global snapshot' in e for e in validate_global(global_review, page, self.kb, self.reviews)))
        self.assertEqual(validate_unit(self.reviews[0], self.records[0], self.kb), [])
        page, global_review = self.integration()
        self.reviews[0]['unitReview']['findings'] += ' More precise review finding.'
        self.assertTrue(any('stale global snapshot' in e for e in validate_global(global_review, page, self.kb, self.reviews)))

    def test_finalize_accepts_v2_and_rejects_stale_local_prose(self):
        from finalize import finalize
        page, global_review = self.integration()
        complete = assemble_review(page, self.kb, self.reviews, global_review)
        write_changed(self.kb / 'content-review.json', json_text(complete))
        delivery = finalize(self.root / 'page.json', self.kb, self.root / 'delivery', 'v2-fixture', compatibility='1.03')
        self.assertTrue(Path(delivery['manifest']).is_file())
        record_path = self.kb / 'unit-records/u01.json'
        record = read_json(record_path); record['sections']['workedExamples'][0] += ' Unreviewed addition.'
        write_changed(record_path, json_text(record))
        with self.assertRaisesRegex(ValueError, 'stale local snapshot'):
            finalize(self.root / 'page.json', self.kb, self.root / 'rejected', 'stale-fixture', compatibility='1.03')
        self.assertFalse((self.root / 'rejected/stale-fixture.html').exists())

    def test_missing_reversed_and_reattributed_cross_unit_relations_fail(self):
        page, global_review = self.integration()
        self.assertTrue(global_review['relationReviews'])
        changed = copy.deepcopy(global_review); changed['relationReviews'].pop()
        self.assertTrue(any('every actual cross-unit relation' in e for e in validate_global(changed, page, self.kb, self.reviews)))
        changed = copy.deepcopy(global_review)
        row = changed['relationReviews'][0]
        row['evidenceKind'] = 'inference' if row['evidenceKind'] == 'material' else 'material'
        self.assertTrue(any('attribution mismatch' in e for e in validate_global(changed, page, self.kb, self.reviews)))
        edge = next(e for e in page['relationships'] if 'page:' + e['id'] in cross_unit_relations(page, self.kb))
        edge['from'], edge['to'] = edge['to'], edge['from']
        self.assertTrue(any('stale global snapshot' in e for e in validate_global(global_review, page, self.kb, self.reviews)))

    def test_global_hash_refresh_cannot_bypass_final_record_binding(self):
        page, global_review = self.integration()
        for key, field in (('frameworks', 'oneLine'), ('glossary', 'definition')):
            changed_page = copy.deepcopy(page); changed_page[key][0][field] += ' Unreviewed change.'
            changed_global = copy.deepcopy(global_review)
            changed_global['reviewedInputs'] = global_snapshot(changed_page, self.kb, self.reviews)
            with self.assertRaisesRegex(ValueError, 'differs from reviewed unit records'):
                assemble_review(changed_page, self.kb, self.reviews, changed_global)

    def test_global_hash_refresh_cannot_bypass_local_staleness(self):
        page, global_review = self.integration()
        record_path = self.kb / 'unit-records/u01.json'
        record = read_json(record_path); record['sections']['workedExamples'][0] += ' Changed full prose.'
        write_changed(record_path, json_text(record))
        global_review['reviewedInputs'] = global_snapshot(page, self.kb, self.reviews)
        with self.assertRaisesRegex(ValueError, 'stale local snapshot'):
            assemble_review(page, self.kb, self.reviews, global_review)

    def test_missing_global_check_or_unit_review_fails_closed(self):
        page, global_review = self.integration()
        global_review['checks'].pop('methodology')
        with self.assertRaisesRegex(ValueError, 'global check categories'):
            assemble_review(page, self.kb, self.reviews, global_review)
        page, global_review = self.integration()
        with self.assertRaisesRegex(ValueError, 'every final unit'):
            assemble_review(page, self.kb, self.reviews[:-1], global_review)

    def test_snapshot_cli_emits_only_dependencies(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'unit_review.py'), 'snapshot',
                                 '--unit-record', str(self.paths[0]), '--knowledge-base', str(self.kb)],
                                text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        actual = json.loads(result.stdout)
        self.assertEqual(actual, snapshot(self.records[0], self.kb))
        self.assertEqual(set(actual), {'record', 'sources', 'methods'})


if __name__ == '__main__':
    unittest.main()
