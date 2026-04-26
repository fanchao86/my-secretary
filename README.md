# Julie - 私人助理 Skill

私人事务管理助理，管理主人信息、健康档案、知识库、日程任务与提醒事项。

> 完整规则定义见 [SKILL.md](SKILL.md)

## 安装

```bash
git clone <repo-url> <skills-path>/julie
cd julie
python3 scripts/setup.py
```

`setup.py` 会自动完成：
1. 检查 Python 版本（需 3.7+）
2. 检查并安装 jieba 分词依赖
3. 验证搜索脚本 `bm25_search.py`
4. 检查数据目录 `data/` 结构
5. **数据版本迁移**（低版本升级时自动逐级执行）
6. 端到端搜索功能验证

> jieba 未安装时搜索仍可运行（bigram 降级模式），但精度较低，建议安装。

## 使用

对话中触发关键词（`Julie`、`助理`、`日程`、`待办`、`提醒`等）激活技能。首次使用时 AI 会引导创建主人档案，自动在项目目录下生成 `data/` 目录及数据文件。

### 支持的操作

| 操作 | 示例 |
|------|------|
| 建档 | "Julie，帮我建档，我叫小明" |
| 查询信息 | "我的生日是什么时候" |
| 修改信息 | "把我的昵称改成大明" |
| 健康档案 | "我最近在吃降压药，帮我记一下" |
| 加入知识 | "记住：我喜欢喝美式咖啡" |
| 查找知识 | "我之前说过喜欢什么咖啡" |
| 添加日程 | "明天下午3点有个会议" |
| 查询日程 | "今天有什么安排" |
| 完成任务 | "把明天的会议标记为已完成" |
| 删除事项 | "删掉明天的会议" |

### 数据文件

运行时自动生成于 `data/` 目录，不纳入版本控制。

```
data/
├── users.md           主人信息
├── doctor.md          健康档案
├── knowledge.md       知识库
├── todo.md            日程与任务
├── vector_index.json  BM25 向量索引
└── version.json       版本信息
scripts/
├── bm25_search.py     BM25 搜索脚本
├── migrate.py         版本迁移工具
└── setup.py           环境安装脚本
```

## 升级

```bash
cd julie
python3 scripts/setup.py    # 自动检测版本并执行迁移
# 或单独执行：
python3 scripts/migrate.py  # 逐级升级到当前技能版本
```

`migrate.py` 按版本顺序逐级执行迁移（重建索引、修正数据格式等），每步完成后写入 `version.json`，支持断点续迁。

## 搜索脚本 CLI

```bash
# 搜索
python3 scripts/bm25_search.py search <index_path> <query> [top_k]

# 添加 / 批量添加
python3 scripts/bm25_search.py add <index_path> '<entry_json>'
python3 scripts/bm25_search.py add-batch <index_path> '<entries_json>'

# 删除 / 批量删除
python3 scripts/bm25_search.py remove <index_path> <entry_id>
python3 scripts/bm25_search.py remove-batch <index_path> id1,id2,...

# 全量重建
python3 scripts/bm25_search.py rebuild <index_path> '<entries_json>'
```

> 1 万条索引约 476 KB，搜索延迟约 90ms；批量 add 100 条约 0.5ms/条。

## 配置

所有行为规则和文件模板定义在 `SKILL.md` 中，修改该文件即可调整助理行为。
