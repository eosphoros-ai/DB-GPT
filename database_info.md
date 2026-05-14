# game_analytics 数据库文档

## 概述

游戏业务测试数据库，覆盖用户、充值、登录、对局、道具、背包、虚拟货币、公会、好友、成就、每日统计、活动等核心业务场景，共 15 张表，约 33 万行数据。

## 数据库连接信息

| 项目 | 值 |
|------|-----|
| 数据库名 | `game_analytics` |
| 类型 | MySQL 8.0 (Docker) |
| Host | 127.0.0.1:3306 |
| 用户 | root |

## 表清单及数据量

| # | 表名 | 说明 | 行数 |
|---|------|------|------|
| 1 | `game_users` | 游戏用户表 | 1,500 |
| 2 | `game_login_logs` | 登录日志表 | 52,613 |
| 3 | `game_recharge_orders` | 充值订单表 | 22,599 |
| 4 | `game_play_sessions` | 游戏对局记录表 | 134,831 |
| 5 | `game_items` | 游戏道具定义表 | 180 |
| 6 | `game_user_inventory` | 用户背包表 | 18,125 |
| 7 | `game_virtual_currency_transactions` | 虚拟货币变动流水表 | 90,108 |
| 8 | `game_guilds` | 公会表 | 45 |
| 9 | `game_guild_members` | 公会成员表 | 1,709 |
| 10 | `game_friends` | 好友关系表 | 7,691 |
| 11 | `game_achievements` | 成就定义表 | 60 |
| 12 | `game_user_achievements` | 用户成就表 | 5,431 |
| 13 | `game_user_daily_stats` | 用户每日统计表 | 14,868 |
| 14 | `game_events` | 活动表 | 28 |
| 15 | `game_event_participation` | 活动参与记录表 | 2,185 |

**总计：约 351,973 行**

---

## 1. game_users（游戏用户表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | BIGINT PK | 用户ID，自增主键 |
| `username` | VARCHAR(50) | 用户名 |
| `nickname` | VARCHAR(100) | 昵称 |
| `email` | VARCHAR(100) | 邮箱 |
| `phone` | VARCHAR(20) | 手机号 |
| `register_date` | DATETIME | 注册时间 |
| `channel` | VARCHAR(30) | 注册渠道：appstore, googleplay, taptap, official, huawei, xiaomi, bilibili, steam |
| `device_type` | VARCHAR(20) | 设备类型：iPhone 14 Pro, Samsung Galaxy S24 等 |
| `device_model` | VARCHAR(50) | 设备型号 |
| `os_version` | VARCHAR(20) | 操作系统版本：iOS 17.4, Android 14, HarmonyOS 4 等 |
| `region` | VARCHAR(20) | 地区：CN, US, JP, KR, TW, SEA, EU |
| `age_group` | VARCHAR(10) | 年龄段：<18, 18-24, 25-34, 35-44, 45+ |
| `gender` | CHAR(1) | 性别：M/F/U |
| `vip_level` | TINYINT | VIP等级 0-10 |
| `total_recharge` | DECIMAL(12,2) | 累计充值金额 |
| `total_virtual_currency` | BIGINT | 累计获得虚拟币 |
| `total_play_seconds` | BIGINT | 累计游戏时长(秒) |
| `last_login` | DATETIME | 最后登录时间 |
| `account_status` | VARCHAR(20) | 账号状态：active, inactive, banned, deleted |

**索引**：`idx_register_date`, `idx_region`, `idx_vip`, `idx_channel`

---

## 2. game_login_logs（登录日志表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `log_id` | BIGINT PK | 日志ID |
| `user_id` | BIGINT | 用户ID |
| `login_time` | DATETIME | 登录时间 |
| `logout_time` | DATETIME | 登出时间 |
| `session_duration_seconds` | INT | 会话时长(秒) |
| `ip_address` | VARCHAR(45) | IP地址 |
| `device_id` | VARCHAR(64) | 设备唯一标识 |
| `login_type` | VARCHAR(20) | 登录方式：账号密码, 手机号, 微信, QQ, AppleID |
| `client_version` | VARCHAR(20) | 客户端版本 |
| `sdk_version` | VARCHAR(20) | SDK版本 |

**索引**：`idx_user_login`, `idx_login_time`

---

