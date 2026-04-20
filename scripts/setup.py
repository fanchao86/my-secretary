#!/usr/bin/env python3
"""
Julie 环境检查与安装脚本
- 检查 Python 版本
- 检查/安装 jieba 依赖
- 验证搜索脚本
- 检查数据目录结构
"""

import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

PASS = f"{GREEN}✓{RESET}"
FAIL = f"{RED}✗{RESET}"
WARN = f"{YELLOW}!{RESET}"


def check_python():
    """检查 Python 版本"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 7:
        print(f"  {PASS} Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  {FAIL} Python {version.major}.{version.minor}，需要 3.7+")
        return False


def check_jieba():
    """检查 jieba 是否可用"""
    try:
        import jieba
        print(f"  {PASS} jieba 已安装")
        return True
    except ImportError:
        print(f"  {WARN} jieba 未安装")
        return False


def install_jieba():
    """安装 jieba"""
    print("\n  正在安装 jieba ...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "jieba"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import jieba  # noqa: F401
        print(f"  {PASS} jieba 安装成功")
        return True
    except Exception as e:
        print(f"  {FAIL} jieba 安装失败: {e}")
        print(f"      请手动执行: pip3 install jieba")
        return False


def check_search_script():
    """验证搜索脚本能正常运行"""
    script_path = os.path.join(SCRIPT_DIR, "bm25_search.py")
    if not os.path.exists(script_path):
        print(f"  {FAIL} 搜索脚本不存在: {script_path}")
        return False
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=10
        )
        if "Usage" in result.stdout or result.returncode == 1:
            print(f"  {PASS} 搜索脚本可执行")
            return True
        else:
            print(f"  {WARN} 搜索脚本输出异常")
            return False
    except Exception as e:
        print(f"  {FAIL} 搜索脚本执行失败: {e}")
        return False


def check_data_dir():
    """检查数据目录和文件"""
    required_files = {
        "users.md": "主人信息",
        "doctor.md": "健康档案",
        "knowledge.md": "知识库",
        "todo.md": "日程与任务",
        "vector_index.json": "BM25 向量索引",
        "version.json": "版本信息",
    }

    if not os.path.exists(DATA_DIR):
        print(f"  {WARN} data/ 目录不存在（首次使用将自动创建）")
        return True

    print(f"  {PASS} data/ 目录存在")
    all_ok = True
    for filename, desc in required_files.items():
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            if size > 0:
                print(f"    {PASS} {filename} ({desc}, {size}B)")
            else:
                print(f"    {WARN} {filename} ({desc}, 空文件)")
        else:
            print(f"    {WARN} {filename} ({desc}, 未创建)")
            all_ok = False
    return all_ok


def verify_search():
    """端到端验证搜索功能"""
    index_path = os.path.join(DATA_DIR, "vector_index.json")
    script_path = os.path.join(SCRIPT_DIR, "bm25_search.py")

    if not os.path.exists(index_path):
        print(f"  {WARN} 跳过（vector_index.json 不存在）")
        return True

    try:
        result = subprocess.run(
            [sys.executable, script_path, "search", index_path, "测试", "1"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print(f"  {PASS} 搜索功能正常")
            return True
        else:
            print(f"  {FAIL} 搜索返回错误")
            return False
    except Exception as e:
        print(f"  {FAIL} 搜索验证失败: {e}")
        return False


def main():
    print("=" * 50)
    print("  Julie 环境检查与安装")
    print("=" * 50)
    print()

    results = {}

    # 1. Python
    print("【1/5】Python 环境")
    results["python"] = check_python()
    print()

    # 2. jieba
    print("【2/5】jieba 依赖")
    jieba_ok = check_jieba()
    if not jieba_ok:
        jieba_ok = install_jieba()
    results["jieba"] = jieba_ok
    print()

    # 3. 搜索脚本
    print("【3/5】搜索脚本")
    results["script"] = check_search_script()
    print()

    # 4. 数据目录
    print("【4/5】数据目录")
    results["data"] = check_data_dir()
    print()

    # 5. 搜索验证
    print("【5/5】搜索功能验证")
    results["search"] = verify_search()
    print()

    # 汇总
    print("=" * 50)
    all_pass = all(results.values())
    if all_pass:
        print(f"  {GREEN}全部通过！Julie 已就绪。{RESET}")
    else:
        print(f"  {YELLOW}部分项需关注，详见上方。{RESET}")
        if not results["jieba"]:
            print(f"  提示: 搜索将使用 bigram 降级模式，精度较低")
            print(f"  建议: pip3 install jieba")
    print("=" * 50)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
