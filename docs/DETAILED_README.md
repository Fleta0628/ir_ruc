# RUC-Pilot (人大校园智能问答助手)

本项目旨在构建一个基于 **RAG (Retrieval-Augmented Generation)** 的下一代场景化校园搜索引擎。

与传统搜索不同，本项目采用了 **Data-Centric AI (以数据为中心)** 的设计理念，利用 **PageRank** 算法解决“官方权威性”排序问题，并引入 **LLM (Qwen2.5)** 进行大规模数据增强，旨在提供具备“认知推理”与“精准溯源”能力的校园问答服务。

---

## 📅 项目路线图 (Roadmap)
所有任务在 conda 环境 `ir` 中完成。

### ✅ 第一阶段：数据获取与基础处理 (已完成)
- **全站爬取**：使用 Scrapy 爬取 `ruc.edu.cn` 及其子域名网页。
- **PageRank 计算**：基于链接关系计算了全局网页权重，解决了“官方页面”与“转载通知”的权重区分问题。
- **产物**：
    - `crawled_data_deduplicated.jsonl`: 去重后的网页数据 (~40w 条)。
    - `pagerank_results.json`: 网页 PageRank 权重字典。

### 🚀 第二阶段：智能 RAG 系统构建 (待开发)
本阶段采用 **“离线数据增强 + 在线混合检索”** 的架构，分为 5 个核心任务。

---

## 🛠 开发任务框架 (Task Framework)

### ✅ Task 1: 类别发现与离线数据增强 (已完成)
**目标**：利用 LLM 对网页进行场景分类与数据增强（生成潜在问题），解决分类不均与语义鸿沟问题。
- **技术栈**：`vLLM` (Native Batching), `Qwen2.5-7B`
- **输入**：`crawled_data_deduplicated.jsonl`
- **步骤**：
    1. **分类体系优化**：
        - 经过多轮验证，最终确定 **News (新闻动态)** / **Research (学术科研)** / **Education (教育服务)** 的三分类体系。
        - 该体系实现了 **News 43% / Research 38% / Education 20%** 的均衡覆盖（Total Mentions）。
    2. **LLM 离线批处理 (Batch Enrichment)**：
        - 使用 `vLLM` 原生引擎 (`batch_processor_native.py`) 对全量 38.6万 条数据进行推理。
        - **输出 JSON**：
            - `soft_categories`: 网页所属的 1-2 个类别（News, Research, Education）。
            - `potential_queries`: 基于网页内容生成的 3 个用户潜在提问。
            - `summary`: 一句话摘要。
    3. **数据合并**：将 `pagerank_score` 和 LLM 处理结果写入每条数据。
- **输出**：`processed_data/enriched_data.jsonl`

### ✅ Task 2: 混合索引构建 (已完成)
**目标**：构建支持语义检索的混合索引知识库。
- **技术栈**：`ChromaDB` (推荐), `BGE-M3`
- **输入**：`processed_data/enriched_data.jsonl`
- **步骤**：
    1. **文本切分 (Chunking)**：使用 `RecursiveCharacterTextSplitter` 将长网页切分为 500-1000 字符的片段。
    2. **向量化 (Embedding)**：构造“增强文本”进行向量化，内容为：`Title + Potential_Queries + Summary + Chunk_Text`。
    3. **索引存储**：存入 ChromaDB，必须包含以下 Metadata 以支持后续筛选和排序：
        - `url`: 原始链接
        - `categories`: 场景分类列表
        - `pagerank`: 权重分数 (float)
        - `title`: 标题
- **输出**：持久化的向量数据库目录 (`./task2/chroma_db`)
- **数据存储格式 (Schema)**：
    - **Document Content**: `Title: {title}\nSummary: {summary}\nQueries: {queries}\nContent: {chunk_text}`
    - **Metadata**:
        - `url`: (str) 原始链接
        - `categories`: (str) 逗号分隔的分类字符串 (e.g., "News,Education")
        - `pagerank`: (float) PageRank 权重
        - `title`: (str) 网页标题

### ✅ Task 3: 场景化检索与排序 (已完成)
**目标**：基于 2x4090 高性能环境，实现“意图识别 + 混合检索 + 多因子重排序”的检索核心，并采用生产级服务架构。
- **技术栈**：
    - **LLM Serving**: `vLLM` (OpenAI Compatible API) 托管 `Qwen2.5-7B-Instruct`。
    - **Retrieval**: `BM25Okapi` (关键词) + `ChromaDB` (语义)。
    - **Client**: `OpenAI SDK` (Python)。
