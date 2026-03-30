#!/bin/bash
# 64个样本全量测试: 原34基线 + 30新增
# 先归档旧缓存，然后逐个运行
cd "$(dirname "$0")/../../server"

# ── 原 34 基线数据集 ──
BASELINE=(
  "2024图册-WS系列"
  "2024禧月【夏日贝壳】*"
  "2025new catalog沙发图册*"
  "2025主卧床合集图册"
  "2025佛山户外沙发*"
  "2025卡奇尔 白色*"
  "2025图册 -HQ系列"
  "2025年报价单下*"
  "2025梳妆台&斗柜图册"
  "2025梳妆台系列"
  "2025相约餐饮家具"
  "Elysium宾利摩卡"
  "Elysium富誉"
  "Elysium开物里"
  "Elysium目居"
  "Elysium知如"
  "Ely北美轻奢硬体*"
  "Ely北美轻奢软体*"
  "一涧物"
  "2025新款电子版"
  "2025秋季新款电子画册"
  "万日红2025中古风家具"
  "万日红实木家具"
  "万日红实木家具2"
  "万日红家具B软床图册*"
  "万日红家具—原创设计师合集*"
  "万日红家具美式中古图册"
  "万日红极简现代沙发*"
  "万日红现代简约图册"
  "万日红现代软床Y图册"
  "万日红美式轻奢BAIGAT*"
  "万日红美式轻奢画册2024*"
  "万日红美式香槟图册"
  "万鑫休闲椅 全"
)

# ── 新增 30 数据集 (按 Excel SKU 数升序) ──
NEW30=(
  "十二星座床垫折页-"
  "酒店椅Hotel chair"
  "屏风图册"
  "2025电子画册-皮沙发"
  "2025-7银星茶台-岛台图册-秋季版"
  "梦芯豪方腾家具新款电子图册"
  "茶台"
  "大理石圆桌（2025.10）"
  "纤佰姿-new"
  "上下子母床2025-9"
  "普通实木椅"
  "吧凳Bar stools"
  "高端五金餐椅Designer chair"
  "荟森活202304图册-休闲椅"
  "2019版本五金茶几"
  "沙发图册（2025.08）"
  "鸣丰整装沙发图册"
  "组合茶几小件图册-24年9月"
  "鹏远家具梳妆台"
  "儿童软床系列"
  "拾间美学4"
  "PU8303电子图册"
  "普通五金餐椅"
  "经典美式套房2025"
  "皇钰思家具2025电子版"
  "2025新款精品妆台"
  "刘顺办公家具"
  "不锈钢餐桌1"
  "2025现代实木"
  "壹业(1)"
)

# 合并
ALL=("${BASELINE[@]}" "${NEW30[@]}")
TOTAL=${#ALL[@]}

echo "====== 全量 ${TOTAL} 数据集 Benchmark 测试 ======"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

FAILED=()
DONE=0

for i in "${!ALL[@]}"; do
  idx=$((i+1))
  ds="${ALL[$i]}"
  echo "============================================================"
  echo "[${idx}/${TOTAL}] 开始: ${ds}"
  echo "时间: $(date '+%H:%M:%S')"
  echo "============================================================"

  # 运行 pipeline
  .venv/bin/python -m pdf_sku.benchmark run --filter "${ds}" 2>&1 | tail -5
  RUN_EXIT=$?

  if [ $RUN_EXIT -ne 0 ]; then
    echo ">>> 运行失败: ${ds}"
    FAILED+=("${ds}")
  fi

  # 对比结果
  .venv/bin/python -m pdf_sku.benchmark compare --filter "${ds}" 2>&1
  echo ""
  DONE=$((DONE+1))
done

echo ""
echo "====== 全部 ${TOTAL} 个数据集测试完成 ======"
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