## 3. game_recharge_orders（充值订单表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_id` | BIGINT PK | 订单ID |
| `user_id` | BIGINT | 用户ID |
| `order_no` | VARCHAR(64) UNIQUE | 订单号 |
| `amount` | DECIMAL(10,2) | 订单金额 |
| `currency_type` | VARCHAR(10) | 货币类型，默认 CNY |
| `pay_method` | VARCHAR(30) | 支付方式：alipay, wechat, apple_iap, google_play, credit_card, paypal |
| `product_id` | VARCHAR(50) | 商品ID |
| `product_name` | VARCHAR(100) | 商品名：6元礼包, 30元礼包, 月卡, 通行证, 首充礼包 等 |
| `product_type` | VARCHAR(20) | 商品类型：diamond, monthly_card, battle_pass, first_recharge, gift_pack |
| `virtual_currency_amount` | INT | 获得虚拟币数量 |
| `order_status` | VARCHAR(20) | 订单状态：pending, success, failed, refunded |
| `create_time` | DATETIME | 创建时间 |
| `pay_time` | DATETIME | 支付时间 |
| `complete_time` | DATETIME | 完成时间 |
| `channel_order_id` | VARCHAR(100) | 渠道订单号 |
| `discount_amount` | DECIMAL(10,2) | 折扣金额 |
| `actual_amount` | DECIMAL(10,2) | 实付金额 |

**索引**：`idx_user_recharge`, `idx_order_status`, `idx_create_time`

---

## 4. game_play_sessions（游戏对局记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | BIGINT PK | 对局ID |
| `user_id` | BIGINT | 用户ID |
| `start_time` | DATETIME | 开始时间 |
| `end_time` | DATETIME | 结束时间 |
| `duration_seconds` | INT | 对局时长(秒) |
| `game_mode` | VARCHAR(30) | 游戏模式：ranked, casual, deathmatch, battle_royale, team_deathmatch, capture_flag, dungeon_raid, arena_pvp, guild_war, tower_defense |
| `map_name` | VARCHAR(50) | 地图名：Dragon Valley, Ice Fortress, Desert Oasis 等10张地图 |
| `character_id` | INT | 使用的角色ID |
| `character_name` | VARCHAR(50) | 角色名称：暗影刺客, 圣光骑士, 冰霜法师 等10个角色 |
| `team_size` | TINYINT | 队伍规模 1-5 |
| `is_team_game` | TINYINT | 是否组队 |
| `score` | INT | 得分 |
| `kills` | INT | 击杀数 |
| `deaths` | INT | 死亡数 |
| `assists` | INT | 助攻数 |
| `damage_dealt` | INT | 造成伤害 |
| `damage_taken` | INT | 承受伤害 |
| `healing_done` | INT | 治疗量 |
| `headshots` | INT | 爆头数 |
| `rank_position` | INT | 最终排名 |
| `total_players` | INT | 总玩家数 |
| `is_win` | TINYINT | 是否胜利 |
| `exp_gained` | INT | 获得经验 |
| `gold_earned` | INT | 获得金币 |
| `server_region` | VARCHAR(20) | 服务器区域 |
| `ping_ms` | INT | 网络延迟(ms) |

**索引**：`idx_user_session`, `idx_game_mode`, `idx_start_time`

---

## 5. game_items（游戏道具定义表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `item_id` | BIGINT PK | 道具ID |
| `item_name` | VARCHAR(100) | 道具名称（含稀有度前缀，如 `[LEGENDARY] 龙牙之刃`） |
| `item_type` | VARCHAR(30) | 道具类型：weapon, armor, skin, potion, pet, mount, emote, card, material, elixir |
| `rarity` | VARCHAR(10) | 稀有度：common, uncommon, rare, epic, legendary, mythic |
| `price_virtual_currency` | INT | 虚拟币价格 |
| `price_diamond` | INT | 钻石价格 |
| `price_real_currency` | DECIMAL(10,2) | 真实货币价格 |
| `max_stack` | INT | 最大堆叠数：1, 10, 50, 99, 999 |
| `is_tradeable` | TINYINT | 是否可交易 |
| `is_consumable` | TINYINT | 是否消耗品 |
| `description` | VARCHAR(500) | 描述 |

**索引**：`idx_item_type`, `idx_rarity`

---

