# Pipeline 已知问题与待处理遗留事项

> 最后更新: 2026-03-23
> 数据集 PDF/Excel 路径前缀: `/home/zzc/Documents/pdf整理/`
> 最新基线: P=79.3% R=88.9% F1=83.8% (81 数据集抽样, 10702 GT SKU)

---

## 一、FP 类问题 (Precision 方向)

### FP-2: 颜色/组合变体导出为独立 SKU

- **现象**: `dedup_by_model` 中 key = `model||color`，同型号不同颜色算不同 SKU
- **影响**: ~15% FP（OY-795 黑/白/灰 → 3 条，ground truth 只算 1 条）
- **根因**: 颜色感知去重设计上把同型号不同颜色视为不同 SKU，但部分 GT 按型号合并
- **方案**: 去掉颜色感知，同 model_number 直接合并；或按业务需求可配置
- **风险**: 中（某些目录颜色变体确实是独立 SKU）
- **源数据集**:
  - 中古系列-沙发(纳威) — PDF: `中古系列-沙发(纳威)/中古系列-沙发(纳威).pdf` Excel: `中古系列-沙发(纳威)/中古系列-沙发(纳威).xlsx`
  - 智鸿家具-餐椅产品展示 — PDF: `智鸿/智鸿家具-餐椅产品展示-2025年9月(1).pdf` Excel: `智鸿/智鸿家具-餐椅产品展示-2025年9月(1).xlsx`
  - 万日红家具美式中古图册 — PDF: `万日红家具美式中古图册/万日红家具美式中古图册.pdf` Excel: `万日红家具美式中古图册/万日红家具美式中古图册A.xlsx`
- **状态**: 🟡 暂不处理

---

### FP-8: 零部件/配件专营图册可能被黑名单误杀

- **现象**: SCENE_PROPS 硬黑名单包含零部件词（椅脚、坐垫、板材等），若遇到专营配件/五金的商家图册，其主营产品会被误过滤
- **影响**: 当前样本无此类图册，暂无实际影响
- **根因**: 黑名单不区分"场景道具中的零部件"和"零部件专营商品"，触发条件为无型号+无价格+名称命中
- **方案**: 将部分零部件词移到 SCENE_SOFT_PROPS（仅 scene_filter=True 时过滤），或检测 CatalogProfile 主营品类含"配件/五金"时跳过这些黑名单
- **源数据集**: 当前无对应样本，后续加入配件类图册时验证
- **状态**: 🔴 待处理

---

### FP-9: Ground Truth 粒度不匹配（套餐 vs 单品）

- **现象**: 每页展示一套餐饮空间方案（卡座+餐椅+餐桌+圆桌等），每件有独立型号，Pipeline 按单品正确提取 ~5 条/页，但 GT 把每页整套方案标为 1 个 SKU
- **影响**: ~292 FP（该数据集 P=9.0%），严重拉低总 P
- **根因**: GT 标注以"场景方案"为粒度而非"单品"，与 Pipeline 按独立型号提取的逻辑不一致
- **方案**: 修正 GT 标注为单品粒度；或在 benchmark compare 中支持套餐匹配模式
- **源数据集**:
  - 2025相约餐饮家具 — PDF: `2025相约餐饮家具/2025相约餐饮家具.pdf` Excel: `2025相约餐饮家具/1683860536480_template.xlsx`
- **状态**: 🔴 待处理，需先确认业务上 SKU 粒度定义

---

### FP-10: 配套产品被提取但 GT 不计

- **现象**: 沙发图册中每页沙发旁的茶几/边几有独立型号（WT-73、2526# 等），Pipeline 正确提取，但 GT 只计算主产品（沙发），配套小件不算 SKU
- **影响**: ~55 FP
- **根因**: GT 只标注了页面主产品，配套展示的茶几/边几虽有独立型号但未纳入 GT；companion_rescue 机制进一步放大了此类 FP
- **方案**: 修正 GT 标注包含配套产品；或根据图册主营品类过滤非主营配套件；或限制 companion_rescue 触发条件
- **源数据集**:
  - 2025新款电子版 (27 FP) — PDF: `七色鸟/2025新款电子版.pdf` Excel: `七色鸟/2025新款电子版.xlsx`
  - 2025秋季新款电子画册 (14 FP) — PDF: `七色鸟/2025秋季新款电子画册.pdf` Excel: `七色鸟/2025秋季新款电子画册.xlsx`
  - 2024图册-WS系列 (部分) — PDF: `2024图册-WS系列/2024图册-WS系列.pdf` Excel: `2024图册-WS系列/已导入148个--2024图册-WS系列.xlsx`
