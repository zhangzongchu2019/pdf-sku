"""
分片策略。对齐: Pipeline 详设 §5.5

>100 页 → 50 页/Chunk × 3 并发
[C1] 表格感知: 分片点不跨表格中间
"""
from __future__ import annotations
from pdf_sku.pipeline.ir import PageChunk
import structlog

logger = structlog.get_logger()


class ChunkingStrategy:
    CHUNK_SIZE = 50
    MAX_PARALLEL = 3
    THRESHOLD = 100
    MAX_ADJUST = 10

    def should_chunk(self, total_pages: int) -> bool:
        return total_pages > self.THRESHOLD

    def create_chunks(
        self, total_pages: int, blank_pages: list[int] | None = None,
    ) -> list[PageChunk]:
        """简单等分分片。"""
        effective = [p for p in range(1, total_pages + 1)
                     if p not in (blank_pages or [])]
        chunks = []
        for i in range(0, len(effective), self.CHUNK_SIZE):
            pages = effective[i:i + self.CHUNK_SIZE]
            chunks.append(PageChunk(chunk_id=len(chunks), pages=pages))
        return chunks

    async def create_chunks_table_aware(
        self,
        job_id: str,
        total_pages: int,
        blank_pages: list[int] | None = None,
        table_pages: set[int] | None = None,
    ) -> list[PageChunk]:
        """
        [C1] 表格感知分片。
        table_pages: 包含表格的页号集合
        """
        effective = [p for p in range(1, total_pages + 1)
                     if p not in (blank_pages or [])]
        if not effective:
            return []

        table_set = table_pages or set()
        chunks = []
        start = 0

        while start < len(effective):
            end = min(start + self.CHUNK_SIZE, len(effective))

            # 如果分片点在表格中间，向后推移
            if end < len(effective):
                adjust = 0
                while (adjust < self.MAX_ADJUST and
                       end + adjust < len(effective) and
                       effective[end + adjust - 1] in table_set):
                    adjust += 1
                end = min(end + adjust, len(effective))

            chunks.append(PageChunk(
                chunk_id=len(chunks),
                pages=effective[start:end],
            ))
            start = end

        logger.info("chunks_created",
                     job_id=job_id, chunks=len(chunks),
                     pages=len(effective), table_aware=bool(table_set))
        return chunks
