---
name: Pipeline 实现规格
description: 证据驱动多模态 Pipeline 的第一版实现方案与约定
type: project
---

# Pipeline 实现规格

## 1. V1 范围

V1 只解决最核心的问题，不追求一步到位。

保留：

- 现有 PDF 解析能力
- OCR
- 布局检测
- 导出接口

V1 要完成：

- 建立文档级弱预判能力
- 建立统一证据层
- 建立区域优先的提取链路
- 建立页面级验证
- 建立有限重入控制器

V1 不做：

- 跨页重构
- 全量业务配置系统
- 开放式 agent 流程
- 更多页型专项 rescue 分支

补充约束：

- V1 需要支持“长表格续页的表头继承”
- 长表格兼容只覆盖“首页有表头、后续页无表头”的简化模式
- 长表格兼容默认假设该 PDF 全部页面都是表格页
- V1 不显式建模变体簇
- 同款多图先挂在同一商品单元下
- 是否存在更细的变体层级，留到后续版本再处理

## 2. 文档级弱预判

### 2.1 目标

只提供弱先验，不主导字段抽取。

第一版默认输出：

- `document_theme`
- `ignore_hints`

### 2.2 采样策略

默认按固定间隔采样 2 页，尽量均匀覆盖文档前后位置。

当前实现约定：

- 运行时默认采样首页和末页
- 若文档只有 1 页，则只采样首页
- 采样结果只用于构建弱提示，不直接决定字段抽取

### 2.3 输出协议

第一版建议输出结构：

```json
{
  "document_theme": "家具产品目录",
  "ignore_hints": [
    "品牌logo",
    "背景装饰图"
  ]
}
```

字段说明：

- `document_theme`
  - 文档主题弱标签
  - 仅作为页面级处理弱先验
- `ignore_hints`
  - 应优先忽略的非商品内容类型
  - 仅作为弱提示，不作为强规则

第一版建议格式：

- `document_theme` 使用简短自然语言短语
- `ignore_hints` 使用简短自然语言短语列表
- 每个短语尽量控制在 2 到 8 个字或少量词组内
- 不输出长段解释
- 不要求固定枚举

推荐示例：

- `document_theme`
  - `家具产品目录`
  - `灯具画册`
  - `服装价格表`
- `ignore_hints`
  - `品牌logo`
  - `背景装饰图`
  - `页眉横幅`
  - `非售卖场景道具`

设计原则：

- 第一版优先可扩展性，不优先做硬枚举
- 后续如果需要统计、分析或规则命中，可以在下游再做可选归一化
- pipeline 主逻辑不应依赖这些自然语言标签的精确匹配

## 3. 长表格续页预处理

### 3.1 目标

兼容“只有首页有表头、后续页只有列数据”的长表格场景。

这类场景下，后续页不应再依赖模型猜测列含义，而应直接继承上游页已经确认的表头定义。

### 3.2 处理原则

- 默认仅从首页提取表头 schema
- 将首页表头 schema 传递到后续全部页面
- 后续页按继承后的列定义解析数据
- 在这一前提下，后续页允许并发处理
- 当前版本不处理“后续页再次出现新表头”或“中间夹杂非表格页”的情况

### 3.3 第一版处理策略

第一版优先走表格结构化解析：

- 首页提取表头
- 后续页按继承表头做列对齐和结构化解析

如果结构化解析失败：

- 再回退到 VLM 表格识别
- 并显式告诉模型“这是表格页”
- 让模型按已知表头语义去理解列内容，而不是自由猜字段

### 3.4 输出要求

预处理阶段应额外产出：

- `table_schema_id`
- `inherited_headers`
- `is_table_continuation`
- `header_source_page`
- `table_pdf_mode`

这些信息应进入后续页面处理上下文，避免后续页再去猜列语义。

### 3.5 输入输出协议

建议输入：

```json
{
  "doc_id": "xxx",
  "page_no": 3,
  "table_blocks": [
    {
      "bbox": [0, 0, 1000, 1400],
      "rows": [["A", "B", "C"]]
    }
  ],
  "raw_text": "...",
  "page_size": [1000, 1400]
}
```

建议输出：

```json
{
  "table_schema_id": "table_schema_page_1",
  "inherited_headers": [
    "商品名称/描述",
    "售价",
    "颜色"
  ],
  "is_table_continuation": true,
  "header_source_page": 1,
  "table_pdf_mode": true
}
```

解释：

- `table_schema_id`
  - 当前表头 schema 的稳定标识
