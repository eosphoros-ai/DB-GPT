#!/usr/bin/env python3
"""游戏业务测试数据生成器 —— 自然语言生成SQL验证用"""
import random, sys, os
from datetime import datetime, timedelta, date

import pymysql

DB_CONFIG = dict(host="127.0.0.1", port=3306, user="root", password="123456", database="game_analytics", charset="utf8mb4")
random.seed(42)

# ====== 基础常量 ======
REGIONS = ["CN","US","JP","KR","TW","SEA","EU"]
CHANNELS = ["appstore","googleplay","taptap","official","huawei","xiaomi","bilibili","steam"]
DEVICES = ["iPhone 14 Pro","iPhone 15","Samsung Galaxy S24","Pixel 8","Xiaomi 14","iPad Pro","Huawei Mate 60","ROG Phone 7"]
OS_VERSIONS = ["iOS 17.4","iOS 16.6","Android 14","Android 13","HarmonyOS 4","iPadOS 17"]
AGE_GROUPS = ["18-24","25-34","35-44","45+","<18"]
GAME_MODES = ["ranked","casual","deathmatch","battle_royale","team_deathmatch","capture_flag","dungeon_raid","arena_pvp","guild_war","tower_defense"]
MAPS = ["Dragon Valley","Ice Fortress","Desert Oasis","Urban Warfare","Jungle Ruins","Sky Temple","Underworld","Volcano Arena","Crystal Cave","Storm Peak"]
CHARACTERS = ["暗影刺客","圣光骑士","冰霜法师","烈焰射手","雷霆战士","暗黑祭司","自然德鲁伊","机械工程师","亡灵术士","精灵游侠"]
ITEM_TYPES = ["weapon","armor","skin","potion","pet","mount","emote","card","material","elixir"]
RARITIES = ["uncommon","common","rare","epic","legendary","mythic"]
PAY_METHODS = ["alipay","wechat","apple_iap","google_play","credit_card","paypal"]
PRODUCTS = [("6元礼包",6.00,"diamond",60),
            ("30元礼包",30.00,"diamond",300),
            ("68元礼包",68.00,"diamond",680),
            ("128元礼包",128.00,"diamond",1280),
            ("328元礼包",328.00,"diamond",3280),
            ("648元礼包",648.00,"diamond",6480),
            ("月卡",30.00,"monthly_card",300),
            ("至尊月卡",98.00,"monthly_card",980),
            ("通行证",68.00,"battle_pass",680),
            ("高级通行证",128.00,"battle_pass",1280),
            ("首充礼包",6.00,"first_recharge",100),
            ("限定皮肤礼包",88.00,"gift_pack",500),
            ("春节礼包",198.00,"gift_pack",2000)]
TXN_TYPES = ["recharge_purchase","quest_reward","daily_login","sell_item","buy_item","gacha","upgrade","skill_unlock","battle_reward","event_reward","achievement_reward","compensation"]
ACHIEVEMENT_CATEGORIES = ["combat","collection","social","exploration","veteran","event"]
EVENT_TYPES = ["limited_time","festival","weekend","season","daily","special"]

def conn():
    return pymysql.connect(**DB_CONFIG)

def gen_users(n=500):
    users = []
    for i in range(n):
        u = (
            f"player_{i+1:04d}",
            f"PlayerNick{i+1:04d}",
            f"player{i+1}@game.com" if i % 5 != 0 else f"vip{i+1}@vipmail.com",
            f"138{random.randint(10000000,99999999)}",
            datetime(2023,1,1) + timedelta(days=random.randint(0,700), hours=random.randint(0,23), minutes=random.randint(0,59)),
            random.choice(CHANNELS),
            random.choice(DEVICES),
            random.choice(OS_VERSIONS),
            random.choices(REGIONS, weights=[35,15,10,8,5,12,15])[0],
            random.choices(AGE_GROUPS, weights=[25,40,20,10,5])[0],
            random.choice(["M","F","U"]),
            random.choices(range(11), weights=[20,18,15,12,10,8,6,5,3,2,1])[0],
            round(random.random() * 5000, 2),
            random.randint(0, 500000),
            random.randint(3600, 3600*500),
            None, "active"
        )
        users.append(u)
    return users