- **状态**: 🔴 待处理，需先确认业务上配套产品是否算独立 SKU

---

### FP-13: 尺寸变体被拆分为独立 SKU

- **现象**: 同一产品不同尺寸规格（如 160×230cm、200×290cm、300×400cm）被拆分为多个 SKU，但 GT 中同型号多尺寸在同一行
- **影响**: 大量 FP，尤其在地毯/窗帘等尺寸为主要规格维度的品类
- **根因**: `_merge_variant_color()` 只合并颜色变体，缺少尺寸变体合并逻辑
- **方案**: 新增 `_merge_variant_size()`，同型号不同尺寸合并为一个 SKU
- **风险**: 低（仅在去重阶段）
- **源数据集**:
  - 丽轩地毯 常规款式图册 (fp=236, P=27.6%) — PDF: `丽轩地毯/常规款式图册2025.9.16-.pdf` Excel: `丽轩地毯/常规款式图册2025.9.16-.xlsx`
- **状态**: 🔴 待处理

---

### FP-14: 非产品页面（公司简介/目录/技术图纸）内容泄露

- **现象**: 公司简介页、产品目录页、技术图纸/尺寸标注页的文字被提取为 SKU（如"Company Introduction"、"电动伸缩门"等）
- **影响**: ~150-200 FP
- **根因**: page_type 分类器没有"非产品页"检测，所有页面都尝试提取
- **方案**: 在 page_processor 中增加非产品页关键词检测（"公司简介"、"联系方式"、"目录"、"品牌故事"等），跳过提取
- **源数据集**:
  - 鸿伟办公 (fp 部分) — PDF: `鸿伟/鸿伟办公.pdf` Excel: `鸿伟/鸿伟办公.xlsx`
  - 壹业 (fp 部分) — PDF: `也斯/壹业(1).pdf` Excel: `也斯/壹业(1).xlsx`
  - 沃世 (fp 部分) — PDF: `沃世/沃世.pdf` Excel: `沃世/沃世.xlsx`
- **状态**: 🔴 待处理

---

## 十、手工审查待办

### MA-1: 伟鸿电子图册 — 疑似 Excel GT 或 PDF 匹配问题

- **现象**: GT=95, 实际提取=2, R=2.1%。95 页 PDF 只匹配到 2 个 SKU，极度异常
- **需要审查**:
  1. Excel GT 的 SKU 名称格式是否与 pipeline 输出兼容（benchmark matching 逻辑能否匹配上）
  2. PDF 内容是否确实含有产品（或是纯展示/无文字纯图）
  3. pipeline 实际提取了多少 SKU（可能提取了很多但 matching 失败）
- **源数据集**: PDF: `伟鸿/电子图册.pdf` Excel: `伟鸿/电子图册.xlsx`
- **状态**: 🔴 待手工审查

### MA-2: 铼顺电子图册 — 疑似 Excel GT 格式极简导致匹配失败

- **现象**: GT=61, 实际提取=2, R=3.3%。4 页 PDF 只匹配到 2 个 SKU
- **需要审查**:
  1. Excel GT 中 SKU 名称为"餐椅1"~"餐椅61"，极简命名，benchmark matching 可能无法匹配
  2. 4 页 PDF 是否真的包含 61 个餐椅（密度异常高）
  3. 可能是 PDF 与 Excel 不匹配（错误的 Excel 文件）
- **源数据集**: PDF: `铼顺/电子图册.pdf` Excel: `铼顺/电子图册.xlsx`
- **状态**: 🔴 待手工审查

---

## 二、Precision 提升路线图

> 基线数据: P=67.3% R=96.4% F1=79.2% (60 数据集, 12104 SKU, 3921 FP)

### 核心发现

| 事实 | 数据 |
|------|------|
| **100% FP 是 name-only** | 3921/3921 FP 无 model/price/specs/color |
| **TP 中 name-only 仅 2.9%** | 234/8183 TP 是 name-only |
| FP confidence 分布 | <0.3: 7.3%, 0.3-0.5: 14.7%, **0.5-0.7: 55.1%**, ≥0.7: 22.8% |
| 87.1% FP 来自 single_stage | 3415/3921 |
| Top FP 名称 | 沙发(186), 地毯(168), 餐椅(127), 茶几(111), 办公椅(102) |