- `inherited_headers`
  - 继承给当前页的数据列定义
- `is_table_continuation`
  - 当前页是否按续表页处理
- `header_source_page`
  - 表头来源页，第一版默认始终为首页
- `table_pdf_mode`
  - 当前 PDF 是否进入“表格 PDF 模式”

### 3.6 失败回退

第一版建议回退顺序：

1. 首页抽取表头失败
   - 尝试 OCR + 表格结构恢复
2. 后续页结构化对齐失败
   - 回退到带表格提示的 VLM
3. VLM 仍无法稳定对齐
   - 标记低置信并保留原始表格文本

这里的回退目标不是“重新猜字段”，而是尽量保住表格原始内容和列顺序。

### 3.7 表格 VLM 回退 Prompt

当结构化表格解析失败时，VLM 回退仍然必须是“带约束的表格理解”，而不是自由抽取。

输入建议：

- 页面截图
- 已知表头 `inherited_headers`
- OCR 或原始表格文本
- 明确提示“这是表格页”

建议 prompt 骨架：

```text
你现在处理的是一个表格页，不是普通商品宣传页。

已知条件：
1. 这页是长表格的一部分。
2. 首页表头已经确定，当前页沿用这些表头。
3. 你的任务是把当前页的每一行数据对齐到给定表头，不要新增字段名。

要求：
1. 只能使用给定的表头。
2. 不允许猜测新的列含义。
3. 若某个单元格无法确定，保留空值或原始文本。
4. 只输出结构化 JSON。
```

输出建议：

```json
{
  "headers": ["商品名称/描述", "售价", "颜色"],
  "rows": [
    {
      "商品名称/描述": "现代椅",
      "售价": "199",
      "颜色": "胡桃色"
    }
  ]
}
```

约束：

- `headers` 必须与 `inherited_headers` 一致
- 不允许生成未定义列
- 单元格值允许保留原始文本
- 允许留空，但不允许编造

## 4. Phase 2: 区域提议实现

### 4.1 目标

Phase 2 不是纯 VLM 一步到位，而是“规则先提议，VLM 再修正”。

第一版默认目标是尽量做到：

- `1 Region = 1 商品单元`

### 4.2 初始候选来源

用确定性方法生成初始候选：

- 原生图片对象
- layout 区域
- 文本块聚类
- OCR 块聚类

先生成一批较粗但高召回的候选区域。

### 4.2.1 原子对象协议

区域提议阶段不直接面对整页自由内容，而是先面对一组“原子对象”。

第一版建议原子对象只保留三类：

- `text_block`
- `image_block`
- `layout_block`

建议统一结构：

```json
{
  "object_id": "text_12",
  "object_type": "text_block",
  "bbox": [100, 200, 380, 280],
  "text": "现代简约单人椅",
  "confidence": 0.98,
  "source": "pdf_text"
}
```

字段说明：

- `object_id`
  - 原子对象唯一标识
- `object_type`
  - `text_block / image_block / layout_block`
- `bbox`
  - 页面坐标系下的包围框
- `text`
  - 仅文本对象需要
- `confidence`
  - 原子对象自身可信度
- `source`
  - 例如 `pdf_text / ocr_text / native_image / render_crop / layout`

### 4.2.2 数字版与扫描版差异

数字版 PDF：

- 优先使用原生图片对象作为 `image_block`
- 优先使用 PDF 原生文本作为 `text_block`
- OCR 作为补充来源

扫描版 PDF：

- 以渲染页中的图片区块作为 `image_block`
- 以 OCR 文本作为 `text_block`
- 若需要，可用 layout 帮助恢复局部区域

### 4.3 VLM 在区域提议阶段的职责

VLM 只负责：

- 做分组
- 做归属
- 做区域修正

VLM 不负责：

- 抽取属性值
- 生成商品名称
- 生成颜色、型号、价格

### 4.4 Phase 2 Prompt 原则

核心要求：

- 只做区域划分和图文归属
- 不做属性抽取
- 不做商品命名
- 输出结构化 JSON

建议输入：

- 页面渲染图
- 原子对象列表
  - `object_id`
  - `object_type`
  - `bbox`
  - `text`
  - `confidence`
  - `source`
- 可选的 layout 区域
- 可选的文档主题弱先验

建议输出：

- `regions`
  - `member_object_ids`
  - `region_type`
  - `confidence`
  - `reason`

第一版推荐做法：

- VLM 主要输出“哪些原子对象属于同一区域”
- 区域 `bbox` 由程序根据成员对象并集确定
- 不把“精确画框”作为第一版主要能力要求

