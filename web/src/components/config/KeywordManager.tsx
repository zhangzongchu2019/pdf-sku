/**
 * 关键词管理器 — 热加载关键词库
 * 支持增删改，批量导入
 */
import { useState, useCallback } from "react";

interface KeywordManagerProps {
  keywords: string[];
  onAdd: (keyword: string) => void;
  onRemove: (keyword: string) => void;
  onBulkImport: (keywords: string[]) => void;
}

export function KeywordManager({
  keywords,
  onAdd,
  onRemove,
  onBulkImport,
}: KeywordManagerProps) {
  const [input, setInput] = useState("");
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkText, setBulkText] = useState("");

  const handleAdd = useCallback(() => {
    const trimmed = input.trim();
    if (trimmed && !keywords.includes(trimmed)) {
      onAdd(trimmed);
      setInput("");
    }
  }, [input, keywords, onAdd]);

  const handleBulkImport = useCallback(() => {
    const newKeywords = bulkText
      .split(/[\n,;，；]/)
      .map((k) => k.trim())
      .filter((k) => k.length > 0 && !keywords.includes(k));
    if (newKeywords.length > 0) {
      onBulkImport(newKeywords);
      setBulkText("");
      setBulkMode(false);
    }
  }, [bulkText, keywords, onBulkImport]);

  return (
    <div
      style={{
        backgroundColor: "#1B2233",
        border: "1px solid #2D3548",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <h4 style={{ margin: 0, fontSize: 13, color: "#E2E8F4" }}>
          关键词库 ({keywords.length})
        </h4>
        <button
          onClick={() => setBulkMode(!bulkMode)}
          style={{
            background: "none",
            border: "1px solid #2D3548",
            borderRadius: 4,
            color: "#94A3B8",
            cursor: "pointer",
            fontSize: 11,
            padding: "3px 8px",
          }}
        >
          {bulkMode ? "单个添加" : "批量导入"}
        </button>
      </div>

      {bulkMode ? (
        <div>
          <textarea
            value={bulkText}
            onChange={(e) => setBulkText(e.target.value)}
            placeholder="每行一个关键词，或用逗号分隔"
            style={{
              width: "100%",
              minHeight: 80,
              padding: 8,
              backgroundColor: "#161D2F",
              border: "1px solid #2D3548",
              borderRadius: 4,
              color: "#E2E8F4",
              fontSize: 12,
              resize: "vertical",
            }}
          />
          <button
            onClick={handleBulkImport}
            style={{
              marginTop: 8,
              padding: "6px 14px",
              backgroundColor: "#22D3EE",
              border: "none",
              borderRadius: 4,
              color: "#0F172A",
              fontWeight: 600,
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            导入
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="输入关键词"
            style={{
              flex: 1,
              padding: "6px 10px",
              backgroundColor: "#161D2F",
              border: "1px solid #2D3548",
              borderRadius: 4,
              color: "#E2E8F4",
              fontSize: 12,
            }}
          />
          <button
            onClick={handleAdd}
            style={{
              padding: "6px 14px",
              backgroundColor: "#22D3EE22",
              border: "1px solid #22D3EE44",
              borderRadius: 4,
              color: "#22D3EE",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            添加
          </button>
        </div>
      )}

      {/* Keyword tags */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {keywords.map((kw) => (
          <span
            key={kw}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 8px",
              backgroundColor: "#22D3EE11",
              border: "1px solid #22D3EE22",
              borderRadius: 4,
              fontSize: 11,
              color: "#22D3EE",
            }}
          >
            {kw}
            <button
              onClick={() => onRemove(kw)}
              style={{
                background: "none",
                border: "none",
                color: "#64748B",
                cursor: "pointer",
                padding: 0,
                fontSize: 12,
                lineHeight: 1,
              }}
            >
              ×
            </button>
          </span>
        ))}
        {keywords.length === 0 && (
          <span style={{ fontSize: 12, color: "#64748B" }}>暂无关键词</span>
        )}
      </div>
    </div>
  );
}

export default KeywordManager;
