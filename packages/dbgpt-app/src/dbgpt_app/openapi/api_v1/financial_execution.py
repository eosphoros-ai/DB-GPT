"""Public execution observations, kept separate from model context/reasoning."""

import json
import time
from datetime import datetime, timezone


def interrupt_financial_progress(state):
    """End the visible active stage without changing report/publication state."""
    tasks = state.get("financial_plan") or []
    now = datetime.now(timezone.utc).isoformat()
    for task in tasks:
        if task.get("status") == "in_progress":
            task.update(
                status="error",
                detail="本次执行已中断，已提取数据和分析草稿已保留；可继续未完成的分析或复核。",
                updatedAt=now,
                finishedAt=now,
            )
    return tasks


class FinancialExecutionLog:
    def __init__(self, clock=None):
        self.clock = clock or time.monotonic
        self.started = self.clock()
        self.last_output = self.started
        self.previous = {}
        self.count = 0

    def observe(self, tasks):
        messages = []
        for task in tasks:
            key = task.get("id")
            value = (task.get("status"), task.get("detail"))
            if value == self.previous.get(key):
                continue
            self.previous[key] = value
            if value[0] == "pending" or not value[1]:
                continue
            if self.count >= 80:
                continue
            self.count += 1
            elapsed = int(self.clock() - self.started)
            messages.append(
                f"[{elapsed // 60:02d}:{elapsed % 60:02d}] "
                f"{task['content']}：{value[1]}\n"
            )
        if messages:
            self.last_output = self.clock()
        return messages

    def waiting(self):
        now = self.clock()
        if now - self.last_output < 20 or self.count >= 80:
            return []
        self.last_output = now
        self.count += 1
        elapsed = int(now - self.started)
        return [
            f"[{elapsed // 60:02d}:{elapsed % 60:02d}] "
            "尚未收到新的处理结果，仍在等待当前工具执行完成。\n"
        ]


class FinancialExecutionStream:
    """Attach live observations to their actual tool step, including history."""

    def __init__(self, history, clock=None):
        self.history = history
        self.clock = clock
        self.records = {}
        self.logs = {}
        self.progress_log = None

    def start(self, round_num, step_id, action, action_input, message):
        record = {
            "id": step_id,
            "title": action,
            "detail": "Action: " + action,
            "action": action,
            "action_input": json.dumps(action_input, ensure_ascii=False),
            "outputs": [],
            "status": "running",
        }
        self.records[round_num] = record
        # One analysis spans several tool calls. Keep its clock and observed
        # stages so review/publish neither replay old work nor reset to 00:00.
        if self.progress_log is None:
            self.progress_log = FinancialExecutionLog(self.clock)
        self.logs[round_num] = self.progress_log
        self.history.append(record)
        return self._append(round_num, [message + "\n"])

    def _append(self, round_num, messages):
        record = self.records.get(round_num)
        if not record:
            return []
        chunks = []
        for message in messages:
            output = {"output_type": "text", "content": message}
            record["outputs"].append(output)
            chunks.append({"type": "step.chunk", "id": record["id"], **output})
        if messages:
            self.logs[round_num].last_output = self.logs[round_num].clock()
        return chunks

    def progress(self, round_num, tasks, observations=()):
        if round_num not in self.records:
            return []
        messages = self.logs[round_num].observe(tasks)
        messages += [message + "\n" for message in observations]
        return self._append(round_num, messages)

    def waiting(self):
        return [
            event
            for round_num, log in self.logs.items()
            for event in self._append(round_num, log.waiting())
        ]

    def finish(self, round_num, final_record):
        record = self.records.pop(round_num, None)
        self.logs.pop(round_num, None)
        if record is None:
            return final_record, False
        final_record["outputs"] = record["outputs"] + final_record.get("outputs", [])
        record.update(final_record)
        return record, True

    def fail_unfinished(self):
        events = []
        for record in self.records.values():
            record["status"] = "failed"
            events.append({"type": "step.done", "id": record["id"], "status": "failed"})
        self.records.clear()
        self.logs.clear()
        return events
