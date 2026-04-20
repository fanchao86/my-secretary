#!/usr/bin/env python3
"""
BM25 搜索实现 - Julie 知识库搜索
使用 jieba 分词，语义精准无噪声

索引 entry 仅保留必要字段：id, text, tokens
其余元数据（source/category/date 等）从 id 前缀和 markdown 文件获取
"""

import json
import math
import re
import sys
import os
from datetime import datetime
from typing import List, Dict

try:
    import jieba
    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False

# BM25 标准参数
K1 = 1.5
B = 0.75

# id 前缀 -> source 映射
ID_PREFIX_MAP = {"k": "knowledge", "t": "todo", "d": "doctor", "u": "users"}
SOURCE_FILE_MAP = {"knowledge": "knowledge.md", "todo": "todo.md", "doctor": "doctor.md", "users": "users.md"}


def source_from_id(entry_id: str) -> str:
    """从 entry id 前缀推断 source"""
    return ID_PREFIX_MAP.get(entry_id[0], "unknown")


def file_from_source(source: str) -> str:
    """从 source 推断 markdown 文件名"""
    return SOURCE_FILE_MAP.get(source, f"{source}.md")


def tokenize(text: str) -> List[str]:
    """jieba 搜索模式分词：长词拆子词 + 保留有意义的单字 + 英文数字"""
    if not text:
        return []

    if _JIEBA_AVAILABLE:
        # 搜索模式：长词再拆子词（如"茉莉花茶"→茉莉/花茶/茉莉花/茉莉花茶）
        words = jieba.cut_for_search(text)
        tokens = []
        for w in words:
            w = w.strip()
            if not w:
                continue
            # 英文/数字整词保留
            if re.match(r'^[a-zA-Z0-9]+$', w):
                tokens.append(w)
            # 中文2字及以上：全部保留
            elif re.match(r'^[\u4e00-\u9fff]+$', w) and len(w) >= 2:
                tokens.append(w)
            # 中文单字：保留（搜索模式下出现的单字通常有检索意义，如"甜""咸"）
            elif re.match(r'^[\u4e00-\u9fff]$', w):
                tokens.append(w)
            # 混合词（如"AI直播"等）保留
            elif len(w) >= 2 and re.search(r'[\u4e00-\u9fff]', w):
                tokens.append(w)
        return tokens
    else:
        # fallback：bigram + 单字 + 英文数字
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens = []
        for i in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[i] + chinese_chars[i+1])
        for c in chinese_chars:
            tokens.append(c)
        tokens.extend(re.findall(r'[a-zA-Z0-9]+', text))
        return tokens


def build_inverted_index(entries: List[Dict], entry_map: Dict[str, Dict]) -> Dict[str, List[Dict]]:
    """构建倒排索引：term -> [(doc_id, tf)]"""
    inverted: Dict[str, List[Dict]] = {}
    for entry in entries:
        doc_id = entry["id"]
        entry_map[doc_id] = entry
        tokens = entry.get("tokens") or tokenize(entry["text"])
        token_counts: Dict[str, int] = {}
        for t in tokens:
            token_counts[t] = token_counts.get(t, 0) + 1
        for term, tf in token_counts.items():
            inverted.setdefault(term, []).append({"doc_id": doc_id, "tf": tf})
    return inverted


def compute_idf(inverted_index: Dict, num_docs: int) -> Dict[str, float]:
    return {
        term: math.log((num_docs - len(doc_list) + 0.5) / (len(doc_list) + 0.5) + 1)
        for term, doc_list in inverted_index.items()
    }


def compute_avgdl(entries: List[Dict]) -> float:
    if not entries:
        return 0
    total = sum(len(e.get("tokens") or tokenize(e["text"])) for e in entries)
    return total / len(entries)


def _token_weight(term: str) -> float:
    """token 长度权重：中文词越长权重越高，单字降权"""
    if re.match(r'^[\u4e00-\u9fff]+$', term):
        n = len(term)
        if n >= 4:
            return 2.0
        elif n == 3:
            return 1.5
        elif n == 2:
            return 1.0
        else:  # 单字
            return 0.5
    return 1.0


