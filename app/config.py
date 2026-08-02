# -*- coding: utf-8 -*-
"""配置读写: 工具根目录下的 config.json

字段: language / theme / last_path
文件损坏或缺失时使用默认值, 不抛异常。
"""
import json
import os

# 工具根目录 = app 包的上一级
TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(TOOL_ROOT, "config.json")

DEFAULT_CONFIG = {
    "language": "en",
    "theme": "dark",
    "last_path": "",
}

# 合法语言代码 (与 i18n.SUPPORTED 保持一致)
_VALID_LANGS = {
    "zh_CN", "zh_TW", "en", "ja", "ko_KR",
    "de", "fr", "es_ES", "pt_BR", "ru", "th",
}


def load_config():
    """读取配置; 失败返回默认配置的副本"""
    cfg = dict(DEFAULT_CONFIG)
    if not os.path.exists(CONFIG_PATH):
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in DEFAULT_CONFIG:
                if k in data:
                    cfg[k] = data[k]
    except Exception:
        # 文件损坏, 用默认值
        return dict(DEFAULT_CONFIG)
    # 规范化
    if cfg.get("language") not in _VALID_LANGS:
        cfg["language"] = DEFAULT_CONFIG["language"]
    if cfg.get("theme") not in ("dark", "light"):
        cfg["theme"] = DEFAULT_CONFIG["theme"]
    if not isinstance(cfg.get("last_path"), str):
        cfg["last_path"] = ""
    return cfg


def save_config(cfg):
    """写入配置; 失败静默"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def config_exists():
    return os.path.exists(CONFIG_PATH)
