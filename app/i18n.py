# -*- coding: utf-8 -*-
"""国际化: 加载 locales/<lang>.json, 提供全局 tr() 函数。

key 用点路径访问, 如 tr('status.loaded', path=..., count=...)。
英文 fallback: 目标语言缺失某个 key 时回退到 en.json, 仍缺失才返回 key 本身。
"""
import json
import os

_LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

# 支持的语言代码 -> 显示名 (用各语言自称, 用于设置下拉)
SUPPORTED = [
    ("zh_CN", "简体中文"), ("zh_TW", "繁體中文"), ("en", "English"),
    ("ja", "日本語"), ("ko_KR", "한국어"), ("de", "Deutsch"),
    ("fr", "Français"), ("es_ES", "Español"), ("pt_BR", "Português"),
    ("ru", "Русский"), ("th", "ไทย"),
]


def _load_file(lang):
    """加载单个语言文件; 失败返回 {}"""
    path = os.path.join(_LOCALES_DIR, f"{lang}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class I18n:
    """单语言翻译器, 带英文 fallback"""

    def __init__(self, lang):
        self.lang = lang
        self.data = {}
        self._en_data = {}
        self._load()

    def _load(self):
        # 英文基础 (fallback 用)
        self._en_data = _load_file("en")
        if self.lang == "en":
            self.data = self._en_data
            return
        # 目标语言: 逐顶层分组合并 (en 为底, target 覆盖)
        target = _load_file(self.lang)
        merged = {}
        for k, v in self._en_data.items():
            if isinstance(v, dict):
                merged[k] = {**v, **(target.get(k) or {})}
            else:
                merged[k] = v
        # 补上 target 独有但 en 没有的顶层分组 (一般不会出现)
        for k, v in target.items():
            if k not in merged:
                merged[k] = v
        self.data = merged

    def _lookup(self, dotted_key):
        """按点路径查找; 失败返回 None"""
        node = self.data
        for part in dotted_key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        return node

    def _lookup_en(self, dotted_key):
        """英文 fallback 查找; 失败返回 None"""
        node = self._en_data
        for part in dotted_key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        return node

    def tr(self, key, **fmt):
        val = self._lookup(key)
        if val is None:
            # 英文 fallback
            val = self._lookup_en(key)
        if val is None:
            return key  # 仍缺失: 返回 key 本身
        if isinstance(val, str) and fmt:
            try:
                return val.format(**fmt)
            except Exception:
                return val
        return val


# ---------- 全局实例 ----------
_current = None  # type: I18n | None


def set_language(lang):
    """切换当前语言"""
    global _current
    _current = I18n(lang)


def current_lang():
    if _current is None:
        return None
    return _current.lang


def tr(key, **fmt):
    """全局翻译函数"""
    if _current is None:
        return key
    return _current.tr(key, **fmt)