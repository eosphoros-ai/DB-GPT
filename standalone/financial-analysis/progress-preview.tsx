/** Browser fixture of the real chat panel; no model, API or daily service. */
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import zh from "../../web/locales/zh";
import ManusRightPanel, {
  ActiveStepInfo,
  ExecutionOutput,
} from "../../web/new-components/chat/content/ManusRightPanel";
import ManusLeftPanel from "../../web/new-components/chat/content/ManusLeftPanel";
import type { TaskItem } from "../../web/new-components/chat/content/TaskPlanCard";

void i18n
  .use(initReactI18next)
  .init({
    lng: "zh",
    resources: { zh: { translation: zh } },
    initImmediate: false,
  });

function Preview() {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [running, setRunning] = useState(true);
  const [steps, setSteps] = useState<ActiveStepInfo[]>([]);
  const [outputs, setOutputs] = useState<Record<string, ExecutionOutput[]>>({});
  const [activeId, setActiveId] = useState<string>();
  // Receives the same tasks payload as plan.update; remount is not needed.
  (window as any).pushProgress = (tasks: TaskItem[], running = true) => {
    setTasks(tasks);
    setRunning(running);
  };
  (window as any).pushExecution = (event: any) => {
    if (event.type === "step.start") {
      setSteps((old) =>
        old.some((step) => step.id === event.id)
          ? old.map((step) =>
              step.id === event.id
                ? { ...step, title: event.title, detail: event.detail }
                : step,
            )
          : [
              ...old,
              {
                id: event.id,
                type: "other",
                title: event.title,
                detail: event.detail,
                status: "running",
              },
            ],
      );
      setActiveId(event.id);
    } else if (event.type === "step.meta") {
      setSteps((old) =>
        old.map((step) =>
          step.id === event.id
            ? {
                ...step,
                title: event.title || step.title,
                action: event.action,
                detail: `Action: ${event.action}\nAction Input: ${JSON.stringify(event.action_input)}`,
              }
            : step,
        ),
      );
    } else if (event.type === "step.chunk") {
      setOutputs((old) => ({
        ...old,
        [event.id]: [
          ...(old[event.id] || []),
          { output_type: event.output_type, content: event.content },
        ],
      }));
    } else if (event.type === "step.done") {
      setSteps((old) =>
        old.map((step) =>
          step.id === event.id
            ? {
                ...step,
                status: event.status === "failed" ? "error" : "completed",
              }
            : step,
        ),
      );
    }
  };
  // Emulate durable history restored by index.tsx without an active SSE stream.
  (window as any).restoreExecution = (saved: any[]) => {
    setRunning(false);
    setSteps(
      saved.map((step) => ({
        id: step.id,
        type: "other",
        title: step.title,
        action: step.action,
        detail: `Action: ${step.action}\nAction Input: ${step.action_input}`,
        status: step.status === "done" ? "completed" : "error",
      })),
    );
    setOutputs(
      Object.fromEntries(saved.map((step) => [step.id, step.outputs])),
    );
    setActiveId(saved[0]?.id);
  };
  const selected = steps.find((step) => step.id === activeId) || null;
  return (
    <main className="flex h-screen bg-slate-50">
      <aside data-testid="left-plan" className="w-[38%] border-r bg-white p-6">
        <ManusLeftPanel
          taskPlan={tasks}
          isWorking={running}
          userQuery="分析一下这份财报"
          attachedFiles={[]}
          activeStepId={activeId}
          onStepClick={setActiveId}
          stepThoughts={{ "step-1": "INTERNAL_THOUGHT_SENTINEL" }}
          sections={[
            {
              id: "execution",
              title: "执行步骤",
              isCompleted: !running,
              steps,
            },
          ]}
        />
      </aside>
      <div data-testid="right-panel" className="flex min-w-0 flex-1 flex-col">
        <ManusRightPanel
          isRunning={running}
          outputs={outputs[activeId || ""] || []}
          activeStep={selected}
        />
      </div>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<Preview />);
