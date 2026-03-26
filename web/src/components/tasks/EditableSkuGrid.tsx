import type { HumanTask } from "../../types/models";
import SkuSpreadsheet, { DEFAULT_SKU_COLUMNS, buildSheetRowsSignature } from "../sku/SkuSpreadsheet";
import type { TaskSkuDraftRow } from "../../stores/taskSkuDraftStore";

type RawSkuRecord = {
  sku_id?: unknown;
  id?: unknown;
  attributes?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toDisplayValue(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map((item) => toDisplayValue(item)).filter(Boolean).join(" / ");
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function normalizeTaskRows(task: HumanTask): TaskSkuDraftRow[] {
  const sources: unknown[] = [];
  const context = isRecord(task.context) ? task.context : {};
  const result = isRecord(task.result) ? task.result : {};
  const aiResult = isRecord(context.ai_result) ? context.ai_result : {};
  const resultAi = isRecord(result.ai_result) ? result.ai_result : {};

  sources.push(
    result.skus,
    result.corrected_skus,
    result.data,
    aiResult.skus,
    aiResult.corrected_skus,
    resultAi.skus,
    resultAi.corrected_skus,
  );

  if (Array.isArray(result.annotations)) {
    for (const annotation of result.annotations) {
      if (!isRecord(annotation)) continue;
      const payload = isRecord(annotation.payload) ? annotation.payload : annotation;
      if (isRecord(payload.attributes)) {
        sources.push([payload]);
      }
    }
  }

  for (const source of sources) {
    if (!Array.isArray(source)) continue;
    const rows = source
      .map((item, index): TaskSkuDraftRow | null => {
        if (!isRecord(item)) return null;
        const sku = item as RawSkuRecord;
        const attributes = isRecord(sku.attributes) ? sku.attributes : item;
        const normalizedAttributes = Object.entries(attributes).reduce<Record<string, string>>(
          (acc, [key, value]) => {
            if (key === "attributes") return acc;
            acc[key] = toDisplayValue(value);
            return acc;
          },
          {},
        );
        if (Object.keys(normalizedAttributes).length === 0) {
          return null;
        }
        const skuId = toDisplayValue(sku.sku_id ?? sku.id ?? normalizedAttributes.sku_id ?? `SKU-${index + 1}`);
        return {
          id: `${task.task_id}-${index}-${skuId || "sku"}`,
          skuId,
          attributes: {
            sku_id: skuId,
            ...normalizedAttributes,
          },
        };
      })
      .filter((row): row is TaskSkuDraftRow => row !== null);

    if (rows.length > 0) {
      return rows;
    }
  }

  return [];
}

export default function EditableSkuGrid({ task }: { task: HumanTask }) {
  const initialRows = normalizeTaskRows(task);
  const draftKey = `task:${task.task_id}:${buildSheetRowsSignature(initialRows)}`;

  return (
    <SkuSpreadsheet
      key={draftKey}
      draftKey={draftKey}
      initialRows={initialRows}
      preferredColumns={DEFAULT_SKU_COLUMNS}
      emptyText="暂无可展示的 SKU 提取结果"
      resetLabel="恢复提取结果"
    />
  );
}