## 6. game_user_inventory（用户背包表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `inventory_id` | BIGINT PK | 记录ID |
| `user_id` | BIGINT | 用户ID |
| `item_id` | BIGINT | 道具ID |
| `quantity` | INT | 数量 |
| `acquire_time` | DATETIME | 获取时间 |
| `acquire_method` | VARCHAR(30) | 获取方式：purchase, loot, craft, gift, reward, exchange |
| `source_desc` | VARCHAR(100) | 来源描述：商城购买, 副本掉落, 打造获得, 好友赠送, 活动奖励, 兑换获得 |
| `expire_time` | DATETIME | 过期时间（部分道具有时效） |

**索引**：`idx_user_items`, `idx_item_users`

---

## 7. game_virtual_currency_transactions（虚拟货币变动流水表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `txn_id` | BIGINT PK | 流水ID |
| `user_id` | BIGINT | 用户ID |
| `currency_type` | VARCHAR(20) | 货币类型：gold, diamond, coin, point |
| `amount` | INT | 变动金额（正=获得，负=消耗） |
| `balance_after` | BIGINT | 变动后余额 |
| `txn_type` | VARCHAR(30) | 交易类型：recharge_purchase, quest_reward, daily_login, sell_item, buy_item, gacha, upgrade, skill_unlock, battle_reward, event_reward, achievement_reward, compensation |
| `related_order_id` | BIGINT | 关联订单ID |
| `create_time` | DATETIME | 创建时间 |
| `remark` | VARCHAR(200) | 备注 |

**索引**：`idx_user_currency`, `idx_txn_type`, `idx_create_time`

---

## 8. game_guilds（公会表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `guild_id` | BIGINT PK | 公会ID |
| `guild_name` | VARCHAR(100) | 公会名称 |
| `guild_tag` | VARCHAR(10) | 公会标签 |
| `leader_user_id` | BIGINT | 会长用户ID |
| `deputy_leader_id` | BIGINT | 副会长用户ID |
| `member_count` | INT | 当前成员数 |
| `max_members` | INT | 最大成员数，默认50 |
| `level` | TINYINT | 公会等级 1-10 |
| `total_contribution` | BIGINT | 总贡献值 |
| `guild_exp` | BIGINT | 公会经验 |
| `description` | VARCHAR(500) | 公会简介 |
| `create_time` | DATETIME | 创建时间 |
| `region` | VARCHAR(20) | 所属区域 |
| `rank_points` | INT | 排名分数 |

**索引**：`idx_guild_leader`, `idx_guild_region`

---

## 9. game_guild_members（公会成员表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGINT PK | 记录ID |
| `guild_id` | BIGINT | 公会ID |
| `user_id` | BIGINT | 用户ID |
| `role` | VARCHAR(20) | 角色：leader, deputy, elder, member, recruit |
| `join_time` | DATETIME | 加入时间 |
| `weekly_contribution` | INT | 本周贡献 |
| `total_contribution` | INT | 累计贡献 |

**唯一约束**：`uk_guild_user (guild_id, user_id)` — 同一用户不能在同一公会中重复

---

## 10. game_friends（好友关系表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGINT PK | 记录ID |
| `user_id` | BIGINT | 用户ID |
| `friend_user_id` | BIGINT | 好友用户ID |
| `intimacy_level` | INT | 亲密度等级 1-20 |
| `intimacy_points` | INT | 亲密值 |
| `create_time` | DATETIME | 建立好友时间 |
| `last_interact_time` | DATETIME | 最后互动时间 |

**唯一约束**：`uk_friendship (user_id, friend_user_id)`

---

## 11. game_achievements（成就定义表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `achievement_id` | BIGINT PK | 成就ID |
| `achievement_name` | VARCHAR(100) | 成就名称 |
| `description` | VARCHAR(500) | 成就描述 |
| `category` | VARCHAR(30) | 成就分类：combat, collection, social, exploration, veteran, event |
| `difficulty` | VARCHAR(10) | 难度：easy, normal, hard, insane |
| `points` | INT | 成就点数 |
| `condition_value` | INT | 达成条件值 |

**索引**：`idx_category`

---

