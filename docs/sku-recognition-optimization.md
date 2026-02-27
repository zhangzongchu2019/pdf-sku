# SKU 识别优化记录

## 已完成优化

### [2025-02-25] 封面过滤 + NMS 去重 + 瓦片合并 + VLM 辅助绑定

**提交**: `dd9d204`

#### 1. 封面/扉页识别
- **文件**: `pipeline/classifier/page_classifier.py`
- **问题**: 扉页被错误分类为 B 类，提取了虚假 SKU
- **方案**: 在 `_rule_classify()` 新增封面/扉页规则（cover 关键词 + 文字极少 → D 类）

#### 2. Boundary NMS 去重
- **文件**: `pipeline/extractor/two_stage.py`
- **问题**: 同一产品划出多个重叠 boundary，SKU 笛卡尔积膨胀 (627 → 预期 ~400)
- **方案**: `identify_boundaries()` 返回前做 IoU > 0.5 NMS 去重

#### 3. SKU 后去重
- **文件**: `pipeline/extractor/consistency_validator.py`
- **方案**: `deduplicate_skus()` 按 (product_name, model_number, size) 去重，保留 confidence 最高

#### 4. 瓦片 PDF 碎片合并
- **文件**: `pipeline/page_processor.py` → `_merge_tile_fragments()`
- **问题**: 瓦片 PDF 每页上百个 <200px 碎片图片，无法绑定
- **方案**: Union-Find 将相邻碎片 (GAP < 5pt) 聚类，生成 `p{page}_composite_{idx}` 虚拟图片

#### 5. VLM 辅助绑定
- **文件**: `pipeline/page_processor.py` → `_vlm_rebind_composites()`
- **问题**: 无文字层的瓦片页，空间绑定不可靠
- **方案**: 截图上标注红色矩形 + IMG-N 标签，发送 VLM 匹配 SKU → 图片

#### 6. 绑定歧义处理
- **文件**: `pipeline/binder/binder.py`
- **方案**: 歧义时仍赋 top1 (confidence × 0.7)，避免完全丢失绑定

#### 7. 整页 bbox 退化处理
- **文件**: `pipeline/extractor/two_stage.py` → `_penalize_fullpage_boundaries()`
- **问题**: LLM 返回整页 bbox，所有 SKU 绑定失去空间区分度
- **方案**: 覆盖 >80% 页面的 boundary，confidence 降至 min(原值, 0.3)

---

### [2026-02-26] 解析修复 + 大瓦片检测 + Prompt 优化 + VLM 绑定增强

#### 2. VLM Rebind JSON 解析修复
- **文件**: `pipeline/page_processor.py` → `_vlm_rebind_composites()`
- **问题**: ResponseParser 4 级解析全部失败 (`parse_fallback_raw`)，VLM rebind 静默返回 None
- **根因**: VLM 响应文本格式不被 ResponseParser 的 orjson/code_block/regex 识别
- **修复**:
  - 添加 `re.search(r'\[[\s\S]*\]', text)` + `json.loads()` 直接提取 fallback
  - 截断 JSON 修复: response 以 `[` 开头但无 `]`（token 限制截断）时，找最后完整的 `}` 补 `]`
- **效果**: page 1 VLM rebind 23/23 成功（之前 0/23）

#### 3. 大瓦片检测
- **文件**: `pipeline/page_processor.py` → `_merge_tile_fragments()`
- **问题**: 瓦片原生尺寸 225×215，short_edge=215 ≥ 200 阈值，未被识别为瓦片页
- **现象**: Job `638352c0` page 16: 111 个碎片未合并，全部作为独立图片
- **修复**: 增加大瓦片检测逻辑 — 图片数 > 50 且多数尺寸相同 (Counter 最频繁尺寸 ≥ 50%) → 视为瓦片页
- **同时修复**: 瓦片页中独立碎片一律标记 `is_fragmented=True`（之前仅标记 short_edge < 200 的）
- **效果**: 111 碎片 → 4 个 composite 图片

