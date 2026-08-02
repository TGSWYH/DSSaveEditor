# -*- coding: utf-8 -*-
"""
DragonSword: Awakening 存档修改器 - 核心库
.db = SQLCipher 4.6.1 加密的 SQLite 数据库
"""
import os, struct, shutil
import hmac as hmac_mod
import datetime
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA512
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

# ==== 加密参数 ====
PASS = b"13314374259236352028"   # SQLCipher 口令
KDF_ITER = 256000                # 主密钥 PBKDF2 迭代
FAST_KDF_ITER = 2                # HMAC 密钥 PBKDF2 迭代
KDF_ALGO = SHA512                # KDF/HMAC 算法 (SQLCipher 4 默认 SHA512)
HMAC_MASK = 0x3A                 # hmac_kdf_salt = kdf_salt XOR 0x3A
PAGE = 4096                      # 页大小
RESERVE = 80                     # 保留区 = IV(16) + HMAC-SHA512(64)
IV_SZ = 16
HMAC_SZ = 64
SQLITE_HEADER = b"SQLite format 3\x00"

MAX_BACKUPS = 30                 # 备份版本保留上限 (自动清理更旧版本)


class DSError(Exception):
    pass


def derive_keys(salt: bytes):
    """从文件 salt 派生 key 和 hmac_key"""
    key = PBKDF2(PASS, salt, dkLen=32, count=KDF_ITER, hmac_hash_module=KDF_ALGO)
    hmac_salt = bytes(b ^ HMAC_MASK for b in salt)
    hmac_key = PBKDF2(key, hmac_salt, dkLen=32, count=FAST_KDF_ITER, hmac_hash_module=KDF_ALGO)
    return key, hmac_key


def decrypt_file(path: str) -> bytes:
    """解密 .db -> 明文 SQLite 文件字节"""
    data = open(path, "rb").read()
    if len(data) % PAGE != 0:
        raise DSError(f"文件大小 {len(data)} 不是页大小 {PAGE} 的整数倍")
    salt = data[:16]
    key, _ = derive_keys(salt)
    out = bytearray()
    npages = len(data) // PAGE
    for pn in range(1, npages + 1):
        st = (pn - 1) * PAGE
        ct_start = st + (16 if pn == 1 else 0)
        ct_end = st + PAGE - RESERVE
        iv = data[ct_end:ct_end + IV_SZ]
        ct = data[ct_start:ct_end]
        pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
        if pn == 1:
            out += SQLITE_HEADER + pt + b"\x00" * RESERVE
        else:
            out += pt + b"\x00" * RESERVE
    return bytes(out)


def encrypt_pages(plain: bytes, salt: bytes) -> bytes:
    """明文 SQLite 字节 -> 加密 .db 字节 (每页新随机 IV + HMAC)"""
    key, hmac_key = derive_keys(salt)
    if len(plain) % PAGE != 0:
        raise DSError(f"明文大小 {len(plain)} 不是页大小 {PAGE} 的整数倍")
    out = bytearray()
    npages = len(plain) // PAGE
    for pn in range(1, npages + 1):
        st = (pn - 1) * PAGE
        body = plain[st:st + PAGE - RESERVE]
        if pn == 1:
            body = body[16:]  # 去掉重建的 SQLite 头, 密文从 offset 16 开始
        iv = get_random_bytes(IV_SZ)
        ct = AES.new(key, AES.MODE_CBC, iv).encrypt(body)
        h = hmac_mod.new(hmac_key, ct + iv + struct.pack("<I", pn), SHA512).digest()
        if pn == 1:
            out += salt
        out += ct
        out += iv + h
    return bytes(out)


def load_plain_db(path: str) -> bytes:
    """解密 .db 文件"""
    return decrypt_file(path)


def save_encrypted(plain: bytes, orig_db_path: str, out_path: str):
    """用原文件 salt 加密明文并保存"""
    salt = open(orig_db_path, "rb").read()[:16]
    enc = encrypt_pages(plain, salt)
    with open(out_path, "wb") as f:
        f.write(enc)


def backup(path: str):
    """备份存档文件 (多版本): 生成 <path>.backup_YYYYMMDD_HHMMSS_mmm。
    自动清理: 保留最近 MAX_BACKUPS 个版本。"""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    bak = f"{path}.backup_{ts}"
    shutil.copy2(path, bak)
    prune_backups(path, keep=MAX_BACKUPS)
    return bak


def list_backups(path: str):
    """列出所有备份版本, 按时间倒序。
    返回 [(路径, mtime, 大小), ...]; 兼容旧版单文件 <path>.backup。"""
    d = os.path.dirname(path)
    base = os.path.basename(path)
    out = []
    if os.path.exists(path + ".backup"):
        p = path + ".backup"
        out.append((p, os.path.getmtime(p), os.path.getsize(p)))
    if os.path.isdir(d):
        for f in sorted(os.listdir(d), reverse=True):
            if f.startswith(base + ".backup_") and os.path.isfile(os.path.join(d, f)):
                p = os.path.join(d, f)
                out.append((p, os.path.getmtime(p), os.path.getsize(p)))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def prune_backups(path: str, keep: int):
    """只保留最近 keep 个备份, 删除更旧的 (兼容旧单文件 .backup 不删)。"""
    items = [p for p, _, _ in list_backups(path) if p != path + ".backup"]
    for p in items[keep:]:
        try:
            os.remove(p)
        except OSError:
            pass
