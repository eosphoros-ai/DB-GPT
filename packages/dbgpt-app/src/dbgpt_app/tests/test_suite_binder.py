"""T3 suite binder: alias normalization, allow/deny gate, SOP watermark, gate order.

The pi-engine per-conversation registry and the plugins Service component live
behind ``CFG.SYSTEM_APP`` (needs a running app), so these tests cover the pure
parts of :mod:`dbgpt_app.openapi.api_v1.suite_binder`: tool-name canonicalization,
:func:`SuiteBinding.violation`, :func:`build_sop_block`, :func:`make_suite_gate`
composition, and the resolution-order fail-soft behaviour.
"""

import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dbgpt.agent.core.base_agent import ConversableAgent
from dbgpt.agent.core.profile.base import ProfileConfig
from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt_app.openapi.api_v1.suite_binder import (
    IMPLICIT_ALLOW,
    SEMANTIC_DEGRADED_WATERMARK,
    SuiteBinding,
    bind_command,
    build_sop_block,
    canonical_suite_tool,
    command_binding_event,
    compose_gates,
    load_binding,
    make_suite_gate,
    report_agent_tool_scope,
    resolve_binding_for_turn,
    suite_message_reference,
)
from dbgpt_serve.plugins.loader import load_suite_dir

SUITES_ROOT = Path(__file__).resolve().parents[5] / "assets" / "suites"


