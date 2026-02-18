/**
 * Job 表格 — 包含排序、列头和行列表
 */
import { useCallback } from "react";
import { JobRow } from "./JobRow";
import type { Job } from "../../types/models";

interface JobTableProps {
  jobs: Job[];
  selectedIds: Set<string>;
  onSelect: (id: string, checked: boolean) => void;
  onSelectAll: (checked: boolean) => void;
  onJobClick: (id: string) => void;
  loading?: boolean;
}

const COLUMNS = [
  { key: "checkbox", label: "", width: 40 },
  { key: "filename", label: "文件名", width: undefined },
  { key: "merchant", label: "商家", width: 100 },
  { key: "pages", label: "页数", width: 60 },
  { key: "route", label: "路由", width: 80 },
  { key: "status", label: "状态", width: 140 },
  { key: "progress", label: "进度", width: 120 },
  { key: "human", label: "待标注", width: 60 },
  { key: "action", label: "操作", width: 60 },
];

export function JobTable({
  jobs,
  selectedIds,
  onSelect,
  onSelectAll,
  onJobClick,
  loading,
}: JobTableProps) {
  const allSelected = jobs.length > 0 && jobs.every((j) => selectedIds.has(j.job_id));

  const handleSelectAll = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => onSelectAll(e.target.checked),
    [onSelectAll],
  );

  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 13,
          color: "#E2E8F4",
        }}
      >
        <thead>
          <tr style={{ borderBottom: "1px solid #2D3548" }}>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                style={{
                  padding: "8px 8px",
                  textAlign: "left",
                  color: "#64748B",
                  fontWeight: 500,
                  fontSize: 11,
                  width: col.width,
                  whiteSpace: "nowrap",
                }}
              >
                {col.key === "checkbox" ? (
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={handleSelectAll}
                    style={{ accentColor: "#22D3EE" }}
                  />
                ) : (
                  col.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={COLUMNS.length} style={{ padding: 40, textAlign: "center", color: "#64748B" }}>
                加载中…
              </td>
            </tr>
          ) : jobs.length === 0 ? (
            <tr>
              <td colSpan={COLUMNS.length} style={{ padding: 40, textAlign: "center", color: "#64748B" }}>
                暂无任务
              </td>
            </tr>
          ) : (
            jobs.map((job) => (
              <JobRow
                key={job.job_id}
                job={job}
                selected={selectedIds.has(job.job_id)}
                onSelect={onSelect}
                onClick={onJobClick}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default JobTable;
