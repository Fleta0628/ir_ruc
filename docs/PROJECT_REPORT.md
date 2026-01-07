# Enhanced RUC Search 项目技术报告

**日期**: 2026-01-06  
**作者**: AI Engineer (Cline)

---

## 1. 项目概览 (Project Overview)

本项目旨在为中国人民大学（RUC）构建下一代场景化校园搜索引擎。不同于传统的关键词匹配搜索，本项目采用了 **Data-Centric AI (以数据为中心)** 的设计理念，结合 **RAG (检索增强生成)** 技术，实现了具备“认知推理”与“精准溯源”能力的智能问答系统。

核心目标：
*   解决校园搜索中“官方权威性”排序难的问题（利用 PageRank）。
*   解决语义鸿沟问题（利用 LLM 进行数据增强）。
*   提供流畅、透明的用户体验（Streamlit 前端 + 流式回答）。

---

## 2. 技术架构 (Architecture)

系统整体采用 **离线处理 + 在线服务** 的架构：

```mermaid
graph TD
    A[RUC 官网数据] -->|Scrapy| B(原始网页)
    B -->|PageRank| C[权威度评分]
    B -->|Qwen2.5| D[离线增强数据]
    D -->|BGE-M3| E[ChromaDB 向量索引]
    D -->|Jieba| F[BM25 倒排索引]
    
    User[用户提问] -->|Streamlit| G[Answer Engine]
    G -->|Intent Detection| H[检索意图路由]
    H -->|Hybrid Search| I[混合检索 (Vec + BM25)]
    I -->|SimCheck & Rerank| J[重排序与去重]
    J -->|Context| K[LLM 生成回答]
    K --> User
```

---

## 3. 全流程技术路径 (Pipeline Details)

### Phase 1: 数据获取与基础处理
*   **爬虫 (Spider)**: 使用 `Scrapy` 对 `ruc.edu.cn` 及其子域名进行全站爬取，获取约 40 万条网页数据。
*   **权威度计算 (PageRank)**: 构建网页链接图，计算全局 PageRank 值。这一步解决了“转载通知”与“官方源头”权重区分的问题，确保官方文件（如教务处原发通知）在检索中具有更高权重。
*   **产物**: `crawled_data_deduplicated.jsonl`, `pagerank_results.json`

### Phase 2: 智能 RAG 系统构建

#### Task 1: 离线数据增强 (Data Enrichment)
*   **模型**: `Qwen2.5-7B` (vLLM Native Batching)
*   **任务**:
    1.  **场景分类**: 将网页划分为 **News (新闻)**, **Research (科研)**, **Education (教学)** 三大类。
    2.  **潜在问题生成 (Query Generation)**: 为每个网页生成 3 个潜在的用户提问，扩展语义覆盖面。
    3.  **摘要生成**: 生成一句话摘要。
*   **结果**: `processed_data/enriched_data.jsonl`

#### Task 2: 混合索引构建 (Indexing)
*   **切分**: `RecursiveCharacterTextSplitter` (Chunk Size: 500-1000)。
*   **Embedding**: 使用 `BGE-M3` 模型生成高维向量。
*   **存储**: `ChromaDB` 存储向量及元数据（URL, Title, PageRank, Categories）。
*   **关键词索引**: 构建 `BM25` 倒排索引，用于精确匹配。

#### Task 3: 场景化检索与排序 (Retrieval & Reranking)
*   **意图识别**: 通过 LLM 路由判断用户意图（如“教务处电话” -> Education）。
*   **混合检索**: 并行执行 Vector Search 和 BM25 Search。
*   **重排序 (Rerank)**: 综合考虑 `Vector Score`, `BM25 Score`, `PageRank`, `Intent Boost` 进行加权排序。
*   **去重 (SimCheck)**: **[关键优化]** 实现了基于标题的去重机制，自动剔除内容重复的网页（如多部门转载同一通知），确保 Top-K 结果的多样性。

#### Task 4: 回答引擎 (Answer Engine)
*   **上下文构建**: 动态加载检索到的文档正文。
*   **Prompt Engineering**: 设计了包含“时间感知”和“严格引用约束”的 System Prompt。
*   **流式输出**: 支持 SSE (Server-Sent Events) 风格的流式响应。

#### Task 5: 前端交互界面 (Frontend)
*   **框架**: `Streamlit`。
*   **优化**:
    *   **Lazy Import**: 延迟加载大模型，实现界面秒级启动。
    *   **Loading Spinner**: 友好的加载状态提示。
    *   **权威度可视化**: 在引用卡片中通过颜色（🟢/🟡/⚪）直观展示信源权威度。

---

## 4. 目录结构说明 (Directory Structure)

整理后的项目结构如下：

```text
enhanced_ruc_search/
├── docs/                   # 项目文档与报告
│   ├── PROJECT_REPORT.md   # 本报告
│   └── server_migration_guide.md
├── scripts/                # 独立工具脚本
│   └── pagerank.py         # PageRank 计算脚本
├── task1/                  # 离线数据增强
├── task2/                  # 索引构建
├── task3/                  # 检索核心 (CampusRetriever)
├── task4/                  # 回答引擎 (AnswerEngine)
├── frontend/               # Streamlit 前端
│   └── app.py
├── ruc_search/             # Scrapy 爬虫源码
├── crawled_data_deduplicated.jsonl  # [核心数据] 原始网页
├── processed_data/         # [核心数据] 增强后的数据
├── requirements.txt        # 依赖列表
└── README.md               # 项目入口文档
```

## 5. 总结与展望

本项目成功构建了一个端到端的 RUC 校园搜索引擎，验证了 Data-Centric AI 在垂直领域搜索中的巨大潜力。通过引入 PageRank 和 LLM 数据增强，显著提升了长尾问题（如“科研基金申请”）的回答质量。

未来的优化方向包括：
1.  **多模态检索**: 支持图片和 PDF 文档的检索。
2.  **在线学习**: 根据用户反馈（点击/点赞）实时更新排序权重。
3.  **知识图谱**: 构建校园实体关系图谱，支持更复杂的推理问答。
