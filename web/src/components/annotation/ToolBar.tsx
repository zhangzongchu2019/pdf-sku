interface Props {
  onSubmit: () => void;
  onSkip: () => void;
  onAddSku: () => void;
  annotationCount: number;
  drawingMode?: boolean;
  onAppendBox?: () => void;
  canAppendBox?: boolean;
}

export default function ToolBar({ onSubmit, onSkip, onAddSku, annotationCount, drawingMode = false, onAppendBox, canAppendBox = false }: Props) {
  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <button
          className={`btn ${drawingMode ? "btn-primary" : "btn-outline"}`}
          onClick={onAddSku}
          title="添加 SKU (Ctrl+N)"
        >
          {drawingMode ? "画框中...（点击取消）" : "+ 添加 SKU"}
        </button>
        {canAppendBox && onAppendBox && (
          <button
            className="btn btn-outline"
            onClick={onAppendBox}
            title="为选中的 SKU 追加一个区域框"
          >
            + 追加区域
          </button>
        )}
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
