import { useImportConfigStore } from "../stores/importConfigStore";
import type { FieldMapping } from "../stores/importConfigStore";

const SKU_SOURCE_FIELDS = [
  "model", "name", "brand", "category", "price", "unit",
  "spec", "material", "color", "size", "weight", "origin",
  "barcode", "description",
];

export default function ImportConfigPage() {
  const {
    apiEndpoint, authToken, fieldMappings, cosConfig,
    setApiEndpoint, setAuthToken,
    addMapping, updateMapping, removeMapping,
    setCosConfig,
  } = useImportConfigStore();

  return (
    <div className="page" style={{ maxWidth: 800 }}>
      <h2>商品导入配置</h2>

      {/* Section 1: API */}
      <Section title="API 接口配置">
        <FormRow label="接口地址">
          <input
            type="text"
            value={apiEndpoint}
            onChange={(e) => setApiEndpoint(e.target.value)}
            placeholder="https://api.example.com/products"
            style={inputStyle}
          />
        </FormRow>
        <FormRow label="Auth Token">
          <input
            type="password"
            value={authToken}
            onChange={(e) => setAuthToken(e.target.value)}
            placeholder="Bearer token"
            style={inputStyle}
          />
        </FormRow>
      </Section>

      {/* Section 2: Field Mappings */}
      <Section title="字段映射">
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #2D3548" }}>
              <th style={thStyle}>SKU 属性</th>
              <th style={thStyle}>目标字段</th>
              <th style={{ ...thStyle, width: 60 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {fieldMappings.map((m: FieldMapping) => (
              <tr key={m.id} style={{ borderBottom: "1px solid #2D354866" }}>
                <td style={{ padding: 6 }}>
                  <select
                    value={m.sourceField}
                    onChange={(e) => updateMapping(m.id, { sourceField: e.target.value })}
                    style={inputStyle}
                  >
                    <option value="">-- 选择 --</option>
                    {SKU_SOURCE_FIELDS.map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                </td>
                <td style={{ padding: 6 }}>
                  <input
                    type="text"
                    value={m.targetField}
                    onChange={(e) => updateMapping(m.id, { targetField: e.target.value })}
                    placeholder="目标字段名"
                    style={inputStyle}
                  />
                </td>
                <td style={{ padding: 6, textAlign: "center" }}>
                  <button
                    onClick={() => removeMapping(m.id)}
                    style={dangerBtnStyle}
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button onClick={addMapping} style={addBtnStyle}>+ 添加映射</button>
      </Section>

      {/* Section 3: COS */}
      <Section title="腾讯云 COS 配置">
        <FormRow label="SecretId">
          <input
            type="text"
            value={cosConfig.secretId}
            onChange={(e) => setCosConfig({ secretId: e.target.value })}
            style={inputStyle}
          />
        </FormRow>
        <FormRow label="SecretKey">
          <input
            type="password"
            value={cosConfig.secretKey}
            onChange={(e) => setCosConfig({ secretKey: e.target.value })}
            style={inputStyle}
          />
        </FormRow>
        <FormRow label="Bucket">
          <input
            type="text"
            value={cosConfig.bucket}
            onChange={(e) => setCosConfig({ bucket: e.target.value })}
            placeholder="my-bucket-1250000000"
            style={inputStyle}
          />
        </FormRow>
        <FormRow label="Region">
          <input
            type="text"
            value={cosConfig.region}
            onChange={(e) => setCosConfig({ region: e.target.value })}
            placeholder="ap-guangzhou"
            style={inputStyle}
          />
        </FormRow>
      </Section>

      <div style={{ marginTop: 16, fontSize: 12, color: "#64748B" }}>
        已自动保存到本地存储
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      marginBottom: 24,
      backgroundColor: "#1B2233",
      border: "1px solid #2D3548",
      borderRadius: 8,
      padding: 16,
    }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#E2E8F4" }}>{title}</h3>
      {children}
    </div>
  );
}

function FormRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
      <label style={{ width: 100, fontSize: 13, color: "#94A3B8", flexShrink: 0 }}>{label}</label>
      <div style={{ flex: 1 }}>{children}</div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "6px 10px",
  backgroundColor: "#0F172A",
  border: "1px solid #2D3548",
  borderRadius: 4,
  color: "#E2E8F4",
  fontSize: 13,
  boxSizing: "border-box",
};

const thStyle: React.CSSProperties = {
  padding: "8px 6px",
  textAlign: "left",
  color: "#64748B",
  fontWeight: 500,
  fontSize: 11,
};

const addBtnStyle: React.CSSProperties = {
  marginTop: 8,
  padding: "4px 12px",
  backgroundColor: "#22D3EE18",
  border: "1px solid #22D3EE33",
  borderRadius: 4,
  color: "#22D3EE",
  cursor: "pointer",
  fontSize: 12,
};

const dangerBtnStyle: React.CSSProperties = {
  padding: "2px 8px",
  backgroundColor: "#EF444418",
  border: "1px solid #EF444433",
  borderRadius: 3,
  color: "#EF4444",
  cursor: "pointer",
  fontSize: 11,
};
