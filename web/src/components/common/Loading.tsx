export default function Loading({ text = "加载中..." }: { text?: string }) {
  return (
    <div className="loading-container">
      <div className="loading-spinner" />
      <p>{text}</p>
    </div>
  );
}
