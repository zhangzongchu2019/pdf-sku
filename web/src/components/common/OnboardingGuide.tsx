import { useSettingsStore } from "../../stores/settingsStore";

/**
 * 新手引导组件 [V1.1 A3]
 * react-joyride 5 步引导
 */
export function OnboardingGuide() {
  const annotationOnboarded = useSettingsStore((s) => s.annotationOnboarded);
  const setAnnotationOnboarded = useSettingsStore((s) => s.setAnnotationOnboarded);

  if (annotationOnboarded) return null;

  const steps = [
    {
      target: "[data-tour='page-grid']",
      title: "1. 选择页面",
      content: "左侧面板展示 PDF 所有页面缩略图，点击选择要标注的页面。",
    },
    {
      target: "[data-tour='canvas-workbench']",
      title: "2. 查看 AI 识别结果",
      content: "中间画布展示页面截图和 AI 预识别的文本/图片元素。蓝色框 = 文本，绿色框 = 图片。",
    },
    {
      target: "[data-tour='lasso-tool']",
      title: "3. 使用套索工具",
      content: "按 L 键切换到套索模式，画圈选中属于同一个 SKU 的元素，然后按 G 创建分组。",
    },
    {
      target: "[data-tour='group-editor']",
      title: "4. 填写 SKU 属性",
      content: "右侧面板编辑每个分组的 SKU 属性（型号、名称、颜色、尺码等）。",
    },
    {
      target: "[data-tour='submit-btn']",
      title: "5. 提交标注",
      content: "确认无误后按 Ctrl+Enter 提交，系统会自动跳转到下一页。",
    },
  ];

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.5)",
        zIndex: 10000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      onClick={() => setAnnotationOnboarded(true)}
    >
      <div
        style={{
          backgroundColor: "#1A1F2C",
          borderRadius: 12,
          padding: 32,
          maxWidth: 480,
          color: "#E2E8F4",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ color: "#22D3EE", marginBottom: 16 }}>欢迎使用标注工具 👋</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 24 }}>
          {steps.map((step, i) => (
            <div key={i} style={{ display: "flex", gap: 12 }}>
              <span style={{ color: "#22D3EE", fontWeight: 600, minWidth: 20 }}>{i + 1}.</span>
              <div>
                <div style={{ fontWeight: 500, marginBottom: 2 }}>{step.title}</div>
                <div style={{ color: "#94A3B8", fontSize: 13 }}>{step.content}</div>
              </div>
            </div>
          ))}
        </div>
        <button
          onClick={() => setAnnotationOnboarded(true)}
          style={{
            width: "100%",
            padding: "10px 0",
            backgroundColor: "#22D3EE",
            color: "#0F1117",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 14,
            fontWeight: 600,
          }}
        >
          开始使用
        </button>
      </div>
    </div>
  );
}

export default OnboardingGuide;
