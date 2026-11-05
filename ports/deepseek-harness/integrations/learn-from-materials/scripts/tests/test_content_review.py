import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from content_review import SCHEMA, fingerprints, validate, validate_file


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class ContentReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kb = Path(self.temp.name)
        parts = ['八项原则，后四项续下页。\n' + '\n'.join(f'{i}. 原则{i}。' for i in range(1, 5)) + '\n',
                 '\n'.join(f'{i}. 原则{i}。' for i in range(5, 9))]
        self.raw = ''.join(parts)
        (self.kb / 'full_text.txt').write_text(self.raw, encoding='utf-8')
        blocks, start = [], 0
        for i, part in enumerate(parts, 1):
            blocks.append(dict(source_id=f's{i}', start_char=start, end_char=start + len(part),
                               content_sha256=hashlib.sha256(part.encode()).hexdigest()))
            start += len(part)
        write(self.kb / 'source_map.json', blocks)
        self.page = dict(schemaVersion='4.3', meta=dict(mode='overview', learningDepth='systematic',
                         language='zh-CN', pageId='fixture'), frameworks=[],
                         contentUnits=[dict(id='u1', core='八项原则', takeaways=[f'原则{i}' for i in range(1, 9)])],
                         decisionRules=[dict(id='r1', when='完成前三步后', do='加快周转', because='避免加速不必要流程')])
        write(self.kb / 'methods.json', dict(schemaVersion='learn-from-materials/methods-v1',
              libraryId='fixture', title='Fixture', language='zh-CN', status='none', note='Synthetic test only', methods=[]))
        write(self.kb / 'methodology.json', dict(status='not-applicable'))
        self.claims = [dict(id=f'c{i}', unitId='u1', text=f'原则{i}',
                           summaryRefs=[f'unit:u1:takeaway:{i-1}']) for i in range(1, 9)]
        write(self.kb / 'summary-ledger.json', dict(claims=self.claims))
        write(self.kb / 'coverage-audit.json', dict(sourceBlocks=[
            dict(sourceId='s1', status='covered', mappedUnits=['u1'], mappedClaims=[f'c{i}' for i in range(1, 5)]),
            dict(sourceId='s2', status='covered', mappedUnits=['u1'], mappedClaims=[f'c{i}' for i in range(5, 9)])]))
        write(self.kb / 'action-rule-ledger.json', dict(candidates=[dict(targetRuleId='r1', status='retained', unitId='u1')]))
        self.ev = lambda i: [dict(kind='text', sourceId='s1' if i < 5 else 's2', quote=f'{i}. 原则{i}。')]
        self.review = dict(schemaVersion=SCHEMA, pageId='fixture', learningDepth='systematic',
            reviewedInputs=fingerprints(self.page, self.kb),
            unitReviews=[dict(unitId='u1', status='completed', sourceIds=['s1', 's2'],
                              findings='Test fixture spans two physical pages.', evidence=self.ev(1) + self.ev(8))],
            claimReviews=[dict(claimId=f'c{i}', status='supported', evidence=self.ev(i), note='Synthetic source mapping') for i in range(1, 9)],
            ruleReviews=[dict(ruleId='r1', status='supported', evidence=self.ev(1), note='Fixture for provenance, not entailment')],
            enumeratedLists=dict(status='searched', sourceIds=['s1', 's2'], note='Checked list across both pages', lists=[
                dict(id='eight', unitId='u1', expectedCount=8, countNote='Original heading says eight',
                     countEvidence=[dict(kind='text', sourceId='s1', quote='八项原则')],
                     items=[dict(id=f'i{i}', order=i, evidence=self.ev(i), claimIds=[f'c{i}'], disposition='retained', reason='Visible item') for i in range(1, 9)])]))

    def errors(self):
        return validate(self.review, self.page, self.kb)

    def test_complete_cross_page_list(self):
        self.assertEqual(self.errors(), [])

    def test_eight_item_list_reduced_to_six_fails(self):
        self.review['enumeratedLists']['lists'][0]['items'] = self.review['enumeratedLists']['lists'][0]['items'][:6]
        self.assertTrue(any('count mismatch' in x for x in self.errors()))

    def test_original_order_unknown_target_and_missing_quote_fail(self):
        item = self.review['enumeratedLists']['lists'][0]['items'][0]
        item['order'] = 8
        item['claimIds'] = ['invented']
        item['evidence'][0]['quote'] = 'not in source'
        errors = self.errors()
        self.assertTrue(any('order mismatch' in x for x in errors))
        self.assertTrue(any('claim targets' in x for x in errors))
        self.assertTrue(any('quote absent' in x for x in errors))

    def test_changed_summary_or_rule_invalidates_review(self):
        self.page['decisionRules'][0]['when'] = '不需要完成前三步'
        self.assertTrue(any('stale reviewedInputs' in x for x in self.errors()))

    def test_new_hashes_do_not_prove_semantic_truth(self):
        # Explicitly document the boundary instead of claiming false fact detection.
        self.page['decisionRules'][0]['when'] = '错误的条件'
        self.review['reviewedInputs'] = fingerprints(self.page, self.kb)
        self.assertEqual(self.errors(), [])

    def test_incomplete_unit_claim_or_rule_review_fails(self):
        for key in ('unitReviews', 'claimReviews', 'ruleReviews'):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.review)
                changed[key].pop()
                self.assertTrue(any('cover every ID' in x for x in validate(changed, self.page, self.kb)))

    def test_source_scope_and_wrong_unit_evidence_fail(self):
        self.review['unitReviews'][0]['sourceIds'] = ['s1']
        self.review['claimReviews'][0]['evidence'][0]['sourceId'] = 'unknown'
        errors = self.errors()
        self.assertTrue(any('scope mismatch' in x for x in errors))
        self.assertTrue(any('wrong-unit' in x for x in errors))

    def test_excluded_visible_claim_is_not_allowed(self):
        self.review['claimReviews'][0]['status'] = 'excluded'
        self.assertTrue(any('cannot be excluded' in x for x in self.errors()))

    def test_unmapped_or_unknown_claim_cannot_cover_a_page(self):
        audit = json.loads((self.kb / 'coverage-audit.json').read_text())
        for bad in ([], ['fake']):
            audit['sourceBlocks'][0]['mappedClaims'] = bad
            write(self.kb / 'coverage-audit.json', audit)
            self.assertTrue(any('known claims' in x for x in self.errors()))

    def test_malformed_list_records_report_errors_without_crashing(self):
        self.review['enumeratedLists']['lists'][0]['items'] = [None, 'bad', 2, {}, [], True]
        write(self.kb / 'content-review.json', self.review)
        self.assertTrue(validate_file(self.kb / 'content-review.json', self.page, self.kb))

    def test_image_evidence_hash_and_traversal_are_checked(self):
        image = self.kb / 'page.png'
        image.write_bytes(b'fixture image')
        ev = self.review['claimReviews'][0]['evidence'][0]
        ev.update(kind='visual', artifact='page.png', sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  quote='Manually transcribed image-only evidence', note='Fixture transcription')
        self.assertEqual(self.errors(), [])
        image.write_bytes(b'changed')
        self.assertTrue(any('visual hash mismatch' in x for x in self.errors()))
        ev['artifact'] = '../outside.png'
        self.assertTrue(any('unsafe visual artifact' in x for x in self.errors()))

    def test_stale_raw_source_hash_fails(self):
        (self.kb / 'full_text.txt').write_text('X' + self.raw[1:], encoding='utf-8')
        self.assertTrue(any('source hash mismatch' in x for x in self.errors()))

    def test_publication_path_does_not_invalidate_review(self):
        self.page['meta']['knowledgeBase'] = 'new-delivery.learnkb/INDEX.md'
        self.assertEqual(self.errors(), [])


if __name__ == '__main__':
    unittest.main()
