"""T3 suite binder: alias normalization, allow/deny gate, SOP watermark, gate order.

The pi-engine per-conversation registry and the plugins Service component live
behind ``CFG.SYSTEM_APP`` (needs a running app), so these tests cover the pure
parts of :mod:`dbgpt_app.openapi.api_v1.suite_binder`: tool-name canonicalization,
:func:`SuiteBinding.violation`, :func:`build_sop_block`, :func:`make_suite_gate`
composition, and the resolution-order fail-soft behaviour.
"""

import asyncio
import unittest

from dbgpt_app.openapi.api_v1.suite_binder import (
    IMPLICIT_ALLOW,
    SEMANTIC_DEGRADED_WATERMARK,
    SuiteBinding,
    build_sop_block,
    canonical_suite_tool,
    compose_gates,
    make_suite_gate,
)


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
    def test_suite_gate_blocks_before_inner_gate(self):
        binding = SuiteBinding(name="sc", version="1", deny={"bash"})
        gate = make_suite_gate(binding)
        observation = asyncio.get_event_loop().run_until_complete(gate("bash", {}))
        self.assertIsNotNone(observation)

    def test_compose_gates_suite_blocks_before_approval(self):
        binding = SuiteBinding(name="sc", version="1", deny={"bash"})
        calls = []

        async def inner(name, args):
            calls.append(name)
            return None

        composed = compose_gates(make_suite_gate(binding), inner)
        loop = asyncio.get_event_loop()
        observation = loop.run_until_complete(composed("bash", {}))
        self.assertIsNotNone(observation)
        self.assertEqual(calls, [])
        self.assertIsNone(loop.run_until_complete(composed("sql_query", {})))
        self.assertEqual(calls, ["sql_query"])


if __name__ == "__main__":
    unittest.main()
