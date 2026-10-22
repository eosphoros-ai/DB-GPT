---
name: result-export
version: 1.0.0
description: Result set export to CSV / Excel. Use when the user needs to download / save / email a report, or when the preview hit max_rows (default 1000) and the full set must be persisted; enforces column-type fidelity, PII masking, and export row-count approval.
name_en: Result Export
name_zh: 结果集导出
description_en: Result set export to CSV / Excel with column-type fidelity, PII masking, and row-count approval. Preserves exact semantic calibration between preview and export.
description_zh: 结果集导出 CSV/Excel 技能。当用户需要把查询结果导出、下载、另存为文件、发报表，或结果行数超过对话预览上限（默认 1000 行）需要落盘获取全量时使用；处理列类型保真、敏感字段脱敏与导出行数上限审批。触发词：导出、下载、另存、CSV、Excel、xlsx、报表、明细导出、落盘、发我一份、全量数据。
user-invocable: true
argument-hint: Current result set or full-detail query to export (CSV/Excel)
argument-hint-en: Current result set or full-detail query to export (CSV/Excel)
argument-hint-zh: 当前结果集或全量明细（导出为 CSV / Excel）
---

# 结果集导出 (Result Export)

## 技能目标

把已执行的结果集（或按需重跑的全量查询）以 **CSV / Excel** 形式安全落盘交付，做到三件事：**列类型保真**（金额不丢精度、日期不变形、长数字不被科学计数法吃掉）、**敏感字段脱敏**（手机号/身份证/邮箱/银行卡按规则掩码）、**行数上限受控**（超阈值走审批 confirm）。

导出是问数链路的最后一环，**不改变口径**：导出用的 SQL 必须与预览用的 SQL 完全一致（同一指标版本、同一默认过滤、同一行级权限）。

## 核心工作流程

1. **确认导出对象**
   - 默认导出**当前会话最近一次结果集**（已在只读从库执行、已通过护栏）。
   - 若用户要"全量"（预览被 `max_rows` 截断），复用同一条已校验 SQL，仅去掉/放大 `LIMIT`；**不得**为此重写口径或去掉过滤条件。
   - 无最近结果集时，先走 `semantic-linking` → `nl2sql-precision` → `readonly-guardrails` 完整链路取数，再导出。

2. **敏感字段识别与脱敏**
   - 调 `guardrails.get_rules(scope=...)` 取脱敏规则（`masking_rules`），或 `metadata.get_table` 读列的敏感标记（`sensitivity: pii`）。
   - 常见处理：手机号 `138****5678`、身份证 `1101**********001X`、邮箱 `ab***@corp.com`、银行卡保留后 4 位、姓名保留姓氏。
   - **脱敏在导出阶段强制执行，不可由模型自行取消**；用户要求明文导出时拒绝，并说明需走权限变更审批（超出问数套件范围）。

3. **行数上限与审批判定**
   - 预估导出行数（`est_scan_rows` 或先 `SELECT COUNT(*)` 同口径计数）。
   - 命中 `approval_overrides` 的 `{tool: export_csv, row_count: ">100000"}` → **停止导出**，交核心审批 gate 弹 dock，告知预估行数、文件大小、脱敏范围与落盘位置，等待用户确认。
   - 未命中 → `auto` 放行。
   - 超过硬上限（如 100 万行）时建议改为分批导出或收窄时间窗，而不是无限放大。

4. **执行导出（`export_csv`）**
   - 调用参数：
     ```json
     export_csv(sql="<与预览一致的已校验 SQL>",
                format="csv",
                params={"current_tenant": "<会话身份>"},
                max_rows=100000,
                masking=["mobile","id_card","email","bank_card"],
                encoding="utf-8-sig",
                filename="valid_gmv_east_china_202609.csv",
                mode="readonly", route="replica", timeout=120)
     ```
   - `format`：`csv`（默认，通用）或 `xlsx`（需多 sheet / 表头样式 / 类型保留时）。
   - `encoding="utf-8-sig"`：带 BOM，避免 Excel 打开中文乱码。
   - `filename`：语义化命名（指标_维度_时间窗），便于用户归档。
   - 拿到：`{path, row_count, columns, bytes, masked_columns, truncated}`。

5. **列类型保真校验**
   - **金额**：`decimal(18,2)` 原样输出，不转 float、不四舍五入到整数；Excel 下设为数值/货币格式而非文本。
   - **日期时间**：统一 `YYYY-MM-DD HH:mm:ss`，不用本地化模糊格式。
   - **长数字串**（订单号、商品编码、身份证）：CSV 中前置防科学计数法处理（Excel 下设为文本格式），避免 `1.23457E+18`。
   - **NULL**：输出空字符串而非字面量 `NULL` / `None`，并在交付说明里注明。
   - **百分比**（如 `mom_pct`）：明确单位（`13.99` 表示 13.99%），列名带 `_pct` 后缀。

