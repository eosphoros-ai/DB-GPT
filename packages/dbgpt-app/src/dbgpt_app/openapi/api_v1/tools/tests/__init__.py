"""Tests for session-file aware ReAct tools (Task 7).

Covers:
- load_file: bounded public observation for selected session files
  (IDs + schema/preview/truncation), subset validation, legacy single
  file and text-only compatibility, and never leaking internal paths;
- execute_analysis: optional file_ids subset validation, env-based
  FILE_PATH/FILES_JSON propagation, partial per-file failures surfaced
  as error chunks with hard failure only when zero files are analyzable;
- code_interpreter: FILE_PATH/FILES_JSON propagated through the
  subprocess environment, and adversarial display names/paths can never
  be interpolated into the generated Python source.
"""
