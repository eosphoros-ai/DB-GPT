#!/usr/bin/env python3
"""Run the v9.1 DOCX acceptance checklist and keep evidence per checklist ID.

The launcher uses only Python's standard library. Browser dependencies come from
web/node_modules; no global installation, server restart, or historical evidence
reuse is performed. See README.md beside this file.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCX = ROOT / 'output/manual-acceptance/DB-GPT-v9.1-手动验收清单-更新版-20260907.docx'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

# These are remaining acceptance obligations, not assertions silently marked passed.
REVIEW = {
    'A01': '', 'A02': '', 'A03': '副本由真实 API 创建；列表中的复制菜单交互需人工复核。',
    'B01': '核对页面缩写、千分位与单位表达。', 'B02': '核对趋势图的轴文字和顺序。',
    'B03': '复核前两家门店的实际悬浮提示。', 'B04': '复核单位说明与财年显示。',
    'B05': '实际三系列图例、柱体和每个系列的悬浮提示需人工复核；不是模型首次生成。',
    'B06': '边界检查不等于所有轴标签可读；面板展开、图表加高与表内滚动需复核。',
    'B07': '标签完整性、遮挡、所有大小值提示与缩写一致性需逐图复核。',
    'B08': '核对深浅主题对比度、长图例悬浮与自定义字号。',
    'B09': '自动比较真实表头/表体几何边界；还需复核金额列语义与深浅模式。',
    'B10': '绘图区高度只记录实测值，不用未经设计确认的像素阈值代替可读性判断。',
    'B11': '顶部截图与溢出探测不替代文字遮挡、换行与操作可点击性的逐项复核。',
    'C01': '真实模型只在 --live-model 下运行；规划的业务准确性需审阅。',
    'C02': '真实模型只在 --live-model 下运行；复核修改后的同一规划、数据源和业务范围。',
    'C03': '真实模型只在 --live-model 下运行；保留首次尝试，不自动重试。',
    'C04': '真实模型只在 --live-model 下运行；任务恢复与列表状态有自动断言。',
    'C05': '真实模型只在 --live-model 下运行；Apple 五类组件及发布绑定还需业务复核。',
    'D01': '', 'D02': 'API 验证临时表格/长表 SQL；交互切换时 G2 中间态仍需人工复核。',
    'D03': '自动验证拖拽、缩放、撤销重做、保存重载；人工复核视觉位置和重叠。',
    'D04': 'AI 单条批注的真实模型提案及确认应用未自动执行；--regression 提供独立工程回归。',
    'D05': 'AI 批量批注的真实模型提案及放弃未自动执行；--regression 提供独立工程回归。',
    'E01': '依赖本轮 C05；自动检查财年参数和结果，页面交互仍需复核。',
    'E02': '依赖本轮 C05；自动检查产品参数和组件影响，页面交互仍需复核。',
    'F01': '真实发布 API 与公开页有断言；编辑器发布弹窗需人工复核。',
    'F02': '匿名只读页面有断言；带筛选的匿名发布需另行复核。',
    'F03': '自动比较 V1/V2/固定最新的业务快照；人工复核三个页面的视觉一致性。',
    'F04': '真实 API 恢复为新修订；历史面板的只读预览交互需人工复核。',
    'F05': 'ZIP 内容逐文件校验；工程文件抽屉中的预览需人工复核。',
    'F06': '自动截图标记为 evidence；8 张齐全不代表 B05–B11 业务和视觉全部通过。',
    'F07': '只撤销本轮副本的历史分享；失效提示的文案需人工复核。',
    'R01': '真实失败 SQL 在保存阶段被拒绝且未新增发布；发布按钮交互、UI 错误卡仍需复核。',
    'R02': '真实空查询有断言；复核页面空状态或过期提示不伪装成新值。',
    'R03': '', 'R04': '自动验证真实并发写入冲突；两标签页冲突处理交互需人工复核。',
    'X01': '自然模型故障只在实际发生时覆盖；SSE 回放单列工程证据。',
    'X02': '自然业务追问及答案归属需实际事件；受控回放不等于真实模型追问。',
    'X03': '自动校验本批 CSV 基准与真实上传预览；模型三表分析结果需人工复核。',
    'X04': '真实服务端类型拒绝有断言；浏览器上传队列断网重试需人工复核。',
    'X05': '只在 --schedule 下创建并暂停本轮副本的每分钟刷新计划。',
    'X06': '真实异常规则数值有断言；AI 只读解释与修订不变需人工复核。',
    'X07': '390 宽度边界与截图有断言；键盘焦点、弹窗及阅读顺序需人工复核。',
    'X08': '只在 --theme-matrix 下生成 32 个真实发布组合；每格视觉结论需人工复核。',
}


def normalize_path(value: str) -> Path:
    # Accept the /D:/... form copied from Codex's file link.
    return Path(re.sub(r'^/([A-Za-z]:[/\\])', r'\1', value)).expanduser().resolve()


def read_checklist(path: Path) -> dict:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
        paragraphs = [''.join(t.text or '' for t in p.findall('.//w:t', NS)).strip()
                      for p in root.findall('.//w:p', NS)]
    cases = []
    current = None
    for paragraph in paragraphs:
        match = re.fullmatch(r'([A-Z]\d{2})\s*[·．.]\s*(.+)', paragraph)
        if match:
            if any(c['id'] == match[1] for c in cases):
                raise ValueError(f'清单编号重复：{match[1]}')
            current = {'id': match[1], 'title': match[2], 'requirements': []}
            cases.append(current)
        elif current and re.match(r'^(操作|通过标准|截图/证据|注意)：', paragraph):
            current['requirements'].append(paragraph)
    if not cases:
        raise ValueError('DOCX 中没有识别到 A01 · 标题 格式的验收条目。')
    text = '\n'.join(paragraphs)
    # Extract the original model prompts, with no expected answers added.
    prompts = {}
    for key, prefix in [('W', '生成精简 Walmart 经营看板'), ('A', '请基于 apple_financial_demo 规划'),
                        ('U', '请分析我刚上传的 customers.csv')]:
        for index, paragraph in enumerate(paragraphs):
            if paragraph.startswith(prefix):
                selected = [paragraph]
                if key == 'A':
                    for extra in paragraphs[index + 1:index + 4]:
                        if extra.startswith(('提供“截至财年”', '提供截至财年', '单位为百万美元', '金额为百万美元')):
                            selected.append(extra)
                if key == 'U':
                    for extra in paragraphs[index + 1:index + 4]:
                        if extra.startswith(('请先识别', '金额按')):
                            selected.append(extra)
                prompts[key] = '\n'.join(selected)
                break
    match = re.search(r'BUILD_ID\s*(?:均为|为)\s*([A-Za-z0-9_-]{15,})', text)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'cases': cases, 'prompts': prompts, 'expected_build_id': match[1] if match else None,
            'text': text}


def aggregate(source: dict, checks: list[dict], run_dir: Path, suites: list[dict]) -> dict:
    rows = []
    for case in source['cases']:
        relevant = [check for check in checks if case['id'] in check.get('ids', [])]
        statuses = {check['status'] for check in relevant}
        automatic = ('失败' if 'failed' in statuses else '阻塞' if 'blocked' in statuses
                     else '通过' if 'passed' in statuses else '未覆盖')
        review = REVIEW.get(case['id'], '此编号没有自动化适配器，需要补充脚本。')
        acceptance = automatic if automatic in ('失败', '阻塞', '未覆盖') else ('待人工复核' if review else '通过')
        rows.append({**case, 'automatic_status': automatic, 'acceptance_status': acceptance,
                     'remaining': review, 'checks': relevant})
    return {'created_at': datetime.now().astimezone().isoformat(),
            'source': {k: v for k, v in source.items() if k != 'text'}, 'run_dir': str(run_dir),
            'counts': dict(Counter(row['acceptance_status'] for row in rows)), 'cases': rows,
            'supplemental_regression': suites,
            'note': '自动检查通过仅代表列出的断言；回放、真实模型、人工视觉结论分别记录。'}


def report_exit(report: dict, strict: bool, runner_code: int) -> int:
    if runner_code or report['counts'].get('失败') or any(s['returncode'] for s in report['supplemental_regression']):
        return 1
    if report['counts'].get('阻塞'):
        return 2
    if strict and any(k != '通过' and v for k, v in report['counts'].items()):
        return 2
    return 0


def write_reports(report: dict, run_dir: Path) -> None:
    (run_dir / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    markdown = ['# DB-GPT v9.1 自动验收结果', '', report['note'], '',
                f"源文件：{report['source']['path']}", f"SHA256：{report['source']['sha256']}", '',
                '；'.join(f'{key} {value}' for key, value in report['counts'].items()), '',
                '| 编号 | 项目 | 自动检查 | 清单结论 |', '|---|---|---|---|']
    html_rows = []
    for row in report['cases']:
        markdown.append(f"| {row['id']} | {row['title']} | {row['automatic_status']} | {row['acceptance_status']} |")
        details = []
        for check in row['checks']:
            artifacts = ' '.join(f'<a href="{html.escape(a, quote=True)}">{html.escape(a)}</a>' for a in check.get('artifacts', []))
            details.append(f"<p><b>{html.escape(check['name'])}</b> [{check['status']}]<br>"
                           f"{html.escape(check.get('message', ''))}<br>{artifacts}</p>")
        obligations = ''.join(f'<p>{html.escape(line)}</p>' for line in row['requirements'])
        html_rows.append(f"<tr data-status='{row['acceptance_status']}'><td>{row['id']}</td>"
                         f"<td>{html.escape(row['title'])}</td><td>{row['automatic_status']}</td>"
                         f"<td>{row['acceptance_status']}</td><td><details><summary>断言、证据与剩余项</summary>"
                         f"{''.join(details)}<p>{html.escape(row['remaining'])}</p><details><summary>原始验收标准</summary>"
                         f"{obligations}</details></details></td></tr>")
    for row in report['cases']:
        markdown.extend(['', f"## {row['id']} · {row['title']}", '', f"结论：{row['acceptance_status']}", ''])
        for check in row['checks']:
            markdown.append(f"- [{check['status']}] {check['name']}：{check.get('message', '')}")
            markdown.extend(f'  - [证据]({a})' for a in check.get('artifacts', []))
        if row['remaining']:
            markdown.extend(['', f"剩余：{row['remaining']}"])
    markdown.extend(['', '## 独立工程回归', '', '这些结果不预填真实模型/人工验收。', ''])
    markdown.extend(f"- {s['name']}：退出码 {s['returncode']}，[日志]({s['log']})" for s in report['supplemental_regression'])
    (run_dir / 'report.md').write_text('\n'.join(markdown), encoding='utf-8')
    doc = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>DB-GPT 自动验收</title>'
           '<style>body{font:15px system-ui;margin:32px;color:#182433;background:#f7f9fc}'
           'table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #d6dde7;padding:12px;text-align:left;vertical-align:top}'
           'tr[data-status="失败"]{background:#fff0f0}tr[data-status="阻塞"]{background:#fff7df}'
           'summary,select{cursor:pointer}details p{max-width:900px;white-space:pre-wrap}a{overflow-wrap:anywhere}</style>'
           '<h1>DB-GPT v9.1 自动验收</h1><p>' + html.escape(report['note']) + '</p><p>' +
           html.escape('；'.join(f'{k} {v}' for k, v in report['counts'].items())) + '</p>'
           '<p><a href="report.md">详细 Markdown</a> · <a href="report.json">JSON</a> · <a href="state.json">本轮资产与版本</a></p>'
           '<label>筛选结论 <select onchange="document.querySelectorAll(\'tbody tr\').forEach(r=>r.hidden=this.value!==\'全部\'&&r.dataset.status!==this.value)">' +
           ''.join(f'<option>{x}</option>' for x in ['全部', '失败', '阻塞', '待人工复核', '通过', '未覆盖']) +
           '</select></label><table><thead><tr><th>编号</th><th>清单项目</th><th>自动检查</th><th>清单结论</th><th>详情</th></tr></thead><tbody>' +
           ''.join(html_rows) + '</tbody></table></html>')
    (run_dir / 'report.html').write_text(doc, encoding='utf-8')


def run_regression(node: str, run_dir: Path, base_url: str, channel: str | None) -> list[dict]:
    """Run existing suites separately; never reuse old reports as this run's evidence."""
    env = {**os.environ, 'DASHBOARD_E2E_BASE_URL': base_url,
           'DASHBOARD_E2E_DISABLE_VIDEO': '1', 'DASHBOARD_E2E_START_SERVER': '0',
           'DASHBOARD_E2E_EVIDENCE_DIR': str(run_dir / 'regression/evidence')}
    if channel:
        env['DASHBOARD_E2E_BROWSER_CHANNEL'] = channel
    replay = ['dashboard-deterministic', 'rendering-fixes', 'editor-overflow',
              'tool-failure-card', 'question-continuity', 'confirmation-continuity', 'generation-timeout']
    commands = [
        ('backend', [sys.executable, '-m', 'pytest', '-c', 'pytest.dashboard.ini',
                     '--basetemp', str(run_dir / 'regression/pytest-tmp'),
                     '--junitxml', str(run_dir / 'regression/backend.xml')], ROOT),
        ('frontend', [node, 'node_modules/vitest/vitest.mjs', 'run', '--config', 'vitest.dashboard.config.mts',
                      '--reporter=default', '--reporter=json', '--outputFile', str(run_dir / 'regression/frontend.json')], ROOT / 'web'),
        ('browser-replay', [node, 'node_modules/@playwright/test/cli.js', 'test',
                            '--config', 'playwright.dashboard.config.ts', '--workers=2', '--retries=0', '--reporter=json',
                            '--output', str(run_dir / 'regression/browser-results'),
                            *[f'{name}.spec.ts' for name in replay]], ROOT / 'web'),
    ]
    results = []
    (run_dir / 'regression').mkdir(exist_ok=True)
    for name, command, cwd in commands:
        log = run_dir / 'regression' / f'{name}.log'
        print(f'[工程回归] {name}（日志：{log}）', flush=True)
        try:
            with log.open('w', encoding='utf-8') as stream:
                completed = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
            code = completed.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            with log.open('a', encoding='utf-8') as stream:
                stream.write(str(error))
            code = 1
        results.append({'name': name, 'returncode': code, 'log': str(log.relative_to(run_dir)).replace('\\', '/')})
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='按 v9.1 Word 清单自动验收；默认在本轮副本执行真实 API/浏览器检查。')
    parser.add_argument('--docx', default=str(DEFAULT_DOCX))
    parser.add_argument('--base-url', default='http://127.0.0.1:5690')
    parser.add_argument('--api-url', help='默认从当前页面的真实 Dashboard 请求自动识别后端地址。')
    parser.add_argument('--walmart-id', default='037be42defcc49c28329d0900bd31ebd')
    parser.add_argument('--apple-id', default='f29cbeb8d6014d8f9ee5dc5ead4951a8')
    parser.add_argument('--expected-build-id', help='显式覆盖文档部署基线。')
    parser.add_argument('--output-root', default=str(ROOT / 'output/manual-acceptance/automation'))
    parser.add_argument('--node', default=shutil.which('node'))
    parser.add_argument('--browser-channel', choices=['chrome', 'msedge', 'chromium'])
    parser.add_argument('--storage-state', help='可选 Playwright 登录状态文件；不复制进报告。')
    parser.add_argument('--live-model', action='store_true', help='追加真实模型 C01–C05，可能产生模型费用；首次失败不自动重试。')
    parser.add_argument('--theme-matrix', action='store_true', help='追加 32 个真实发布页面组合与截图。')
    parser.add_argument('--schedule', action='store_true', help='追加真实一分钟调度与暂停验证，约需 3 分钟。')
    parser.add_argument('--regression', action='store_true', help='追加现有 pytest、Vitest 和受控浏览器回放。')
    parser.add_argument('--list-only', action='store_true', help='只读取 DOCX、生成覆盖报告，不连接服务。')
    parser.add_argument('--strict', action='store_true', help='存在待人工复核/未覆盖时也返回 2。')
    args = parser.parse_args(argv)
    source = read_checklist(normalize_path(args.docx))
    run_id = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    run_dir = normalize_path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    config = {**vars(args), 'root': str(ROOT), 'out': str(run_dir), 'run_id': run_id, 'python': sys.executable,
              'source': {k: v for k, v in source.items() if k != 'text'},
              'script_sha256': {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                                for file in Path(__file__).parent.iterdir() if file.suffix in ('.py', '.cjs')},
              'expected_build_id': args.expected_build_id or source['expected_build_id']}
    (run_dir / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    (run_dir / 'source-checklist.txt').write_text(source['text'], encoding='utf-8')
    print(f'已读取 {len(source["cases"])} 项；本轮输出：{run_dir}', flush=True)
    code, suites = 0, []
    if not args.list_only:
        if not args.node:
            print('未找到 Node.js，请使用 --node 指定宿主或项目运行时。', flush=True)
            code = 1
        else:
            try:
                with (run_dir / 'runner.log').open('w', encoding='utf-8') as log:
                    with subprocess.Popen([args.node, str(Path(__file__).with_name('live_acceptance.cjs')),
                                           str(run_dir / 'config.json')], cwd=ROOT, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace') as process:
                        for line in process.stdout:
                            log.write(line)
                            log.flush()
                            print(line, end='', flush=True)
                        code = process.wait()
            except KeyboardInterrupt:
                code = 130
            except OSError as error:
                print(error, flush=True)
                code = 1
        if args.regression and args.node and code != 130:
            suites = run_regression(args.node, run_dir, args.base_url, args.browser_channel)
    checks = []
    events = run_dir / 'checks.jsonl'
    if events.exists():
        for line in events.read_text(encoding='utf-8').splitlines():
            try:
                checks.append(json.loads(line))
            except json.JSONDecodeError:
                code = 1  # Interrupted partial record must not produce a green run.
    if code and not checks:
        checks.append({'ids': list(REVIEW), 'name': '运行器启动', 'status': 'blocked',
                       'message': f'Node/浏览器启动未完成，退出码 {code}。', 'artifacts': []})
    report = aggregate(source, checks, run_dir, suites)
    report['runner_exit_code'] = code
    if code:
        report['note'] += f' 运行器未正常完成（退出码 {code}），请检查 runner.log；未执行的项目不算通过。'
    write_reports(report, run_dir)
    print(json.dumps(report['counts'], ensure_ascii=False), flush=True)
    print(f'打开报告：{run_dir / "report.html"}', flush=True)
    return report_exit(report, args.strict, code)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        print(f'验收启动失败：{error}', file=sys.stderr)
        raise SystemExit(2)
