# Changelog

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
