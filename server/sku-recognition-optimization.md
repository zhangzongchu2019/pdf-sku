# SKU 识别优化待办

## 1. SKU Boundary bbox 精度不足

**问题**: two_stage 提取时，LLM 对部分页面返回整页范围的 `source_bbox`，而非 per-SKU 精确区域，导致 binder 无法通过空间距离匹配图片。

**现象**: Job `ee9c3249` 第 27 页，21 个 SKU 的 `source_bbox` 均为 `{83,89,2010,1864}`（整页），4 张图片无法绑定。对比第 31 页 SKU bbox 为半页区域 `{1456,62,2780,1340}`，22 个绑定正常。

**根因**: two_stage Step 1 boundary 识别返回的区域粒度不够，或 Step 2 提取时未细化 bbox。

**优化方向**:
- 优化 boundary 识别 prompt，要求 LLM 返回更细粒度的 SKU 区域
- 在 binder 中增加 fallback 策略：当 SKU bbox 覆盖面积 > 页面 50% 时，尝试基于文本内容就近匹配
- 考虑利用 PDF 解析的 text_block 位置信息辅助定位 SKU 区域

## 2. Boundary 重叠导致 SKU 笛卡尔积膨胀

**问题**: two_stage Step 1 为同一产品划出多个重叠 boundary，Step 2 对每个 boundary 独立提取，产生大量重复 SKU。

**现象**: Job `ee9c3249` 第 28 页，合理 SKU 数约 16（7+7+1+1），实际提取 44 个（×2.75）。

- "斜三条 1+2+3 高箱"：7 种尺寸变体，3 个重叠 boundary 各提取 7 个 → 21 个
  - bbox1 `{2226,318,2779,631}`、bbox2 `{2235,494,2780,925}`、bbox3 `{2408,653,2780,980}` 大量重叠
- "斜三条 1+2+3 沙发"：同样 7 种尺寸，3 个重叠 boundary → 21 个

**根因**: Step 1 boundary 识别未做 IoU 去重/合并，重叠区域各自独立进入 Step 2 提取。

**优化方向**:
- Step 1 后增加 boundary NMS（非极大值抑制）：IoU > 0.5 的 boundary 合并为一个
- Step 2 提取后增加 SKU 去重：相同 `product_name` + 相同 `size` 的 SKU 只保留置信度最高的一条
- 考虑在 `ConsistencyValidator` 中增加跨 boundary 重复检测规则