#### 4. Boundary Prompt 优化
- **文件**: `pipeline/extractor/two_stage.py` → `BOUNDARY_PROMPT_TEMPLATE`
- **问题**: 场景照中小件家具（五斗柜、矮柜）被 VLM 忽略
- **修复**: 添加指令 "Scene/room photos often contain MULTIPLE products... Each distinct product must have its own boundary, even if it appears small or in the background."
- **效果**: Job `638352c0` page 11: 6 → 7 SKU（VLM 提取能力的上限，仍可能漏 1-2 件小家具）

---

### [2026-02-26] 纯图页面 SKU 提取 + 图片去重 + 绑定修复

**背景**: 多个 Job 存在系统性问题:
- Job `fc63a59d` (拾间美学报价及目录.pdf): 106 页中 30 页 B 类 SKU=0
- Job `da3ae8b9` (HUA LAI XUAN Furniture Portfolio): 141 页中 128 页 SKU=0
- Job `5e44db72` (2025茶几.pdf): page 3/6 图片重复、绑定错误

#### 1. 放宽纯图页面 SKU validity (Fix 1)
- **文件**: `pipeline/extractor/consistency_validator.py`, `pipeline/page_processor.py`
- **问题**: 纯图页面（无/极少文字）→ LLM 只能识别 product_name → `enforce_sku_validity` strict 模式要求 name+(model|size) → 全部 invalid → SKU=0
- **方案**: `enforce_sku_validity()` 增加 `text_block_count` 参数，`text_block_count <= 5` 时进入 relaxed 模式（任何属性非空即 valid）
- **阈值调整**: 初始设 <=3，但 da3ae8b9 画册页面 text_block_count=4 仍未命中 → 调整为 <=5
- **效果**: da3ae8b9 page 3 从 sku=0 → sku=1（product_name only 通过 relaxed 验证）

#### 2. PDF 图片去重 (Fix 2)
- **文件**: `pipeline/page_processor.py` → `_dedup_images()`, `_bbox_overlap_ratio()`
- **问题**: PDF 解析器 `get_images()` 提取出重复/重叠图片（不同分辨率版本 + 全局装饰图片）
- **方案**: 在 Phase 2（image_hash 计算后）和 Phase 2b（瓦片合并前）之间插入去重:
  1. **小图过滤**: `short_edge < 30` → `search_eligible=False`
  2. **哈希去重**: 相同 `image_hash` → 保留分辨率最高的，其余标记 `is_duplicate=True`
  3. **重叠去重**: bbox 重叠率 > 70% (`overlap/min_area`) → 保留高分辨率的
- **效果**: Job `5e44db72` page 3: 5 张→去重 3 张剩 2 张; page 6: 6 张→去重 4 张剩 2 张

#### 3. 零 bbox 绑定降级 + 单 SKU 多图绑定 (Fix 3)
- **文件**: `pipeline/binder/binder.py`
- **问题**: `source_bbox=[0,0,0,0]` 的 SKU 空间绑定完全失效; 单 SKU 页面多张图片只绑定一张
- **方案**:
  - **零 bbox 降级**: `_is_zero_bbox()` 检测 → 绑定到 deliverable 中最大面积图片 (confidence=0.4, is_ambiguous=True)
  - **单 SKU 多图**: `len(skus)==1 and len(deliverable)>=1` → 所有图片绑定到该 SKU (confidence=0.7, 带 rank)
- **效果**: 零 bbox SKU 不再无绑定; 但多 SKU + 零 bbox 场景全部绑到同一张图（已在 Fix 4/5 中修复）

#### 4. strict validity 放宽为 "任意两个核心属性" (Fix 4 / 原 P6)
- **文件**: `pipeline/extractor/consistency_validator.py`
- **问题**: strict 模式要求 `has_name and (has_model or has_size)`，LLM 有时只返回 model+size 不返回 name → invalid
- **方案**: 改为 `core_count = sum([has_name, has_model, has_size]) >= 2`，即 name/model/size 中任意两个即可
- **效果**: fc63a59d page 19 从 sku=0 → sku=4（model+size 通过验证，不再强制要求 name）

