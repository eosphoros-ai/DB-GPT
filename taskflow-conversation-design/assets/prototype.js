(function () {
  "use strict";
  const el = (id) => document.getElementById(id);
  const initial = () => [
    { id: "start", name: "开始", desc: "接收任务目标与运行参数", boundary: true },
    { id: "output", name: "输出", desc: "整理最终结果返回对话", boundary: true },
  ];
  let nodes = initial(), pending = null, history = [], selected = null;
  let revision = 0, verified = null, bound = false, created = false, published = false, topic = "";
  function escape(value) {
    return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }
  function notice(text, warning = false) {
    el("notice").textContent = text;
    el("notice").classList.toggle("warning", warning);
  }
  function bubble(who, text, extra = "") {
    const div = document.createElement("div");
    div.className = "bubble" + (who === "你" ? " user" : "");
    div.innerHTML = '<div class="speaker">' + escape(who) + '</div>' + escape(text) + extra;
    el("messages").appendChild(div);
    el("messages").scrollTop = el("messages").scrollHeight;
  }
  function draft() {
    published = false;
    el("flow-state").textContent = "未保存草稿";
    el("flow-state").className = "tag";
  }
  function render() {
    const display = pending ? pending.nodes : nodes;
    el("nodes").innerHTML = display.map((n, i) => (
      (i ? '<div class="line"></div>' : "") +
      '<button class="node' + (n.boundary ? " boundary" : "") + (selected === n.id ? " selected" : "") +
      (pending && !nodes.some((old) => old.id === n.id) ? " proposed" : "") +
      (n.status === "success" ? " done" : "") + '" data-node="' + escape(n.id) + '">' +
      '<span class="node-icon">' + (n.id === "start" ? "▷" : n.id === "output" ? "✓" : "A") +
      '</span><span class="n-name">' + escape(n.name) + '</span><small>' +
      escape(n.desc) + '</small><small>' +
      (n.id === "fetch" && !bound ? '<span class="tag warn">待选择数据源</span>' :
        n.status === "success" ? '<span class="tag green">试运行成功</span>' :
        n.boundary ? '<span class="tag green">边界</span>' : '<span class="tag">Agent</span>') + '</small></button>'
    )).join("");
    el("canvas-state").textContent = pending ? "候选修改 · 待应用" : created ? (verified === revision ? "当前版本已验证" : "草稿 · 待验证") : "等待描述目标";
    el("send").textContent = created ? "提出修改 ↑" : "生成工作流 ↑";
    el("save").disabled = !created || !!pending;
    el("run").disabled = !created || !!pending;
    el("publish").disabled = !created || !!pending || verified !== revision || published;
    el("undo").disabled = !history.length || !!pending;
    el("context").textContent = selected ? "已选节点 · 本演示修改范围为整个流程" : "作用范围：整个流程";
    const node = nodes.find((n) => n.id === selected);
    if (!node || node.boundary || pending) {
      el("properties").classList.add("hidden");
      return;
    }
    el("properties").classList.remove("hidden");
    el("properties").innerHTML = '<h4>' + escape(node.name) + ' · 节点配置</h4><p>职责：' +
      escape(node.desc) + '</p><p>输入：任务目标与上游步骤产出</p><p>产出：' +
      escape(node.result || "任务结果与可引用证据") + '</p><p>能力：' +
      escape(node.tools || "使用任务所需的已有能力") + '</p>' +
      (node.id === "fetch" ? '<label class="small" for="datasource">只读数据源（演示资源）</label><select id="datasource"><option value="">请选择数据源</option><option value="demo"' + (bound ? " selected" : "") + '>业务库（示例）</option></select>' : "") +
      '<button id="ask-node">把该节点带入对话</button>';
  }
  function proposal(prompt) {
    if (pending) {
      notice("请先应用或放弃当前候选，再提出下一项修改。", true);
      return;
    }
    bubble("你", prompt);
    if (/失败/.test(prompt)) {
      bubble("生成助手", "本次模拟生成失败，输入和现有画布已保留。可以重试或继续手动编辑。");
      notice("失败场景：原工作流未发生变化。", true);
      return;
    }
    if (/并行|循环|分支/.test(prompt)) {
      bubble("生成助手", "首版仅支持顺序执行。这个请求需要额外的编排语义；请先确认串行方案是否满足目标，或保留需求等待后续支持。");
      notice("未将不支持的编排静默转换为串行。", true);
      return;
    }
    if (/写库|删除数据|执行DDL|发消息/.test(prompt)) {
      bubble("生成助手", "该任务包含首版尚不支持的外部操作。当前仅可设计读取、分析与报告流程，不能运行或发布包含这类操作的工作流。");
      notice("未生成包含首版不支持操作的可运行流程。", true);
      return;
    }
    if (!created) {
      topic = /巡检|数据库|慢查询/.test(prompt) ? "db" : "sales";
      nodes = [
        initial()[0],
        { id: "fetch", name: topic === "db" ? "采集 Agent" : "取数 Agent", desc: topic === "db" ? "采集数据库与慢查询证据" : "读取本月与上月销售数据，明确口径", tools: "只读数据查询", result: "数据、查询口径、缺口" },
        { id: "analysis", name: topic === "db" ? "诊断 Agent" : "分析 Agent", desc: topic === "db" ? "根据采集证据诊断风险与原因" : "按地区归因，列出结论和数据证据", tools: "受控计算能力", result: "结论、证据与不确定性" },
        { id: "visual", name: "图表 Agent", desc: "将已有分析结果生成图表", tools: "图表产物生成", result: "图表与说明" },
        { id: "report", name: "报告 Agent", desc: "汇总证据、图表与行动建议", tools: "报告产物生成", result: "完整报告与证据引用" },
        initial()[1],
      ];
      created = true; revision++; verified = null; draft();
      el("flow-title").textContent = topic === "db" ? "数据库健康诊断" : "销售下降归因分析";
      bubble("生成助手", "已生成四个业务 Agent 的顺序流程。取数 → 分析 → 图表 → 报告。数据源仍需你选择；配置之前不会执行查询。");
      notice("结构已生成。点击取数或采集 Agent，绑定示例数据源后可试运行。");
      render();
      return;
    }
    let next = nodes.map((n) => ({ ...n, status: undefined }));
    let summary;
    if (/复核|审核|检查结论/.test(prompt)) {
      if (next.some((n) => n.id === "review")) {
        bubble("生成助手", "流程已包含复核 Agent。可以描述希望调整的检查要求。");
        notice("未重复新增相同职责的 Agent。");
        return;
      }
      next.splice(next.findIndex((n) => n.id === "visual"), 0, {
        id: "review", name: "复核 Agent", desc: "检查分析结论是否有数据证据支持", tools: "上游证据核对", result: "核对结果与结论修正建议",
      });
      summary = "新增 1 个复核 Agent，位于分析后、图表前；其余职责和资源保持不变。";
    } else if (/简洁|精简|摘要/.test(prompt)) {
      next = next.map((n) => n.id === "report" ? { ...n, desc: "生成简洁摘要，保留证据和行动建议" } : n);
      summary = "修改报告 Agent 的输出要求为简洁摘要，保留证据和行动建议。";
    } else {
      bubble("生成助手", "演示支持“增加复核 Agent”和“让报告更简洁”两种修改，可使用快捷示例体验。真实产品会由模型根据当前流程解释和生成修改。");
      notice("本原型仅演示固定交互，未对这条请求生成修改。");
      return;
    }
    pending = { nodes: next, revision };
    bubble("生成助手", "建议修改如下。请审阅画布中的候选结果，再决定是否应用。",
      '<div class="change-card"><p>' + escape(summary) + '</p><button data-change="apply" class="primary">应用修改</button><button data-change="discard">放弃</button></div>');
    notice("候选尚未改变当前草稿。应用后需要重新试运行。");
    render();
  }
  el("send").addEventListener("click", () => {
    const prompt = el("prompt").value.trim();
    if (!prompt) { notice("请描述想完成的任务或修改目标。", true); return; }
    proposal(prompt);
    el("prompt").value = "";
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => {
    el("prompt").value = button.dataset.prompt;
    el("prompt").focus();
  }));
  el("nodes").addEventListener("click", (event) => {
    const button = event.target.closest("[data-node]");
    if (!button) return;
    if (pending) { notice("请先应用或放弃候选，再编辑节点配置。", true); return; }
    selected = button.dataset.node; render();
  });
  el("properties").addEventListener("change", (event) => {
    if (event.target.id !== "datasource") return;
    bound = event.target.value === "demo"; revision++; verified = null;
    nodes = nodes.map((n) => ({ ...n, status: undefined })); draft();
    notice(bound ? "示例只读数据源已绑定。当前草稿可试运行。" : "已清除数据源，试运行前需要重新选择。", !bound);
    render();
  });
  el("properties").addEventListener("click", (event) => {
    if (event.target.id !== "ask-node") return;
    const node = nodes.find((n) => n.id === selected);
    el("prompt").value = "调整“" + node.name + "”：";
    el("prompt").focus();
    notice("节点名称已带入输入。完整产品支持显式选择节点局部作用范围。");
  });
  el("messages").addEventListener("click", (event) => {
    const action = event.target.closest("[data-change]");
    if (!action) return;
    if (!pending) { notice("该候选已处理，不能重复应用。", true); return; }
    if (action.dataset.change === "apply") {
      if (pending.revision !== revision) { notice("候选已过期，请基于当前草稿重新生成。", true); return; }
      history.push({ nodes: nodes.map((n) => ({ ...n })), bound });
      nodes = pending.nodes; revision++; verified = null; draft();
      bubble("生成助手", "修改已应用，可继续调整或重新试运行。");
      notice("当前草稿已更新；旧验证结果已失效。");
    } else {
      bubble("生成助手", "已放弃候选，当前工作流保持原样。");
      notice("候选已放弃。");
    }
    pending = null; render();
  });
  el("undo").addEventListener("click", () => {
    const old = history.pop();
    if (!old) return;
    nodes = old.nodes.map((n) => ({ ...n, status: undefined })); bound = old.bound;
    revision++; verified = null; selected = null; draft(); render();
    notice("已撤销最近一次应用的修改，请重新试运行当前版本。");
  });
  el("run").addEventListener("click", () => {
    if (!bound) {
      selected = "fetch"; render();
      notice("试运行被阻止：取数 Agent 尚未绑定只读数据源。", true);
      bubble("生成助手", "请先为取数 Agent 选择数据源，才能验证这条流程。");
      return;
    }
    verified = revision;
    nodes = nodes.map((n) => ({ ...n, status: "success" }));
    bubble("试运行", "模拟试运行成功：每个 Agent 已完成交接，最终报告可查看。实际产品会展示真实输入、调用摘要和产物。");
    notice("当前版本模拟验证成功，可以发布。此演示未调用真实模型与工具。");
    render();
  });
  el("save").addEventListener("click", () => {
    el("flow-state").textContent = "已保存草稿（模拟）";
    notice("草稿保存状态已模拟展示；本演示不会向产品写入数据。");
  });
  el("publish").addEventListener("click", () => {
    if (verified !== revision || pending) return;
    published = true;
    el("flow-state").textContent = "已发布（模拟）";
    el("flow-state").className = "tag green";
    bubble("生成助手", "发布状态已模拟展示。正式产品发布后，工作流可从任务对话中复用。");
    notice("演示闭环完成。没有调用真实发布接口。");
    render();
  });
  el("reset").addEventListener("click", reset);
  function reset() {
    nodes = initial(); pending = null; history = []; selected = null;
    revision = 0; verified = null; bound = false; created = false; published = false;
    el("messages").textContent = ""; el("prompt").value = "";
    el("flow-title").textContent = "未命名流程"; el("flow-state").textContent = "未创建";
    el("flow-state").className = "tag";
    bubble("生成助手", "描述你想完成的任务，我会拆解 Agent 职责、生成编排，并提示需要补齐的能力和资源。可先体验下方销售分析示例。");
    notice("可体验：生成 → 点击取数 Agent 绑定数据源 → 增加复核 → 应用修改 → 试运行 → 发布。");
    render();
  }
  reset();
})();
