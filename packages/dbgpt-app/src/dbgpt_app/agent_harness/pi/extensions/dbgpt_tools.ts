// DB-GPT agent tools bridge for the pi harness engine.
//
// Installed into the isolated pi agent dir by
// ``dbgpt_app.agent_harness.pi.tool_bridge.install_extension`` and
// auto-discovered at pi startup. Registers one native pi tool per
// entry of ``DBGPT_TOOLS_MANIFEST``; each tool executes server-side
// through the loopback harness endpoint, so DB-GPT's containment
// (read-only SQL connector, sandboxed code interpreter, ...) applies.
//
// Environment (injected by PiHarnessConfig.build_env):
//   DBGPT_TOOLS_MANIFEST  JSON array: [{name, description, parameters}]
//   DBGPT_TOOLS_RUN_URL   loopback POST endpoint executing one tool
//   DBGPT_TOOLS_TOKEN     bearer token for the loopback endpoint
//   DBGPT_TOOLS_CONV_ID   conversation anchoring the server-side ToolPack

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

interface ManifestTool {
  name: string;
  description: string;
  parameters: {
    type?: string;
    properties?: Record<string, { type?: string; description?: string }>;
    required?: string[];
  };
}

export default function (pi: ExtensionAPI) {
  // Global input hygiene for pi built-ins: models (deepseek-v4-flash
  // observed) send numeric strings / explicit nulls that fail pi's strict
  // schema validation and surface as instant tool failures. event.input
  // is mutable per the extension contract, so coerce in place.
  pi.on("tool_call", async (event: any) => {
    const input = event?.input;
    if (!input || typeof input !== "object") return;
    for (const key of Object.keys(input)) {
      const v = input[key];
      if (v === null || v === undefined) delete input[key];
    }
    if (event.toolName === "read") {
      for (const key of ["offset", "limit"]) {
        const v = input[key];
        if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) {
          input[key] = Number(v);
        }
      }
    }
    if (event.toolName === "bash" && typeof input.timeout === "string") {
      const n = Number(input.timeout);
      if (!Number.isNaN(n)) input.timeout = n;
    }
  });

  let manifest: ManifestTool[] = [];
  try {
    manifest = JSON.parse(process.env.DBGPT_TOOLS_MANIFEST || "[]");
  } catch {
    manifest = [];
  }
  const runUrl = process.env.DBGPT_TOOLS_RUN_URL || "";
  const statusUrl = process.env.DBGPT_TOOLS_STATUS_URL || "";
  const token = process.env.DBGPT_TOOLS_TOKEN || "";
  const convId = process.env.DBGPT_TOOLS_CONV_ID || "";
  if (!manifest.length || !runUrl) return;

  for (const entry of manifest) {
    pi.registerTool({
      name: entry.name,
      label: entry.name,
      description: entry.description,
      // The manifest carries a plain JSON schema; pi validates it
      // directly (typebox compiles raw JSON schemas).
      parameters: entry.parameters as any,
      // Compatibility shim before pi's schema validation: some models
      // (deepseek-v4-flash observed) wrap the payload under the tool
      // name ({"sql_query": "SELECT ..."}) or invent a single wrong
      // key; fold those shapes into the declared parameters.
      prepareArguments(args: any) {
        if (!args || typeof args !== "object") return args;
        // String-typed schema props (e.g. question's ``questions`` JSON
        // string) coerce object/array payloads instead of failing validation.
        const propSpecs = entry.parameters?.properties || {};
        for (const [key, value] of Object.entries(args)) {
          const spec: any = propSpecs[key];
          const stringish =
            spec &&
            (spec.type === "string" ||
              (spec.anyOf || []).some((a: any) => a && a.type === "string"));
          if (stringish && value !== null && typeof value === "object") {
            (args as any)[key] = JSON.stringify(value);
          }
        }
        const keys = Object.keys(args);
        const required = entry.parameters?.required || [];
        const props = Object.keys(entry.parameters?.properties || {});
        const firstKey = required[0] || props[0];
        if (keys.length === 1 && keys[0] === entry.name) {
          const inner = args[keys[0]];
          if (inner && typeof inner === "object") return inner;
          if (firstKey) return { [firstKey]: inner };
        }
        if (keys.length === 1 && firstKey && !props.includes(keys[0])) {
          return { [firstKey]: args[keys[0]] };
        }
        return args;
      },

      async execute(toolCallId, params, signal) {
        // ask-user: server registers the pending question and streams the
        // card to the product; we poll the status endpoint until the user
        // answers (or the 300s server-side timeout expires).
        if (entry.name === "question" && statusUrl) {
          try {
            const start = await fetch(runUrl, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({
                conv_id: convId,
                tool: "question",
                arguments: params || {},
              }),
              signal,
            });
            const startJson: any = await start.json().catch(() => null);
            const requestId = startJson?.data?.request_id;
            if (!start.ok || !requestId) {
              return {
                content: [
                  {
                    type: "text",
                    text: `ask_user failed to register: HTTP ${start.status}`,
                  },
                ],
                details: {},
              };
            }
            const deadline = Date.now() + 320_000;
            while (Date.now() < deadline) {
              await new Promise(r => setTimeout(r, 2000));
              if (signal?.aborted) {
                return {
                  content: [{ type: "text", text: "ask_user cancelled." }],
                  details: {},
                };
              }
              const poll = await fetch(
                `${statusUrl}?request_id=${encodeURIComponent(requestId)}`,
                { headers: { Authorization: `Bearer ${token}` }, signal },
              );
              const pollJson: any = await poll.json().catch(() => null);
              const state = pollJson?.data?.state;
              if (state && state !== "pending") {
                return {
                  content: [
                    { type: "text", text: String(pollJson?.data?.result || state) },
                  ],
                  details: { state },
                };
              }
            }
            return {
              content: [
                {
                  type: "text",
                  text: "Question timed out after 300 seconds. Proceeding without user answer.",
                },
              ],
              details: {},
            };
          } catch (err) {
            return {
              content: [{ type: "text", text: `ask_user failed: ${String(err)}` }],
              details: {},
            };
          }
        }
        try {
          const res = await fetch(runUrl, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              conv_id: convId,
              tool: entry.name,
              arguments: params || {},
            }),
            signal,
          });
          const raw = await res.text();
          let payload: any = null;
          try {
            payload = JSON.parse(raw);
          } catch {
            payload = null;
          }
          const text =
            payload && payload.data && typeof payload.data.result === "string"
              ? payload.data.result
              : raw || `DB-GPT tool endpoint returned HTTP ${res.status}`;
          return {
            content: [{ type: "text", text }],
            details: { status: res.status },
          };
        } catch (err) {
          return {
            content: [
              {
                type: "text",
                text: `DB-GPT tool call failed: ${String(err)}`,
              },
            ],
            details: {},
          };
        }
      },
    });
  }
}
