/**
 * 阈值滑块 — 带输入框的双控件
 * 包含安全护栏警告
 */
import { useState, useCallback } from "react";

interface ThresholdSliderProps {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
  warning?: string | null;
}

export function ThresholdSlider({
  label,
  value,
  min = 0,
  max = 1,
  step = 0.01,
  onChange,
  warning,
}: ThresholdSliderProps) {
  const [inputValue, setInputValue] = useState(value.toString());

  const handleSlider = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const v = parseFloat(e.target.value);
      onChange(v);
      setInputValue(v.toFixed(2));
    },
    [onChange],
  );

  const handleInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      setInputValue(raw);
      const v = parseFloat(raw);
      if (!isNaN(v) && v >= min && v <= max) {
        onChange(v);
      }
    },
    [onChange, min, max],
  );

  const handleBlur = useCallback(() => {
    setInputValue(value.toFixed(2));
  }, [value]);

  return (
    <div style={{ marginBottom: 12 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 4,
        }}
      >
        <label style={{ fontSize: 12, color: "#94A3B8" }}>{label}</label>
        <input
          type="text"
          value={inputValue}
          onChange={handleInput}
          onBlur={handleBlur}
          style={{
            width: 60,
            padding: "2px 6px",
            backgroundColor: "#161D2F",
            border: "1px solid #2D3548",
            borderRadius: 4,
            color: "#E2E8F4",
            fontSize: 12,
            textAlign: "right",
          }}
        />
      </div>

      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleSlider}
        style={{
          width: "100%",
          accentColor: warning ? "#F59E0B" : "#22D3EE",
        }}
      />

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 10,
          color: "#64748B",
        }}
      >
        <span>{min}</span>
        <span>{max}</span>
      </div>

      {warning && (
        <div
          style={{
            marginTop: 4,
            padding: "4px 8px",
            backgroundColor: "#F59E0B11",
            border: "1px solid #F59E0B33",
            borderRadius: 4,
            fontSize: 11,
            color: "#F59E0B",
          }}
        >
          ⚠ {warning}
        </div>
      )}
    </div>
  );
}

export default ThresholdSlider;
