# pdf-sku-web

> PDF 自动分类与 SKU 提取系统 — 前端 SPA

## 技术栈

React 18 · TypeScript 5.5 · Vite 5 · Zustand (immer) · Tailwind CSS · TUS Upload · Canvas API

## 快速启动

```bash
# 1. 安装依赖
npm install

# 2. 启动开发服务器 (API 代理到 localhost:8000)
npm run dev

# 3. 访问 http://localhost:5173
```

## 工程结构

```
src/
├── api/          # Axios 封装 (4 个模块: jobs/tasks/config/ops)
├── stores/       # Zustand Stores (7个: job/sse/upload/annotation/notification/settings/importConfig)
├── types/        # TypeScript 类型 (对齐数据字典 §2 + §5)
├── routes/       # 路由页面 (含 ImportConfigPage)
├── components/   # canvas/ + annotation/ + dashboard/ + common/
├── hooks/        # useDebounce / useKeyboard
├── utils/        # security (DOMPurify) / a11y (ARIA)
└── workers/      # hashWorker (SHA-256)
```

## 文档 (`docs/` 目录)

| 文档 | 用途 |
|------|------|
| frontend_technical_design_v1_1 | **前端完整蓝图** (3,371行) |
| data_dictionary_state_machines | 类型/枚举/状态 速查 |
| openapi_v2_0.yaml | API schema → 可用 `npm run generate-api` 自动生成类型 |
| uiux_spec_v1_3 | UI/UX 设计规范 |
| test_strategy_v1_2 | 前端测试用例 |

## 开发约定

- **分支**: `feature/fe/{desc}` → `develop` → `main`
- **类型安全**: `npm run type-check` 零错误
- **API 类型同步**: 修改 OpenAPI 后执行 `npm run generate-api`
