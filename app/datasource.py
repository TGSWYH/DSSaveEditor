# -*- coding: utf-8 -*-
"""数据层: 内存 SQLite 操作封装 + ID->中文名 映射。

SaveData 从旧 ds_editor.py 迁移而来, 方法签名保持一致:
  load / select_all / update_cell / insert_row / delete_row /
  save_to_db / list_tables / table_columns / close

NameResolver 复用旧版 _resolve_name / _format_cell 逻辑, 仅用于显示层。
"""
import os
import json
import sqlite3

import ds_save

from .config import TOOL_ROOT
from . import i18n

USER_DBID = 1000  # 当前玩家主键

# 货币 ITEM_CID 映射 (内置回退名, 优先用 id_names.json)
CUR_GOLD = 1000001
CUR_DIAMOND = 1000002
CUR_MAP = {CUR_GOLD: "金币", CUR_DIAMOND: "钻石(现金)"}

# 类型转换失败哨兵
INVALID = object()


def localize_name(name):
    """名称本地化: name 可能是 {lang: text} 字典(新格式) 或纯字符串(旧格式)。
    按当前界面语言取值, 缺失时回退 en -> zh_CN -> 任意首项。
    """
    if not isinstance(name, dict):
        return name
    lang = i18n.current_lang() or "zh_CN"
    if lang in name:
        return name[lang]
    for fallback in ("en", "zh_CN"):
        if fallback in name:
            return name[fallback]
    for v in name.values():
        if v:
            return v
    return None


