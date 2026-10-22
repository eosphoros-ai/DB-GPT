# 场景套件（专家套件）落表设计

> v1.0 · 2026-10-22 · 配套：`scenario-suite-impl-plan.md`（T2 registry）、`data-agent-product-design.md` §5
> 目标库：DB-GPT 元数据库（`pilot/meta_data/dbgpt.db` SQLite / 生产 MySQL），沿用 `dbgpt_serve_*` 表族与 `Model`/`BaseDao` 约定。

---

## 一、落表原则（先立规矩，避免过度建表）

改造方案已定调：**「套件包本身就是存储，registry 只记安装态与 pin」**。据此划清「落表 / 不落表」边界：

| 数据 | 落不落表 | 存哪 | 理由 |
|---|---|---|---|
| 套件内容（sop/skills/few_shots/README/templates） | ❌ 不落表 | 套件包目录 / zip（对象存储） | 包即权威源，可 diff/回滚/git 化；落表=把文件塞进 blob，治理口子失守 |
| 安装态 / 启用停用 / 版本 | ✅ 落表 | `dbgpt_serve_plugins` | registry 的本体，按工作空间(实例)级生效 |
| 首页渲染投影（Tab/推荐问题/路由词/命令） | ✅ 落表（派生缓存） | `dbgpt_serve_plugins.manifest_snapshot`(JSON) | GET /suites 不必每次读盘解包；**可从包重建**，等同语义层「派生索引」哲学 |
| 安装/启用/切换/升级/pin 审计 | ✅ 落表 | `dbgpt_serve_plugins_event` | 回答「这次结论是哪个套件版本跑出来的」，支撑按套件版本审计（§5.3） |
| 市场目录（可安装的套件清单） | ✅ 落表（P2） | `dbgpt_serve_plugins_hub` | 对标现有 `plugin_hub`；P0 三官方套件走内置包路径，可暂不启用 |
| 会话 pin（slug@version） | ❌ 不落新表 | 复用 `chat_history`/对话的 `ext_info.suite` | 与 `harness_engine` 按请求覆盖同机制（§4.4）；切换动作写 `plugins_event` |
| approval_overrides 策略 | ❌ 不落新表 | 留在 manifest；bind 时合并进现有 `approval_policy_*` | 合并顺序 core deny > suite > core default；enforcement 在核心 gate（§5.4），套件只声明 |
| recommended_questions | ❌ 不落新表 | manifest（投影进 snapshot） | 若要接入现有 `recommend_question` 表，做**单向同步**（可选，P1） |
| semantic proposals（套件播种的指标草稿） | ❌ 不落套件表 | 进语义层「待审队列」表 | 归属语义层治理面，批准权在语义层不在套件 |

一句话：**三张新表**（P0 建 `dbgpt_serve_plugins` + `dbgpt_serve_plugins_event`，P2 建 `dbgpt_serve_plugins_hub`），其余全部复用现有表或留在包内。

**命名决议（2026-10-22 定稿）**：serve 模块目录与表名**统一为 plugins**——`packages/dbgpt-serve/src/dbgpt_serve/plugins/` + `dbgpt_serve_plugins*` 三表，对齐产品左栏"专家套件/Plugins"模块名与 AntWork 插件词汇；与 dbgpts 既有 `my_plugin` / `plugin_hub` 靠 `dbgpt_serve_` 前缀区分。**领域对象在包/manifest 层仍称 suite**（`suite.yaml` / `kind: scenario-suite` / 包目录 `assets/suites/` / Entity 类名 `SuiteEntity`），即"包叫 suite、库表叫 plugins"，二者一一映射不混用。

---

## 二、表结构总览（ER）

