---
name: Pipeline 文档索引
description: 证据驱动多模态 Pipeline 的设计、实现和导出契约索引
type: project
---

# Pipeline 文档索引

当前文档体系按职责拆分为三份，避免设计原则、实现细节和导出契约耦合在一起。

## 文档分工

- [pipeline-design.md](/home/fulei/codes/pdf-sku/docs/pipeline-design.md)
  - 回答“这个 pipeline 是什么、为什么这么设计”
  - 包含业务定义、核心原则、视觉与文本边界、主链路骨架

- [pipeline-implementation.md](/home/fulei/codes/pdf-sku/docs/pipeline-implementation.md)
  - 回答“第一版准备怎么实现”
  - 包含区域提议实现思路、核心对象、质量控制、有限重入、V1 约定

- [pipeline-export-contract.md](/home/fulei/codes/pdf-sku/docs/pipeline-export-contract.md)
  - 回答“最终 Excel 必须怎么导出”
  - 包含字段顺序、重点识别字段、图片列展开规则、图片嵌入要求

- [pipeline-v2-usage.md](/home/fulei/codes/pdf-sku/docs/pipeline-v2-usage.md)
  - 回答“怎么把系统切到 v2 并实际跑起来”
  - 包含在线 Job、benchmark、单文件脚本三种使用方式

## 阅读顺序

建议按以下顺序阅读：

1. 先看 [pipeline-design.md](/home/fulei/codes/pdf-sku/docs/pipeline-design.md)
2. 再看 [pipeline-implementation.md](/home/fulei/codes/pdf-sku/docs/pipeline-implementation.md)
3. 最后看 [pipeline-export-contract.md](/home/fulei/codes/pdf-sku/docs/pipeline-export-contract.md)

如果你现在要直接运行，请先看：

- [pipeline-v2-usage.md](/home/fulei/codes/pdf-sku/docs/pipeline-v2-usage.md)

## 解释优先级

如果三份文档出现理解冲突，优先级按以下顺序处理：

1. [pipeline-export-contract.md](/home/fulei/codes/pdf-sku/docs/pipeline-export-contract.md)
2. [pipeline-design.md](/home/fulei/codes/pdf-sku/docs/pipeline-design.md)
3. [pipeline-implementation.md](/home/fulei/codes/pdf-sku/docs/pipeline-implementation.md)

## 当前状态

当前主方向已经定下：

- 证据先行
- 视觉主导归属与验证
- 文本属性禁止臆造
- 几何关系只做弱特征
- 页面级高召回
- 有限重入，不做开放式 agent 循环

非阻塞的后续优化项，统一放在 [pipeline-implementation.md](/home/fulei/codes/pdf-sku/docs/pipeline-implementation.md) 尾部。
