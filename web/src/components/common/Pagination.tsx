interface Props {
  current: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}

export default function Pagination({ current, total, pageSize, onChange }: Props) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  const pages: number[] = [];
  const start = Math.max(1, current - 2);
  const end = Math.min(totalPages, current + 2);
  for (let i = start; i <= end; i++) pages.push(i);

  return (
    <div className="pagination">
      <button disabled={current === 1} onClick={() => onChange(current - 1)}>上一页</button>
      {pages.map((p) => (
        <button key={p} className={p === current ? "active" : ""} onClick={() => onChange(p)}>
          {p}
        </button>
      ))}
      <button disabled={current === totalPages} onClick={() => onChange(current + 1)}>下一页</button>
      <span className="pagination-info">共 {total} 条</span>
    </div>
  );
}