```
                     ┌───────────────────────────┐
   套件包(磁盘/zip)   │   dbgpt_serve_plugins     │  安装态注册表(工作空间级)
   suite.yaml ──────▶│   slug+version+status     │◀── 首页/路由/绑定读 manifest_snapshot
   skills/           │   manifest_snapshot(JSON) │
   prompts/          └───────────┬───────────────┘
   (权威源,不落表)                 │ 1:N 审计
                                  ▼
                     ┌───────────────────────────┐        复用(不新建)
                     │ dbgpt_serve_plugins_event │   ┌─▶ approval_policy_rule/setting/log
                     │  install/enable/switch/   │   │   (approval_overrides 合并进此)
                     │  upgrade/pin/uninstall    │   │
                     └───────────────────────────┘   ├─▶ chat_*.ext_info.suite = slug@version
                                                     │   (会话 pin, 按请求覆盖)
   市场(P2)          ┌───────────────────────────┐   │
                     │  dbgpt_serve_plugins_hub  │   └─▶ recommend_question (可选单向同步)
                     │  对标 plugin_hub          │
                     └───────────────────────────┘
```

---

## 三、P0 表一：`dbgpt_serve_plugins`（安装/启用注册表）

对标 `my_plugin`（dbgpts/my），记录「哪个工作空间装了哪个套件的哪个版本、启没启用」。**内容不在这，在包里**。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK, autoincrement | 自增主键 |
| `name` | String(255) | NOT NULL | 套件 slug（`db-query`/`db-analysis`/`db-ops`），对应 manifest.name |
| `display` | String(255) | | 显示名（智能取数） |
| `icon` | String(64) | | 图标（🔍/📊/🛠️） |
| `scenario_id` | String(64) | index | query/analysis/ops，供首页 Tab 与路由分组 |
| `version` | String(64) | NOT NULL | 已安装/生效版本（对话 pin 的取值来源） |
| `source` | String(32) | NOT NULL, default `official` | official / enterprise / market |
| `execution` | String(16) | default `react` | react / flow(P1)，冗余自 manifest 便于列表筛选 |
| `status` | String(16) | NOT NULL, default `installed` | installed / enabled / disabled |
| `workspace_id` | String(128) | index, nullable | 工作空间(实例)级启用范围；NULL = 全局。对齐 §5.7「启用按工作空间级生效」 |
| `package_path` | String(512) | | 套件包在磁盘/对象存储的路径（权威源指针） |
| `package_digest` | String(64) | | 包 sha256，用于完整性校验与「包变更→版本漂移」检测 |
| `manifest_snapshot` | Text(JSON) | | **派生缓存**：从 suite.yaml 投影的可渲染字段（见下），可从包重建 |
| `use_count` | Integer | default 0 | 累计被 pin/调用次数（对齐 my_plugin.use_count） |
| `enabled_at` | DateTime | nullable | 最近启用时间 |
| `user_name` | String(255) | nullable | 安装人/负责人 |
| `sys_code` | String(128) | index, nullable | 系统码（沿用全局约定） |
| `gmt_created` | DateTime | default utcnow | 安装时间 |
| `gmt_modified` | DateTime | onupdate utcnow | 更新时间 |

**约束**：`UniqueConstraint("workspace_id", "name", name="uk_plugins_ws_name")` —— 同一工作空间同一套件只保留一条生效记录（升级=改 version+写 event，不并存多行；多版本历史查 `plugins_event`）。

**`manifest_snapshot` JSON 结构**（loader 解包后投影，仅放「首页/路由/绑定」要用的只读字段，不放 sop 全文）：

```json
{
  "routing": {"keywords": ["查", "统计", "导出", "GMV", "客单价", "top", "环比", "明细"]},
  "recommended_questions": [
    {"text": "查询上月各区域销售额", "hint": "按 region 汇总，含环比"}
  ],
  "commands": ["/nl2sql", "/schema", "/metric", "/export"],
  "tools": {"allow": ["semantic_search","schema_link","nl2sql","sql_execute","export_csv"], "deny": ["ddl","shell"]},
  "approval_overrides": [{"match": {"tool":"sql_execute","est_scan_gb":">100"}, "action":"confirm","reason":"高代价扫描"}],
  "artifacts": ["sql_card","result_table","citation"],
  "context_defaults": {"semantic_model":"required","datasource":"session"},
  "semantic": {"layer":"mysql_prod","require":"required","consumption":"metric_first","pin":{"policy":"latest_published"}},
  "skills": ["semantic-linking","nl2sql-precision","readonly-guardrails","result-export"],
  "output_contract": "result_set+sql"
}
```

