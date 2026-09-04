# DSSaveEditor — 龙之剑觉醒 存档修改器

DragonSword: Awakening（龙之剑觉醒，UE 5.3.2）的本地存档修改工具。

本版本基于 [noobdawn/DSSaveEditor](https://github.com/noobdawn/DSSaveEditor) 修改，修改作者：**TGSWYH**。

本修改版新增成就计数编辑、按角色筛选已穿戴装备并修改词条，修复深色主题显示问题，并完善临时文件清理与独立 EXE 打包。

- 读取/修改 SQLCipher 加密的存档数据库（角色、货币、装备词条、技能、背包、任务等）
- 查看和修改全部成就计数
- 11 种界面语言（切换语言后物品/角色/词条/技能名同步跟随）
- 现代暗色 Qt6 界面（总览 / 角色养成 / 装备 / 背包 / 数据工具）
- 修改前自动备份，可随时还原

> 存档格式与破解细节见 **[存档文件解析.md](./docs/存档文件解析.md)**。

## 环境要求

- Python 3.10+（开发环境 3.14 验证通过）
- Windows（界面基于 Qt，其他平台理论可用但未验证）

## 安装与运行

```bash
pip install -r requirements.txt
python run_editor.py
```

首次启动默认英文界面，可在「设置」中切换语言（重启生效）。点击「打开存档」选择 `...\DS\Saved\SaveGames\<账号ID>\<账号ID>_Slot1.db` 即可。

## 功能总览

| 页面 | 功能 |
|---|---|
| 📊 总览 | 玩家信息、金币快捷修改、角色列表（点击跳转） |
| 👤 角色养成 | 等级（经验自动匹配）/飞升/超越/HP、技能等级（0~上限，槽位规则）、大师技点亮 |
| ⚔ 装备 | 强化(0~15)、锁定、**词条定制**（按系列+属性筛选）、装备删除/新增 |
| 🎒 背包 | 堆叠物品+料理，**批量操作**（勾选多删/统一设数量/±1000） |
| 🏆 成就 | 查看并修改全部成就组的阶段与计数 |
| 🛠 数据工具 | 全部 105 张表通用编辑（高级） |

## 目录结构

```
DSSaveEditor/
├── run_editor.py          # 启动入口
├── ds_save.py             # 加密核心（SQLCipher 解密/加密/HMAC）
├── build.bat              # 打包脚本（PyInstaller onefile → dist\DSSaveEditor.exe）
├── requirements.txt       # 运行依赖（PySide6 / pycryptodome）
├── app/                   # 应用代码
│   ├── main.py            # 应用入口逻辑
│   ├── i18n.py            # 本地化框架（JSON 语言包 + en 兜底）
│   ├── config.py          # 用户配置（config.json：语言/主题/上次路径）
│   ├── datasource.py      # 存档数据操作（SaveData / NameResolver / QuestManager）
│   ├── ui_main.py         # 主窗口与导航
│   ├── ui_common.py       # 通用 UI 辅助（卡片/清空布局）
│   ├── ui_overview.py     # 总览页
│   ├── ui_character.py    # 角色养成页（含入队/出队/一键满级）
│   ├── ui_karma.py        # 宿命烙印页
│   ├── ui_vehicle.py      # 使魔页
│   ├── ui_equipment.py    # 装备页（强化/词条/符文槽）
│   ├── ui_inventory.py    # 背包页（新增道具/批量）
│   ├── ui_quest.py        # 任务页（主线/因缘/英雄记录/区域/晋升/其他/未开放）
│   ├── ui_backup.py       # 备份管理 + 修改对比对话框
│   ├── ui_tools.py        # 数据工具页
│   ├── ui_settings.py     # 设置对话框
│   ├── ui_theme.py        # 深色/浅色 QSS 主题
│   └── locales/           # 11 种语言文件（zh_CN/zh_TW/en/ja/ko_KR/de/fr/es_ES/pt_BR/ru/th）
├── data/                  # 游戏数据映射（由 FModel 导出表生成）
│   ├── id_names.json      # 物品/角色/怪物/NPC/使魔 → 11 语言名
│   ├── stat_names.json    # 属性/主词条/副词条 → 11 语言名
│   ├── equip_items.json   # 装备基底（系列/部位/品质）
│   ├── equipment_exp.json # 强化等级经验规则（按品质）
│   ├── skill_names.json   # 角色技能槽 → 名称/等级上限
│   ├── level_exp.json     # 等级 → 合法经验值
│   ├── quest_data.json    # 任务元数据（325 任务 + 记录卡 + 动态任务）
│   ├── character_data.json # 可入队角色元数据（图鉴范围/隐藏标志）
│   ├── vehicle_data.json  # 使魔元数据（名称/类型/介绍/DLC）
│   ├── gem_stat.json      # 符文属性定义
│   └── item_types.json    # 背包可新增物品类型清单
└── docs/
    └── 存档文件解析.md      # 存档格式与破解全过程文档
```

## 维护指南

### 各层职责

| 层 | 文件 | 职责 | 修改注意 |
|---|---|---|---|
| 加密 | `ds_save.py` | SQLCipher 加解密 | **一般不要动**；改密钥/参数见《存档文件解析.md》3.4，动错会导致无法读写存档 |
| 数据 | `app/datasource.py` | SQLite 操作封装、名称解析 | 表操作统一走 `SaveData`；新增名称映射列走 `NameResolver` |
| UI | `app/ui_main.py` | 全部界面 | 新增页面：建页面类 + 在 `MainWindow` 注册（pages/nav_items/stack/refresh_all_pages） |
| 本地化 | `app/i18n.py` + `locales/*.json` | 文案 | 所有可见文案必须走 `i18n.tr("key")`；新 key 加入 zh_CN/en，其余语言自动 en 兜底 |
| 数据文件 | `data/*.json` | 名称/规则映射 | 由游戏解包表生成，见下 |

### 新增界面文案

1. 在 `app/locales/zh_CN.json` 与 `en.json` 对应段加 key（其余 9 语言无需改，自动回退英文）
2. 代码中 `i18n.tr("段.key")` 调用；支持 `{占位符}` 格式化（如 `tr("x.y", n=3)`）

### 新增语言

1. 复制 `app/locales/en.json` 为 `app/locales/<code>.json`（code 如 `fr`、`ja`）
2. 翻译其中的文案
3. 在 `app/i18n.py` 的 `SUPPORTED` 列表注册（code, 显示名）

### 重新生成数据文件

数据文件来自游戏 pak 解包（FModel，本游戏 pak 无加密）：

| 数据文件 | 源表（`Content/Design/GameData/`） |
|---|---|
| `data/id_names.json` | GameItemData / PCCharacterData / MonsterCharacterData / NPCCharacterData / VehicleCharacterData / StringData |
| `data/stat_names.json` | StatListData / EquipmentMainStatData / EquipmentSubStatData / StringData |
| `data/skill_names.json` | PCSkillGrowthData / StringData |
| `data/level_exp.json` | PCCharacterLevelData |
| `data/equip_items.json` | GameItemData（ItemType=EQUIPMENT） |
| `data/quest_data.json` | QuestMainData / QuestStepData / QuestRecordData / DynamicQuest* / StringQuestData |
| `data/character_data.json` | PCCharacterData / CharCollectionData |
| `data/vehicle_data.json` | VehicleCharacterData / GameItemData / StringData |
| `data/gem_stat.json` | GemStatData |
| `data/item_types.json` | GameItemData（ItemType 清单） |

生成逻辑：表内 `Name` 字段 → StringData ID → 取 11 语言字段（SourceString=韩文, En, Ja, Zh_CN, Zh_TW, De, Fr, Es_ES, Pt_BR, Ru, Th）。**注意词条属性名需大小写无关匹配**（词条里 `MaxHP` vs 表里 `MAXHP`）。

### 游戏规则速查（来自数据，改动需一致）

- 技能等级上限：槽 5-8→10，槽 1/2/4→7，闪避固定，大师技 0/1 点亮
- 等级经验：`LEVEL=L → EXP = level_exp[L]`
- 装备词条系列：`ITEM_CID 前3位 - 134 = 词条前缀`；部位：Category 1300-1304 = 头/上衣/下衣/手套/鞋
- 强化上限按品质（EquipmentLevelData）：NORMAL 3 / SUPERIOR 6 / RARE 9 / EPIC 12 / LEGENDARY 15；改强化等级自动写入匹配 EXP（EXP = 上一档 LevelMaxExp，否则游戏加载会回退）

### 常见问题

- **打不开存档**：确认文件是 `*_Slot1.db`；先备份再操作
- **切换语言后名称不变**：语言切换需重启生效；名称映射随语言
- **修改不生效**：点「保存修改」才会写回（自动先备份）；`.db.backup` 可还原

## 免责声明

本工具仅用于学习与研究存档格式。修改存档可能影响游戏体验与账号安全，请自行备份、谨慎使用。