#### 5. 零 bbox 位置启发式绑定 (Fix 5 / 原 P7)
- **文件**: `pipeline/binder/binder.py` → `_bind_zero_bbox_skus()`
- **问题**: 多 SKU + 零 bbox 全绑到最大图，无法区分上下排列的产品
- **方案**: 所有 SKU 都是零 bbox 时，按图片 Y 坐标排序与 SKU 出现顺序一一对应:
  - SKU 数 == 图片数 → 1:1 对应 (confidence=0.55)
  - SKU 数 < 图片数 → 前 N 张按序对应
  - SKU 数 > 图片数 → 多余 SKU 绑最大图 (confidence=0.35)
- **效果**: 5e44db72 page 3/6 两个 SKU 分别绑定到不同图片（之前都绑同一张）

#### 回归验证 (Job `638352c0`, 53 页家具画册)

基线: 296 SKU。抽样 7 页 reprocess 对比:

| 页码 | 类型 | 旧 SKU | 新 SKU | 变化 | 说明 |
|------|------|--------|--------|------|------|
| P3   | 普通 | 8      | 8      | 0    | 持平 |
| P11  | 普通 | 7      | 6      | -1   | LLM 波动 (P2 已知问题) |
| P16  | 瓦片 | 14     | 14     | 0    | 持平 |
| P32  | 瓦片 | 25     | 25     | 0    | 持平 |
| P33  | 瓦片 | 29     | 28     | -1   | LLM 波动 |
| P44  | 少SKU | 2     | 2      | 0    | 持平 |
| P47  | 少SKU | 2     | 2      | 0    | 持平 |

**结论: 无退化**。5/7 页完全一致，2 页差异仅 1 SKU（LLM 提取随机性，非代码回归）。瓦片页逻辑未受图片去重影响。

---

### [2026-02-27] Phase 2c 合成大图布局检测

**背景**: 部分产品目录 PDF 将整页内容（含多个产品照片）嵌入为单个 XObject，导致提取出一张覆盖整页的大图而非独立产品照片（如 Job `603ec88c` 第 3 页）。

#### 1. DocLayout-YOLO 布局检测
- **文件**: `pipeline/layout_detector.py` (新建)
- **方案**: 引入 DocLayout-YOLO 模型，在 Phase 2b 后增加 Phase 2c，自动检测大图中的 Figure 区域
- **触发条件**: 页面仅 1 张 `search_eligible` 图片，且 bbox 面积 > 60% 页面面积
- **检测**: 用 `doclayout_yolo.YOLOv10` 加载模型（懒加载单例），置信度阈值 0.25
- **NMS**: 去掉包含其他小框的大框（overlap_ratio > 80%）
- **拆分**: ≥2 个 Figure 区域才拆分，子图 ID 为 `p{page}_region_{idx}`，`data=b""` 由 Phase 8 `_crop_composites` 裁剪
- **Graceful degradation**: `doclayout-yolo` 未安装或模型文件不存在时自动跳过

#### 2. 坐标系对齐
- Phase 2c: YOLO 像素坐标 → ÷ (img_px / bbox_pt) → PDF points
- Phase 8: bbox × (150/72) → 截图像素坐标
- `_crop_composites` 已支持 `_region_` 前缀匹配

#### 3. 验证结果
- Job `603ec88c` 第 3 页: 1 张全页大图 → 3 个 `p3_region_*` 子图（左上产品、右上产品、右下产品）
- 原大图 `search_eligible=False`，3 个子图全部 `search_eligible=True`

---

## 待优化问题

> 以下为用户反馈中排除确定性代码 bug 后，需要从模型/策略层面优化的问题。