### 4.4.1 `RegionProposal` JSON Schema

第一版建议输出 schema：

```json
{
  "regions": [
    {
      "region_id": "region_1",
      "region_type": "product_unit",
      "member_object_ids": ["text_1", "text_2", "image_3", "layout_2"],
      "confidence": 0.92,
      "reason": "主图与文案相邻，且小图属于同一商品"
    }
  ],
  "ignored_object_ids": ["image_9"]
}
```

约束：

- `region_type` 第一版只允许：
  - `product_unit`
  - `ignore`
- `member_object_ids` 只能引用输入里出现过的对象
- 不允许模型生成新的对象 ID
- 一个对象默认只应归属于一个 `product_unit`
- 若对象无法确定归属，可进入 `ignored_object_ids`

程序侧补充：

- `bbox` 不由模型直接输出
- 由成员对象并集生成最终 `RegionProposal.bbox`
- 若一个 region 没有任何成员对象，应直接丢弃

### 4.4.2 Prompt v1

第一版 prompt 建议固定成“任务定义 + 输入对象 + 输出 JSON + 禁止项”四段。

建议骨架：

```text
你是一个页面商品单元分组器，不是属性抽取器。

任务：
根据页面截图以及给定的原子对象列表，
把属于同一商品单元的对象分到同一个 region。

要求：
1. 只做区域划分和图文归属，不抽取属性，不命名商品。
2. 默认尽量让一个 region 只对应一个商品单元。
3. 如果一个大图旁边有多个小图，且视觉上属于同一商品，应放入同一区域。
4. 如果存在独立文案或独立商品块，应拆成不同区域。
5. 如果页面没有文案，也要尽量恢复多个独立商品区域。
6. 明显宣传图、logo、背景装饰图不要输出为商品区域。
7. 只能使用输入中已有的 object_id。
8. 只输出 JSON。
```

第一版不建议：

- 在 prompt 中要求模型输出精确 bbox
- 在这一阶段要求模型输出商品名称
- 在这一阶段要求模型输出价格、颜色、型号

## 5. 核心对象

说明：

- 第一版运行时已经显式落地 `PageEvidence` 和 `RegionProposal`
- 第一版运行时继续复用现有 `SKUResult` 作为候选和验证后的统一承载对象
- 字段级最小证据当前主要通过 `evidence_mode`、`raw_attribute_text`、`product_description` 这些字段保留
- 下述 `EvidenceRef / FieldEvidence / RegionEvidence / CandidateSKU / VerifiedSKU` 更接近推荐扩展形态，不要求第一版全部独立成类

### 5.1 `PageEvidence`

页面级原始证据容器。

关键内容：

- 页面尺寸
- PDF 文本块
- OCR 文本块
- 图片对象
- 布局区域
- 页面渲染图
- 页面提示信息
- 表格表头继承信息

### 5.2 `RegionProposal`

候选商品单元区域。

关键字段：

- `region_id`
- `bbox`
- `region_type`
- `proposal_source`
- `score`
- `member_object_ids`
- `reason`

说明：

- `Region` 是中间证据容器，不是最终商品对象
- 第一版尽量让一个 `Region` 对应一个商品单元
- `Region` 的划分质量是新 pipeline 的核心能力之一

### 5.3 `EvidenceRef`

统一引用底层证据对象。

关键字段：

- `source_type`
- `object_id`
- `bbox`
- `text`
- `confidence`

### 5.4 `FieldEvidence`

字段级证据。

关键字段：

- `field_name`
- `field_value`
- `support`
- `refs`
- `evidence_text`
- `confidence`

目标态要求：

- 关键字段默认都应带 `FieldEvidence`
- 没有证据引用的字段不能视为高可信

证据来源分类建议至少区分：

- `pdf_text`
- `ocr_text`
- `multi_source`
- `visual_only`

说明：

- 这里更适合做“证据来源分类”
- `confidence` 单独记录，不与来源分类混为一体
- `support` 第一版建议只区分：
  - `direct`
  - `normalized`
  - `derived`

### 5.5 `RegionEvidence`

区域级证据聚合结果。

关键字段：

- `region_id`
- `text_refs`
- `ocr_refs`
- `image_refs`
- `region_context_text`
- `render_ref`

### 5.6 `CandidateSKU`

区域级候选商品单元。

关键字段：

- `candidate_id`
- `region_id`
- `attributes`
- `field_evidence`
- `confidence`

说明：