def bm25_search(
    query: str,
    entries: List[Dict],
    inverted_index: Dict,
    idf: Dict,
    avgdl: float,
    entry_map: Dict[str, Dict],
    top_k: int = 5
) -> List[Dict]:
    query_tokens = tokenize(query)
    query_tf: Dict[str, int] = {}
    for t in query_tokens:
        query_tf[t] = query_tf.get(t, 0) + 1

    doc_scores: Dict[str, float] = {}
    for term, qtf in query_tf.items():
        if term not in inverted_index:
            continue
        idf_val = idf.get(term, 0)
        tw = _token_weight(term)
        for doc_info in inverted_index[term]:
            doc_id = doc_info["doc_id"]
            tf = doc_info["tf"]
            entry = entry_map.get(doc_id)
            if not entry:
                continue
            doc_len = len(entry.get("tokens") or tokenize(entry["text"]))
            score = idf_val * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * doc_len / avgdl))
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + score * tw * (0.5 + 0.5 * qtf / max(qtf, 1))

    sorted_ids = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
    result = []
    for doc_id, score in sorted_ids[:top_k]:
        entry = entry_map.get(doc_id)
        if entry:
            src = source_from_id(doc_id)
            result.append({
                "id": doc_id,
                "source": src,
                "file": file_from_source(src),
                "text": entry["text"],
                "score": round(score, 4)
            })
    return result


def load_vector_index(path: str) -> Dict:
    if not os.path.exists(path):
        return {"version": "2.0", "updateDate": "", "entries": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_vector_index(path: str, data: Dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def _now_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _normalize_entry(entry: Dict) -> Dict:
    """将外部传入的 entry 规范化为精简格式"""
    text = entry.get("text") or entry.get("originalText", "")
    tokens = entry.get("tokens") or tokenize(text)
    return {"id": entry["id"], "text": text, "tokens": tokens}


def add_entry(vector_index_path: str, entry: Dict) -> None:
    data = load_vector_index(vector_index_path)
    data["entries"].append(_normalize_entry(entry))
    data["updateDate"] = _now_date()
    save_vector_index(vector_index_path, data)


def add_entries(vector_index_path: str, new_entries: List[Dict]) -> None:
    data = load_vector_index(vector_index_path)
    for entry in new_entries:
        data["entries"].append(_normalize_entry(entry))
    data["updateDate"] = _now_date()
    save_vector_index(vector_index_path, data)


def remove_entry(vector_index_path: str, entry_id: str) -> bool:
    data = load_vector_index(vector_index_path)
    original_len = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
    if len(data["entries"]) < original_len:
        data["updateDate"] = _now_date()
        save_vector_index(vector_index_path, data)
        return True
    return False


def remove_entries(vector_index_path: str, entry_ids: List[str]) -> int:
    id_set = set(entry_ids)
    data = load_vector_index(vector_index_path)
    original_len = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["id"] not in id_set]
    removed = original_len - len(data["entries"])
    if removed > 0:
        data["updateDate"] = _now_date()
        save_vector_index(vector_index_path, data)
    return removed


def search(query: str, vector_index_path: str, top_k: int = 5) -> List[Dict]:
    data = load_vector_index(vector_index_path)
    entries = data.get("entries", [])
    if not entries:
        return []
    entry_map: Dict[str, Dict] = {}
    inverted = build_inverted_index(entries, entry_map)
    idf = compute_idf(inverted, len(entries))
    avgdl = compute_avgdl(entries)
    return bm25_search(query, entries, inverted, idf, avgdl, entry_map, top_k)


def rebuild_index(vector_index_path: str, source_entries: List[Dict]) -> None:
    entries = [_normalize_entry(e) for e in source_entries]
    save_vector_index(vector_index_path, {
        "version": "2.0",
        "updateDate": _now_date(),
        "entries": entries
    })


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: bm25_search.py <command> <vector_index_path> [args...]")
        print("Commands: search <query> [top_k], add (stdin JSON), remove <entry_id>, rebuild (stdin JSON array)")
        sys.exit(1)

    vector_path = sys.argv[2]

    if sys.argv[1] == "search":
        query = sys.argv[3] if len(sys.argv) > 3 else ""
        top_k = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        results = search(query, vector_path, top_k)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif sys.argv[1] == "add":
        entry = json.loads(sys.stdin.read())
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