### P1: 场景图 SKU 提取遗漏
- **现象**: 卧室/客厅场景照中，主体家具（床、沙发）能识别，但小件/背景家具（五斗柜、矮柜、装饰柜）经常被遗漏
- **案例**: Job `638352c0` page 11 — 4 张卧室场景图，每张含 床+床头柜+五斗柜，应 8 个 SKU，实际 6-7 个，缺少右侧五斗柜
- **已做**: 优化 boundary prompt 强调 "even if it appears small or in the background"，效果有限 (6→7)
- **优化方向**:
  - 两阶段提取：先识别场景中所有家具类型列表，再逐个定位 bbox
  - 在提取 prompt 中提供页面其他位置已识别到的产品列表作为参照，暗示可能还有遗漏
  - 对场景图做多次独立 VLM 调用取并集

### P2: 单次提取结果不稳定
- **现象**: 同一页面多次重处理，SKU 数量差异较大
- **案例**: Job `638352c0` page 13 — 首次处理仅 1 个 SKU，重处理后 4 个（正确数量）；page 12 — 首次 3 个，重处理后 4 个
- **根因**: LLM 提取具有随机性，单次调用可能遗漏大量产品
- **优化方向**:
  - 提取后检查 SKU 数量是否合理（如 SKU 数远少于页面图片数），若不合理自动重试
  - 对 B/C 类页面设定最低 SKU 期望数（如每张产品图至少 1 个 SKU）
  - 多次提取取并集，去重后合并

### ~~P3: LLM 返回的 source_bbox 指向错误区域~~ ✅ 已修复
- **已做**:
  - 无文字层页面: VLM rebind 扩展到所有多 SKU 纯图页（不限 composite/region），视觉匹配纠正空间绑定
  - 有文字层页面: `_refine_sku_bboxes()` 用 PDF 文本块精确位置修正 LLM 的 source_bbox
- **案例**: Job `638352c0` page 51 — 两个 SKU 绑反 → VLM rebind 修正

### ~~P4: 单图长页列数推断局限~~ ✅ 已废弃
- **决策**: 删除 `_split_single_image_page()` 网格拆分。单图页不再拆分，所有 SKU 共享同一张完整大图
- **原因**: 机械等分会从产品中间切断，裁剪出半截图片。直接绑定完整大图效果更好

### P5: VLM Rebind 大量 SKU 时截断
- **现象**: SKU 数 + Region 数较多时，VLM 响应被 token 限制截断，JSON 数组不完整
- **案例**: Job `3a86d6d8` page 2 — 17 SKU × 17 region，VLM 响应被截断
- **已做**: 截断 JSON 修复（补 `]`），但截断后的 SKU 无匹配结果
- **优化方向**:
  - 分批发送 VLM rebind（如每批 10 个 SKU）
  - 增加 VLM 调用的 max_tokens 参数
  - 使用更紧凑的输出格式（如 `[0,2,4,6,...]` 代替 `[{"sku_index":0,"image_index":2},...]`）

### ~~P6: strict 模式要求 product_name 但 LLM 有时不返回~~ ✅ 已修复 (Fix 4)

### ~~P7: 多 SKU + 零 bbox 页面绑定退化~~ ✅ 已修复 (Fix 5)

---

## 文件改动清单

| 文件 | 改动要点 |
|------|----------|
| `pipeline/page_processor.py` | VLM rebind 解析修复+合并模式、大瓦片检测、composite 裁剪、text_block bbox 修正 |
| `pipeline/extractor/two_stage.py` | Boundary prompt 优化、NMS 去重、整页 bbox 惩罚 |
| `pipeline/extractor/consistency_validator.py` | SKU 去重、relaxed 模式、strict 放宽为任意两个核心属性 |
| `pipeline/classifier/page_classifier.py` | 封面/扉页规则 |
| `pipeline/binder/binder.py` | 歧义绑定、单图页快捷绑定、product_group 传播、零 bbox 降级/位置启发式绑定、单 SKU 多图绑定 |
| `pipeline/layout_detector.py` | Phase 2c 合成大图布局检测: DocLayout-YOLO 模型加载 + Figure 检测 + NMS + 坐标转换 |
