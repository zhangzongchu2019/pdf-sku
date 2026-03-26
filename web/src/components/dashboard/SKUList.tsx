import SkuSpreadsheet, { DEFAULT_SKU_COLUMNS, buildSheetRowsSignature } from "../sku/SkuSpreadsheet";
import type { TaskSkuDraftRow } from "../../stores/taskSkuDraftStore";
import type { SKU } from "../../types/models";

interface SKUListProps {
  skus: SKU[];
  jobId?: string;
  onReconcile?: (skuId: string) => void;
}

const DASHBOARD_COLUMNS = [
  ...DEFAULT_SKU_COLUMNS,
  "validity",
  "status",
  "import_confirmation",
  "page_number",
  "image_count",
  "attribute_source",
];

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

function normalizeSkuRows(skus: SKU[]): TaskSkuDraftRow[] {
  return skus.map((sku, index) => ({
    id: `${sku.sku_id}-${index}`,
    skuId: sku.sku_id,
    attributes: {
      sku_id: sku.sku_id,
      ...Object.entries(sku.attributes || {}).reduce<Record<string, string>>((acc, [key, value]) => {
        acc[key] = toDisplayValue(value);
        return acc;
      }, {}),
      validity: sku.validity,
      status: sku.status ?? "",
      import_confirmation: sku.import_confirmation,
      page_number: String(sku.page_number ?? ""),
      image_count: String(sku.images?.length ?? 0),
      attribute_source: sku.attribute_source,
    },
  }));
}

export function SKUList({ skus, jobId, onReconcile }: SKUListProps) {
  const validCount = skus.filter((s) => s.validity === "valid").length;
  const needsReviewCount = skus.filter((s) => s.validity === "needs_review").length;
  const invalidCount = skus.filter((s) => s.validity === "invalid").length;
  const assumedCount = skus.filter((s) => s.import_confirmation === "assumed").length;
  const confirmedCount = skus.filter((s) => s.import_confirmation === "confirmed").length;
  const initialRows = normalizeSkuRows(skus);
  const draftKey = `job:${jobId ?? "global"}:sku-sheet:${buildSheetRowsSignature(initialRows)}`;

  return (
    <div className="sku-dashboard">
      <div className="sku-summary-bar">
        <span className="sku-summary-chip neutral">共 {skus.length} 个 SKU</span>
        <span className="sku-summary-chip success">有效 {validCount}</span>
        <span className="sku-summary-chip warning">待审 {needsReviewCount}</span>
        <span className="sku-summary-chip danger">无效 {invalidCount}</span>
        <span className="sku-summary-chip info">确认 {confirmedCount}</span>
        {assumedCount > 0 && <span className="sku-summary-chip accent">假设 {assumedCount}</span>}
        {onReconcile && (
          <button className="btn btn-sm" type="button" onClick={() => onReconcile("")}>
            触发对账
          </button>
        )}
      </div>

      <SkuSpreadsheet
        key={draftKey}
        draftKey={draftKey}
        initialRows={initialRows}
        preferredColumns={DASHBOARD_COLUMNS}
        emptyText="当前 Job 暂无 SKU 数据"
        resetLabel="恢复原始 SKU"
      />
    </div>
  );
}

export default SKUList;