> 为何要这份 snapshot 而不是每次读包：GET /suites（首页 Tab、推荐问题、自动路由关键词、套件详情 manifest 关键值）是高频只读，读盘解包+YAML 解析代价高；snapshot 是**可重建的派生投影**，安装/升级时由 loader 写入，包变更时按 `package_digest` 触发重建。与语义层「结构化权威源 + KB 派生索引」同一套哲学。

---

## 四、P0 表二：`dbgpt_serve_plugins_event`（审计/timeline 事件）

支撑 §5.3「审计可回答这次结论是哪个插件版本跑出来的」与 §4.2 切换=一条 timeline 事件。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK, autoincrement | |
| `suite_name` | String(255) | NOT NULL, index | 套件 slug |
| `event_type` | String(32) | NOT NULL, index | install / enable / disable / uninstall / upgrade / switch / pin |
| `from_version` | String(64) | nullable | 升级/切换前版本 |
| `to_version` | String(64) | nullable | 升级/切换后版本 |
| `conv_uid` | String(128) | index, nullable | 关联对话（switch/pin 事件必填；install/enable 为空） |
| `workspace_id` | String(128) | index, nullable | 工作空间 |
| `detail` | Text(JSON) | nullable | 事件载荷，如 `{"from":"db-query@1.0.0","to":"db-ops@1.0.0","reason":"跨场景:这数为什么不对"}` |
| `user_name` | String(255) | nullable | 操作人 |
| `sys_code` | String(128) | index, nullable | |
| `gmt_created` | DateTime | default utcnow, index | 事件时间 |

**典型写入**：
- 安装官方套件 → `install`（to_version=1.0.0）
- 首页启用 → `enable`；停用 → `disable`
- 对话创建 pin → `pin`（conv_uid + to_version）
- 会话内切换场景 → `switch`（conv_uid + from/to），同时更新对话 `ext_info.suite`，历史轮保留旧 pin
- 升级 → `upgrade`（from/to），仅影响新对话（旧对话 pin 不漂移，§五风险）

---

## 五、P2 表三：`dbgpt_serve_plugins_hub`（市场目录）

对标现有 `plugin_hub`，P0 可不建（三官方套件走内置包路径）。列沿用 plugin_hub：

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | Integer PK | |
| `name` | String(255) unique NOT NULL | slug |
| `display` / `icon` / `description` | String | 卡片展示 |
| `author` / `email` | String(255) | 作者（企业专属 = 租户） |
| `type` | String(255) | 固定 `scenario-suite` |
| `version` | String(255) | 市场最新版本 |
| `category` / `tags` | String / Text(JSON) | 分组（官方内置/企业专属/市场）与标签 |
| `readme` | Text | 详情页 README |
| `storage_channel` / `storage_url` / `download_param` | String(255) | 下载渠道（对齐 plugin_hub） |
| `visibility` | String(32) | public / enterprise / private |
| `download_count` / `installed` | Integer | 热度与已安装计数 |
| `gmt_created` / `gmt_modified` | DateTime | |

**约束**：`UniqueConstraint("name", "version", name="uk_plugins_hub")`。

---

## 六、与现有表的关系（复用，不重造）

| 现有表 | 复用方式 |
|---|---|
| `approval_policy_rule` / `approval_policy_setting` / `approval_policy_log`（`api_v1/approval_policy.py`） | 套件 `approval_overrides` 在**会话 bind 期**由 `merge_suite_overrides(policy, suite)` 合并进 policy（仅加严），gate 执行期不感知套件；合并结果与决议写既有 `tool_approval_log`/`approval_policy_log`。**不新建审批表** |
| 对话表 `ext_info`（`chat_*` / `gpts_conversations`） | 会话 pin 写 `ext_info.suite = "db-query@1.0.0"`，与 `harness_engine` 按请求覆盖同机制；切换=新轮 ext_info + 一条 `plugins_event` |
| `recommend_question` | 可选：安装/升级时把 snapshot.recommended_questions **单向同步**进此表供首页统一读取（P1，非必须；P0 直接从 snapshot 读） |
| `my_plugin` / `plugin_hub`（dbgpts） | **不复用其表**，仅对标其 Entity/Dao 写法与列约定。语义不同：dbgpts 是单个 agent/command/flow 包，suite 是「会话级配置束（含 N 技能）」（§5.5 边界）。命名区分靠 `dbgpt_serve_` 前缀：`dbgpt_serve_plugins*`（本模块）vs `my_plugin`/`plugin_hub`（dbgpts） |

