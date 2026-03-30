import { useEffect } from "react";
import { jobsApi } from "../api/jobs";

/**
 * 预加载 Hook — 当前页加载完成后预加载下一页截图
 */
export function usePrefetch(
  currentJobId: string | null,
  currentPageNo: number | null,
  adjacentPages: number[],
) {
  useEffect(() => {
    if (!currentJobId || currentPageNo === null || adjacentPages.length === 0) return;

    const timer = setTimeout(async () => {
      const nextPage = adjacentPages[0];
      try {
        const img = new Image();
        img.src = jobsApi.getPagePreviewUrl(currentJobId, nextPage);
        await jobsApi.getPage(currentJobId, nextPage);
      } catch {
        // Silent fail for prefetch
      }
    }, 2000);

    return () => clearTimeout(timer);
  }, [currentJobId, currentPageNo, adjacentPages]);
}