### P1 ★★★★★ — Name-only SKU 降权/过滤

- **问题**: LLM 对场景图中的物品返回泛化名称（"沙发""茶几"），无任何具体属性
- **FP 覆盖**: 3921/3921 (100%)
- **TP 风险**: 234/8183 (2.9%)
- **方案**: A) Scorer 中 name-only + 泛化名称 → 大幅降 confidence → 阈值裁剪; B) 对 name-only SKU 要求 OCR 佐证; C) 同页已有 model-bearing SKU 时删除同名 name-only SKU
- **状态**: 🟡 已实现，30样本验证完成。对有model-bearing的页面惩罚生效（如万日红BAIGAT FP 153→20），但 pure_img+无model-bearing的豁免条件导致IMG_DENSE高FP未被过滤

### P2 ★★★★ — IMG_DENSE 页面提取策略优化

- **问题**: 密集图片页切片后，每个切片独立提取，产生大量泛化 FP
- **FP 覆盖**: 1496 (38.2%)，FP rate 37.3%
- **方案**: A) 切片结果交叉验证; B) 全页+切片两轮提取取交集; C) 对 IMG_DENSE 要求更严格的 validity
- **状态**: 🔴 未开始

### P3 ★★★☆ — SINGLE_TALL 页面重复提取

- **问题**: 单品纵向长页，同一产品不同角度照片被分别提取为多个 SKU
- **FP 覆盖**: 753 (19.2%)，FP rate 38.1%
- **方案**: A) 切片间去重：相似 product_name → 合并; B) 识别同一产品的多角度图 → 统一归为一个 SKU
- **状态**: 🔴 未开始

### P4 ★★★☆ — TABLE 页面 FP 过高

- **问题**: 表格页 FP rate 高达 56.9%，348 个 FP
- **FP 覆盖**: 348 (8.9%)
- **方案**: A) 表格页优先用 text_rule 提取; B) 表格行数与 SKU 数校验; C) 表格结构解析增强
- **状态**: 🔴 未开始

### P5 ★★☆☆ — Confidence 阈值裁剪

- **问题**: 55.1% FP 的 confidence 在 0.5-0.7，但 TP 中也有此区间
- **方案**: A) 全局 confidence 阈值提升到 0.3-0.4; B) 组合条件裁剪：name-only + conf < 0.5 → 删除
- **状态**: 🔴 未开始

### P6 ★★☆☆ — companion_rescue 误救

- **问题**: companion_rescue FP rate 35.4% (184 FP / 520 total)
- **FP 覆盖**: 184 (4.7%)
- **方案**: A) 收紧触发条件; B) rescue 后二次校验
- **状态**: 🔴 未开始

### P7 ★★☆☆ — MIXED_TABLE 异常高 FP rate

- **问题**: MIXED_TABLE FP rate 70.2% (59/84)
- **FP 覆盖**: 59 (1.5%)
- **方案**: 混合表格页分类识别 + 专用提取策略
- **状态**: 🔴 未开始

### FP 分布快查

**按页面类型:**

| 页面类型 | Total | FP | FP Rate | FP Share |
|----------|-------|-----|---------|----------|
| IMG_DENSE | 4011 | 1496 | 37.3% | 38.2% |
| SINGLE_TALL | 1978 | 753 | 38.1% | 19.2% |
| IMG_LABEL | 1922 | 456 | 23.7% | 11.6% |
| TABLE | 612 | 348 | 56.9% | 8.9% |
| MULTI_SPARSE | 1013 | 299 | 29.5% | 7.6% |
| MIXED_OTHER | 821 | 246 | 30.0% | 6.3% |
| SINGLE_LARGE | 1495 | 242 | 16.2% | 6.2% |
| MIXED_TABLE | 84 | 59 | 70.2% | 1.5% |
| SINGLE_STD | 168 | 22 | 13.1% | 0.6% |

**按提取方法:**

| 方法 | Total | FP | FP Rate | FP Share |
|------|-------|-----|---------|----------|
| single_stage | 10485 | 3415 | 32.6% | 87.1% |
| single_stage_rescue | 882 | 274 | 31.1% | 7.0% |
| companion_rescue | 520 | 184 | 35.4% | 4.7% |
| text_rule_fallback | 199 | 48 | 24.1% | 1.2% |

---

## 三、Recall 类问题 (低 R 数据集)

> 来源: 64 数据集 benchmark (2026-03-22, commit 2d29683)

