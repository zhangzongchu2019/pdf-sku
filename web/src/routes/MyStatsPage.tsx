/**
 * 我的统计页 /annotate/my-stats
 */
import { useState, useEffect, useCallback } from "react";
import { MyOutcomeStats } from "../components/annotator/MyOutcomeStats";
import { opsApi } from "../api/ops";
import { useAuthStore } from "../stores/authStore";

export default function MyStatsPage() {
  const annotatorId = useAuthStore((s) => s.annotatorId);
  const [stats, setStats] = useState<{
    todayPages: number;
    avgTimeMs: number;
    accuracy: number;
    weeklyRank?: number;
    trendData: { date: string; avgTime: number }[];
    outcomeMetrics: {
      extracted: number;
      imported: number;
      pending: number;
      rejected: number;
    };
  } | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    if (!annotatorId) return;
    try {
      setLoading(true);
      const raw = await opsApi.getMyOutcomeStats();
      // Map from API shape to component props
      const data = raw as Record<string, unknown>;
      setStats({
        todayPages: (data.today_completed as number) ?? 0,
        avgTimeMs: (data.avg_time_ms as number) ?? 0,
        accuracy: (data.today_accuracy as number) ?? 0,
        weeklyRank: data.weekly_rank as number | undefined,
        trendData: (data.trend_7d as { date: string; avgTime: number }[]) ?? [],
        outcomeMetrics: {
          extracted: (data.today_skus as number) ?? 0,
          imported: (data.imported as number) ?? 0,
          pending: (data.pending as number) ?? 0,
          rejected: (data.rejected as number) ?? 0,
        },
      });
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  }, [annotatorId]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  if (loading) {
    return (
      <div style={{ padding: 24, color: "#64748B" }}>加载统计数据…</div>
    );
  }

  if (!stats) {
    return (
      <div style={{ padding: 24, color: "#64748B" }}>暂无统计数据</div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 18, color: "#E2E8F4" }}>
        我的统计
      </h2>
      <MyOutcomeStats {...stats} />
    </div>
  );
}
