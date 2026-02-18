import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * 全局错误边界 [§2.1]
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100vh",
            backgroundColor: "#0F1117",
            color: "#E2E8F4",
            fontFamily: "'Inter', sans-serif",
          }}
        >
          <h1 style={{ fontSize: 24, marginBottom: 16 }}>页面出错了</h1>
          <p style={{ color: "#94A3B8", marginBottom: 24 }}>
            {this.state.error?.message ?? "发生了未知错误"}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: "8px 24px",
              backgroundColor: "#22D3EE",
              color: "#0F1117",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            刷新页面
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