class SuiteCommandTest(unittest.TestCase):
    def test_message_reference_snapshots_resolved_command(self):
        binding = self.make_binding()
        bind_command(binding, "/nl2sql")
        reference = suite_message_reference(binding, {"suite_display": "智能取数"})
        bind_command(binding, "/schema")
        self.assertEqual(
            reference,
            {"name": "db-query", "display": "智能取数", "command": "/nl2sql"},
        )
        self.assertIsNone(suite_message_reference(None))
        self.assertEqual(
            suite_message_reference(binding, {"suite_display": 123})["display"],
            "db-query",
        )

    def make_binding(self, slug="db-query"):
        root = SUITES_ROOT / slug
        package = load_suite_dir(root)
        manifest = package.manifest
        return SuiteBinding(
            name=slug,
            version=manifest["version"],
            package_path=str(root),
            commands=manifest["commands"],
            skills=manifest["skills"],
            package_format=manifest["package_format"],
            sop_text=(root / manifest["sop"]).read_text(),
            allow={"sql_query"},
            deny={"bash"},
        )

    def test_every_shipped_command_loads_its_declared_skill(self):
        for slug in ("db-query", "db-analysis", "db-ops"):
            for command in self.make_binding(slug).commands:
                with self.subTest(suite=slug, command=command["name"]):
                    binding = self.make_binding(slug)
                    bind_command(binding, command["name"])
                    self.assertFalse(binding.command_error)
                    self.assertEqual(binding.command_skill, command["skill"])
                    block = build_sop_block(binding)
                    self.assertIn(f"本轮快捷命令：{command['name']}", block)
                    self.assertIn(binding.command_skill_text, block)
                    event = command_binding_event(binding)
                    self.assertTrue(event["skill_loaded"])
                    self.assertEqual(
                        event["skill_sha256"],
                        hashlib.sha256(
                            binding.command_skill_text.encode("utf-8")
                        ).hexdigest(),
                    )
                    # Loading a skill cannot widen the suite's tools.
                    self.assertIsNotNone(binding.violation("bash"))
                    self.assertIsNotNone(binding.violation("load_skill"))
                    self.assertIsNone(binding.violation("sql_query"))

    def test_query_and_analysis_load_their_full_dependency_chain(self):
        for slug, command, expected in (
            (
                "db-query",
                "/nl2sql",
                {
                    "skills/nl2sql-precision/SKILL.md",
                    "skills/semantic-linking/SKILL.md",
                    "skills/readonly-guardrails/SKILL.md",
                    "prompts/query-playbook.md",
                },
            ),
            (
                "db-analysis",
                "/analyze",
                {
                    "skills/multi-step-analysis/SKILL.md",
                    "skills/dataset-scoping/SKILL.md",
                    "skills/chart-advisor/SKILL.md",
                    "skills/attribution-analysis/SKILL.md",
                    "skills/report-generation/SKILL.md",
                    "templates/report-template.md",
                    "prompts/analysis-playbook.md",
                },
            ),
        ):
            binding = self.make_binding(slug)
            bind_command(binding, command)
            self.assertFalse(binding.command_error)
            self.assertEqual(
                {doc["path"] for doc in binding.loaded_documents}, expected
            )
            self.assertIn(binding.sop_text.strip(), build_sop_block(binding))

    def test_analysis_report_template_survives_actual_agent_prompt_rendering(self):
        binding = self.make_binding("db-analysis")
        bind_command(binding, "/analyze")
        block = build_sop_block(binding)
        self.assertIn("{{...}}", block)
        self.assertIn("{{report_title}}", block)
        agent = ConversableAgent(
            profile=ProfileConfig(name="literal-prompt", role="analyst")
        ).bind(PromptTemplate.from_literal(block))
        loop = asyncio.new_event_loop()
        try:
            rendered = loop.run_until_complete(
                agent.build_system_prompt(context={"report_title": "Do not substitute"})
            )
        finally:
            loop.close()
        self.assertEqual(rendered, block)
        for document in binding.loaded_documents:
            if "content" in document:
                self.assertIn(document["content"], rendered)

    def test_native_builtin_keeps_tool_gate_sop_and_semantic_warning(self):
        package = load_suite_dir(SUITES_ROOT / "db-query")
        row = SimpleNamespace(
            name=package.name,
            version=package.version,
            status="enabled",
            package_path=package.path,
            manifest_snapshot=package.snapshot,
        )
        with (
            patch(
                "dbgpt_app.openapi.api_v1.suite_binder._plugins_service",
                return_value=SimpleNamespace(get=lambda _: row),
            ),
            patch(
                "dbgpt_app.openapi.api_v1.suite_binder._probe_semantic_status",
                return_value="degraded",
            ),
        ):
            binding = load_binding("db-query")
        self.assertEqual(binding.package_format, "qwenwork-plugin")
        self.assertIsNotNone(binding.violation("bash"))
        self.assertIsNotNone(binding.violation("ddl"))
        self.assertIsNone(binding.violation("sql_query"))
        self.assertTrue(binding.sop_text)
        self.assertEqual(binding.watermark, SEMANTIC_DEGRADED_WATERMARK)

    def test_native_analysis_tools_match_registered_chart_and_report_tools(self):
        package = load_suite_dir(SUITES_ROOT / "db-analysis")
        row = SimpleNamespace(
            name=package.name,
            version=package.version,
            status="enabled",
            package_path=package.path,
            manifest_snapshot=package.snapshot,
        )
        with (
            patch(
                "dbgpt_app.openapi.api_v1.suite_binder._plugins_service",
                return_value=SimpleNamespace(get=lambda _: row),
            ),
            patch(
                "dbgpt_app.openapi.api_v1.suite_binder._probe_semantic_status",
                return_value="degraded",
            ),
        ):
            binding = load_binding("db-analysis")
        bind_command(binding, "/analyze")
        self.assertIsNone(binding.violation("chart_query"))
        self.assertIsNone(binding.violation("generate_report"))
        self.assertIsNotNone(binding.violation("code"))
        self.assertIsNotNone(binding.violation("bash"))
        self.assertIsNotNone(binding.violation("html_interpreter"))
        binding.deny.add("generate_report")
        self.assertIsNotNone(binding.violation("generate_report"))

    def test_unknown_command_blocks_business_tools(self):
        binding = self.make_binding()
        bind_command(binding, "/not-installed")
        self.assertIn("没有快捷命令", binding.command_error)
        self.assertFalse(command_binding_event(binding)["skill_loaded"])
        self.assertIsNotNone(binding.violation("sql_query"))
        self.assertIsNone(binding.violation("question"))

    def test_missing_or_outside_skill_path_cannot_run(self):
        for path in ("missing/SKILL.md", "../db-ops/.qwenwork-plugin/plugin.json"):
            binding = self.make_binding()
            binding.skills = [{"name": "semantic-linking", "path": path}]
            bind_command(binding, "/schema")
            self.assertTrue(binding.command_error)
            self.assertFalse(binding.command_skill_text)
            self.assertIsNotNone(binding.violation("sql_query"))

    def test_turn_selection_is_not_sticky_and_typed_commands_resolve(self):
        service = SimpleNamespace(
            registry=SimpleNamespace(current_pin=lambda _: ("db-query", "1.1.0"))
        )
        for ext, text, expected in (
            ({"suite_command": "/schema"}, "orders", "/schema"),
            ({}, "[Database: Walmart_Sales] /metric valid_gmv", "/metric"),
            ({}, "下一个普通问题", ""),
        ):
            with (
                patch(
                    "dbgpt_app.openapi.api_v1.suite_binder._plugins_service",
                    return_value=service,
                ),
                patch(
                    "dbgpt_app.openapi.api_v1.suite_binder.load_binding",
                    side_effect=lambda _: self.make_binding(),
                ),
            ):
                result = resolve_binding_for_turn(
                    SimpleNamespace(ext_info=ext, conv_uid="test", user_input=text)
                )
            self.assertIsNotNone(result)
            self.assertEqual(result.command, expected)


class NativePluginBindingTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.skill = self.root / "skills/doctor/SKILL.md"
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text(
            "# Doctor\n[知识](../knowledge/SKILL.md)\n"
            "[Repeated](../knowledge/SKILL.md#rules)\n"
            "```\n[Example](missing.md)\n```\n",
            encoding="utf-8",
        )
        knowledge = self.root / "skills/knowledge/SKILL.md"
        knowledge.parent.mkdir()
        knowledge.write_text(
            "# Shared rules\n[Template](report%20template.md)\n"
            "[Cycle](../doctor/SKILL.md)\n",
            encoding="utf-8",
        )
        (knowledge.parent / "report template.md").write_text(
            "# Report template\nNever invent measurements", encoding="utf-8"
        )
        self.binding = SuiteBinding(
            name="native",
            version="1",
            package_format="qwenwork-plugin",
            package_path=str(self.root),
            commands=[
                {
                    "name": "/SQL 体检",
                    "aliases": ["/doctor", "/SQL Doctor"],
                    "skill": "doctor",
                }
            ],
            skills=[{"name": "doctor", "path": "skills/doctor/SKILL.md"}],
        )

    def test_alias_loads_transitive_references_once_and_records_hashes(self):
        bind_command(self.binding, "/SQL Doctor")
        self.assertEqual(self.binding.command, "/SQL 体检")
        self.assertFalse(self.binding.command_error)
        event = command_binding_event(self.binding)
        self.assertTrue(event["skill_loaded"])
        self.assertEqual(len(event["documents"]), 3)
        for doc in event["documents"]:
            text = (self.root / doc["path"]).read_text().strip()
            self.assertEqual(
                doc["sha256"], hashlib.sha256(text.encode("utf-8")).hexdigest()
            )
            self.assertNotIn("content", doc)
        self.assertIn("Never invent measurements", build_sop_block(self.binding))

    def test_missing_outside_and_empty_references_stop_business_execution(self):
        for link in ("missing.md", "../../../outside.md", "empty.md"):
            with self.subTest(link=link):
                (self.skill.parent / "empty.md").write_text("")
                self.skill.write_text(f"# Doctor\n[Required]({link})")
                bind_command(self.binding, "/doctor")
                self.assertTrue(self.binding.command_error)
                self.assertFalse(command_binding_event(self.binding)["skill_loaded"])
                self.assertIsNotNone(self.binding.violation("sql_query"))
                self.assertIsNone(self.binding.violation("question"))

    def test_oversized_skill_is_rejected(self):
        self.skill.write_text("x" * (512 * 1024 + 1))
        bind_command(self.binding, "/doctor")
        self.assertTrue(self.binding.command_error)
        self.assertIsNotNone(self.binding.violation("sql_query"))

    def test_rebinding_unknown_command_clears_previous_skill(self):
        bind_command(self.binding, "/doctor")
        bind_command(self.binding, "/missing")
        self.assertEqual(self.binding.command_skill, "")
        self.assertEqual(command_binding_event(self.binding)["documents"], [])

    def test_typed_chinese_and_spaced_english_aliases_resolve(self):
        service = SimpleNamespace(
            registry=SimpleNamespace(current_pin=lambda _: ("native", "1"))
        )
        for text in ("/SQL 体检 select 1", "/SQL Doctor select 1"):
            with (
                patch(
                    "dbgpt_app.openapi.api_v1.suite_binder._plugins_service",
                    return_value=service,
                ),
                patch(
                    "dbgpt_app.openapi.api_v1.suite_binder.load_binding",
                    return_value=self.binding,
                ),
            ):
                binding = resolve_binding_for_turn(
                    SimpleNamespace(ext_info={}, conv_uid="test", user_input=text)
                )
            self.assertEqual(binding.command, "/SQL 体检")
            self.assertFalse(binding.command_error)


