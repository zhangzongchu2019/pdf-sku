#!/bin/bash
# 批量重跑所有 Job (按页数从小到大)
# 每个 Job 启动后等待完成再启动下一个

API="http://localhost:8000/api/v1"
export PGPASSWORD=pdfsku
DB_CMD="psql -h localhost -U pdfsku -d pdfsku -t -A"

# 获取所有 Job，按页数排序
JOBS=$($DB_CMD -c "SELECT job_id || '|' || total_pages || '|' || source_file FROM pdf_jobs ORDER BY total_pages ASC")

TOTAL=$(echo "$JOBS" | wc -l)
IDX=0
SUCCESS=0
FAILED=0

echo "======================================"
echo " 批量重跑 $TOTAL 个 Job"
echo "======================================"

for line in $JOBS; do
    JOB_ID=$(echo "$line" | cut -d'|' -f1)
    PAGES=$(echo "$line" | cut -d'|' -f2)
    FILENAME=$(echo "$line" | cut -d'|' -f3)
    IDX=$((IDX + 1))

    echo ""
    echo "[$IDX/$TOTAL] $FILENAME ($PAGES 页)"
    echo "  Job: $JOB_ID"

    # 调用 reprocess-ai
    RESP=$(curl -s -X POST "$API/ops/jobs/$JOB_ID/reprocess-ai")
    QUEUED=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('queued',''))" 2>/dev/null)

    if [ "$QUEUED" != "True" ]; then
        echo "  ❌ 启动失败: $RESP"
        FAILED=$((FAILED + 1))
        continue
    fi

    echo "  ⏳ 已启动，等待完成..."

    # 轮询等待终态 (最长 30 分钟)
    TIMEOUT=1800
    ELAPSED=0
    INTERVAL=10

    while [ $ELAPSED -lt $TIMEOUT ]; do
        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))

        STATUS=$($DB_CMD -c "SELECT status FROM pdf_jobs WHERE job_id = '$JOB_ID'")

        case "$STATUS" in
            FULL_IMPORTED|PARTIAL_FAILED)
                SKU_COUNT=$($DB_CMD -c "SELECT count(*) FROM skus WHERE job_id = '$JOB_ID'")
                echo "  ✅ $STATUS | SKU: $SKU_COUNT | 耗时: ${ELAPSED}s"
                SUCCESS=$((SUCCESS + 1))
                break
                ;;
            PROCESSING|EVALUATED|EVALUATING)
                # 仍在处理
                DONE=$($DB_CMD -c "SELECT count(*) FROM pages WHERE job_id = '$JOB_ID' AND status NOT IN ('PENDING', 'AI_PROCESSING')")
                echo -ne "\r  ⏳ $STATUS | 已完成 $DONE/$PAGES 页 | ${ELAPSED}s"
                ;;
            EVAL_FAILED|DEGRADED_HUMAN)
                # 又失败了
                ERR=$($DB_CMD -c "SELECT error_message FROM pdf_jobs WHERE job_id = '$JOB_ID'")
                echo "  ❌ $STATUS: $ERR | 耗时: ${ELAPSED}s"
                FAILED=$((FAILED + 1))
                break
                ;;
            *)
                echo -ne "\r  ⏳ $STATUS | ${ELAPSED}s"
                ;;
        esac
    done

    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo "  ⚠️  超时 (${TIMEOUT}s)"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "======================================"
echo " 完成: $SUCCESS 成功, $FAILED 失败 (共 $TOTAL)"
echo "======================================"