- 可以表示“视觉上成立的商品单元”
- 但文本属性仍必须遵守“无证据不补写”

### 5.7 `VerifiedSKU`

页面级验证后的商品单元。

关键字段：

- `sku_id`
- `region_ids`
- `attributes`
- `field_evidence`
- `evidence_mode`
- `verification_status`
- `source_candidate_ids`

说明：

- `evidence_mode` 推荐至少区分：
  - `text_backed`
  - `visual_only`

### 5.8 `BindingDecision`

商品单元与图片资产的最终映射。

关键字段：

- `sku_id`
- `region_id`
- `image_id`
- `binding_type`
- `confidence`

说明：

- 第一版只区分主图和细节图
- 不引入“共享图”概念
- 若区域划分正确，优先选择区域内最大、最清晰、最完整的一张图作为主图
- 同一区域内其余相关图片统一视为细节图、局部图或同款图
- 第一版不主动定义“规格图片”，导出时该列默认留空

### 5.9 中间记录

为了后续排查问题，至少应记录：

- 区域提议来源
- 区域合并或拆分原因
- 字段证据来源分类
- 页面级验证动作
- 资产生成方式
  - `native_image`
  - `merged_tiles`
  - `render_crop`
- 重入触发原因

这些记录用于可追溯，不对外导出。

## 6. 质量控制与重入

### 6.1 原则

第一版需要质量控制，但不依赖固定权重总分。

更合理的方式是：

- 确定性层检查硬事实
- VLM 判断语义歧义
- 控制器决定是否重入或升级

### 6.2 应由确定性层判断的内容

- 关键字段是否无证据
- 文本或图片是否未被任何区域吸收
- 是否出现明显重复候选
- 是否超出预算
- `visual_only` 区域是否小到明显更像碎片而不是商品图

### 6.3 应由 VLM 判断的内容

- 图文是否属于同一商品单元
- 多张图是否属于同一商品
- 装饰物还是真商品
- 候选应合并、拆分还是丢弃

### 6.4 有限重入

允许有限重入，不允许开放式循环。

允许动作：

- `retry_region_proposal`
- `retry_region_extraction`
- `retry_page_verification`
- `retry_binding_resolution`
- `escalate_to_human`

约束：

- 每类动作每页最多一次
- 每页最多两轮主循环
- 超预算后直接结束或转人工

当前实现约定：

- 第一版运行时代码尚未启用完整的重入控制器
- 当前只保留单轮 `region_refine` 和单轮 `page_verify`
- 完整的 `retry_region_proposal / retry_region_extraction / retry_page_verification / retry_binding_resolution` 留到后续版本

接受新结果的原则：

- 漏提风险不上升
- 关键字段无证据情况不恶化
- 图文归属歧义减少
- 合并/拆分冲突减少
- 绑定未决减少

## 7. 当前实现约定

以下内容已作为当前默认实现约定。

- 文档级弱预判输出 `document_theme + ignore_hints`
- `document_theme` 与 `ignore_hints` 第一版使用简短自然语言短语，不使用硬枚举
- 长表格模式下默认只从首页提取表头
- 长表格模式下默认认为该 PDF 全部页面都是表格页
- 长表格页优先走结构化解析，失败后再回退到带表格提示的 VLM
- `region_type` 第一版只保留 `product_unit` 和 `ignore`
- `region_type` 在后续一段时间内也不主动扩展
- 属性相关文本先进入“商品描述”，再抽离结构化字段
- `visual_only` 商品单元默认不采用“只要成区就输出”
- `visual_only` 采用宽松策略，只要成区且不明显属于宣传/装饰，就允许输出
- `visual_only` 增加最小面积阈值，但阈值尽可能小，只用于过滤明显碎片
- 第一版建议使用页面面积占比阈值 `min_visual_only_area_ratio = 0.003`
- 同页重复商品默认合并为一个商品单元
- 图片资产当前默认保留筛选后的全部相关图片
- `规格图片` 列第一版默认留空

## 8. 非阻塞后续优化项

以下问题不会阻塞编码，但后续可按需要继续优化：

- `document_theme / ignore_hints` 后续是否需要增加可选归一化层
- `min_visual_only_area_ratio` 是否需要按文档类型区分

## 9. 说明

这份文档只承载实现细节和默认约定。

业务语义放在 [pipeline-design.md](/home/fulei/codes/pdf-sku/docs/pipeline-design.md)。
Excel 导出契约放在 [pipeline-export-contract.md](/home/fulei/codes/pdf-sku/docs/pipeline-export-contract.md)。