---

## 七、Entity / Dao 代码骨架（对齐 dbgpts/my 写法）

`packages/dbgpt-serve/src/dbgpt_serve/plugins/config.py`：

```python
APP_NAME = "plugins"                      # serve app / 产品模块名（左栏"专家套件"）
SERVE_APP_NAME = "dbgpt_serve_plugins"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Plugins"
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
SERVER_APP_TABLE_NAME = SERVE_APP_NAME                # dbgpt_serve_plugins（安装/启用注册表）
SERVER_EVENT_TABLE_NAME = f"{SERVE_APP_NAME}_event"   # dbgpt_serve_plugins_event（审计/timeline）
SERVER_HUB_TABLE_NAME = f"{SERVE_APP_NAME}_hub"       # dbgpt_serve_plugins_hub（市场目录, P2）
```

`plugins/models/models.py`：

```python
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint, Index
from dbgpt.storage.metadata import BaseDao, Model
from ..config import SERVER_APP_TABLE_NAME, SERVER_EVENT_TABLE_NAME


class SuiteEntity(Model):
    __tablename__ = SERVER_APP_TABLE_NAME
    id = Column(Integer, primary_key=True, comment="autoincrement id")
    name = Column(String(255), nullable=False, comment="suite slug, e.g. db-query")
    display = Column(String(255), nullable=True, comment="display name")
    icon = Column(String(64), nullable=True, comment="icon emoji")
    scenario_id = Column(String(64), index=True, nullable=True, comment="query|analysis|ops")
    version = Column(String(64), nullable=False, comment="installed/active version")
    source = Column(String(32), nullable=False, default="official", comment="official|enterprise|market")
    execution = Column(String(16), nullable=True, default="react", comment="react|flow(P1)")
    status = Column(String(16), nullable=False, default="installed", comment="installed|enabled|disabled")
    workspace_id = Column(String(128), index=True, nullable=True, comment="instance-level scope; NULL=global")
    package_path = Column(String(512), nullable=True, comment="package location (source of truth)")
    package_digest = Column(String(64), nullable=True, comment="sha256 of package for drift detect")
    manifest_snapshot = Column(Text, nullable=True, comment="derived JSON projection, rebuildable")
    use_count = Column(Integer, nullable=True, default=0, comment="pin/invoke count")
    enabled_at = Column(DateTime, nullable=True, comment="last enabled time")
    user_name = Column(String(255), nullable=True, comment="installer/owner")
    sys_code = Column(String(128), index=True, nullable=True, comment="system code")
    gmt_created = Column(DateTime, default=datetime.utcnow, comment="install time")
    gmt_modified = Column(DateTime, default=datetime.now, onupdate=datetime.utcnow, comment="update time")
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uk_plugins_ws_name"),)


class SuiteEventEntity(Model):
    __tablename__ = SERVER_EVENT_TABLE_NAME
    id = Column(Integer, primary_key=True, comment="autoincrement id")
    suite_name = Column(String(255), nullable=False, index=True, comment="suite slug")
    event_type = Column(String(32), nullable=False, index=True, comment="install|enable|disable|uninstall|upgrade|switch|pin")
    from_version = Column(String(64), nullable=True)
    to_version = Column(String(64), nullable=True)
    conv_uid = Column(String(128), index=True, nullable=True, comment="for switch/pin events")
    workspace_id = Column(String(128), index=True, nullable=True)
    detail = Column(Text, nullable=True, comment="JSON payload")
    user_name = Column(String(255), nullable=True)
    sys_code = Column(String(128), index=True, nullable=True)
    gmt_created = Column(DateTime, default=datetime.utcnow, index=True)


class SuiteDao(BaseDao[SuiteEntity, "ServeRequest", "ServeResponse"]):
    # from_request / to_request / to_response 三方法，写法照 dbgpts/my/models/models.py
    ...
```

---

## 八、DDL（MySQL 生产 / SQLite 开发各一份，便于 alembic 迁移）