class SaveData:
    """内存 SQLite 数据操作封装 (基于临时文件挂载, 编辑即生效)"""

    def __init__(self):
        self.db_path = None          # 原始 .db 路径
        self.conn = None             # sqlite 连接
        self.table_count = 0
        self._tmpfile = None
        self._baseline = None        # 打开时的表快照 (供 build_diff 对比)

    # ---------- 加载 / 保存 ----------
    def load(self, db_path):
        """解密 .db -> 临时文件 sqlite (直接挂载, 编辑即生效)"""
        plain = ds_save.load_plain_db(db_path)
        if self.conn:
            self.close()
        self._import_plain(plain)
        self.db_path = db_path
        self.table_count = self._table_count()
        self._rebuild_baseline()

    def _import_plain(self, plain_bytes):
        """把明文 SQLite 字节导入临时文件数据库"""
        import tempfile
        fd, tmpfile = tempfile.mkstemp(suffix=".db")
        try:
            os.write(fd, plain_bytes)
            os.close(fd)
            if self.conn:
                self.conn.close()
            self.conn = sqlite3.connect(tmpfile)
            self.conn.row_factory = sqlite3.Row
            self.conn.executescript("PRAGMA foreign_keys=OFF;")
            self._tmpfile = tmpfile
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.remove(tmpfile)
            except OSError:
                pass
            raise

    def _table_count(self):
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        )
        return cur.fetchone()[0]

    def list_tables(self):
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [r[0] for r in cur.fetchall()]

    def table_columns(self, table):
        """返回 [(name, type, is_pk), ...]"""
        cur = self.conn.execute(f'PRAGMA table_info("{table}")')
        return [(r[1], r[2], r[5]) for r in cur.fetchall()]

    def select_all(self, table, where="", params=()):
        sql = f'SELECT * FROM "{table}"'
        if where:
            sql += " WHERE " + where
        try:
            return self.conn.execute(sql, params).fetchall()
        except sqlite3.Error as e:
            raise ds_save.DSError(str(e))

    def update_cell(self, table, pk_cols, pk_vals, col, value):
        set_clause = f'"{col}"=?'
        where = " AND ".join(f'"{c}"=?' for c in pk_cols)
        sql = f'UPDATE "{table}" SET {set_clause} WHERE {where}'
        self.conn.execute(sql, (value, *pk_vals))
        self.conn.commit()

    def delete_row(self, table, pk_cols, pk_vals):
        where = " AND ".join(f'"{c}"=?' for c in pk_cols)
        sql = f'DELETE FROM "{table}" WHERE {where}'
        self.conn.execute(sql, pk_vals)
        self.conn.commit()

    def insert_row(self, table, cols, values):
        placeholders = ",".join("?" * len(cols))
        col_list = ",".join(f'"{c}"' for c in cols)
        sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'
        self.conn.execute(sql, values)
        self.conn.commit()

    def execute(self, sql, params=()):
        """直接执行 SQL (供友好面板 upsert 等使用)"""
        self.conn.execute(sql, params)
        self.conn.commit()

    def fetchone(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def save_to_db(self):
        """把内存库写回原始 .db (先自动备份)"""
        if not self.db_path:
            raise ds_save.DSError("没有打开存档")
        bak = ds_save.backup(self.db_path)
        plain = self._export_plain()
        ds_save.save_encrypted(plain, self.db_path, self.db_path)
        self._rebuild_baseline()   # 保存成功后基线 = 当前状态
        return bak

    # ---------- 修改对比 (build_diff) ----------
    def _row_key(self, cols, row):
        """行唯一键: 主键列值元组; 无主键表用全列值元组"""
        pk_vals = tuple(row[c] for c, _, is_pk in cols if is_pk)
        if pk_vals:
            return pk_vals
        return tuple(row[c] for c, _, _ in cols)

    def _snapshot(self):
        """全表快照: {表: {行键: {列: 值}}}"""
        snap = {}
        for t in self.list_tables():
            cols = self.table_columns(t)
            names = [c[0] for c in cols]
            rows = {}
            try:
                for r in self.conn.execute(f'SELECT * FROM "{t}"'):
                    rows[self._row_key(cols, r)] = dict(zip(names, r))
            except sqlite3.Error:
                continue
            snap[t] = rows
        return snap

    def _rebuild_baseline(self):
        """重建打开时基线快照 (load 与 save 成功后调用)"""
        self._baseline = self._snapshot() if self.conn else None

    def build_diff(self):
        """对比当前内存库与打开时基线, 返回 {表: {"added": [行], "removed": [行],
        "modified": [{"key": 行键, "changes": {列: (旧值, 新值)}}]}}
        仅包含有变化的表; 供"应用修改"界面展示。"""
        if self._baseline is None or self.conn is None:
            return {}
        cur = self._snapshot()
        diff = {}
        for t in set(self._baseline) | set(cur):
            base = self._baseline.get(t, {})
            now = cur.get(t, {})
            added = [now[k] for k in now if k not in base]
            removed = [base[k] for k in base if k not in now]
            modified = []
            for k in now:
                if k in base and base[k] != now[k]:
                    old, new = base[k], now[k]
                    changes = {c: (old.get(c), new.get(c))
                               for c in set(old) | set(new)
                               if old.get(c) != new.get(c)}
                    modified.append({"key": k, "changes": changes})
            if added or removed or modified:
                diff[t] = {"added": added, "removed": removed, "modified": modified}
        return diff

    def _export_plain(self):
        if not self._tmpfile:
            raise ds_save.DSError("内部错误: 未挂载临时数据库")
        self.conn.commit()
        with open(self._tmpfile, "rb") as f:
            return f.read()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        if self._tmpfile:
            try:
                os.remove(self._tmpfile)
            except OSError:
                pass
            self._tmpfile = None


# ============================================================
# ID -> 中文名 映射 (显示层)
# ============================================================
class NameResolver:
    """加载 id_names.json, 按列名规则解析中文名; 失败则空。"""

    def __init__(self):
        self.names = {}
        path = os.path.join(TOOL_ROOT, "id_names.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in ("item", "character", "monster", "npc", "vehicle", "desc"):
                if k not in data or not isinstance(data[k], dict):
                    data[k] = {}
            self.names = data
        except Exception:
            self.names = {}

    def resolve(self, col_name, value):
        """根据列名和值查名称 (按当前界面语言); 未命中返回 None。
        约定:
          ITEM_CID      -> item
          CHARACTER_CID -> character
          VEHICLE_CID   -> vehicle
          COSTUME_CID   -> item 再 costume
          其他 *_CID    -> item/character/monster/npc/vehicle 依次试
        """
        if value is None or not self.names:
            return None
        try:
            key = str(int(value))
        except (ValueError, TypeError):
            key = str(value)

        col = (col_name or "").upper()

        def lookup(b):
            return localize_name(self.names.get(b, {}).get(key))

        if col == "ITEM_CID":
            return lookup("item")
        if col == "CHARACTER_CID":
            return lookup("character")
        if col == "VEHICLE_CID":
            return lookup("vehicle")
        if col == "COSTUME_CID":
            return lookup("item") or lookup("costume")
        if col.endswith("_CID"):
            for b in ("item", "character", "monster", "npc", "vehicle"):
                n = lookup(b)
                if n:
                    return n
        return None

    def format(self, col_name, value):
        """显示层格式化: 命中名称则 'ID (名称)', 否则原值"""
        if value is None:
            return ""
        name = self.resolve(col_name, value)
        if name:
            return f"{value} ({name})"
        return value


def cast_value(text, col_type):
    """把字符串按列类型转换; 失败返回 INVALID 哨兵"""
    t = (col_type or "").upper()
    if text == "" or text is None:
        return None
    try:
        if "INT" in t:
            return int(text)
        if "REAL" in t or "FLOAT" in t or "DOUB" in t:
            return float(text)
        return text
    except (ValueError, TypeError):
        return INVALID


# ============================================================
# 任务系统 (任务状态 / 记录卡 / 区域任务)
# ============================================================
class QuestManager:
    """任务状态读写 + quest_data.json 元数据。

    存档表:
      tb_quest_complete     (USER_DBID, QUEST_CID, CATEGORY)         已完成
      tb_quest_hold         (USER_DBID, QUEST_CID, USE_TRACKING,     进行中
                             STEP_ID, CNT, FAILED_CNT)
      tb_quest_record_reward(USER_DBID, CARD_ID, REWARD_ORDER)       记录卡奖励档位
      tb_dynamic_quest_group(USER_DBID, GROUP_ID, LAST_QUEST_ID,     区域任务进行中
                             QUEST_ID, STEP, CNT, FAILED_CNT)
      tb_dynamic_quest_complete(USER_DBID, QUEST_ID, COMPLETE_CNT)   区域任务完成次数

    quest_data.json 元数据:
      quests         {qid: {id, category, db_category, name{lang}, group,
                             pre, next, steps{min,max,count,max_cnt}, ...}}
      record_groups  {'1': [卡], '101': [卡]}  卡: {card_id, title, subtitle, quests, max_order}
      epic_lines     {card_id: {title, subtitle, quests, max_order}}  因缘 5 线
      episodes       {episode_id: {char_id, order, group_id}}         英雄记录 5 线
      dynamic        {qid: {id, group, name, trigger, steps, ...}}    区域任务
    """

    # 页面 -> QuestMainData.Category
    PAGE_CATEGORIES = {
        "main": "MAIN",
        "epic": "EPIC",
        "character": "CHARACTER",
        "grade": "ADVENT_GRADE",
        "other": "OTHER",   # 游离 EPIC/CHARACTER（不属任何线）
    }
    # 隐藏: 教程/测试
    HIDDEN_CATEGORIES = {"TUTORIAL", "SUB"}

    def __init__(self, data):
        self.data = data
        self.quests = {}
        self.record_groups = {}
        self.epic_lines = {}
        self.episodes = {}
        self.dynamic = {}
        self._char_names = self._load_char_names()
        self._load_meta()

    def _load_meta(self):
        path = os.path.join(TOOL_ROOT, "quest_data.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self.quests = meta.get("quests", {})
            self.record_groups = meta.get("record_groups", {})
            self.epic_lines = meta.get("epic_lines", {})
            self.episodes = meta.get("episodes", {})
            self.dynamic = meta.get("dynamic", {})
        except Exception:
            self.quests = {}

    # ---------- 元数据辅助 ----------
    def q(self, qid):
        return self.quests.get(str(qid), {})

    def qname(self, qid):
        """任务名本地化 (缺失回退)"""
        return localize_name(self.q(qid).get("name"))

    def is_hidden(self, qid):
        m = self.q(qid)
        if not m:
            return True
        if m.get("category") in self.HIDDEN_CATEGORIES:
            return True
        # EPIC 测试任务 9000013
        return m.get("category") == "EPIC" and int(qid) >= 9000000

    def is_epic_line_quest(self, qid):
        return any(int(qid) in line.get("quests", [])
                   for line in self.epic_lines.values())

    def is_episode_quest(self, qid):
        return str(self.q(qid).get("group")) in self.episodes

    def main_open_ids(self):
        """已开放主线任务 ID 集合: QuestRecordData 组1 冒险记录 8 张卡 (8 章 x 10 任务)。
        仅 10001~10090 有中文名/步骤数据; 11001+ 为未开放内容。"""
        ids = set()
        for c in self.record_groups.get("1", []):
            ids.update(int(x) for x in c.get("quests", []))
        return ids

    def is_main_unreleased(self, qid):
        """主线任务是否未开放 (有中文名与步骤的 80 个为已开放, 其余为未开放)"""
        m = self.q(qid)
        if m.get("category") != "MAIN":
            return False
        return int(qid) not in self.main_open_ids()

    def quests_by_page(self, page):
        """返回该页任务 [(qid_str, meta), ...] 按 id 升序"""
        out = []
        for qid, m in self.quests.items():
            if self.is_hidden(qid):
                continue
            cat = m.get("category")
            if page == "other":
                if cat == "EPIC" and not self.is_epic_line_quest(qid):
                    out.append((qid, m))
                elif cat == "CHARACTER" and not self.is_episode_quest(qid):
                    out.append((qid, m))
            elif page == "unreleased":
                if self.is_main_unreleased(qid):
                    out.append((qid, m))
            elif page == "main":
                if cat == "MAIN" and not self.is_main_unreleased(qid):
                    out.append((qid, m))
            elif cat == self.PAGE_CATEGORIES.get(page):
                out.append((qid, m))
        out.sort(key=lambda x: int(x[0]))
        return out

    def lines_of(self, page):
        """页面分组 [(key, name, [qid...]), ...]
        main: 8 章 (冒险记录 8 卡); epic: 因缘 5 线; character: 英雄记录 5 线;
        unreleased/grade/other: 单组"""
        if page == "main":
            lines = []
            for c in self.record_groups.get("1", []):
                ids = [str(x) for x in c.get("quests", []) if not self.is_hidden(x)]
                if not ids:
                    continue
                name = (localize_name(c.get("subtitle"))
                        or localize_name(c.get("title"))
                        or f"卡 {c.get('card_id')}")
                lines.append((str(c.get("card_id")), name, ids))
            return lines
        if page == "epic":
            lines = []
            for cid, line in self.epic_lines.items():
                ids = [str(x) for x in line.get("quests", []) if not self.is_hidden(x)]
                lines.append((cid, localize_name(line.get("title")) or localize_name(line.get("subtitle")), ids))
            return lines
        if page == "character":
            lines = []
            for ep_id in sorted(self.episodes, key=lambda e: self.episodes[e].get("order", 99)):
                ep = self.episodes[ep_id]
                ids = [qid for qid, m in self.quests_by_page("character")
                       if str(m.get("group")) == str(ep_id)]
                lines.append((str(ep_id), self.char_name(ep.get("char_id")), ids))
            return lines
        # unreleased / grade / other: 单组
        ids = [qid for qid, _ in self.quests_by_page(page)]
        return [("all", None, ids)] if ids else []

    def char_name(self, char_id):
        """英雄名 (id_names.json character)"""
        return localize_name(self._char_names.get(str(char_id))) if char_id is not None else None

    def _load_char_names(self):
        path = os.path.join(TOOL_ROOT, "id_names.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f).get("character", {})
            except Exception:
                pass
        return {}

    def card_by_id(self, card_id):
        for cards in self.record_groups.values():
            for c in cards:
                if c.get("card_id") == int(card_id):
                    return c
        return None

    # ---------- 状态查询 ----------
    def load_states(self):
        """返回 (completed, holds)
        completed: {db_category: set(cid)}
        holds:     {cid: {'step','cnt','tracking'}}"""
        completed = {}
        holds = {}
        if not self.data.conn:
            return completed, holds
        for r in self.data.select_all("tb_quest_complete"):
            cat, cid = r["CATEGORY"], r["QUEST_CID"]
            completed.setdefault(cat, set()).add(int(cid))
        for r in self.data.select_all("tb_quest_hold"):
            holds[int(r["QUEST_CID"])] = {
                "step": r["STEP_ID"] or 0,
                "cnt": r["CNT"] or 0,
                "tracking": r["USE_TRACKING"] or 0,
            }
        return completed, holds

    def quest_state(self, completed, holds, qid):
        """任务状态: 'done' / 'hold' / 'none' + 详情"""
        i = int(qid)
        m = self.q(qid)
        if i in holds:
            return "hold", holds[i]
        for cat, ids in completed.items():
            if cat == m.get("db_category") and i in ids:
                return "done", None
        return "none", None

    # ---------- 状态修改 ----------
    def set_complete(self, quest_cid, db_category):
        """标记完成: 写 tb_quest_complete, 删 tb_quest_hold"""
        d = self.data
        if d.conn is None:
            return
        d.execute(
            "INSERT OR REPLACE INTO tb_quest_complete (USER_DBID, QUEST_CID, CATEGORY) VALUES (?,?,?)",
            (USER_DBID, int(quest_cid), int(db_category)),
        )
        d.execute("DELETE FROM tb_quest_hold WHERE USER_DBID=? AND QUEST_CID=?",
                  (USER_DBID, int(quest_cid)))

    def set_hold(self, quest_cid, step_id, cnt, tracking=0):
        """设为进行中: upsert tb_quest_hold, 删 tb_quest_complete"""
        d = self.data
        if d.conn is None:
            return
        d.execute(
            "INSERT OR REPLACE INTO tb_quest_hold (USER_DBID, QUEST_CID, USE_TRACKING, STEP_ID, CNT, FAILED_CNT) "
            "VALUES (?,?,?,?,?,0)",
            (USER_DBID, int(quest_cid), int(tracking or 0), int(step_id or 0), int(cnt or 0)),
        )
        d.execute("DELETE FROM tb_quest_complete WHERE USER_DBID=? AND QUEST_CID=?",
                  (USER_DBID, int(quest_cid)))

    def reset_quest(self, quest_cid):
        """重置为未开始: 删除两表记录"""
        d = self.data
        if d.conn is None:
            return
        d.execute("DELETE FROM tb_quest_complete WHERE USER_DBID=? AND QUEST_CID=?",
                  (USER_DBID, int(quest_cid)))
        d.execute("DELETE FROM tb_quest_hold WHERE USER_DBID=? AND QUEST_CID=?",
                  (USER_DBID, int(quest_cid)))

    # ---------- 记录卡 ----------
    def load_card_orders(self):
        """{card_id: reward_order}"""
        out = {}
        if self.data.conn is None:
            return out
        for r in self.data.select_all("tb_quest_record_reward"):
            out[int(r["CARD_ID"])] = r["REWARD_ORDER"] or 0
        return out

    def set_card_order(self, card_id, order):
        d = self.data
        if d.conn is None:
            return
        d.execute(
            "INSERT OR REPLACE INTO tb_quest_record_reward (USER_DBID, CARD_ID, REWARD_ORDER) VALUES (?,?,?)",
            (USER_DBID, int(card_id), int(order)),
        )

    def reset_card_order(self, card_id):
        d = self.data
        if d.conn is None:
            return
        d.execute("DELETE FROM tb_quest_record_reward WHERE USER_DBID=? AND CARD_ID=?",
                  (USER_DBID, int(card_id)))

    def card_order_from_state(self, card, completed, holds):
        """记录卡档位 = 卡内已完成任务数 (0..max_order)。
        依据: 存档中卡档位 REWARD_ORDER 与卡内已完成任务数完全一致
        (如卡 4101 17 任务中完成 9 个 -> REWARD_ORDER=9)。"""
        n = 0
        for qid in card.get("quests", []):
            st, _ = self.quest_state(completed, holds, qid)
            if st == "done":
                n += 1
        return n

    # ---------- 区域任务 (动态任务) ----------
    def load_dynamic_states(self):
        """返回 (groups, complete_cnt)
        groups: {group_id: {'last_quest','quest','step','cnt'}}
        complete_cnt: {quest_id: cnt}"""
        groups, complete = {}, {}
        if self.data.conn is None:
            return groups, complete
        for r in self.data.select_all("tb_dynamic_quest_group"):
            groups[int(r["GROUP_ID"])] = {
                "last_quest": r["LAST_QUEST_ID"] or 0,
                "quest": r["QUEST_ID"] or 0,
                "step": r["STEP"] or 0,
                "cnt": r["CNT"] or 0,
            }
        for r in self.data.select_all("tb_dynamic_quest_complete"):
            complete[int(r["QUEST_ID"])] = r["COMPLETE_CNT"] or 0
        return groups, complete

    def set_dynamic_group(self, group_id, last_quest_id, step=0, cnt=0, quest_id=0):
        d = self.data
        if d.conn is None:
            return
        d.execute(
            "INSERT OR REPLACE INTO tb_dynamic_quest_group "
            "(USER_DBID, GROUP_ID, LAST_QUEST_ID, QUEST_ID, STEP, CNT, FAILED_CNT) "
            "VALUES (?,?,?,?,?,?,0)",
            (USER_DBID, int(group_id), int(last_quest_id), int(quest_id), int(step), int(cnt)),
        )

    def delete_dynamic_group(self, group_id):
        d = self.data
        if d.conn is None:
            return
        d.execute("DELETE FROM tb_dynamic_quest_group WHERE USER_DBID=? AND GROUP_ID=?",
                  (USER_DBID, int(group_id)))

    def set_dynamic_complete(self, quest_id, cnt):
        d = self.data
        if d.conn is None:
            return
        d.execute(
            "INSERT OR REPLACE INTO tb_dynamic_quest_complete (USER_DBID, QUEST_ID, COMPLETE_CNT) VALUES (?,?,?)",
            (USER_DBID, int(quest_id), int(cnt)),
        )

    def delete_dynamic_complete(self, quest_id):
        d = self.data
        if d.conn is None:
            return
        d.execute("DELETE FROM tb_dynamic_quest_complete WHERE USER_DBID=? AND QUEST_ID=?",
                  (USER_DBID, int(quest_id)))

    # ---------- 宿命烙印图鉴 (tb_karma_collection_switch) ----------
    # 位图规律 (已验证存档 46 个烙印 CID 全部吻合):
    #   CATEGORY = CID // 64
    #   BIT      = 1 << (CID % 64)
    #   BIT_FIELD 该位为 1 = 图鉴已解锁
    @staticmethod
    def karma_collection_cid(cid):
        """烙印 CID -> (CATEGORY, BIT)"""
        cid = int(cid)
        return cid // 64, 1 << (cid % 64)

    def is_karma_collection_unlocked(self, cid):
        """该烙印图鉴是否已解锁"""
        if self.data.conn is None:
            return False
        cat, bit = self.karma_collection_cid(cid)
        row = self.data.fetchone(
            "SELECT BIT_FIELD FROM tb_karma_collection_switch WHERE USER_DBID=? AND CATEGORY=?",
            (USER_DBID, cat))
        return bool(row and (int(row[0] or 0) & bit))

    def unlock_karma_collection(self, cid):
        """解锁烙印图鉴 (位或; 无记录则插入)"""
        d = self.data
        if d.conn is None:
            return
        cat, bit = self.karma_collection_cid(cid)
        row = d.fetchone(
            "SELECT BIT_FIELD FROM tb_karma_collection_switch WHERE USER_DBID=? AND CATEGORY=?",
            (USER_DBID, cat))
        field = int(row[0] or 0) if row else 0
        new_field = field | bit
        if row is None:
            d.execute(
                "INSERT INTO tb_karma_collection_switch (USER_DBID, CATEGORY, BIT_FIELD) VALUES (?,?,?)",
                (USER_DBID, cat, new_field))
        else:
            d.execute(
                "UPDATE tb_karma_collection_switch SET BIT_FIELD=? WHERE USER_DBID=? AND CATEGORY=?",
                (new_field, USER_DBID, cat))