def gen_items(n=80):
    prefixes = { "weapon":["龙牙之刃","暗影长剑","圣光战锤","冰霜法杖","烈焰长弓","雷霆战斧","暗黑匕首","机械炮","亡灵镰刀","精灵弯刀"],
        "armor":["龙鳞铠甲","暗影斗篷","圣光之盾","冰霜护甲","烈焰战靴","雷霆头盔","暗黑胸甲","机械外骨骼","亡灵披风","精灵轻甲"],
        "skin":["血色玫瑰","暗夜猎手","极地探险家","夏日沙滩","赛博朋克","国风旗袍","圣诞老人","万圣幽灵","春节限定","机甲战士"],
        "potion":["生命药水","魔法药水","力量药剂","敏捷药剂","抗性药剂","经验药水","暴击药水","速度药水","隐身药剂","觉醒药水"],
        "pet":["小火龙","冰晶凤凰","暗影狼","雷霆鹰","精灵鹿","机械犬","九尾狐","幽灵猫","麒麟","白泽"],
        "mount":["烈焰战马","冰霜巨龙","暗影猎豹","雷霆飞鹰","彩虹独角兽","机械摩托","祥云","筋斗云","飞剑","莲花座"],
        "emote":["嘲讽","爱心","愤怒","哭泣","大笑","鼓掌","庆祝","挑衅","拜拜","666"],
        "card":["攻击+10%","防御+10%","暴击+15%","生命+20%","速度+12%","经验+25%","金币+30%","掉落+18%","抗性+10%","回蓝+15%"],
        "material":["强化石","进化水晶","附魔卷轴","符文碎片","龙鳞","凤凰羽毛","暗影精华","元素晶核","锻造图纸","星辰碎片"],
        "elixir":["智慧灵药","力量灵药","幸运药水","不朽秘药","蜕变神药","觉醒神水","天命药剂","轮回丹","续命丹","天劫丹"] }
    items = []
    for item_type_name, names in prefixes.items():
        for rarity in RARITIES:
            name = f"[{rarity.upper()}] {random.choice(names)}"
            items.append((name, item_type_name, rarity,
                random.randint(100, 50000), random.randint(10, 5000),
                round(random.uniform(0, 199.99), 2), random.choice([1,10,50,99,999]),
                random.randint(0,1), random.randint(0,1),
                f"{name} - 稀有度:{rarity} 类型:{item_type_name}"))
    return items[:n]

def batch_insert(cursor, table, columns, rows, chunk=500, ignore_dups=False):
    placeholders = ",".join(["%s"] * len(columns))
    col_names = ",".join(columns)
    ignore = "IGNORE" if ignore_dups else ""
    sql = f"INSERT {ignore} INTO {table} ({col_names}) VALUES ({placeholders})"
    for i in range(0, len(rows), chunk):
        cursor.executemany(sql, rows[i:i+chunk])