```sql
-- MySQL
CREATE TABLE dbgpt_serve_plugins (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(255) NOT NULL COMMENT 'suite slug',
  display       VARCHAR(255) NULL,
  icon          VARCHAR(64)  NULL,
  scenario_id   VARCHAR(64)  NULL,
  version       VARCHAR(64)  NOT NULL,
  source        VARCHAR(32)  NOT NULL DEFAULT 'official',
  execution     VARCHAR(16)  NULL DEFAULT 'react',
  status        VARCHAR(16)  NOT NULL DEFAULT 'installed',
  workspace_id  VARCHAR(128) NULL,
  package_path  VARCHAR(512) NULL,
  package_digest VARCHAR(64) NULL,
  manifest_snapshot TEXT NULL,
  use_count     INT NULL DEFAULT 0,
  enabled_at    DATETIME NULL,
  user_name     VARCHAR(255) NULL,
  sys_code      VARCHAR(128) NULL,
  gmt_created   DATETIME DEFAULT CURRENT_TIMESTAMP,
  gmt_modified  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_plugins_ws_name (workspace_id, name),
  KEY idx_scenario (scenario_id), KEY idx_status (status), KEY idx_sys (sys_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE dbgpt_serve_plugins_event (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  suite_name   VARCHAR(255) NOT NULL,
  event_type   VARCHAR(32)  NOT NULL,
  from_version VARCHAR(64)  NULL,
  to_version   VARCHAR(64)  NULL,
  conv_uid     VARCHAR(128) NULL,
  workspace_id VARCHAR(128) NULL,
  detail       TEXT NULL,
  user_name    VARCHAR(255) NULL,
  sys_code     VARCHAR(128) NULL,
  gmt_created  DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_suite (suite_name), KEY idx_event (event_type),
  KEY idx_conv (conv_uid), KEY idx_created (gmt_created)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 九、迁移与落地注意

- **迁移（P0 实际落地方式，2026-10-22）**：SQLite 开发库走 `_MODELS` 注册 + 启动期 `db.create_all()` 自动建表（`db_model_initialization.py` 已导入 `SuiteEntity`/`SuiteEventEntity`）；MySQL 生产库按仓库惯例手工执行 `assets/schema/dbgpt.sql` 中新增的两段 `CREATE TABLE IF NOT EXISTS`。**alembic revision 暂不手写**（仓库 versions 为 autogenerate 全量 dump，手写易撞 head），留待维护者下次统一 autogenerate 时带入；`plugins_hub`(P2) 留到 P2。启动默认跑 alembic upgrade 的行为不变（`dbgpt_server.py` 无 `--disable_alembic_upgrade` 参数——见既有踩坑记录）。
- **首次内置**：三官方套件随包出货，服务启动时由 loader 扫描 `assets/suites/*` → upsert 进 `dbgpt_serve_plugins`（source=official, status=enabled, workspace_id=NULL 全局），并写 `install` event（幂等：按 name+version+digest 判重）。
- **snapshot 重建**：安装/升级时 loader 写 snapshot；`package_digest` 变化即触发重建，保证首页投影与包一致。
- **索引**：`plugins(workspace_id,name)` 唯一 + `scenario_id/status/sys_code` 普通索引；`plugins_event(conv_uid/gmt_created)` 供对话回看与审计时间线查询。
- **多租户**：`sys_code` 沿用全局约定；`workspace_id` 承载 §5.7「实例级启用」。二者组合覆盖「企业专属套件仅本租户可见」。

---

## 十、验收（落表出口）

1. 服务启动后 `dbgpt_serve_plugins` 出现三行官方套件（status=enabled, workspace_id=NULL, snapshot 非空且可 JSON 解析）；
2. 首页 GET /suites 仅读 `dbgpt_serve_plugins`（不读盘）即可渲染 Tab/推荐问题/路由词/命令；
3. 启用/停用/切换/升级各写一条 `plugins_event`，且会话 pin 落在对话 `ext_info.suite`（不新建 pin 表）；
4. 审批合并只在 bind 期改内存 policy + 写既有 `*_approval_log`，`dbgpt_serve_plugins` 不存任何放宽后的策略；
5. 删除某套件包并重启 → registry 标记 disabled 且不报错（fail-soft，包缺失降级）。
