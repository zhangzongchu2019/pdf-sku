/**
 * 设置页 /settings
 */
import { useSettingsStore } from "../stores/settingsStore";

export default function SettingsPage() {
  const settings = useSettingsStore();

  const toggleStyle = (active: boolean): React.CSSProperties => ({
    width: 40,
    height: 22,
    borderRadius: 11,
    backgroundColor: active ? "#22D3EE" : "#334155",
    position: "relative",
    cursor: "pointer",
    transition: "background-color 0.2s",
    border: "none",
    padding: 0,
  });

  const dotStyle = (active: boolean): React.CSSProperties => ({
    width: 16,
    height: 16,
    borderRadius: "50%",
    backgroundColor: "#fff",
    position: "absolute",
    top: 3,
    left: active ? 21 : 3,
    transition: "left 0.2s",
  });

  return (
    <div style={{ padding: 24, maxWidth: 640, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 24px", fontSize: 18, color: "#E2E8F4" }}>设置</h2>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Theme */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>深色主题</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>切换深色/浅色模式</div>
          </div>
          <button
            style={toggleStyle(settings.theme === "dark")}
            onClick={() => settings.setTheme(settings.theme === "dark" ? "light" : "dark")}
            aria-label="切换主题"
          >
            <span style={dotStyle(settings.theme === "dark")} />
          </button>
        </div>

        {/* Skip submit confirm */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>跳过提交确认</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>提交标注时不弹出确认对话框</div>
          </div>
          <button
            style={toggleStyle(settings.skipSubmitConfirm)}
            onClick={() => settings.setSkipSubmitConfirm(!settings.skipSubmitConfirm)}
            aria-label="跳过提交确认"
          >
            <span style={dotStyle(settings.skipSubmitConfirm)} />
          </button>
        </div>

        {/* Enable rest reminder */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>休息提醒</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>连续标注后提醒休息</div>
          </div>
          <button
            style={toggleStyle(settings.enableRestReminder)}
            onClick={() => settings.setEnableRestReminder(!settings.enableRestReminder)}
            aria-label="休息提醒"
          >
            <span style={dotStyle(settings.enableRestReminder)} />
          </button>
        </div>

        {/* Rest reminder minutes */}
        {settings.enableRestReminder && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
            <div>
              <div style={{ fontSize: 13, color: "#E2E8F4" }}>提醒间隔（分钟）</div>
              <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>连续工作多久后提醒</div>
            </div>
            <input
              type="number"
              min={10}
              max={180}
              value={settings.restReminderMinutes}
              onChange={(e) => settings.setRestReminderMinutes(Number(e.target.value))}
              style={{
                width: 64,
                padding: "4px 8px",
                backgroundColor: "#0F172A",
                border: "1px solid #2D3548",
                borderRadius: 4,
                color: "#E2E8F4",
                fontSize: 13,
                textAlign: "center",
              }}
            />
          </div>
        )}

        {/* Enable sound */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>通知音效</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>收到紧急通知时播放声音</div>
          </div>
          <button
            style={toggleStyle(settings.enableSound)}
            onClick={() => settings.setEnableSound(!settings.enableSound)}
            aria-label="通知音效"
          >
            <span style={dotStyle(settings.enableSound)} />
          </button>
        </div>

        {/* Preferred page size */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>每页显示条数</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>列表页面的默认分页大小</div>
          </div>
          <select
            value={settings.preferredPageSize}
            onChange={(e) => settings.setPreferredPageSize(Number(e.target.value))}
            style={{
              padding: "4px 8px",
              backgroundColor: "#0F172A",
              border: "1px solid #2D3548",
              borderRadius: 4,
              color: "#E2E8F4",
              fontSize: 13,
            }}
          >
            {[10, 20, 50, 100].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
