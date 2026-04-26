#!/usr/bin/env python3
"""
Julie 数据迁移工具
处理低版本到高版本的升级，逐级执行迁移步骤。
"""

import json
import os
import sys
from typing import List, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")

SKILL_VERSION = "3.2.2"


def get_current_version() -> str:
    """读取 version.json 中的版本号，兼容旧字段 dataVersion"""
    path = os.path.join(DATA_DIR, "version.json")
    if not os.path.exists(path):
        return "0.0.0"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version") or data.get("dataVersion", "0.0.0")
    except (json.JSONDecodeError, KeyError):
        return "0.0.0"


def write_version(version: str, description: str = "") -> None:
    """写入 version.json"""
    path = os.path.join(DATA_DIR, "version.json")
    from datetime import date
    data = {
        "version": version,
        "updateDate": date.today().strftime("%Y-%m-%d"),
        "description": description,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ version.json → {version}")


def parse_version(v: str) -> Tuple[int, ...]:
    """将 'X.Y.Z' 转为可比较的元组"""
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0, 0, 0)


def rebuild_vector_index() -> bool:
    """全量重建向量索引"""
    script = os.path.join(SCRIPT_DIR, "bm25_search.py")
    index_path = os.path.join(DATA_DIR, "vector_index.json")
    sys.path.insert(0, SCRIPT_DIR)

    # 从 markdown 文件提取所有条目
    entries = []
    file_patterns = [
        ("knowledge.md", "k"),
        ("todo.md", "t"),
        ("doctor.md", "d"),
        ("users.md", "u"),
    ]

    for filename, prefix in file_patterns:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.split("\n")
        idx = 0
        for line in lines:
            line = line.strip()
            # 提取 markdown 列表项: - [ ] 内容 或 - 内容
            item = None
            if line.startswith("- [x]") or line.startswith("- [X]"):
                item = line[5:].strip()
            elif line.startswith("- [ ]"):
                item = line[5:].strip()
            elif line.startswith("- ") and not line.startswith("- [") and not line.startswith("##"):
                item = line[2:].strip()
            if item:
                idx += 1
                entries.append({"id": f"{prefix}{idx}", "text": item})

    # 通过子进程调用 rebuild（复用现有逻辑）
    import subprocess
    result = subprocess.run(
        [sys.executable, script, "rebuild", index_path, json.dumps(entries, ensure_ascii=False)],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        print(f"  ✓ 向量索引重建完成（{len(entries)} 条）")
        return True
    else:
        print(f"  ✗ 向量索引重建失败: {result.stderr}")
        return False


# ── 迁移步骤表 ──
# 每个条目: (from_version, to_version, description, handler)
MIGRATIONS: List[Tuple[str, str, str, callable]] = []


def migration(from_v: str, to_v: str, desc: str):
    """装饰器：注册迁移步骤"""
    def decorator(fn):
        MIGRATIONS.append((from_v, to_v, desc, fn))
        return fn
    return decorator


@migration("0.0.0", "3.0.0", "首次安装：创建数据目录和 version.json")
def migrate_initial():
    os.makedirs(DATA_DIR, exist_ok=True)
    write_version("3.0.0", "首次初始化")
    return True


@migration("3.0.0", "3.2.0", "升级 BM25 索引结构（v1 → v2）")
def migrate_bm25_v2():
    print("  → 重建向量索引以匹配新版 tokenizer...")
    return rebuild_vector_index()


@migration("3.2.0", "3.2.1", "JSON 参数传递与触发器格式修正")
def migrate_trigger():
    print("  → 索引格式无变化，更新版本号")
    return True


@migration("3.2.1", "3.2.2", "BM25 搜索校正、批量操作 CLI、数据迁移工具、README 更新")
def migrate_322():
    print("  → BM25 打分公式修正（去除无效权重因子），搜索行为略有变化")
    print("  → 重建索引以确保评分一致性...")
    return rebuild_vector_index()


def run_migrations() -> bool:
    """从当前版本逐级迁移到目标版本"""
    current = get_current_version()
    target = SKILL_VERSION

    print(f"当前版本: {current}")
    print(f"目标版本: {target}")
    print()

    if parse_version(current) >= parse_version(target):
        print("无需迁移。")
        return True

    pending = [
        (fv, tv, desc, fn)
        for fv, tv, desc, fn in MIGRATIONS
        if parse_version(current) <= parse_version(fv) < parse_version(target)
    ]
    pending.sort(key=lambda m: parse_version(m[0]))

    if not pending:
        print(f"未找到从 {current} → {target} 的迁移路径。")
        return False

    print(f"需要执行 {len(pending)} 步迁移:")
    for fv, tv, desc, _ in pending:
        print(f"  [{fv} → {tv}] {desc}")
    print()

    for fv, tv, desc, fn in pending:
        print(f"执行 [{fv} → {tv}] {desc}...")
        success = fn()
        if not success:
            print(f"  ✗ 迁移失败于步骤 [{fv} → {tv}]")
            return False
        write_version(tv, desc)

    print(f"\n✓ 全部迁移完成，版本 {current} → {target}")
    return True


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