## 12. game_user_achievements（用户成就表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGINT PK | 记录ID |
| `user_id` | BIGINT | 用户ID |
| `achievement_id` | BIGINT | 成就ID |
| `progress` | INT | 当前进度 |
| `target_value` | INT | 目标值 |
| `is_completed` | TINYINT | 是否完成 |
| `complete_time` | DATETIME | 完成时间 |
| `claimed` | TINYINT | 是否已领奖 |

**唯一约束**：`uk_user_achievement (user_id, achievement_id)`

---

## 13. game_user_daily_stats（用户每日统计表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `stat_id` | BIGINT PK | 统计ID |
| `stat_date` | DATE | 统计日期 |
| `user_id` | BIGINT | 用户ID |
| `login_count` | TINYINT | 登录次数 |
| `total_play_seconds` | INT | 总游戏时长(秒) |
| `session_count` | INT | 对局次数 |
| `recharge_amount` | DECIMAL(10,2) | 充值金额 |
| `recharge_count` | INT | 充值次数 |
| `diamond_spent` | INT | 钻石消耗 |
| `diamond_earned` | INT | 钻石获得 |
| `gold_spent` | INT | 金币消耗 |
| `gold_earned` | INT | 金币获得 |
| `kills` | INT | 击杀数 |
| `deaths` | INT | 死亡数 |
| `wins` | INT | 胜场数 |
| `total_games` | INT | 总局数 |
| `missions_completed` | INT | 完成任务数 |
| `items_acquired` | INT | 获得道具数 |
| `friends_added` | INT | 新增好友数 |
| `guild_contribution` | INT | 公会贡献值 |

**唯一约束**：`uk_date_user (stat_date, user_id)`

---

## 14. game_events（活动表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | BIGINT PK | 活动ID |
| `event_name` | VARCHAR(100) | 活动名称 |
| `event_type` | VARCHAR(30) | 活动类型：limited_time, festival, weekend, season, daily, special |
| `start_time` | DATETIME | 开始时间 |
| `end_time` | DATETIME | 结束时间 |
| `description` | VARCHAR(1000) | 活动描述 |
| `min_level` | TINYINT | 最低参与等级 |
| `reward_summary` | VARCHAR(500) | 奖励摘要 |
| `is_recurring` | TINYINT | 是否定期重复 |

**索引**：`idx_event_time`

---

## 15. game_event_participation（活动参与记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGINT PK | 记录ID |
| `event_id` | BIGINT | 活动ID |
| `user_id` | BIGINT | 用户ID |
| `participation_time` | DATETIME | 参与时间 |
| `score` | INT | 得分 |
| `ranking` | INT | 排名 |
| `rewards_obtained` | VARCHAR(500) | 获得的奖励 |
| `completed` | TINYINT | 是否完成 |

**唯一约束**：`uk_event_user (event_id, user_id)`

---

## 自然语言查询示例

以下是一些可以用来验证 NL-to-SQL 的自然语言提问：

| # | 查询问题 | 涉及表 | 难度 |
|---|---------|--------|------|
| 1 | 查询充值金额最高的10个用户，显示用户名、VIP等级和累计充值金额 | users, recharge_orders | 简单 |
| 2 | 统计各地区用户的平均对局时长 | users, play_sessions | 简单 |
| 3 | 上月每天的新增登录用户数是多少 | login_logs | 中等 |
| 4 | 胜率最高的前5个游戏模式是什么 | play_sessions | 中等 |
| 5 | 查询每个公会的成员数量和总贡献值，按贡献值降序排列 | guilds, guild_members | 中等 |
| 6 | 哪些用户既充了月卡又购买了通行证 | recharge_orders | 中等 |
| 7 | 好友数量最多的前20个用户及其充值总额 | users, friends, recharge_orders | 较难 |
| 8 | 统计每个稀有度等级的道具被玩家拥有的总数量 | items, user_inventory | 较难 |
| 9 | 上月每个渠道的新增用户中，7日留存率（7天内再次登录）是多少 | users, login_logs | 困难 |
| 10 | 查询充值金额超过平均充值金额3倍的高价值用户，并显示他们最常玩的游戏模式 | recharge_orders, play_sessions | 困难 |

## 数据生成方式

数据由 `scripts/gen_game_test_data.py` 脚本生成，使用 Python 随机生成符合游戏业务逻辑的高仿真测试数据。重新生成：

```bash
uv run python scripts/gen_game_test_data.py
```