### R-1: IMG_DENSE 切片数不足

- **现象**: IMG_DENSE 页面（密集小图网格），当前切片策略产出的切片数远小于实际产品数
- **影响**: 大量 SKU 未被提取
- **受影响数据集**:
  - Ely北美轻奢软体 R=50.1%, FN=237
  - Ely北美轻奢硬体 R=80.1%, FN=51
  - 2019版本五金茶几 R=53.7%, FN=38
- **方案**: 对 IMG_DENSE 增加切片密度（按图片网格对齐），或采用多轮切片策略
- **状态**: 🔴 未开始 (P2 优先级)

### R-2: SINGLE_LARGE 切片数不足

- **现象**: 单大图页面切片为 2 份，LLM 单次提取遗漏部分 SKU
- **影响**: 边际 SKU 被遗漏
- **受影响数据集**:
  - 万日红实木家具2 R=71.6%, FN=33
  - 2025现代实木 R=85.4%, FN=53
- **方案**: SINGLE_LARGE 增加切片数（如 3-4 份），或对 FN 比例高的页面触发重试
- **状态**: 🔴 未开始

### R-3: Scorer 对纯图/低文字目录过严

- **现象**: 纯图/低文字目录中 SKU 天生 name-only（无型号无价格），评分公式给 model+price 55% 权重导致分数天生低
- **受影响数据集**: 万日红现代简约, 万日红极简沙发, 万日红美式香槟, 万日红设计师合集
- **状态**: ✅ 已修复 (commit 2d29683)
  - Fix 1: 放宽 pure_visual 阈值 (text_len≤80, img_cov≥0.95)
  - Fix 2: 修复 scene_filter 覆盖 pure_visual 的 bug
  - Fix 3: 纯图上下文评分补偿 (s_name, s_catalog)
  - Fix 4: 全英文名称惩罚对纯图目录豁免

### R-4: LLM 提取遗漏/不稳定

- **现象**: VLM 对场景图中小件家具遗漏，单次提取结果波动
- **影响**: 部分页面 SKU 数不足
- **缓解**: Retry 机制 + Prompt 强化（已实现）
- **残余**: VLM 能力上限，无法 100% 覆盖
- **状态**: 🟡 已缓解，VLM 能力上限难以突破

---

## 四、Pipeline 按阶段问题清单

### P1: PDF 解析

| 问题 | 触发条件 | 影响 | 现状 |
|------|---------|------|------|
| pdfplumber 不兼容 | 特殊 PDF 格式 | 降级到 PyMuPDF | ✅ 已有 3 级兜底 |
| Level3 OCR-lite 退化 | 前两级全失败 | 只返回单大文本块, 无准确 bbox | ✅ 已兜底, 低频 |
| CMYK 图片转换失败 | pix.n ≥ 5 | 图片数据丢失 → 绑定失败 | ✅ 已处理, 失败返回空 bytes |

### P2a: 图片去重

| 问题 | 触发条件 | 影响 | 现状 |
|------|---------|------|------|
| 重叠去重误合并 | bbox overlap > 70% 但不同产品 | 图片数减少 → 绑定目标减少 | ✅ 低风险, 阈值70%较保守 |

### P2b: 瓦片碎片合并

| 问题 | 触发条件 | 影响 | 现状 |
|------|---------|------|------|
| 未识别为瓦片页 | 大瓦片 short_edge≥200 | 碎片作独立图, 绑定混乱 | ✅ 已修复: Counter 尺寸检测 |
| 聚类过度合并 | GAP=5pt 内不同产品碎片 | 多产品合为一个 composite | 🟡 低风险 |
| 孤立碎片丢失 | 单碎片聚类 | 标记 fragmented, 不参与绑定 | ✅ 设计如此 |

### P4: 跨页表格检测

| 问题 | 触发条件 | 影响 | 现状 |
|------|---------|------|------|
| 前页未缓存 | 并行处理, 前页未完成 | 续表未检测 → 当前页表格不完整 | 🟡 优雅降级返回 None |
| 非标续表关键词 | "第二部分" 等 | 未识别续表 | 🟡 已知局限 |

### P5: 页面分类

| 问题 | 触发条件 | 影响 | 现状 |
|------|---------|------|------|
| 封面误判为 B 类 | 无 price/model 但有产品词 | 产生虚假 SKU | ✅ 已修复: 封面规则 |
| 产品页误判为 D 类 | text_block≤3, 无 price/model | SKIPPED, SKU 全丢 | 🟡 需关注, conf≥0.85 才跳 |

