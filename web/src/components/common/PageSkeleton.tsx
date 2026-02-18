/**
 * 页面骨架屏 — 路由 Suspense fallback [§2.2]
 */
export function PageSkeleton() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        padding: 24,
        maxWidth: 1200,
        margin: "0 auto",
      }}
    >
      {/* Header skeleton */}
      <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
        <div className="skeleton-pulse" style={{ width: 200, height: 28, borderRadius: 6 }} />
        <div className="skeleton-pulse" style={{ width: 120, height: 28, borderRadius: 6 }} />
      </div>
      {/* Cards skeleton */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="skeleton-pulse"
            style={{ height: 100, borderRadius: 8 }}
          />
        ))}
      </div>
      {/* Table skeleton */}
      <div className="skeleton-pulse" style={{ height: 400, borderRadius: 8 }} />
      <style>{`
        .skeleton-pulse {
          background: linear-gradient(90deg, #1A1F2C 25%, #242B3D 50%, #1A1F2C 75%);
          background-size: 200% 100%;
          animation: pulse 1.5s ease-in-out infinite;
        }
        @keyframes pulse {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  );
}

export default PageSkeleton;
