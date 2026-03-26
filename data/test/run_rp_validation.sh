#!/bin/bash
# R+P 合并改进验证: 测试本次分析中 R/P 低下的目标数据集
# 对应 commit: 352ba53 (feat: R+P 合并改进)
cd "$(dirname "$0")/../../server"

DATASETS=(
  # ── R 低下 (FN 主导, A1/A2/A3 改进目标) ──
  "佛山奢品嘉户外家具图册"        # R=46.9%, FN=230, IMG_DENSE 切片不足
  "2025现代实木"                   # R=48.6%, FN=187, 祥云, 切片不足
  "2025诗柏盈家具餐台系列*"        # R=41.5%, FN=120, 大量SKU漏提
  "鹏远家具休闲桌椅"              # R=42.7%, FN=75, 产出极少
  "曼岛8号新品"                    # R=41.7%, FN=14, 产出极少
  # ── P 低下 (FP 主导, B1/B2/B3/B4 改进目标) ──
  "2025相约餐饮家具"              # P=11.2%, FP=230, fake model+装饰品
  "凯跃*"                          # P=20.1%, FP=342, 营销文案+低conf
  "常规款式图册2025*"              # P=27.6%, FP=236, 丽轩地毯尺寸变体
  "2025网椅办公椅"                # P=28.3%, FP=43, FP严重
  "万日红美式轻奢画册2024*"        # P=59.1%, FP=96, 低conf配件
  "扫描版-万日红中古风家具"        # P=49.0%, FP=53, 低conf配件
)

TOTAL=${#DATASETS[@]}
echo "====== R+P 合并改进验证 (${TOTAL} 个目标数据集) ======"
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
echo "====== 验证完成 ======"
echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "成功: $((TOTAL - ${#FAILED[@]})), 失败: ${#FAILED[@]}"

if [ ${#FAILED[@]} -gt 0 ]; then
  echo "失败数据集:"
  for f in "${FAILED[@]}"; do
    echo "  - ${f}"
  done
fi

echo ""
echo "====== 全量汇总对比 ======"
.venv/bin/python -m pdf_sku.benchmark compare 2>&1