6. **交付与溯源**
   - 以文件卡形式交付，附一行摘要：口径（指标 + 版本）、时间窗、行数、脱敏列、执行库（只读从库）。
   - 引用溯源 chips 与预览保持一致（指标版本 / 表 / 样例 / 规则），保证"这份文件和对话里那个数是同一口径"。
   - 用户 👍 → 该 Q→SQL 沉淀进样例库；✏️ 纠错 → 进语义标注待审队列（不直接改权威源）。

## 完整流程示例

```
场景 A：导出当前预览结果（小数据量，auto 放行）

Step 1: 最近结果集 = 华东区上月有效GMV按渠道拆分（4 行）
Step 2: guardrails.get_rules → masking_rules: [mobile, id_card, email, bank_card]
        本结果集无 PII 列 → 无需脱敏
Step 3: row_count = 4 < 100000 → 未命中审批 override → auto
Step 4: export_csv(sql=<同一 SQL>, format="csv",
                   params={"current_tenant":"t_8821"},
                   encoding="utf-8-sig",
                   filename="valid_gmv_east_china_by_channel_202609.csv",
                   mode="readonly", route="replica", timeout=120)
  → {path:"/outputs/valid_gmv_east_china_by_channel_202609.csv",
     row_count:4, bytes:312, masked_columns:[], truncated:false}
Step 5: 类型校验 → valid_gmv_cur/prev 保留 2 位小数 ✅ mom_pct 单位说明 ✅
Step 6: 交付文件卡 + 摘要「指标 met_007 v2 · 2026-09 · 华东 · 4 行 · 只读从库」


场景 B：导出三年订单明细（大数据量，触发审批 + 脱敏）

用户：「把这三年的订单明细全量导出，要客户手机号」

Step 1: 复用已校验明细 SQL（含 status IN (1,2,3) / is_deleted = 0 / tenant_id 行级权限）
Step 2: metadata.get_table(orders) → mobile 标记 sensitivity: pii → 强制脱敏 mobile
Step 3: SELECT COUNT(*) 同口径 → 预估 12,400,000 行 > 100000
        → 命中 {tool: export_csv, row_count: ">100000"} → 停止，弹审批 dock：
          「大批量导出确认 · 预估 1240 万行 · 约 1.9 GB · 脱敏列：mobile · 落盘 /outputs/」
          动作：[确认导出] [取消] [收窄到近 3 个月]
Step 5': 用户选「收窄到近 3 个月」→ 重写时间窗（口径不变）→ 预估 86 万行
         → 仍 > 10 万 → 二次确认 → 用户批准
Step 4': export_csv(sql=<收窄后 SQL>, format="xlsx", max_rows=1000000,
                    masking=["mobile"], encoding="utf-8-sig",
                    filename="order_items_detail_202607-202609.xlsx",
                    mode="readonly", route="replica", timeout=600)
  → {path:"/outputs/order_items_detail_202607-202609.xlsx", row_count:861342,
     masked_columns:["mobile"], truncated:false}
Step 5': 类型校验 → order_id 长数字设为文本格式（防科学计数法）✅
         paid_at 统一 YYYY-MM-DD HH:mm:ss ✅ amount decimal 保真 ✅
Step 6': 交付 + 摘要「明细导出 · 2026-07~09 · 861,342 行 · mobile 已脱敏 · 只读从库」
```

## 注意事项

- **口径不可漂移**：导出 SQL 必须与预览 SQL 完全一致（同指标版本、同默认过滤、同行级权限）。为"导出全量"而删掉 `status IN (1,2,3)` 或 `is_deleted = 0` 是严重错误——那会导出退款单与已删除单。
- **脱敏不可关闭**：PII 列的掩码由规则强制，模型与用户均不能在会话内取消；明文需求走权限变更审批（不在问数套件范围）。
- **行级权限照旧**：`tenant_id = :current_tenant` 必须在导出 SQL 中，防止跨租户数据落盘外泄。
- **只读通道**：导出同样走 `mode="readonly"` + `route="replica"`，不因为"要跑很久"而切主库。
- **别撑爆对话**：需要大结果集时用导出，而不是把预览 `max_rows` 调到十万级。
- **CSV 中文乱码**：统一 `utf-8-sig`（带 BOM），否则 Excel 直开乱码。
- **长数字陷阱**：订单号/商品编码/身份证在 CSV 里易被 Excel 转科学计数法并丢精度，须按文本处理。
- **文件名语义化**：`指标_维度_时间窗.扩展名`，避免 `export(1).csv` 这类无信息命名。
- **超时设置**：导出耗时长，`timeout` 应高于预览（如 120~600s）；超时后提示分批或收窄，不静默重试。
- **交付要说清边界**：明确告知行数、时间窗、脱敏列、是否截断，避免用户把样本当全量下结论。