def main():
    db = conn()
    cur = db.cursor()
    print("开始生成测试数据...")

    # 1. users
    print("1/15 生成用户数据...")
    users = gen_users(500)
    batch_insert(cur, "game_users",
        ["username","nickname","email","phone","register_date","channel","device_type","os_version","region","age_group","gender","vip_level","total_recharge","total_virtual_currency","total_play_seconds","last_login","account_status"],
        users)
    db.commit()
    cur.execute("SELECT user_id FROM game_users")
    user_ids = [r[0] for r in cur.fetchall()]

    # 2. login_logs
    print("2/15 生成登录日志...")
    login_rows = []
    for uid in user_ids:
        n_logins = random.randint(5, 30)
        dt = datetime(2024,6,1) + timedelta(days=random.randint(0,200))
        for _ in range(n_logins):
            login = dt + timedelta(hours=random.randint(0,23), minutes=random.randint(0,59))
            dur = random.randint(60, 18000)
            logout = login + timedelta(seconds=dur)
            login_rows.append((uid, login, logout, dur,
                f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
                f"DEV_{random.randint(100000,999999)}",
                random.choice(["账号密码","手机号","微信","QQ","AppleID"]),
                f"v{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,99)}",
                f"sdk_{random.randint(10,50)}"))
            dt = login + timedelta(hours=random.randint(6,72))
    batch_insert(cur, "game_login_logs",
        ["user_id","login_time","logout_time","session_duration_seconds","ip_address","device_id","login_type","client_version","sdk_version"],
        login_rows)
    db.commit()

    # 3. recharge_orders
    print("3/15 生成充值订单...")
    order_rows = []
    for uid in user_ids:
        if random.random() < 0.3: continue  # 30% 用户有充值
        n_orders = random.randint(1, 20)
        for _ in range(n_orders):
            prod = random.choice(PRODUCTS)
            create = datetime(2024,3,1) + timedelta(days=random.randint(0,400), hours=random.randint(0,23))
            status = random.choices(["success","success","success","success","refunded","failed"], weights=[70,10,10,5,3,2])[0]
            pay = None; complete = None
            if status == "success":
                pay = create + timedelta(seconds=random.randint(5,120))
                complete = pay + timedelta(seconds=random.randint(1,30))
            elif status == "refunded":
                pay = create + timedelta(seconds=random.randint(5,120))
                complete = pay + timedelta(days=random.randint(1,7))
            order_rows.append((
                uid, f"ORD{int(create.timestamp())}{uid:06d}{random.randint(0,999):03d}",
                prod[1], "CNY", random.choice(PAY_METHODS),
                f"PROD_{prod[0]}", prod[0], prod[2], prod[3],
                status, create, pay, complete, f"CH_{random.randint(1000000,9999999)}",
                round(random.uniform(0, prod[1]*0.2),2),
                round(prod[1] - random.uniform(0, prod[1]*0.15),2) if status != "refunded" else 0
            ))
    batch_insert(cur, "game_recharge_orders",
        ["user_id","order_no","amount","currency_type","pay_method","product_id","product_name","product_type","virtual_currency_amount","order_status","create_time","pay_time","complete_time","channel_order_id","discount_amount","actual_amount"],
        order_rows)
    db.commit()

    # 4. play_sessions
    print("4/15 生成对局记录...")
    session_rows = []
    for uid in user_ids:
        n_sessions = random.randint(10, 80)
        dt = datetime(2024,5,1) + timedelta(days=random.randint(0,200))
        for _ in range(n_sessions):
            start = dt + timedelta(hours=random.randint(0,23), minutes=random.randint(0,59))
            dur = random.randint(120, 3600)
            end = start + timedelta(seconds=dur)
            mode = random.choice(GAME_MODES)
            kills = random.choices([0]*10 + list(range(1,30)), k=1)[0]
            deaths = random.randint(0, 20)
            session_rows.append((uid, start, end, dur, mode,
                random.choice(MAPS), random.randint(1,20), random.choice(CHARACTERS),
                random.choice([1,2,3,4,5]), random.randint(0,1),
                random.randint(0, 5000), kills, deaths, random.randint(0, kills*2),
                random.randint(0, 100000), random.randint(0, 80000),
                random.randint(0, 50000), random.randint(0, kills),
                random.randint(1, 100), random.randint(2, 100), random.randint(0,1),
                random.randint(100, 5000), random.randint(10, 500),
                random.choice(["CN","CN","US","JP","KR","EU"]), random.randint(10, 300)))
            dt = start + timedelta(hours=random.randint(1, 12))
    batch_insert(cur, "game_play_sessions",
        ["user_id","start_time","end_time","duration_seconds","game_mode","map_name","character_id","character_name","team_size","is_team_game","score","kills","deaths","assists","damage_dealt","damage_taken","healing_done","headshots","rank_position","total_players","is_win","exp_gained","gold_earned","server_region","ping_ms"],
        session_rows)
    db.commit()

    # 5. items
    print("5/15 生成道具...")
    items = gen_items(80)
    batch_insert(cur, "game_items",
        ["item_name","item_type","rarity","price_virtual_currency","price_diamond","price_real_currency","max_stack","is_tradeable","is_consumable","description"],
        items)
    db.commit()
    cur.execute("SELECT item_id FROM game_items")
    item_ids = [r[0] for r in cur.fetchall()]

    # 6. user_inventory
    print("6/15 生成背包数据...")
    inv_rows = []
    for uid in user_ids[:400]:
        n_items = random.randint(3, 30)
        seen = set()
        for _ in range(n_items):
            iid = random.choice(item_ids)
            if iid in seen: continue
            seen.add(iid)
            acq = datetime(2024,4,1) + timedelta(days=random.randint(0,350))
            inv_rows.append((uid, iid, random.randint(1, 99),
                acq, random.choice(["purchase","loot","craft","gift","reward","exchange"]),
                random.choice(["商城购买","副本掉落","打造获得","好友赠送","活动奖励","兑换获得"]),
                acq + timedelta(days=random.randint(0,365)) if random.random() < 0.3 else None))
    batch_insert(cur, "game_user_inventory",
        ["user_id","item_id","quantity","acquire_time","acquire_method","source_desc","expire_time"],
        inv_rows)
    db.commit()

    # 7. virtual_currency
    print("7/15 生成虚拟币流水...")
    vc_rows = []
    for uid in user_ids:
        bal = random.randint(1000, 100000)
        n_txns = random.randint(10, 50)
        dt = datetime(2024,5,1) + timedelta(days=random.randint(0,200))
        for _ in range(n_txns):
            ctype = random.choice(["gold","gold","gold","diamond","diamond","coin","point"])
            ttype = random.choice(TXN_TYPES)
            direction = 1 if ttype in ["recharge_purchase","quest_reward","daily_login","sell_item","battle_reward","event_reward","achievement_reward","compensation"] else -1
            amt = direction * random.randint(1, 5000 if ctype == "diamond" else 10000)
            if bal + amt < 0: amt = random.randint(0, bal)
            bal += amt
            vc_rows.append((uid, ctype, amt, bal, ttype, None if random.random() < 0.7 else random.randint(1,10000),
                dt + timedelta(seconds=random.randint(0,86400)),
                f"{ttype} - {ctype} {'获得' if direction>0 else '消耗'}{abs(amt)}"))
            dt += timedelta(hours=random.randint(1, 48))
    batch_insert(cur, "game_virtual_currency_transactions",
        ["user_id","currency_type","amount","balance_after","txn_type","related_order_id","create_time","remark"],
        vc_rows)
    db.commit()

    # 8. guilds
    print("8/15 生成公会...")
    guild_rows = []
    guild_leaders = random.sample(user_ids[:200], 15)
    guild_names = ["龙之谷","暗影议会","圣光骑士团","冰霜之巅","烈焰盟","雷霆之怒","暗黑王朝","自然守护者","机械帝国","亡灵军团","精灵王国","荣耀战歌","星辰大海","不灭传说","巅峰对决"]
    for i, leader in enumerate(guild_leaders):
        guild_rows.append((guild_names[i], guild_names[i][:4],
            leader, None, random.randint(5, 50), 50,
            random.randint(1, 10), random.randint(10000, 500000),
            random.randint(100000, 5000000),
            f"欢迎加入{guild_names[i]}！", datetime(2024,1,1) + timedelta(days=random.randint(0,300)),
            random.choice(REGIONS), random.randint(0, 10000)))
    batch_insert(cur, "game_guilds",
        ["guild_name","guild_tag","leader_user_id","deputy_leader_id","member_count","max_members","level","total_contribution","guild_exp","description","create_time","region","rank_points"],
        guild_rows)
    db.commit()
    cur.execute("SELECT guild_id, leader_user_id FROM game_guilds")
    guilds = list(cur.fetchall())

    # 9. guild_members
    print("9/15 生成公会成员...")
    gm_rows = []
    used_pairs = set()
    for gid, leader in guilds:
        gm_rows.append((gid, leader, "leader", datetime(2024,1,1) + timedelta(days=random.randint(0,300)),
            random.randint(500,5000), random.randint(10000,200000)))
        used_pairs.add((gid, leader))
        n_members = random.randint(10, 45)
        members = random.sample([u for u in user_ids if u != leader], n_members)
        for m in members:
            if (gid, m) in used_pairs: continue
            used_pairs.add((gid, m))
            gm_rows.append((gid, m, random.choices(["deputy","elder","member","member","member","recruit"], weights=[2,5,20,15,10,8])[0],
                datetime(2024,1,1) + timedelta(days=random.randint(0,300)),
                random.randint(0,3000), random.randint(0,50000)))
    batch_insert(cur, "game_guild_members",
        ["guild_id","user_id","role","join_time","weekly_contribution","total_contribution"],
        gm_rows, ignore_dups=True)
    db.commit()

    # 10. friends
    print("10/15 生成好友关系...")
    friend_rows = []
    pairs = set()
    for uid in user_ids[:300]:
        n_friends = random.randint(0, 25)
        for _ in range(n_friends):
            fid = random.choice(user_ids)
            if uid == fid: continue
            key = (min(uid,fid), max(uid,fid))
            if key in pairs: continue
            pairs.add(key)
            friend_rows.append((uid, fid, random.randint(1,20), random.randint(0,10000),
                datetime(2024,3,1) + timedelta(days=random.randint(0,400)),
                datetime(2024,6,1) + timedelta(days=random.randint(0,200))))
    batch_insert(cur, "game_friends",
        ["user_id","friend_user_id","intimacy_level","intimacy_points","create_time","last_interact_time"],
        friend_rows, ignore_dups=True)
    db.commit()

    # 11. achievements
    print("11/15 生成成就定义...")
    ach_names = {
        "combat": ["初次击杀","百人斩","千人斩","万人敌","连杀之王","爆头专家","残血反杀","一挑五","Penta Kill","战斗大师"],
        "collection": ["小小收藏家","皮肤收集者","武器大师","宠物爱好者","坐骑达人","道具收藏家","稀有物品猎手","全图鉴收集","时装达人","宝物猎人"],
        "social": ["初次交友","社交达人","公会新星","公会元老","好友成群","亲密无间","点赞狂魔","分享达人","社区活跃","团队之星"],
        "exploration": ["初次探险","地图探索者","秘境发现者","全地图踏破","隐藏任务达人","宝箱猎人","彩蛋发现者","旅行家","探险家","开拓者"],
        "veteran": ["老玩家","忠诚玩家","资深玩家","元老玩家","不朽玩家","传承者","年度玩家","从一而终","初心不改","岁月见证"],
        "event": ["节日快乐","活动达人","排名前十","全勤参与","限定成就","特殊贡献","周年庆","冠军","MVP","幸运之星"]}
    ach_rows = []
    for cat, names in ach_names.items():
        for nm in names:
            ach_rows.append((nm, f"完成{cat}成就：{nm}",
                cat, random.choice(["easy","normal","normal","hard","hard","insane"]),
                random.randint(10, 100), random.randint(1, 100000)))
    batch_insert(cur, "game_achievements",
        ["achievement_name","description","category","difficulty","points","condition_value"],
        ach_rows)
    db.commit()
    cur.execute("SELECT achievement_id FROM game_achievements")
    ach_ids = [r[0] for r in cur.fetchall()]

    # 12. user_achievements
    print("12/15 生成用户成就...")
    ua_rows = []
    for uid in user_ids[:350]:
        done = set()
        n_ach = random.randint(3, 35)
        for _ in range(n_ach):
            aid = random.choice(ach_ids)
            if aid in done: continue
            done.add(aid)
            completed = random.random() < 0.6
            target = random.randint(1, 1000)
            ua_rows.append((uid, aid,
                random.randint(target//2, target) if not completed else target,
                target, 1 if completed else 0,
                datetime(2024,5,1) + timedelta(days=random.randint(0,200)) if completed else None,
                random.randint(0,1)))
    batch_insert(cur, "game_user_achievements",
        ["user_id","achievement_id","progress","target_value","is_completed","complete_time","claimed"],
        ua_rows, ignore_dups=True)
    db.commit()

    # 13. daily_stats
    print("13/15 生成每日统计...")
    ds_rows = []
    start = date(2024,11,1)
    for uid in user_ids[:250]:  # 250 users with daily stats for ~90 days
        d = start
        for _ in range(random.randint(30, 90)):
            d = d + timedelta(days=random.randint(1, 3))
            if d >= date.today(): break
            ds_rows.append((d, uid,
                random.randint(1, 10), random.randint(0, 28800),
                random.randint(1, 15), round(random.uniform(0, 500), 2),
                random.randint(0, 3), random.randint(0, 2000), random.randint(0, 5000),
                random.randint(0, 10000), random.randint(0, 5000),
                random.randint(0, 50), random.randint(0, 30), random.randint(0, 10),
                random.randint(0, 25), random.randint(0, 10),
                random.randint(0, 20), random.randint(0, 3),
                random.randint(0, 500)))
    batch_insert(cur, "game_user_daily_stats",
        ["stat_date","user_id","login_count","total_play_seconds","session_count","recharge_amount","recharge_count","diamond_spent","diamond_earned","gold_spent","gold_earned","kills","deaths","wins","total_games","missions_completed","items_acquired","friends_added","guild_contribution"],
        ds_rows, ignore_dups=True)
    db.commit()

    # 14. events
    print("14/15 生成活动...")
    event_names = {
        "limited_time": ["新春盛典","夏日狂欢","周年庆典","限时特惠","国庆献礼"],
        "festival": ["春节红包","中秋赏月","圣诞礼物","万圣惊魂","元宵灯会"],
        "weekend": ["周末双倍经验","周末BOSS来袭","周末特惠商城","周末PK赛"],
        "season": ["S1赛季·春","S2赛季·夏","S3赛季·秋","S4赛季·冬","排位巅峰赛"],
        "daily": ["每日签到","每日任务","每日首胜","每日限时副本"],
        "special": ["新服庆典","版本更新福利","感恩回馈","名人堂挑战","跨服争霸"]}
    event_rows = []
    for etype, names in event_names.items():
        for nm in names:
            st = datetime(2024, random.randint(1,12), random.randint(1,25))
            et = st + timedelta(days=random.randint(3, 30))
            if et < datetime.now(): et = datetime(2025, random.randint(1,6), random.randint(1,25))
            event_rows.append((nm, etype, st, et,
                f"{nm} - {etype}活动", random.randint(1,50),
                f"钻石x{random.randint(100,5000)} 金币x{random.randint(1000,50000)} 限定道具x{random.randint(1,3)}",
                random.randint(0,1)))
    batch_insert(cur, "game_events",
        ["event_name","event_type","start_time","end_time","description","min_level","reward_summary","is_recurring"],
        event_rows)
    db.commit()
    cur.execute("SELECT event_id FROM game_events")
    event_ids = [r[0] for r in cur.fetchall()]

    # 15. event_participation
    print("15/15 生成活动参与...")
    ep_rows = []
    done_pairs = set()
    for uid in user_ids[:300]:
        n_ep = random.randint(2, 15)
        for _ in range(n_ep):
            eid = random.choice(event_ids)
            if (eid, uid) in done_pairs: continue
            done_pairs.add((eid, uid))
            ep_rows.append((eid, uid, datetime(2024,6,1) + timedelta(days=random.randint(0,300)),
                random.randint(0, 10000), random.randint(1, 500),
                f"钻石x{random.randint(50,2000)} 金币x{random.randint(500,10000)}",
                random.randint(0,1)))
    batch_insert(cur, "game_event_participation",
        ["event_id","user_id","participation_time","score","ranking","rewards_obtained","completed"],
        ep_rows, ignore_dups=True)
    db.commit()

    db.close()
    print("全部测试数据生成完毕！")

if __name__ == "__main__":
    main()
