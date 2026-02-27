# Changelog

## V0.4.0 (2026-02-27)

### 新功能
- **Phase 2c 合成大图布局检测**: 引入 DocLayout-YOLO 模型，自动检测并拆分覆盖整页的合成大图为独立产品区域
  - 触发条件: 页面仅 1 张 search_eligible 图片且 bbox 面积 > 60% 页面面积
  - 检测到 ≥2 个 Figure 区域时拆分为 `p{page}_region_{idx}` 子图
  - NMS 后处理去除包含关系的冗余大框
  - Graceful degradation: ultralytics/doclayout-yolo 未安装或模型不存在时自动跳过

### 配置
- 新增环境变量: `DOCLAYOUT_MODEL_PATH`, `LAYOUT_DETECT_ENABLED`, `LAYOUT_DETECT_CONFIDENCE`
- 新增 optional dependency group: `layout = ["doclayout-yolo>=0.0.4", "ultralytics>=8.1.0"]`

### 部署
- `setup.sh` 新增自动安装布局检测依赖和下载模型的步骤
- `server/.gitignore` 新增 `models/*.pt` 忽略规则
- `README.md` 更新前置要求、项目结构和手动安装说明

---

## V0.3.0 (2026-02-24)

### 新功能
- **Product→SKU 两级层级模型**: SKU 按产品分组，支持 `product_id` 和 `variant_label`
- **OpenAI 兼容客户端**: 通用 `OpenAICompatClient`（`openai_compat.py`）支持 laozhang.ai / OpenRouter 等中转服务
- **OpenRouter 集成**: 可通过 OpenRouter 访问 400+ 模型
- **图片锚点空间聚类**: 使用图片 bbox 作为锚点，改进文字块分组
- **模型号 pattern 分割**: 按型号标记（如 858B#）自动拆分 SKU 边界
- **系列共有属性识别**: 材质/颜色作为系列级属性，不按颜色拆分变体

### 改进
- **SKUList 按产品分组显示**: 可折叠/展开产品组
- **LLM Prompt 产品分组格式**: 提升多产品页面识别准确率
- **Exporter 自动分配正式 product_id**: 格式化产品 ID 分配
- **Binder 同产品组绑定优化**: 同产品组 SKU 统一绑定到最高置信度图片

### 数据库变更
- `skus` 表新增 `product_id` (TEXT) 和 `variant_label` (TEXT) 列
- 新增索引 `idx_skus_product(job_id, product_id)`
- 新增 Alembic 迁移 `003_add_product_grouping`

### 配置
- 新增环境变量：`GEMINI_API_BASE`, `QWEN_API_BASE`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`

---

## V0.2.0 (2026-02-21)

### Pipeline 并行化
- **Orchestrator 重构**: 删除 `_process_sequential` / `_process_chunked` 双模式，统一为 `_process_parallel`，使用 `asyncio.Semaphore` 控制并发（默认 5，通过 `PIPELINE_CONCURRENCY` 环境变量配置）
- **CrossPageMerger 并发安全**: `cache_page` / `find_continuation` 改为 async + per-job `asyncio.Lock`；前页未缓存时优雅降级
- **每页独立 DB session**: 并行页面不再共享数据库会话，避免并发写冲突
- **ChunkingStrategy 解耦**: Orchestrator 不再依赖 ChunkingStrategy
- **性能提升**: 18 页 PDF 处理时间从 ~22 分钟降至 ~5 分钟

### Job 详情页增强
- **后端**: 新增 `GET /jobs/{id}/images/{image_id}` 图片服务端点
- **后端**: 新增 `GET /jobs/{id}/pages/{n}/detail` 页面+SKU+图片合并响应
- **后端**: `GET /jobs/{id}/skus` 返回每个 SKU 的 `images` 数组（通过 SKUImageBinding JOIN）
- **前端**: Pages 表格新增缩略图列（60x80 lazy loading）
- **前端**: 点击页面行展开详情（大图 + 页面 SKU 列表 + 产品图片缩略图）
- **前端**: SKU 列表图片列显示缩略图（32x32），点击弹出 Lightbox
- **前端**: SKU 列表点击展开显示全部属性详情
- **前端**: 兼容 `model_number`/`product_name` 和 `model`/`name` 字段名

### 商品导入配置 UI
- **新增页面**: `/config/import`（仅 admin 角色）
- **新增 Store**: `importConfigStore` (Zustand + persist + immer)，数据保存到 localStorage
- **三个配置区块**: API 接口配置、字段映射表（可增删行）、腾讯云 COS 配置
- **导航集成**: OPS_NAV 添加"导入配置"入口

### 文档版本更新
- 技术架构文档: V1.6 → V1.7
- Pipeline 详细设计: V1.1 → V1.2
- Gateway 详细设计: V1.1 → V1.2
- 服务端版本: 0.1.0 → 0.2.0
- 前端版本: 0.1.0 → 0.2.0

---

## V0.1.0 (2026-02-18)

- 初始版本：完整 Pipeline 9 阶段处理链、Gateway、Evaluator、Collaboration、Output、Feedback 模块
- 前端 SPA：Dashboard、Job 管理、标注系统、配置管理
