import { useState, useRef, useEffect } from "react";

/**
 * 页面缩略图网格 — 左面板 [§7.4]
 * 支持虚拟滚动和懒加载
 */
interface PageInfo {
  page_no: number;
  status: string;
  confidence?: number | null;
  task_id?: string | null;
}

interface PageGridProps {
  pages: PageInfo[];
  currentPageNo: number | null;
  jobId: string;
  onPageSelect: (pageNo: number) => void;
}

export function PageGrid({ pages, currentPageNo, jobId, onPageSelect }: PageGridProps) {
  return (
    <div
      data-tour="page-grid"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, 1fr)",
        gap: 8,
        padding: 8,
        overflowY: "auto",
        height: "100%",
      }}
    >
      {pages.map((page) => (
        <PageThumbnail
          key={page.page_no}
          page={page}
          jobId={jobId}
          isActive={page.page_no === currentPageNo}
          onSelect={() => onPageSelect(page.page_no)}
        />
      ))}
    </div>
  );
}

function PageThumbnail({
  page,
  jobId,
  isActive,
  onSelect,
}: {
  page: PageInfo;
  jobId: string;
  isActive: boolean;
  onSelect: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setLoaded(true);
      },
      { rootMargin: "200px" },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  const statusColor: Record<string, string> = {
    AI_COMPLETED: "#52C41A",
    HUMAN_COMPLETED: "#52C41A",
    IMPORTED_CONFIRMED: "#1890FF",
    HUMAN_QUEUED: "#FAAD14",
    HUMAN_PROCESSING: "#FAAD14",
    AI_FAILED: "#FF4D4F",
    IMPORT_FAILED: "#FF4D4F",
    DEAD_LETTER: "#FF4D4F",
    BLANK: "#434343",
    PENDING: "#262626",
  };

  return (
    <div
      ref={ref}
      onClick={onSelect}
      style={{
        cursor: "pointer",
        borderRadius: 6,
        overflow: "hidden",
        border: isActive ? "2px solid #22D3EE" : "2px solid transparent",
        backgroundColor: "#1A1F2C",
        position: "relative",
      }}
    >
      {loaded ? (
        <img
          src={`/api/v1/jobs/${jobId}/pages/${page.page_no}/screenshot?w=120`}
          alt={`第 ${page.page_no} 页`}
          style={{ width: "100%", height: 80, objectFit: "cover" }}
          loading="lazy"
        />
      ) : (
        <div style={{ width: "100%", height: 80, backgroundColor: "#242B3D" }} />
      )}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "2px 6px",
          fontSize: 11,
          color: "#94A3B8",
        }}
      >
        <span>P{page.page_no}</span>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: statusColor[page.status] ?? "#434343",
          }}
        />
      </div>
    </div>
  );
}

export default PageGrid;
