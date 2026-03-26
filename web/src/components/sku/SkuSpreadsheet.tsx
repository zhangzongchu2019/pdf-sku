import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useTaskSkuDraftStore, type TaskSkuDraftRow } from "../../stores/taskSkuDraftStore";

export const DEFAULT_SKU_COLUMNS = [
  "sku_id",
  "product_name",
  "model_number",
  "sku_code",
  "brand",
  "price",
  "currency",
  "color",
  "size",
  "specs",
  "material",
  "description",
];

const COLUMN_LABELS: Record<string, string> = {
  sku_id: "SKU编号",
  product_name: "产品名称",
  model_number: "型号",
  sku_code: "SKU编码",
  brand: "品牌",
  price: "价格",
  currency: "币种",
  color: "颜色",
  size: "尺寸",
  specs: "规格",
  spec: "规格",
  material: "材质",
  description: "描述",
  category: "分类",
  name: "名称",
  weight: "重量",
  unit: "单位",
  barcode: "条码",
  origin: "产地",
  validity: "有效性",
  status: "状态",
  import_confirmation: "导入确认",
  page_number: "页码",
  image_count: "图片数",
  attribute_source: "属性来源",
};

const COLUMN_WIDTHS: Record<string, number> = {
  sku_id: 54,
  product_name: 58,
  model_number: 54,
  sku_code: 54,
  brand: 46,
  price: 42,
  currency: 40,
  color: 46,
  size: 46,
  specs: 50,
  spec: 50,
  material: 46,
  description: 58,
  category: 46,
  name: 54,
  weight: 42,
  unit: 38,
  barcode: 54,
  origin: 46,
  validity: 46,
  status: 46,
  import_confirmation: 56,
  page_number: 38,
  image_count: 38,
  attribute_source: 50,
};

const COLUMN_MAX_WIDTHS: Record<string, number> = {
  sku_id: 120,
  product_name: 150,
  model_number: 120,
  sku_code: 120,
  brand: 96,
  price: 80,
  currency: 72,
  color: 96,
  size: 96,
  specs: 132,
  spec: 132,
  material: 96,
  description: 160,
  category: 96,
  name: 132,
  weight: 72,
  unit: 68,
  barcode: 132,
  origin: 96,
  validity: 84,
  status: 84,
  import_confirmation: 104,
  page_number: 68,
  image_count: 68,
  attribute_source: 96,
};

function uniqueColumns(columns: string[]): string[] {
  return Array.from(new Set(columns.filter(Boolean)));
}

export function buildSheetRowsSignature(rows: TaskSkuDraftRow[]): string {
  const raw = rows
    .map((row) => `${row.id}|${JSON.stringify(row.attributes)}`)
    .join("||");
  let hash = 0;
  for (let index = 0; index < raw.length; index += 1) {
    hash = (hash * 33 + raw.charCodeAt(index)) >>> 0;
  }
  return hash.toString(36);
}

