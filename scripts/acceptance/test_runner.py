"""Regression tests for honest checklist reporting and DOCX parsing; stdlib only."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location('runner', Path(__file__).with_name('run_acceptance.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class AcceptanceRunnerTests(unittest.TestCase):
    def test_actual_document_has_all_45_ids_and_original_prompts(self):
        source = runner.read_checklist(runner.DEFAULT_DOCX)
        self.assertEqual({c['id'] for c in source['cases']}, set(runner.REVIEW))
        self.assertEqual(len(source['cases']), 45)
        self.assertIn('截至财年', source['prompts']['A'])
        self.assertIn('金额为百万美元', source['prompts']['A'])
        self.assertIn('等待我确认', source['prompts']['W'])
        self.assertNotIn('6,737,218,987.11', source['prompts']['W'])

    def test_duplicate_docx_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'duplicate.docx'
            with ZipFile(file, 'w') as archive:
                archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' +
                                 '<w:p><w:r><w:t>A01 · 环境</w:t></w:r></w:p>' * 2 + '</w:body></w:document>')
            with self.assertRaisesRegex(ValueError, '重复'):
                runner.read_checklist(file)

    def test_partial_coverage_never_becomes_full_acceptance(self):
        source = {'cases': [{'id': 'B10', 'title': '视觉', 'requirements': []}], 'path': 'fixture', 'sha256': 'test'}
        report = runner.aggregate(source, [{'ids': ['B10'], 'name': '截图', 'status': 'passed'}], Path('.'), [])
        self.assertEqual(report['cases'][0]['automatic_status'], '通过')
        self.assertEqual(report['cases'][0]['acceptance_status'], '待人工复核')
        self.assertEqual(runner.report_exit(report, True, 0), 2)

    def test_first_failure_is_not_overwritten_by_later_success(self):
        source = {'cases': [{'id': 'A01', 'title': '环境', 'requirements': []}]}
        checks = [{'ids': ['A01'], 'status': status} for status in ['failed', 'passed']]
        report = runner.aggregate(source, checks, Path('.'), [])
        self.assertEqual(report['counts'], {'失败': 1})
        self.assertEqual(runner.report_exit(report, False, 0), 1)

    def test_unexecuted_and_unknown_cases_are_not_passes(self):
        source = {'cases': [{'id': x, 'title': x, 'requirements': []} for x in ['C01', 'Z99']]}
        report = runner.aggregate(source, [], Path('.'), [])
        self.assertEqual(report['counts'], {'未覆盖': 2})
        self.assertIn('没有自动化适配器', report['cases'][1]['remaining'])

    def test_new_docx_letter_group_is_retained_as_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'future.docx'
            with ZipFile(file, 'w') as archive:
                archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Z99 · 新增验收</w:t></w:r></w:p></w:body></w:document>')
            source = runner.read_checklist(file)
            self.assertEqual(source['cases'][0]['id'], 'Z99')
            self.assertEqual(runner.aggregate(source, [], Path(directory), [])['counts'], {'未覆盖': 1})

    def test_html_report_escapes_untrusted_errors_and_retains_evidence(self):
        source = {'cases': [{'id': 'A01', 'title': '环境', 'requirements': ['操作：打开页面']}], 'path': 'fixture', 'sha256': 'test'}
        checks = [{'ids': ['A01'], 'name': '<script>bad</script>', 'status': 'failed', 'message': '<img onerror="bad">', 'artifacts': ['api/a.json']}]
        with tempfile.TemporaryDirectory() as directory:
            report = runner.aggregate(source, checks, Path(directory), [])
            runner.write_reports(report, Path(directory))
            markup = (Path(directory) / 'report.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>bad', markup)
            self.assertIn('href="api/a.json"', markup)
            self.assertEqual(len(json.loads((Path(directory) / 'report.json').read_text(encoding='utf-8'))['cases']), 1)


if __name__ == '__main__':
    unittest.main()