### P6: SKU 提取

| 问题 | 触发条件 | 影响 | 现状 |
|------|---------|------|------|
| VLM 遗漏小件家具 | 场景图, 小家具在背景 | SKU 数不足 | 🟡 Prompt 已强化, VLM 上限 |
| 单次提取不稳定 | LLM 随机性 | 相同页结果波动 0~4 | ✅ 已修复: Retry 机制 |
| source_bbox 位置偏差 | LLM 坐标定位不准 | 绑定错误 | ✅ 已修复: text_block bbox 修正 + VLM rebind |
| 两阶段+单阶段全失败 | LLM 连续返回空 | SKU=0 | ✅ Retry 缓解 |
| Boundary 膨胀 | VLM 返回大量重叠 boundary | 笛卡尔积爆炸 | ✅ 已修复: NMS IoU>0.5 |
| 整页 bbox | VLM 返回覆盖整页的矩形 | 无意义 boundary | ✅ 已修复: >80%面积 conf 降到 0.3 |

### P7: 一致性校验

| 问题 | 触发条件 | 影响 | 现状 |
|------|---------|------|------|
| Strict validity 纯图页全灭 | text_block≤5 且只有 name | 过滤后 SKU=0 | ✅ 已修复: relaxed 模式 |
| 过度去重 | (name, model, size) 碰巧相同 | 多 SKU 合并为 1 | 🟡 低风险, 有 product_id 区分 |

### P8: 绑定

| 问题 | 触发条件 | 影响 | 现状 |
|------|---------|------|------|
| 零 bbox 全绑最大图 | LLM 未返回坐标 | 无法区分 SKU 对应哪张图 | ✅ 已修复: 位置启发式 |
| 距离阈值不适配 | 布局未知, 阈值过小 | 无候选 → 无绑定 | ✅ 有 fallback (threshold×3) |
| VLM rebind token 截断 | 17+ SKU × 17 region | JSON 无结尾 | ✅ 已修复: 分批+紧凑格式+截断修复 |
| VLM rebind 未匹配 SKU 丢绑定 | VLM 部分 SKU 未返回匹配 | 替换模式下原绑定丢失 | ✅ 已修复: 合并模式 |
| 绑定歧义丢失 | 多候选 distance 相近 | 原流程返回 None | ✅ 已修复: 绑 top1 (conf×0.7) |
| 单图长页无绑 | 1 图+多 SKU+无文字 | SKU 全部绑同一张图 | ✅ 已修复: 所有 SKU 共享完整大图 |

---

## 五、SKU 丢失的 6 条关键路径

```
路径①: 页面误判为 D → SKIPPED → SKU 全丢
  触发: 产品页但 text_block≤3, 无 price/model
  诊断: status="SKIPPED", page_type="D"

路径②: 两阶段+单阶段+Retry 全失败 → SKU=0
  触发: LLM 连续返回空或解析失败
  诊断: skus=[], extraction_method=None

路径③: Validity 全灭 → 过滤后 SKU=0
  触发: 纯图页 strict 模式, 或属性过少
  诊断: extraction_method 有值但 skus=[]

路径④: 绑定全失败 → SKU 存在但无图片
  触发: 所有 SKU bbox=(0,0,0,0) + 无 eligible 图片
  诊断: bindings=[], validation.has_errors=True

路径⑤: VLM 遗漏小件 → SKU 数不足
  触发: 场景照中小家具被忽略
  诊断: len(skus) < eligible_count, 但未达 retry 阈值(≥50%)

路径⑥: 去重过度 → 多个相似 SKU 合并为 1
  触发: (name, model, size) 三元组碰巧相同
  诊断: deduplicate 日志显示合并数 > 0
```

---

## 六、按页面类型的风险矩阵

| 页面类型 | 高风险阶段 | 典型问题 | 缓解措施 |
|----------|-----------|---------|---------|
| 瓦片页 (上百碎片) | P2b, P8 | 聚类合并 + VLM rebind 截断 | Union-Find + 分批 rebind |
| 单图长页 | P8 | 所有 SKU 零 bbox | 所有 SKU 共享完整大图 + VLM rebind |
| 场景照 (卧室/客厅) | P6 | 小件遗漏 | Prompt 强化 + Retry |
| 标准目录页 | P6, P7 | 提取不稳定 + validity 过滤 | Retry + relaxed validity |
| 表格页 | P4, P5 | 续表漏检 + 误分类 | 跨页合并 + 规则兜底 |
| 封面/扉页 | P5 | 误判为产品页 | 封面规则检测 |

