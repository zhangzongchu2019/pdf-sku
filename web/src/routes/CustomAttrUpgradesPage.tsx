/**
 * 自定义属性升级审核页 /ops/custom-attr-upgrades
 */
import { useState, useEffect, useCallback } from "react";
import { opsApi } from "../api/ops";
import Pagination from "../components/common/Pagination";
import type { CustomAttrUpgrade } from "../types/models";

export default function CustomAttrUpgradesPage() {
  const [upgrades, setUpgrades] = useState<CustomAttrUpgrade[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("PENDING");

  const fetchUpgrades = useCallback(async () => {
    try {
      setLoading(true);
      const res = await opsApi.listCustomAttrUpgrades({ status: filter, page, size: 20 });
      setUpgrades(res.data);
      setTotal(res.pagination.total);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, [page, filter]);

  useEffect(() => { fetchUpgrades(); }, [fetchUpgrades]);

  const handleReview = async (upgradeId: string, action: "approve" | "reject") => {
    try {
      await opsApi.reviewCustomAttrUpgrade({ upgrade_id: upgradeId, action });
      fetchUpgrades();
    } catch {
      // handle
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 18, color: "#E2E8F4" }}>
        自定义属性升级
      </h2>

      {/* Filter tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {["PENDING", "APPROVED", "REJECTED", "ALL"].map((f) => (
          <button
            key={f}
            onClick={() => { setFilter(f === "ALL" ? "" : f); setPage(1); }}
            style={{
              padding: "4px 12px",
              backgroundColor: (filter === f || (f === "ALL" && !filter)) ? "#22D3EE22" : "transparent",
              border: `1px solid ${(filter === f || (f === "ALL" && !filter)) ? "#22D3EE44" : "#2D3548"}`,
              borderRadius: 4,
              color: (filter === f || (f === "ALL" && !filter)) ? "#22D3EE" : "#94A3B8",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            {f === "ALL" ? "全部" : f}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ color: "#64748B" }}>加载中…</div>
      ) : upgrades.length === 0 ? (
        <div style={{ color: "#64748B" }}>暂无升级请求</div>
      ) : (
        <>
          <table
            style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, color: "#E2E8F4" }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid #2D3548" }}>
                {["ID", "商家", "属性名", "建议值", "状态", "创建时间", "操作"].map((h) => (
                  <th key={h} style={{ padding: "8px", textAlign: "left", color: "#64748B", fontWeight: 500, fontSize: 11 }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {upgrades.map((u) => (
                <tr key={u.upgrade_id} style={{ borderBottom: "1px solid #2D354866" }}>
                  <td style={{ padding: "8px" }}>{u.upgrade_id}</td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>{u.merchant_id}</td>
                  <td style={{ padding: "8px" }}>{u.attribute_key}</td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>{u.proposed_value}</td>
                  <td style={{ padding: "8px" }}>
                    <span style={{
                      padding: "1px 6px",
                      backgroundColor: u.status === "pending" ? "#F59E0B18" : u.status === "approved" ? "#22C55E18" : "#EF444418",
                      border: `1px solid ${u.status === "pending" ? "#F59E0B33" : u.status === "approved" ? "#22C55E33" : "#EF444433"}`,
                      borderRadius: 3, fontSize: 11,
                      color: u.status === "pending" ? "#F59E0B" : u.status === "approved" ? "#22C55E" : "#EF4444",
                    }}>
                      {u.status.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>
                    {new Date(u.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: "8px" }}>
                    {u.status === "pending" && (
                      <div style={{ display: "flex", gap: 4 }}>
                        <button
                          onClick={() => handleReview(u.upgrade_id, "approve")}
                          style={{ padding: "3px 8px", backgroundColor: "#22C55E18", border: "1px solid #22C55E33", borderRadius: 3, color: "#22C55E", cursor: "pointer", fontSize: 11 }}
                        >
                          通过
                        </button>
                        <button
                          onClick={() => handleReview(u.upgrade_id, "reject")}
                          style={{ padding: "3px 8px", backgroundColor: "#EF444418", border: "1px solid #EF444433", borderRadius: 3, color: "#EF4444", cursor: "pointer", fontSize: 11 }}
                        >
                          拒绝
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 16 }}>
            <Pagination current={page} total={total} pageSize={20} onChange={setPage} />
          </div>
        </>
      )}
    </div>
  );
}