export function formatSheetColumnLabel(column: string): string {
  if (COLUMN_LABELS[column]) {
    return COLUMN_LABELS[column];
  }
  return column
    .split("_")
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

function getColumnWidth(column: string): number {
  return COLUMN_WIDTHS[column] ?? 48;
}

function getColumnMaxWidth(column: string): number {
  return COLUMN_MAX_WIDTHS[column] ?? 240;
}

function estimateTextWidth(text: string): number {
  let width = 8;
  for (const char of text) {
    width += /[\u4e00-\u9fff]/.test(char) ? 10 : 6;
  }
  return width;
}

function getColumnMinimumVisibleWidth(column: string): number {
  const labelWidth = estimateTextWidth(formatSheetColumnLabel(column));
  return Math.max(getColumnWidth(column), labelWidth + 34);
}

function getAutoColumnWidth(column: string, rows: TaskSkuDraftRow[]): number {
  const labelWidth = estimateTextWidth(formatSheetColumnLabel(column));
  const minWidth = getColumnMinimumVisibleWidth(column);
  const maxWidth = getColumnMaxWidth(column);

  let contentWidth = 0;
  for (const row of rows) {
    const value = row.attributes[column] ?? "";
    if (!value.trim()) continue;
    contentWidth = Math.max(contentWidth, estimateTextWidth(value));
  }

  if (contentWidth === 0) {
    return minWidth;
  }

  return Math.min(
    Math.max(minWidth, labelWidth + 10, contentWidth + 18),
    maxWidth,
  );
}

export function getSheetColumns(rows: TaskSkuDraftRow[], preferredColumns: string[] = DEFAULT_SKU_COLUMNS): string[] {
  const discovered = new Set<string>();
  rows.forEach((row) => {
    Object.keys(row.attributes || {}).forEach((key) => discovered.add(key));
  });

  const ordered = [...preferredColumns];
  const rest = Array.from(discovered)
    .filter((key) => !preferredColumns.includes(key))
    .sort((a, b) => a.localeCompare(b));
  return uniqueColumns([...ordered, ...rest]);
}

function buildEmptyRow(draftKey: string, rowIndex: number, columns: string[]): TaskSkuDraftRow {
  const rowId = `${draftKey}-${Date.now()}-${rowIndex}-${Math.random().toString(36).slice(2, 8)}`;
  const attributes = columns.reduce<Record<string, string>>((acc, column) => {
    acc[column] = column === "sku_id" ? `SKU-${rowIndex + 1}` : "";
    return acc;
  }, {});
  if (!("sku_id" in attributes)) {
    attributes.sku_id = `SKU-${rowIndex + 1}`;
  }
  return {
    id: rowId,
    skuId: attributes.sku_id,
    attributes,
  };
}

function fillMissingColumns(rows: TaskSkuDraftRow[], columns: string[]): TaskSkuDraftRow[] {
  return rows.map((row) => ({
    ...row,
    skuId: row.attributes.sku_id ?? row.skuId,
    attributes: columns.reduce<Record<string, string>>((acc, column) => {
      acc[column] = row.attributes[column] ?? (column === "sku_id" ? row.skuId || "" : "");
      return acc;
    }, {}),
  }));
}

function parseClipboardMatrix(text: string): string[][] {
  const normalized = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const lines = normalized.split("\n");
  if (lines.length > 1 && lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines.map((line) => line.split("\t"));
}

interface ActiveCell {
  rowIndex: number;
  columnIndex: number;
}

interface SkuSpreadsheetProps {
  draftKey: string;
  initialRows: TaskSkuDraftRow[];
  preferredColumns?: string[];
  emptyText?: string;
  resetLabel?: string;
}

export default function SkuSpreadsheet({
  draftKey,
  initialRows,
  preferredColumns = DEFAULT_SKU_COLUMNS,
  emptyText = "暂无 SKU 数据",
  resetLabel = "重置草稿",
}: SkuSpreadsheetProps) {
  const draft = useTaskSkuDraftStore((state) => state.drafts[draftKey]);
  const ensureDraft = useTaskSkuDraftStore((state) => state.ensureDraft);
  const replaceDraft = useTaskSkuDraftStore((state) => state.replaceDraft);
  const updateCell = useTaskSkuDraftStore((state) => state.updateCell);
  const [activeCell, setActiveCell] = useState<ActiveCell | null>(null);
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const [manuallyResizedColumns, setManuallyResizedColumns] = useState<Record<string, boolean>>({});
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const topScrollRef = useRef<HTMLDivElement | null>(null);
  const bottomScrollRef = useRef<HTMLDivElement | null>(null);
  const tableRef = useRef<HTMLTableElement | null>(null);
  const syncSourceRef = useRef<"top" | "bottom" | null>(null);
  const [tableScrollWidth, setTableScrollWidth] = useState(0);

  useEffect(() => {
    if (!draft) {
      ensureDraft(draftKey, initialRows);
    }
  }, [draft, draftKey, ensureDraft, initialRows]);

  const rows = draft ?? initialRows;
  const columns = useMemo(() => getSheetColumns(rows, preferredColumns), [preferredColumns, rows]);
  const filledRows = useMemo(() => fillMissingColumns(rows, columns), [columns, rows]);
  const autoColumnWidths = useMemo(
    () =>
      columns.reduce<Record<string, number>>((acc, column) => {
        acc[column] = getAutoColumnWidth(column, filledRows);
        return acc;
      }, {}),
    [columns, filledRows],
  );

  useEffect(() => {
    setColumnWidths((prev) => {
      const next: Record<string, number> = {};
      let changed = false;
      columns.forEach((column) => {
        const current = prev[column];
        if (manuallyResizedColumns[column] && current) {
          next[column] = current;
          return;
        }
        next[column] = autoColumnWidths[column];
        if (current !== next[column]) {
          changed = true;
        }
      });
      if (!changed && Object.keys(prev).length === Object.keys(next).length) {
        return prev;
      }
      return next;
    });
  }, [autoColumnWidths, columns, manuallyResizedColumns]);

  useEffect(() => {
    const tableNode = tableRef.current;
    if (!tableNode) return;

    const updateWidth = () => {
      setTableScrollWidth(tableNode.scrollWidth);
    };

    updateWidth();

    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => updateWidth());
    observer.observe(tableNode);
    return () => observer.disconnect();
  }, [columns, filledRows, columnWidths]);

  const focusCell = (rowIndex: number, columnIndex: number) => {
    const key = `${rowIndex}:${columnIndex}`;
    window.requestAnimationFrame(() => {
      inputRefs.current[key]?.focus();
      inputRefs.current[key]?.select();
    });
  };

  const moveActiveCell = (rowIndex: number, columnIndex: number) => {
    const nextRow = Math.max(0, Math.min(rowIndex, filledRows.length - 1));
    const nextColumn = Math.max(0, Math.min(columnIndex, columns.length - 1));
    setActiveCell({ rowIndex: nextRow, columnIndex: nextColumn });
    focusCell(nextRow, nextColumn);
  };

  const commitRows = (nextRows: TaskSkuDraftRow[]) => {
    replaceDraft(draftKey, fillMissingColumns(nextRows, columns));
  };

  const handleAddRow = () => {
    const nextRows = [
      ...filledRows,
      buildEmptyRow(draftKey, filledRows.length, columns.length > 0 ? columns : preferredColumns),
    ];
    commitRows(nextRows);
    moveActiveCell(nextRows.length - 1, 0);
  };

  const handleDeleteRow = (rowIndex: number) => {
    const nextRows = filledRows.filter((_, index) => index !== rowIndex);
    commitRows(nextRows);
    if (nextRows.length > 0) {
      moveActiveCell(Math.min(rowIndex, nextRows.length - 1), 0);
    } else {
      setActiveCell(null);
    }
  };

  const applyMatrix = (startRow: number, startColumn: number, matrix: string[][]) => {
    const nextRows = [...filledRows];
    const requiredRows = startRow + matrix.length;
    while (nextRows.length < requiredRows) {
      nextRows.push(buildEmptyRow(draftKey, nextRows.length, columns));
    }

    matrix.forEach((matrixRow, rowOffset) => {
      const targetRow = nextRows[startRow + rowOffset];
      const nextAttributes = { ...targetRow.attributes };
      matrixRow.forEach((value, columnOffset) => {
        const column = columns[startColumn + columnOffset];
        if (!column) return;
        nextAttributes[column] = value;
      });
      nextRows[startRow + rowOffset] = {
        ...targetRow,
        skuId: nextAttributes.sku_id ?? targetRow.skuId,
        attributes: nextAttributes,
      };
    });

    commitRows(nextRows);
    moveActiveCell(
      Math.min(startRow + matrix.length - 1, nextRows.length - 1),
      Math.min(startColumn + (matrix[0]?.length ?? 1) - 1, columns.length - 1),
    );
  };

  const startResize = (column: string, event: ReactMouseEvent<HTMLSpanElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = columnWidths[column] ?? autoColumnWidths[column] ?? getColumnWidth(column);
    const minWidth = getColumnMinimumVisibleWidth(column);

    const onMouseMove = (moveEvent: MouseEvent) => {
      const delta = moveEvent.clientX - startX;
      const nextWidth = Math.max(minWidth, startWidth + delta);
      setColumnWidths((prev) => ({
        ...prev,
        [column]: nextWidth,
      }));
    };

    const onMouseUp = () => {
      setManuallyResizedColumns((prev) => ({
        ...prev,
        [column]: true,
      }));
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  const resetColumnWidth = (column: string) => {
    setColumnWidths((prev) => ({
      ...prev,
      [column]: autoColumnWidths[column],
    }));
    setManuallyResizedColumns((prev) => ({
      ...prev,
      [column]: false,
    }));
  };

  const syncHorizontalScroll = (source: "top" | "bottom") => {
    const topNode = topScrollRef.current;
    const bottomNode = bottomScrollRef.current;
    if (!topNode || !bottomNode) return;

    const sourceNode = source === "top" ? topNode : bottomNode;
    const targetNode = source === "top" ? bottomNode : topNode;
    if (syncSourceRef.current && syncSourceRef.current !== source) return;
    syncSourceRef.current = source;
    targetNode.scrollLeft = sourceNode.scrollLeft;
    window.requestAnimationFrame(() => {
      syncSourceRef.current = null;
    });
  };

  if (columns.length === 0 && filledRows.length === 0) {
    return (
      <div className="sku-sheet-empty">
        <div>{emptyText}</div>
        <button className="btn btn-primary btn-sm" type="button" onClick={handleAddRow}>
          新增首行
        </button>
      </div>
    );
  }

  return (
    <div className="sku-sheet">
      <div className="sku-sheet-toolbar">
        <div className="sku-sheet-toolbar-left">
          <span className="sku-sheet-count">{filledRows.length} 行 SKU</span>
          <span className="sku-sheet-tip">支持从 Excel 直接复制整块内容后粘贴到任意单元格</span>
        </div>
        <div className="sku-sheet-toolbar-right">
          <button className="btn btn-sm" type="button" onClick={handleAddRow}>
            新增 SKU
          </button>
          <button
            className="btn btn-text btn-sm"
            type="button"
            onClick={() => replaceDraft(draftKey, initialRows)}
          >
            {resetLabel}
          </button>
        </div>
      </div>

      <div
        ref={topScrollRef}
        className="sku-sheet-scroll sku-sheet-scroll-top"
        onScroll={() => syncHorizontalScroll("top")}
      >
        <div style={{ width: tableScrollWidth, height: 1 }} />
      </div>

      <div
        ref={bottomScrollRef}
        className="sku-sheet-scroll sku-sheet-scroll-bottom"
        onScroll={() => syncHorizontalScroll("bottom")}
      >
        <table ref={tableRef} className="sku-sheet-table">
          <colgroup>
            <col style={{ width: 44 }} />
            {columns.map((column) => (
              <col key={column} style={{ width: columnWidths[column] ?? autoColumnWidths[column] ?? getColumnWidth(column) }} />
            ))}
            <col style={{ width: 76 }} />
          </colgroup>
          <thead>
            <tr>
              <th className="sku-sheet-index-head">#</th>
              {columns.map((column) => (
                <th key={column}>
                  <div className="sku-sheet-head-inner">
                    <span className="sku-sheet-head-label" title={formatSheetColumnLabel(column)}>
                      {formatSheetColumnLabel(column)}
                    </span>
                    <span
                      className="sku-sheet-resize-handle"
                      onMouseDown={(event) => startResize(column, event)}
                      onDoubleClick={() => resetColumnWidth(column)}
                      title="拖拽调整列宽，双击恢复自动宽度"
                    />
                  </div>
                </th>
              ))}
              <th className="sku-sheet-action-head">操作</th>
            </tr>
          </thead>
          <tbody>
            {filledRows.map((row, rowIndex) => (
              <tr key={row.id}>
                <td className="sku-sheet-index-cell">{rowIndex + 1}</td>
                {columns.map((column, columnIndex) => {
                  const isActive = activeCell?.rowIndex === rowIndex && activeCell?.columnIndex === columnIndex;
                  return (
                    <td
                      key={column}
                      className={`sku-sheet-cell ${isActive ? "is-active" : ""} ${
                        column === "sku_id" ? "is-key-column" : ""
                      }`}
                    >
                      <input
                        ref={(node) => {
                          inputRefs.current[`${rowIndex}:${columnIndex}`] = node;
                        }}
                        className="sku-sheet-input"
                        value={row.attributes[column] ?? ""}
                        onFocus={() => setActiveCell({ rowIndex, columnIndex })}
                        onClick={() => setActiveCell({ rowIndex, columnIndex })}
                        onChange={(event) =>
                          updateCell(draftKey, row.id, column, event.target.value)
                        }
                        onPaste={(event) => {
                          const matrix = parseClipboardMatrix(event.clipboardData.getData("text"));
                          if (matrix.length === 0) return;
                          event.preventDefault();
                          applyMatrix(rowIndex, columnIndex, matrix);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "ArrowRight") {
                            event.preventDefault();
                            moveActiveCell(rowIndex, columnIndex + 1);
                          } else if (event.key === "ArrowLeft") {
                            event.preventDefault();
                            moveActiveCell(rowIndex, columnIndex - 1);
                          } else if (event.key === "ArrowDown") {
                            event.preventDefault();
                            moveActiveCell(rowIndex + 1, columnIndex);
                          } else if (event.key === "ArrowUp") {
                            event.preventDefault();
                            moveActiveCell(rowIndex - 1, columnIndex);
                          } else if (event.key === "Enter") {
                            event.preventDefault();
                            moveActiveCell(rowIndex + 1, columnIndex);
                          } else if (event.key === "Tab") {
                            event.preventDefault();
                            moveActiveCell(rowIndex, columnIndex + (event.shiftKey ? -1 : 1));
                          }
                        }}
                        placeholder="-"
                      />
                    </td>
                  );
                })}
                <td className="sku-sheet-action-cell">
                  <button
                    className="btn btn-text btn-sm"
                    type="button"
                    onClick={() => handleDeleteRow(rowIndex)}
                  >
                    删除行
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