---

## 七、快速诊断指南

当怀疑某页 SKU 缺失时，按顺序检查日志：

1. `page_type="D"` + `SKIPPED` → 路径①, 检查分类
2. `extraction_method=None` → 路径②, 提取全失败
3. 有 `extraction_method` 但 `skus=[]` → 路径③, validity 过滤
4. `sku_extraction_retry` 日志 → 看 before/after
5. `vlm_rebind_parse_failed` / `vlm_rebind_low_coverage` → VLM 绑定问题
6. `image_dedup` 的 deduped 数量 → 过度去重

---

## 八、已实现优化总览 (25 项)

| # | 问题 | 修复 | 文件 |
|---|------|------|------|
| 1 | 扉页虚假 SKU | 封面规则检测 | page_classifier.py |
| 2 | Boundary 膨胀 | NMS IoU>0.5 | two_stage.py |
| 3 | SKU 重复 | (name,model,size) 去重 | consistency_validator.py |
| 4 | 瓦片碎片无法绑 | Union-Find + composite | page_processor.py |
| 5 | 无文字层绑定失效 | VLM rebind (合并模式, 覆盖所有纯图多SKU页) | page_processor.py |
| 6 | 绑定歧义丢失 | 绑 top1 (conf×0.7) | binder.py |
| 7 | 整页 bbox | >80% 面积降 conf | two_stage.py |
| 8 | 纯图页 validity 全灭 | relaxed 模式 | consistency_validator.py |
| 9 | 单图长页无绑 | 所有 SKU 共享完整大图 | page_processor.py |
| 10 | 大瓦片未识别 | Counter 尺寸检测 | page_processor.py |
| 11 | VLM rebind 解析失败 | regex+json+截断修复 | page_processor.py |
| 12 | 单次提取不稳定 | Retry 机制 | page_processor.py |
| 13 | 小件家具遗漏 | Boundary prompt 强化 | two_stage.py |
| 14 | 床垫/尺寸描述 FP | Scorer 硬过滤 (s_name=0.0) | sku_scorer.py |
| 15 | 英文品牌名 FP | 全英文 2-4 词惩罚 + 无硬信号 -0.15 | sku_scorer.py |
| 16 | 场景装饰物 FP | 场景黑名单扩展 (硬+软) | sku_dedup.py |
| 17 | Companion SKU 被 reviewer 丢弃 | companion_rescue 打标 + reviewer 保护 | page_processor.py, sku_reviewer.py |
| 18 | 切片零结果漏提取 | OCR-guided 回退 (ocr_text_len>30) | page_processor.py |
| 19 | MIXED_OTHER 零 SKU | 垂直三等分切片回退 | page_processor.py |
| 20 | 同页切片重复 (FP-1) | normalize_model + IMG_DENSE similarity 去重 | sku_dedup.py, page_processor.py |
| 21 | 封面/品牌页 FP (FP-3) | MARKETING_KEYWORDS 扩展 | sku_dedup.py |
| 22 | rescue 场景道具 (FP-4) | rescue 传 scene_filter + SCENE_FILTER_TEXT | single_stage.py, page_processor.py |
| 23 | name-only 低 conf (FP-5) | 无型号+无价格+conf<0.4 过滤 | sku_dedup.py |
| 24 | 汇总页去重 (FP-6) | normalize_model 增强 cross_page_dedup | sku_dedup.py |
| 25 | 零部件误提取 (FP-7) | SCENE_PROPS 黑名单扩展 | sku_dedup.py |

---

## 九、历史基线

| 版本 | P | R | F1 | 样本数 | 备注 |
|------|---:|---:|---:|---:|------|
| iter4-final | 61.9% | 98.0% | 75.8% | 60 | 旧基线 |
| scene-prop-filter | 67.3% | 96.4% | 79.2% | 60 | +OCR信号+黑名单 |
| 34样本基线 | 80.7% | 91.8% | 85.9% | 34 | 修改前基线 |
| recall-precision-fix | 81.6% | 90.5% | 85.8% | 34 | 有回归 |
| 64数据集-pure-visual-fix | 73.5% | 92.7% | 82.0% | 56 | 2026-03-22 |
| **81数据集抽样** | **79.3%** | **88.9%** | **83.8%** | **81** | 最新 (2026-03-23, commit 9286331) |
