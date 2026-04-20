#!/usr/bin/env python3
"""
BM25 纯算法实现 - Julia 知识库搜索
无需外部依赖，直接运行
"""

import json
import math
import re
import sys
import os
from typing import List, Dict, Any

# BM25 标准参数
K1 = 1.5
B = 0.75


def tokenize(text: str) -> List[str]:
    """优化分词：双字词bigram + 英文单词，精确匹配优先
    策略：单字精确匹配能力牺牲，换取无交叉匹配的语义检索
    """
    if not text:
        return []

    # 提取中文字符序列
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)

    tokens = []
    # 双字词bigram（捕获语义单元）
    for i in range(len(chinese_chars) - 1):
        bigram = chinese_chars[i] + chinese_chars[i+1]
        tokens.append(bigram)

    # 英文/数字按单词
    english_words = re.findall(r'[a-zA-Z0-9]+', text)
    tokens.extend(english_words)

    return tokens


def build_inverted_index(entries: List[Dict]) -> Dict[str, List[Dict]]:
    """构建倒排索引：term -> [(doc_id, tf)]"""
    inverted: Dict[str, List[Dict]] = {}
    for entry in entries:
        doc_id = entry["id"]
        tokens = entry.get("tokens", tokenize(entry["originalText"]))
        # 去重统计 tf
        token_counts: Dict[str, int] = {}
        for t in tokens:
            token_counts[t] = token_counts.get(t, 0) + 1
        for term, tf in token_counts.items():
            if term not in inverted:
                inverted[term] = []
            inverted[term].append({"doc_id": doc_id, "tf": tf})
    return inverted


def compute_idf(inverted_index: Dict, num_docs: int) -> Dict[str, float]:
    """计算每个 term 的 IDF 值"""
    idf: Dict[str, float] = {}
    for term, doc_list in inverted_index.items():
        # IDF = log((N - n + 0.5) / (n + 0.5) + 1)
        n = len(doc_list)
        idf[term] = math.log((num_docs - n + 0.5) / (n + 0.5) + 1)
    return idf


def compute_avgdl(entries: List[Dict]) -> float:
    """计算平均文档长度（以 token 数计）"""
    if not entries:
        return 0
    total = sum(len(e.get("tokens", tokenize(e["originalText"]))) for e in entries)
    return total / len(entries)


def bm25_search(
    query: str,
    entries: List[Dict],
    inverted_index: Dict,
    idf: Dict,
    avgdl: float,
    top_k: int = 5
) -> List[Dict]:
    """对 query 返回 top_k 条 BM25 得分最高的条目"""
    query_tokens = tokenize(query)
    doc_scores: Dict[str, float] = {}

    # 统计 query 中每个 term 出现的次数
    query_tf: Dict[str, int] = {}
    for t in query_tokens:
        query_tf[t] = query_tf.get(t, 0) + 1

    for term, qtf in query_tf.items():
        if term not in inverted_index:
            continue
        idf_val = idf.get(term, 0)
        for doc_info in inverted_index[term]:
            doc_id = doc_info["doc_id"]
            tf = doc_info["tf"]
            # 找到对应 entry 的 doc_len
            entry = next((e for e in entries if e["id"] == doc_id), None)
            if not entry:
                continue
            doc_len = len(entry.get("tokens", tokenize(entry["originalText"])))
            # BM25 公式
            score = idf_val * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * doc_len / avgdl))
            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0
            doc_scores[doc_id] += score * (0.5 + 0.5 * qtf / max(qtf, 1))

    # 排序
    sorted_ids = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
    result = []
    for doc_id, score in sorted_ids[:top_k]:
        entry = next((e for e in entries if e["id"] == doc_id), None)
        if entry:
            entry["bm25_score"] = round(score, 4)
            result.append(entry)
    return result


def load_vector_index(path: str) -> Dict:
    """加载向量索引文件"""
    if not os.path.exists(path):
        return {"version": "1.0", "updateDate": "", "entries": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_vector_index(path: str, data: Dict) -> None:
    """保存向量索引文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_entry(vector_index_path: str, entry: Dict) -> None:
    """添加一条 entry 到向量索引"""
    data = load_vector_index(vector_index_path)
    # tokenize
    if "tokens" not in entry or not entry["tokens"]:
        entry["tokens"] = tokenize(entry["originalText"])
    data["entries"].append(entry)
    from datetime import datetime
    data["updateDate"] = datetime.now().strftime("%Y-%m-%d")
    save_vector_index(vector_index_path, data)


def remove_entry(vector_index_path: str, entry_id: str) -> bool:
    """从向量索引删除一条 entry，返回是否删除成功"""
    data = load_vector_index(vector_index_path)
    original_len = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
    if len(data["entries"]) < original_len:
        from datetime import datetime
        data["updateDate"] = datetime.now().strftime("%Y-%m-%d")
        save_vector_index(vector_index_path, data)
        return True
    return False


def search(query: str, vector_index_path: str, top_k: int = 5) -> List[Dict]:
    """从向量索引搜索，返回 top_k 结果"""
    data = load_vector_index(vector_index_path)
    entries = data.get("entries", [])
    if not entries:
        return []
    inverted = build_inverted_index(entries)
    idf = compute_idf(inverted, len(entries))
    avgdl = compute_avgdl(entries)
    return bm25_search(query, entries, inverted, idf, avgdl, top_k)


def rebuild_index(vector_index_path: str, source_entries: List[Dict]) -> None:
    """全量重建向量索引（从 markdown 重新解析传入）"""
    from datetime import datetime
    entries_with_tokens = []
    for e in source_entries:
        e = dict(e)
        e["tokens"] = tokenize(e["originalText"])
        entries_with_tokens.append(e)
    data = {
        "version": "1.0",
        "updateDate": datetime.now().strftime("%Y-%m-%d"),
        "entries": entries_with_tokens
    }
    save_vector_index(vector_index_path, data)


if __name__ == "__main__":
    # 命令行测试
    # 用法: python3 bm25_search.py search <vector_index_path> "<query>" [top_k]
    # 用法: python3 bm25_search.py add <vector_index_path> <json_entry>
    # 用法: python3 bm25_search.py remove <vector_index_path> <entry_id>
    # 用法: python3 bm25_search.py rebuild <vector_index_path>  # 从 stdin 读 entries 数组
    if len(sys.argv) < 3:
        print("Usage: bm25_search.py <command> <vector_index_path> [args...]")
        sys.exit(1)

    vector_path = sys.argv[2]

    if sys.argv[1] == "search":
        query = sys.argv[3] if len(sys.argv) > 3 else ""
        top_k = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        results = search(query, vector_path, top_k)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif sys.argv[1] == "add":
        entry = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        add_entry(vector_path, entry)
        print("OK")
    elif sys.argv[1] == "remove":
        entry_id = sys.argv[3] if len(sys.argv) > 3 else ""
        ok = remove_entry(vector_path, entry_id)
        print("OK" if ok else "NOT_FOUND")
    elif sys.argv[1] == "rebuild":
        entries = json.loads(sys.stdin.read())
        rebuild_index(vector_path, entries)
        print("OK")