class CanonicalSuiteToolTest(unittest.TestCase):
    def test_manifest_aliases_map_to_registered_tools(self):
        self.assertEqual(canonical_suite_tool("sql_execute"), "sql_query")
        self.assertEqual(canonical_suite_tool("shell"), "bash")
        self.assertEqual(canonical_suite_tool("shell_interpreter"), "bash")
        self.assertEqual(canonical_suite_tool("code_interpreter"), "code")

    def test_unknown_names_pass_through(self):
        self.assertEqual(canonical_suite_tool("question"), "question")
        self.assertEqual(canonical_suite_tool("todowrite"), "todowrite")


class SuiteBindingViolationTest(unittest.TestCase):
    def test_deny_hits_and_blocks(self):
        binding = SuiteBinding(name="sc", version="1", deny={"bash"})
        observation = binding.violation("bash")
        self.assertIsNotNone(observation)
        self.assertIn("denied", observation)
        self.assertIn("sc@1", observation)

    def test_allow_miss_blocks_but_question_stays(self):
        binding = SuiteBinding(name="sc", version="1", allow={"sql_query"})
        self.assertIsNotNone(binding.violation("bash"))
        self.assertIsNone(binding.violation("sql_query"))
        for tool in sorted(IMPLICIT_ALLOW):
            self.assertIsNone(binding.violation(tool))

    def test_unrestricted_allow_never_blocks(self):
        binding = SuiteBinding(name="sc", version="1", allow=None)
        self.assertIsNone(binding.violation("bash"))
        self.assertIsNone(binding.violation("sql_query"))


class BuildSopBlockTest(unittest.TestCase):
    def test_sop_text_and_watermark_appended(self):
        binding = SuiteBinding(
            name="sc",
            version="2",
            sop_text="只读、超时、行数护栏",
            semantic_status="degraded",
            watermark=SEMANTIC_DEGRADED_WATERMARK,
        )
        block = build_sop_block(binding)
        self.assertIn("场景套件 SOP（sc@2）", block)
        self.assertIn("只读、超时、行数护栏", block)
        self.assertIn(SEMANTIC_DEGRADED_WATERMARK, block)

    def test_bound_binding_has_no_watermark(self):
        binding = SuiteBinding(
            name="sc", version="2", sop_text="sop", semantic_status="bound"
        )
        block = build_sop_block(binding)
        self.assertNotIn(SEMANTIC_DEGRADED_WATERMARK, block)


class GateOrderTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.addCleanup(self.loop.close)

    def test_report_helpers_are_delegated_only_to_child_and_keep_approval(self):
        binding = SuiteBinding(
            name="analysis", version="1", allow={"generate_report", "sql_query"}
        )
        calls = []

        async def inner(name, args):
            calls.append(name)
            return "approval required"

        gate = compose_gates(make_suite_gate(binding), inner)
        loop = self.loop
        self.assertIn(
            "not in suite", loop.run_until_complete(gate("html_interpreter", {}))
        )
        with report_agent_tool_scope():
            self.assertEqual(
                loop.run_until_complete(gate("html_interpreter", {})),
                "approval required",
            )
            self.assertIn("not in suite", loop.run_until_complete(gate("code", {})))
            binding.deny.add("html_interpreter")
            self.assertIn(
                "denied", loop.run_until_complete(gate("html_interpreter", {}))
            )
            binding.deny.clear()
            binding.command_error = "required skill missing"
            self.assertIn(
                "required skill missing",
                loop.run_until_complete(gate("html_interpreter", {})),
            )
            binding.command_error = ""
        self.assertIn(
            "not in suite", loop.run_until_complete(gate("html_interpreter", {}))
        )
        self.assertEqual(calls, ["html_interpreter"])

    def test_suite_gate_blocks_before_inner_gate(self):
        binding = SuiteBinding(name="sc", version="1", deny={"bash"})
        gate = make_suite_gate(binding)
        observation = self.loop.run_until_complete(gate("bash", {}))
        self.assertIsNotNone(observation)

    def test_compose_gates_suite_blocks_before_approval(self):
        binding = SuiteBinding(name="sc", version="1", deny={"bash"})
        calls = []

        async def inner(name, args):
            calls.append(name)
            return None

        composed = compose_gates(make_suite_gate(binding), inner)
        loop = self.loop
        observation = loop.run_until_complete(composed("bash", {}))
        self.assertIsNotNone(observation)
        self.assertEqual(calls, [])
        self.assertIsNone(loop.run_until_complete(composed("sql_query", {})))
        self.assertEqual(calls, ["sql_query"])


if __name__ == "__main__":
    unittest.main()
