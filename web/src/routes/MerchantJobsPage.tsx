/**
 * 商家Jobs页
 */
import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { opsApi } from "../api/ops";
import type { MerchantStats } from "../types/models";

export default function MerchantJobsPage() {
  const { merchantId } = useParams<{ merchantId: string }>();
  const [stats, setStats] = useState<MerchantStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    if (!merchantId) return;
    try {
      setLoading(true);
      const data = await opsApi.getMerchantStats(merchantId);
      setStats(data);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, [merchantId]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  if (loading) {
    return <div style={{ padding: 24, color: "#64748B" }}>加载中…</div>;
  }

  if (!stats) {
    return <div style={{ padding: 24, color: "#64748B" }}>未找到商家信息</div>;
  }

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 18, color: "#E2E8F4" }}>
        商家 {merchantId}
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
          marginBottom: 24,
        }}
      >
        <StatCard label="总Job数" value={stats.total_jobs} />
        <StatCard label="总SKU数" value={stats.total_skus} />
        <StatCard label="成功率" value={`${(stats.success_rate * 100).toFixed(1)}%`} />
        <StatCard label="平均处理时间" value={`${(stats.avg_process_time / 1000).toFixed(1)}s`} />
      </div>

      {/* Recent jobs could be listed here, fetched from search */}
      <div style={{ color: "#64748B", fontSize: 13 }}>
        商家详情页 — 可扩展查看该商家所有Job和SKU趋势
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        padding: 16,
        backgroundColor: "#1B2233",
        border: "1px solid #2D3548",
        borderRadius: 8,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: "#E2E8F4" }}>{value}</div>
    </div>
  );
}
