interface Props {
  onSubmit: () => void;
  onSkip: () => void;
  onAddSku: () => void;
  annotationCount: number;
}

export default function ToolBar({ onSubmit, onSkip, onAddSku, annotationCount }: Props) {
  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <button className="btn btn-outline" onClick={onAddSku} title="添加 SKU (Ctrl+N)">
          + 添加 SKU
        </button>
        <span className="toolbar-info">修改: {annotationCount} 项</span>
      </div>
      <div className="toolbar-right">
        <button className="btn btn-ghost" onClick={onSkip} title="跳过 (Esc)">
          跳过
        </button>
        <button className="btn btn-primary" onClick={onSubmit}
                title="提交 (Ctrl+Enter)" disabled={annotationCount === 0}>
          提交标注 ({annotationCount})
        </button>
      </div>
    </div>
  );
}