- **架构升级 (Optimization)**：
    - 采用 **Client-Server** 架构：`CampusRetriever` 不再本地加载大模型，而是通过 HTTP API 调用本地运行的 vLLM 服务。
    - **显存解耦**：vLLM 独立管理显存（支持 Continuous Batching），检索器轻量化运行。
    - **混合检索优化**：针对现有向量索引特性，调整了排序权重 (`BM25 * 0.7 + Vec * 0.1`)，显著提升了准确率。
    - **结果去重 (Deduplication)**：实现了基于标题的 **SimCheck 去重机制**，自动剔除内容重复的网页（如多部门转载的同一通知），确保 Top-K 结果的多样性。
- **核心步骤**：
    1. **服务启动**：使用 `task3/start_vllm.sh` 启动本地推理服务。
    2. **BM25 构建**：`task3/build_bm25.py` 预计算倒排索引。
    3. **检索流程**：
        - **Router**: 调用 vLLM API 分析意图 (News/Research/Education)。
        - **Recall**: 并行执行 BM25 和 Vector Search。
        - **Rerank**: 基于 `Keywords + Semantics + PageRank + Intent` 的多因子排序。
- **输出**：
    - `task3/campus_retriever.py`: 支持 API 调用的检索器类。
    - `task3/start_vllm.sh`: 服务启动脚本。

### ✅ Task 4: 认知推理与回答引擎 (Answer Engine)
**目标**：基于检索内容生成高质量、具备逻辑推理的回答，构建 `AnswerEngine`。
- **技术栈**：`OpenAI SDK` (Client), `vLLM` (Server), `Prompt Engineering`
- **核心组件**：
    1. **AnswerEngine**: 封装了检索与生成逻辑的核心类。
        - **动态内容加载**：为了解决 BM25 检索结果缺失正文的问题，引擎在初始化时加载 `enriched_data.jsonl` 构建 `{url: content}` 内存映射，确保所有检索结果都能获取到完整上下文。
        - **智能截断**：针对长文本，采用 `Summary + Content[:600]` 的策略，平衡上下文完整性与 Token 消耗 (适配 4096 Context Window)。
    2. **Prompt System**:
        - **动态时间注入**：自动注入当前日期 (e.g., `Current Date: 2025-01-05`)，准确回答时效性问题。
        - **严格引用约束**：System Prompt 强制模型使用 `[1]` 格式标注来源，并根据检索到的 Metadata (Title, URL) 生成参考文献列表。
- **输出**：
    - `task4/answer_engine.py`: 回答引擎实现。
    - `task4/test_engine.py`: 端到端测试脚本。

### ✅ Task 5: 前端交互界面 (已完成)
**目标**：提供用户友好的问答界面，展示 Data-Centric AI 的核心价值。
- **技术栈**：`Streamlit`
- **核心功能**：
    1.  **极简交互**：流式问答，响应迅速。
    2.  **透明化推理**：使用 Status Bar 展示“意图识别”与“检索过程”。
    3.  **权威信源标注**：基于 PageRank 对参考网页进行权威度评级 (High/Medium/Low)。
    4.  **调试模式**：支持查看原始文本块与详细打分详情。
    5.  **性能优化**：采用 **Lazy Import** 策略，实现界面的秒级启动，并提供清晰的加载反馈。
- **产物**：
    - `frontend/app.py`: Streamlit 前端应用。

## 📂 建议目录结构


enhanced_ruc_search/
├── task3/                  # Task 3: 检索核心 (New)
│   ├── config.py           # 硬件与路径配置
│   ├── start_vllm.sh       # [服务] vLLM 启动脚本
│   ├── build_bm25.py       # BM25 索引构建脚本
│   ├── campus_retriever.py # 核心检索类 (vLLM Client + Hybrid Search)
│   └── test_retrieval.py   # 端到端测试
├── offline_inference/      # Task 1: LLM 离线推理与数据增强
│   ├── batch_processor.py        # [核心] vLLM 原生全量批处理脚本
│   ├── label_sampler.py          # [工具] 小规模采样标注验证
│   ├── data_sampler.py           # [工具] 数据随机采样
│   ├── stat_distribution.py      # [工具] 类别分布统计
│   ├── batch_processor_api.py    # [备用] 基于 API 的批处理脚本 (Legacy)
│   └── prompt_templates.py       # [配置] Qwen 提示词模板
├── retrieval/              # Task 2 (Legacy)
│   ├── vector_store.py     # ChromaDB 封装
├── task4/                  # Task 4: 回答生成引擎
│   ├── answer_engine.py    # [核心] RAG 回答生成器
│   └── test_engine.py      # [测试] 问答测试脚本
├── frontend/               # Task 5: 前端代码
│   └── app.py              # [核心] Streamlit 交互界面
├── crawled_data_deduplicated.jsonl  # [输入] 原始数据
├── pagerank_results.json            # [输入] PR 结果
└── README.md                        # 本文档

## 📦 新增依赖 (requirements.txt)

建议添加以下库：
```text
langchain
langchain-community
chromadb
openai
tiktoken
vllm
streamlit
pandas
jieba
scikit-learn
rank_bm25
transformers
accelerate
