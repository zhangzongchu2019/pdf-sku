#!/bin/bash
# 测试 R<80% 或 P<80% 的数据集 (共35个)
# 用于验证 FP-2/FP-11/FP-12 三项修复效果
cd "$(dirname "$0")/../../server"

DATASETS=(
  # ── R<80% (4个) ──
  "Ely北美轻奢软体*"
  "2019版本五金茶几"
  "拾间美学4"
  "万日红实木家具2"
  # ── P<80% (31个, 去重后) ──
  "2025相约餐饮家具"
  "上下子母床2025-9"
  "梦芯豪方腾家具新款电子图册"
  "屏风图册"
  "2025秋季新款电子画册"
  "大理石圆桌（2025.10）"
  "万日红美式轻奢BAIGAT*"
  "皇钰思家具2025电子版"
  "2024禧月【夏日贝壳】*"
  "万日红家具美式中古图册"
  "Elysium富誉"
  "2025-7银星茶台-岛台图册-秋季版"
  "2025新款精品妆台"
  "2024图册-WS系列"
  "万日红美式轻奢画册2024*"
  "茶台"
  "2025新款电子版"
  "组合茶几小件图册-24年9月"
  "万日红2025中古风家具"
  "经典美式套房2025"
  "刘顺办公家具"
  "鹏远家具梳妆台"
  "2025主卧床合集图册"
  "万日红极简现代沙发*"
  "普通五金餐椅"
  "壹业(1)"
  "Elysium目居"
  "万日红现代简约图册"
  "PU8303电子图册"
  "万日红美式香槟图册"
  "不锈钢餐桌1"
)

TOTAL=${#DATASETS[@]}
echo "====== R<80% 或 P<80% 数据集测试 (${TOTAL} 个) ======"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

FAILED=()
DONE=0

for i in "${!DATASETS[@]}"; do
  idx=$((i+1))
  ds="${DATASETS[$i]}"
  echo "============================================================"
  echo "[${idx}/${TOTAL}] ${ds}"
  echo "时间: $(date '+%H:%M:%S')"
  echo "============================================================"

  .venv/bin/python -m pdf_sku.benchmark run --filter "${ds}" --force 2>&1 | tail -5
  RUN_EXIT=$?

  if [ $RUN_EXIT -ne 0 ]; then
    echo ">>> 运行失败: ${ds}"
    FAILED+=("${ds}")
  fi

  .venv/bin/python -m pdf_sku.benchmark compare --filter "${ds}" 2>&1
  echo ""
  DONE=$((DONE+1))
done

echo ""
echo "====== 测试完成 (${TOTAL} 个) ======"
echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "成功: $((TOTAL - ${#FAILED[@]})), 失败: ${#FAILED[@]}"

if [ ${#FAILED[@]} -gt 0 ]; then
  echo "失败数据集:"
  for f in "${FAILED[@]}"; do
    echo "  - ${f}"
  done
fi

echo ""
echo "====== 这批数据集汇总对比 ======"
FILTER_ARGS=""
for ds in "${DATASETS[@]}"; do
  FILTER_ARGS="${FILTER_ARGS} --filter \"${ds}\""
done
# 全量汇总
.venv/bin/python -m pdf_sku.benchmark compare 2>&1
