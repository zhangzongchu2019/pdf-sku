# PDF-SKU 提取系统前端技术详细设计

> **文档版本**: V1.2
> **上游依赖**: UI/UX V1.3 · TA V1.7 · OpenAPI V2.0 · BRD V2.1 · 后端详设 V1.2 · 前端评审报告
> **技术栈**: React 18 + TypeScript 5 + Vite 5 + Zustand (immer)
> **目标浏览器**: Chrome/Edge 100+, Firefox 100+, Safari 16+

---

## V1.2 变更记录 (2026-02-21)

| 变更 | 影响章节 |
|------|---------|
| 新增 `importConfigStore.ts` — 商品导入配置 (Zustand + persist + immer, localStorage) | §1.2, §3.1 |
| 新增 `ImportConfigPage.tsx` — 商品导入配置页面 (/config/import, admin) | §1.2, §2.1 |
| `jobStore.ts` 新增 `pageDetail` 状态 + `fetchPageDetail` action | §3.1 |
| `jobs.ts` API 新增 `getPageDetail`, `getImageUrl` 方法 + PageDetail 类型 | §5.2 |
| `JobDetailPage.tsx` Pages tab 增加缩略图列 + 点击展开详情行（大图+SKU+图片） | §5.6 |
| `SKUList.tsx` 图片列展示缩略图 + 点击展开全属性 + Lightbox | §5.6 |
| `Layout.tsx` OPS_NAV 新增"导入配置"入口 | §2.1 |
| 兼容 `model_number`/`product_name` 和 `model`/`name` 属性字段名 | §5.6 |

---

## V1.1 变更记录

以 V1.0 为基础，合入两类变更：

**一、评审修复（31 项：7 P0 + 16 P1 + 8 P2）**

| ID | 优先级 | 变更 | 影响章节 |
|----|--------|------|---------|
| A1 | P0 | 右键上下文菜单完整规格 | §6.5 |
| B1 | P0 | SSE 事件扩展至 9 种（+heartbeat/pages_batch_update/job_failed/sla_auto_resolve/sla_auto_accepted） | §5.3 |
| B2 | P0 | Config impact-preview API 集成 | §5.2 |
| C1 | P0 | Zustand 引入 immer middleware，Map→immer-safe 操作 | §3.1 |
| D1 | P0 | Canvas ResizeObserver 重适配 | §4.4 |
| E1 | P0 | tus 上传后 Job 创建失败回滚 DELETE /uploads/{id} | §5.5 |
| G1 | P0 | XSS 防护：ESLint no-danger + DOMPurify | §9.3 |
| A2 | P1 | 通知三级优先级→UI 行为映射 | §3.1 |
| A3 | P1 | 新手引导 react-joyride 5 步配置 | §6.6 |
| A4 | P1 | 休息提醒 useRestReminder hook | §6.7 |
| B3 | P1 | 批量操作 API 封装（batch-retry/cancel/reassign/skip） | §5.2 |
| B4 | P1 | 跨页 SKU API 封装 | §5.2 |
| C2 | P1 | Set→string[] + immer 统一方案 | §3.1 |
| C3 | P1 | undo 与 annotation 操作原子性 | §3.1 |
| D2 | P1 | 套索坐标系统一（减去容器 offset） | §4.6 |
| D3 | P1 | ElementOverlay 改用 transform: translate3d | §4.5 |
| D4 | P1 | 事件委托：容器级 onClick + data-element-id | §4.5 |
| E2 | P1 | Axios 拦截器区分全局/业务错误 | §5.1 |
| E3 | P1 | heartbeat 连续失败降级提示 | §5.4 |
| F1 | P1 | 生产环境 PerformanceObserver longtask 监控 | §7.2 |
| F2 | P1 | SSE 降级轮询动态间隔（PROCESSING 5s / 其他 30s） | §5.3 |
| G2 | P1 | ARIA 标签完整对照表（8 种组件） | §9.4 |
| G3 | P1 | CSRF Token 策略（纯 JWT → 不需要，备注确认） | §9.3 |
| A5 | P2 | 批量操作浮层 BatchActionFloater | §6.5 |
| A6 | P2 | 跳过提交确认 settingsStore.skipSubmitConfirm | §3.1 |
| B5 | P2 | 评测报告 API 封装 | §5.2 |
| C4 | P2 | jobStore.selectedIds SSE 后自动清理 | §3.1 |
| D5 | P2 | 点阵背景离屏 Canvas / CSS 替代 | §4.4 |
| E4 | P2 | Web Worker hashWorker 60s 超时保护 | §5.5 |
| F3 | P2 | Service Worker 截图版本化缓存 | §7.6 |
| G4 | P2 | forced-colors 高对比度适配 | §9.1 |

**二、OpenAPI V2.0 对齐（15 项增强）**

| 变更 | 影响章节 |
|------|---------|
| Job.user_status + action_hint 双轨状态 | §3.1, §9.2 |
| TaskDetail +locked_by/locked_at/rework_count/timeout_at | §9.2 |
| SKUImage +binding_method/is_duplicate/image_hash | §9.2 |
| POST /annotations 独立标注端点 (8 种 type) | §5.2 |
| POST /tasks/next 自动领取 | §5.2 |
| GET /metrics, GET /ops/dashboard/events | §5.2 |
| POST /ops/tasks/batch-skip | §5.2 |
| /ops/custom-attr-upgrades (GET+POST) | §5.2 |
| GET /jobs +created_after/created_before | §5.2 |
| Evaluation +route_reason/sampling/prompt_version | §9.2 |
| PrescanResult +raw_metrics | §9.2 |
| ErrorResponse.severity → toast/modal/banner 映射 | §5.1 |
| PaginationMeta 独立 schema | §9.2 |
| HealthResponse +version/uptime_sec/worker_id | §9.2 |
| Tag 细分 12 个 → API 模块重组 | §5.2 |

---

## 1. 工程架构

### 1.1 架构分层

```
┌─────────────────────────────────────────────────────────┐
│                    Pages / Routes                        │  路由页面层
├─────────────────────────────────────────────────────────┤
│                    Feature Modules                       │  业务模块层
│  Upload │ Dashboard │ Annotate │ Config │ Annotators     │
├─────────────────────────────────────────────────────────┤
│                    Shared Components                     │  共享组件层
│  StatusTag │ MetricCard │ PageThumbnail │ CanvasCore     │
│  ContextMenu │ BatchActionFloater │ OnboardingGuide     │  ← V1.1 新增
├─────────────────────────────────────────────────────────┤
│                    State Management (Zustand + immer)    │  状态层 ← V1.1: immer
│  uploadStore │ jobStore │ annotationStore │ sseStore ... │
│  authStore (persist/localStorage)                        │  ← V1.2 新增
│  settingsStore                                          │  ← V1.1 新增
├─────────────────────────────────────────────────────────┤
│                    API / Service Layer                   │  服务层
│  apiClient │ sseManager │ tusUploader │ authApi           │
│  annotationApi │ opsApi                                  │  ← V1.1 新增
├─────────────────────────────────────────────────────────┤
│                    Infrastructure                        │  基础设施
│  design-tokens │ hooks │ utils │ types │ i18n            │
│  security (DOMPurify + CSP) │ a11y (ARIA)               │  ← V1.1 新增
└─────────────────────────────────────────────────────────┘
```

### 1.2 目录结构

```
src/
├── app/
│   ├── App.tsx                        # 根组件（Layout + Router）
│   ├── router.tsx                     # 路由定义（§2 路由设计）
│   └── providers.tsx                  # 全局 Provider 组合
│
├── pages/                             # 路由页面（thin wrapper）
│   ├── auth/                          # [V1.2] 认证页面
│   │   ├── LoginPage.tsx              #   登录（公共路由）
│   │   └── RegisterPage.tsx           #   注册（公共路由，角色选择 uploader/annotator）
│   ├── admin/                         # [V1.2] 管理页面
│   │   └── UserManagePage.tsx         #   用户 CRUD（仅 admin）
│   ├── upload/
│   │   └── UploadPage.tsx
│   ├── dashboard/
│   │   ├── DashboardPage.tsx
│   │   └── JobDetailPage.tsx
│   ├── annotate/
│   │   ├── AnnotatePage.tsx
│   │   ├── MyStatsPage.tsx
│   │   └── HistoryPage.tsx
│   ├── config/
│   │   ├── ConfigListPage.tsx
│   │   ├── ConfigEditPage.tsx
│   │   └── ImportConfigPage.tsx       # [V1.2] 商品导入配置 (API+字段映射+COS)
│   ├── annotators/
│   │   ├── AnnotatorListPage.tsx
│   │   └── AnnotatorDetailPage.tsx
│   ├── eval/                          # 评测模块页面
│   │   ├── EvalListPage.tsx
│   │   └── EvalDetailPage.tsx
│   ├── merchants/
│   │   └── MerchantJobsPage.tsx
│   ├── ops/                           # [V1.1] 运维页面
│   │   └── CustomAttrUpgradesPage.tsx
│   ├── notifications/
│   │   └── NotificationPage.tsx
│   └── settings/
│       └── SettingsPage.tsx
│
├── features/                          # 业务模块（核心逻辑 + 子组件）
│   ├── upload/
│   │   ├── components/
│   │   │   ├── DropZone.tsx
│   │   │   ├── ConfigSelector.tsx
│   │   │   ├── UploadQueue.tsx
│   │   │   └── RecentUploadsTable.tsx
│   │   ├── hooks/
│   │   │   └── useTusUpload.ts
│   │   └── index.ts
│   │
│   ├── dashboard/
│   │   ├── components/
│   │   │   ├── MetricsRow.tsx
│   │   │   ├── JobTable.tsx
│   │   │   ├── JobRow.tsx
│   │   │   ├── JobStatusTag.tsx        # [V1.1] 双轨状态: internal + user_status
│   │   │   ├── ActionHintBadge.tsx     # [V1.1] action_hint 展示
│   │   │   ├── BatchActionBar.tsx
│   │   │   ├── TimelineDrawer.tsx
│   │   │   ├── RouteTraceCard.tsx
│   │   │   └── PrescanCard.tsx         # [V1.1] 展示 raw_metrics
│   │   ├── job-detail/
│   │   │   ├── PageHeatmap.tsx
│   │   │   ├── SKUList.tsx
│   │   │   ├── PageStatusTable.tsx
│   │   │   └── EvaluationCard.tsx      # [V1.1] 展示 route_reason/sampling/prompt_version
│   │   └── index.ts
│   │
│   ├── annotate/
│   │   ├── canvas-engine/
│   │   │   ├── CoordinateSystem.ts
│   │   │   ├── ViewportManager.ts
│   │   │   ├── CanvasRenderer.ts
│   │   │   ├── LassoGeometry.ts
│   │   │   ├── PerformanceMonitor.ts
│   │   │   └── OffscreenGrid.ts        # [V1.1] 离屏 Canvas 点阵背景 (D5)
│   │   ├── canvas/
│   │   │   ├── CanvasWorkbench.tsx
│   │   │   ├── ElementOverlayContainer.tsx  # [V1.1] 事件委托容器 (D4)
│   │   │   ├── ElementOverlay.tsx
│   │   │   ├── GroupBoundingBox.tsx
│   │   │   ├── LassoSVG.tsx
│   │   │   ├── DragGhost.tsx
│   │   │   └── BatchActionFloater.tsx  # [V1.1] 多选浮层 (A5)
│   │   ├── components/
│   │   │   ├── left-panel/
│   │   │   │   ├── PageGrid.tsx
│   │   │   │   └── PageThumbnail.tsx
│   │   │   ├── right-panel/
│   │   │   │   ├── GroupEditor.tsx
│   │   │   │   ├── SKUAttributeForm.tsx
│   │   │   │   ├── AmbiguousBindingCard.tsx
│   │   │   │   └── CrossPageMergePanel.tsx
│   │   │   ├── SLABar.tsx
│   │   │   ├── SubmitConfirmModal.tsx
│   │   │   └── LockStatusIndicator.tsx  # [V1.1] 展示 locked_by/timeout_at (V2.0)
│   │   ├── hooks/
│   │   │   ├── useKeyboardShortcuts.ts
│   │   │   ├── useHeartbeat.ts
│   │   │   ├── useSLATimer.ts
│   │   │   ├── usePrefetch.ts
│   │   │   ├── useRestReminder.ts      # [V1.1] 60min 休息提醒 (A4)
│   │   │   └── useAutoPickTask.ts      # [V1.1] POST /tasks/next 集成
│   │   └── index.ts
│   │
│   ├── config/
│   │   ├── components/
│   │   │   ├── ProfileList.tsx
│   │   │   ├── ThresholdSlider.tsx
│   │   │   ├── ImpactPreviewPanel.tsx  # [V1.1] impact-preview 集成 (B2)
│   │   │   ├── KeywordManager.tsx
│   │   │   └── AuditLogTable.tsx
│   │   └── index.ts
│   │
│   ├── annotators/
│   │   ├── components/
│   │   │   ├── AnnotatorTable.tsx
│   │   │   ├── AnnotatorDailyChart.tsx
│   │   │   └── MyOutcomeStats.tsx
│   │   └── index.ts
│   │
│   └── eval/                           # [V1.1] 评测模块 (B5)
│       ├── components/
│       │   ├── EvalReportTable.tsx
│       │   ├── EvalDetailView.tsx
│       │   └── EvalRunButton.tsx
│       └── index.ts
│
├── shared/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx
│   │   │   ├── Sidebar.tsx             # [V1.2] 按角色条件渲染导航分区
│   │   │   ├── GlobalBanner.tsx
│   │   │   ├── PageSkeleton.tsx
│   │   │   └── RequireAuth.tsx         # [V1.2] 路由守卫（未登录→/login, 角色不符→重定向）
│   │   ├── ContextMenu.tsx             # [V1.1] 完整实现 (A1)
│   │   ├── OnboardingGuide.tsx         # [V1.1] 完整实现 (A3)
│   │   ├── RestReminderFloat.tsx       # [V1.1] 休息浮窗 (A4)
│   │   ├── StatusTag.tsx
│   │   ├── MetricCard.tsx
│   │   └── ErrorBoundary.tsx
│   │
│   ├── hooks/
│   │   ├── useWebVitals.ts
│   │   ├── useLongTaskMonitor.ts       # [V1.1] 生产环境 longtask (F1)
│   │   ├── usePerformanceTier.ts
│   │   └── useDebouncedCallback.ts     # [V1.1] 通用 debounce hook
│   │
│   ├── design-tokens.ts
│   ├── security.ts                     # [V1.1] DOMPurify 封装 (G1)
│   └── a11y.ts                         # [V1.1] ARIA 辅助函数 (G2)
│
├── services/
│   ├── api/
│   │   ├── client.ts                   # [V1.1] severity→UI 映射; [V1.2] 解构 init 避免 headers 覆盖
│   │   ├── auth.ts                     # [V1.2] login/register/me/changePassword/admin CRUD
│   │   ├── jobs.ts                     # [V1.1] +batch-retry/cancel, created_after/before; [V1.2] +merchantId
│   │   ├── tasks.ts                    # [V1.1] +/tasks/next, batch-skip/reassign
│   │   ├── config.ts                   # [V1.1] +impact-preview
│   │   ├── annotations.ts             # [V1.1] POST /annotations (V2.0)
│   │   ├── eval.ts                     # [V1.1] 评测 API (B5)
│   │   ├── ops.ts                      # [V1.1] custom-attr-upgrades + dashboard events
│   │   └── upload.ts                   # [V1.2] getUploadOffset HEAD 补充 auth headers
│   └── sse/
│       └── SSEManager.ts              # [V1.1] 9 事件 + 动态轮询 (B1, F2)
│
├── stores/
│   ├── uploadStore.ts
│   ├── jobStore.ts                     # [V1.1] user_status/action_hint + selectedIds 清理
│   ├── annotationStore.ts             # [V1.1] immer + 原子 undo
│   ├── undoStore.ts
│   ├── sseStore.ts
│   ├── notificationStore.ts           # [V1.1] 三级优先级 (A2)
│   ├── authStore.ts
│   ├── settingsStore.ts               # [V1.1] 用户偏好 (A6)
│   └── importConfigStore.ts           # [V1.2] 商品导入配置 (persist/localStorage)
│
├── types/
│   ├── models.ts                       # [V1.1] 对齐 OpenAPI V2.0
│   ├── api.ts
│   └── events.ts                       # [V1.1] SSE 9 事件类型
│
├── workers/
│   └── hashWorker.ts                   # [V1.1] 60s 超时保护 (E4)
│
└── sw.ts                               # [V1.1] 版本化缓存 (F3)
```

### 1.3 核心技术选型

| 层面 | 选型 | 版本 | 职责 |
|------|------|------|------|
| 框架 | React | 18.3+ | SPA，hooks 驱动 |
| 语言 | TypeScript | 5.4+ | 全量 strict 模式 |
| 构建 | Vite | 5.x | 开发/构建/HMR |
| UI 库 | Ant Design | 5.x | 表格/表单/弹窗/布局 |
| 状态管理 | Zustand + **immer** | 4.x | 轻量 store + 不可变更新 [V1.1 C1/C2] |
| 路由 | React Router | 6.x | 嵌套路由 + 懒加载 |
| HTTP | Axios | 1.x | 请求拦截/重试/取消 |
| 表单 | React Hook Form | 7.x | SKU 属性编辑 + 配置编辑 |
| 图表 | Recharts | 2.x | 看板趋势图/路由分布图 |
| 虚拟滚动 | react-virtuoso | 4.x | 1000 页缩略图网格 |
| 文件上传 | tus-js-client | 3.x | 断点续传 |
| 拖拽 | @dnd-kit | 6.x | 画布→右栏跨区域拖拽 |
| 引导 | react-joyride | 2.x | 新手 5 步引导 [V1.1 A3] |
| 画布 | Canvas 2D + DOM | 原生 | 截图渲染 + 可交互覆盖层 |
| CSS | CSS Modules + Ant Design Token | — | 组件级样式隔离 |
| 国际化 | react-intl | 预留 | 中文优先 |
| 监控 | web-vitals + **PerformanceObserver** | 3.x | FCP/LCP/FID/CLS + longtask [V1.1 F1] |
| 安全 | **DOMPurify** | 3.x | XSS 防护 [V1.1 G1] |

---

## 2. 路由设计

### 2.1 路由表

```typescript
// src/app/router.tsx
import { createBrowserRouter } from 'react-router-dom';

const router = createBrowserRouter([
  // [V1.2] 公共路由（无需登录）
  { path: '/login', lazy: () => import('@/pages/auth/LoginPage') },
  { path: '/register', lazy: () => import('@/pages/auth/RegisterPage') },

  {
    path: '/',
    element: <RequireAuth><AppLayout /></RequireAuth>,  // [V1.2] 路由守卫包裹
    errorElement: <ErrorBoundary />,
    children: [
      // 首页：角色自适应重定向
      { index: true, element: <HomeRedirect /> },

      // 模块一：上传
      { path: 'upload', lazy: () => import('@/pages/upload/UploadPage') },

      // 模块二：看板
      { path: 'dashboard', lazy: () => import('@/pages/dashboard/DashboardPage') },
      { path: 'dashboard/:jobId', lazy: () => import('@/pages/dashboard/JobDetailPage') },

      // 模块三：标注
      { path: 'annotate', lazy: () => import('@/pages/annotate/AnnotatePage') },
      { path: 'annotate/my-stats', lazy: () => import('@/pages/annotate/MyStatsPage') },
      { path: 'annotate/history', lazy: () => import('@/pages/annotate/HistoryPage') },
      { path: 'annotate/:fileId', lazy: () => import('@/pages/annotate/AnnotatePage') },
      { path: 'annotate/:fileId/:pageNo', lazy: () => import('@/pages/annotate/AnnotatePage') },

      // 商家
      { path: 'merchants/:merchantId/jobs', lazy: () => import('@/pages/merchants/MerchantJobsPage') },

      // 配置
      { path: 'config', lazy: () => import('@/pages/config/ConfigListPage') },
      { path: 'config/import', lazy: () => import('@/pages/config/ImportConfigPage') },  // [V1.2]
      { path: 'config/:profileId', lazy: () => import('@/pages/config/ConfigEditPage') },

      // 标注员
      { path: 'annotators', lazy: () => import('@/pages/annotators/AnnotatorListPage') },
      { path: 'annotators/:id', lazy: () => import('@/pages/annotators/AnnotatorDetailPage') },

      // 评测
      { path: 'eval', lazy: () => import('@/pages/eval/EvalListPage') },
      { path: 'eval/:reportId', lazy: () => import('@/pages/eval/EvalDetailPage') },

      // [V1.1] 运维
      { path: 'ops/custom-attr-upgrades', lazy: () => import('@/pages/ops/CustomAttrUpgradesPage') },

      // [V1.2] 用户管理（仅 admin）
      { path: 'admin/users', lazy: () => import('@/pages/admin/UserManagePage') },

      // 通知
      { path: 'notifications', lazy: () => import('@/pages/notifications/NotificationPage') },

      // 设置
      { path: 'settings', lazy: () => import('@/pages/settings/SettingsPage') },
    ],
  },
]);
```

### 2.2 路由守卫

```typescript
// src/shared/components/layout/AppLayout.tsx
function AppLayout() {
  const { role } = useAuthStore();
  const location = useLocation();

  // 角色权限矩阵（对齐 UI/UX §1.2）[V1.2 修订：operator → uploader]
  const ROLE_ACCESS: Record<string, string[]> = {
    '/upload':      ['uploader', 'admin'],
    '/dashboard':   ['uploader', 'admin'],          // uploader 只读
    '/annotate':    ['annotator', 'admin'],
    '/config':      ['uploader', 'admin'],           // uploader 只查看
    '/annotators':  ['uploader', 'admin'],
    '/eval':        ['uploader', 'admin'],
    '/ops':         ['admin'],                        // [V1.1] 运维页面仅 admin
    '/admin':       ['admin'],                        // [V1.2] 用户管理仅 admin
  };

  useEffect(() => {
    const rule = Object.entries(ROLE_ACCESS)
      .find(([prefix]) => location.pathname.startsWith(prefix));
    if (rule && !rule[1].includes(role)) {
      navigate(role === 'annotator' ? '/annotate' : '/dashboard');
    }
  }, [location, role]);

  return (
    <div className={styles.layout}>
      <Sidebar />
      <GlobalBanner />
      <main className={styles.content}>
        <Suspense fallback={<PageSkeleton />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}
```

### 2.3 代码分割策略

| 分包 | 包含 | 触发加载 | 预估大小 |
|------|------|---------|---------| 
| `vendor` | react + react-dom + antd 核心 | 首屏 | ~180KB gzip |
| `upload-chunk` | tus-js-client + DropZone | /upload 路由 | ~40KB |
| `dashboard-chunk` | recharts + 看板组件 | /dashboard 路由 | ~80KB |
| `annotate-chunk` | dnd-kit + canvas 引擎 + 标注组件 | /annotate 路由 | ~120KB |
| `config-chunk` | 配置编辑器 + 影响预估 | /config 路由 | ~30KB |
| `eval-chunk` | 评测报告组件 | /eval 路由 | ~20KB |
| `security` | DOMPurify | 按需加载 | ~15KB |

---

## 3. 状态管理

### 3.1 Store 架构（Zustand + immer）

> **[V1.1 C1/C2]** 所有 Store 统一使用 `immer` middleware。解决 `Map`/`Set` 在 Zustand 浅比较下不触发重渲染的问题。`prefetchCache` 保持 `Map` 类型、`selectedElementIds` 保持 `Set` 类型，通过 immer 的 proxy 保证变更检测。

```typescript
// src/stores/helpers.ts — 统一 Store 创建工厂
import { create, StateCreator } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { persist, PersistOptions } from 'zustand/middleware';

// 基础 Store（immer 默认启用）
export function createStore<T extends object>(
  initializer: StateCreator<T, [['zustand/immer', never]]>,
) {
  return create<T>()(immer(initializer));
}

// 持久化 Store（immer + persist）
export function createPersistStore<T extends object>(
  initializer: StateCreator<T, [['zustand/immer', never], ['zustand/persist', T]]>,
  options: PersistOptions<T>,
) {
  return create<T>()(immer(persist(initializer, options)));
}
```

```typescript
// src/stores/uploadStore.ts
// 全局上传队列 — 跨路由保持，侧边栏显示进度
interface UploadStore {
  queue: UploadItem[];
  addFile: (file: File, profileId: string) => void;
  updateProgress: (uploadId: string, progress: number) => void;
  setStatus: (uploadId: string, status: UploadStatus) => void;
  removeCompleted: () => void;
}
export const useUploadStore = createPersistStore<UploadStore>(
  (set) => ({
    queue: [],
    addFile: (file, profileId) => set((s) => {
      s.queue.push({ id: crypto.randomUUID(), file, profileId, progress: 0, status: 'uploading' });
    }),
    updateProgress: (uploadId, progress) => set((s) => {
      const item = s.queue.find(i => i.id === uploadId);
      if (item) item.progress = progress;
    }),
    setStatus: (uploadId, status) => set((s) => {
      const item = s.queue.find(i => i.id === uploadId);
      if (item) item.status = status;
    }),
    removeCompleted: () => set((s) => {
      s.queue = s.queue.filter(i => i.status !== 'completed');
    }),
  }),
  { name: 'pdf-sku-uploads', partialize: (s) => ({ queue: s.queue }) as any }
);
```

```typescript
// src/stores/jobStore.ts
// Job 列表 + 筛选 + 双轨状态（V2.0）
interface JobStore {
  jobs: Job[];
  filters: JobFilters;
  selectedIds: string[];          // [V1.1 C2] Set → string[] 避免浅比较问题
  pagination: PaginationMeta;
  setFilter: (f: Partial<JobFilters>) => void;
  toggleSelect: (id: string) => void;
  selectAll: () => void;
  clearSelection: () => void;
  fetchJobs: () => Promise<void>;
  // SSE 回调
  updatePageStatus: (pageNo: number, status: string) => void;
  updateJobStatus: (jobId: string, status: string) => void;
  updateFromPoll: (data: JobDetail) => void;
}

export const useJobStore = createStore<JobStore>((set, get) => ({
  jobs: [],
  filters: {},
  selectedIds: [],
  pagination: { page: 1, size: 20, total: 0, total_pages: 0 },
  setFilter: (f) => set((s) => { Object.assign(s.filters, f); }),
  toggleSelect: (id) => set((s) => {
    const idx = s.selectedIds.indexOf(id);
    if (idx >= 0) s.selectedIds.splice(idx, 1);
    else s.selectedIds.push(id);
  }),
  selectAll: () => set((s) => {
    s.selectedIds = s.jobs.map(j => j.job_id);
  }),
  clearSelection: () => set((s) => { s.selectedIds = []; }),

  fetchJobs: async () => {
    const { filters, pagination } = get();
    const { data } = await jobApi.list({
      ...filters,
      page: pagination.page,
      size: pagination.size,
    });
    set((s) => {
      s.jobs = data.items;
      s.pagination = data.meta;
      // [V1.1 C4] SSE 后自动清理：仅保留当前列表中存在的 selectedIds
      const currentIds = new Set(data.items.map((j: Job) => j.job_id));
      s.selectedIds = s.selectedIds.filter(id => currentIds.has(id));
    });
  },
  updatePageStatus: (pageNo, status) => { /* SSE handler */ },
  updateJobStatus: (jobId, status) => set((s) => {
    const job = s.jobs.find(j => j.job_id === jobId);
    if (job) job.status = status as any;
  }),
  updateFromPoll: (data) => set((s) => {
    const idx = s.jobs.findIndex(j => j.job_id === data.job_id);
    if (idx >= 0) s.jobs[idx] = { ...s.jobs[idx], ...data };
  }),
}));
```

```typescript
// src/stores/annotationStore.ts
// 当前标注页面状态 — 最复杂的 Store
// [V1.1 C1] 使用 immer，Map/Set 变更可被正确追踪
// [V1.1 C3] 每个状态变更方法内部同时推送 undoStore，确保原子性

interface AnnotationStore {
  // 当前上下文
  currentTaskId: string | null;
  currentJobId: string | null;
  currentPageNo: number | null;

  // 元素与分组
  elements: AnnotationElement[];
  groups: AnnotationGroup[];
  selectedElementIds: string[];      // [V1.1 C2] Set → string[]
  selectedGroupId: string | null;
  activeToolMode: 'select' | 'lasso';

  // 页面属性
  pageType: PageType | null;
  layoutType: LayoutType | null;
  pageTypeModified: boolean;
  layoutTypeModified: boolean;

  // 跨页 SKU
  crossPageSKUs: CrossPageSKU[];

  // 歧义绑定
  ambiguousBindings: AmbiguousBinding[];

  // 预加载缓存
  prefetchCache: Map<string, PrefetchData>;   // immer 可追踪 Map 变更

  // [V1.1 A4] 休息提醒
  sessionStartAt: number;

  // 操作方法 — 每个方法内部同时推送 undoStore [V1.1 C3]
  loadTask: (taskId: string) => Promise<void>;
  createGroup: (elementIds: string[]) => void;
  deleteGroup: (groupId: string) => void;
  moveElementToGroup: (elementId: string, groupId: string) => void;
  removeElementFromGroup: (elementId: string) => void;
  updateSKUAttribute: (groupId: string, field: string, value: string) => void;
  setPageType: (type: PageType) => void;
  setLayoutType: (type: LayoutType) => void;
  resolveBinding: (elementId: string, selectedUri: string | null) => void;
  buildSubmitPayload: () => TaskCompletePayload;
  // [V1.1] 新增
  autoPickNext: () => Promise<TaskDetail | null>;
  submitAnnotation: (type: AnnotationType, payload: object) => Promise<void>;
  selectAllUngrouped: () => void;
  openSubmitConfirm: () => void;
  nextPage: () => void;
  prevPage: () => void;
  skipPage: () => void;
  deleteSelectedGroup: () => void;
  cancelCurrentAction: () => void;
  toggleShortcutHelp: () => void;
  setTool: (mode: 'select' | 'lasso') => void;
  refreshFileList: () => void;
  updateThumbnail: (pageNo: number, status: string) => void;
  updateSLA: (taskId: string, slaLevel: string) => void;
  reset: () => void;
}

export const useAnnotationStore = createStore<AnnotationStore>((set, get) => ({
  currentTaskId: null,
  currentJobId: null,
  currentPageNo: null,
  elements: [],
  groups: [],
  selectedElementIds: [],         // [V1.1 C2]
  selectedGroupId: null,
  activeToolMode: 'select',
  pageType: null,
  layoutType: null,
  pageTypeModified: false,
  layoutTypeModified: false,
  crossPageSKUs: [],
  ambiguousBindings: [],
  prefetchCache: new Map(),
  sessionStartAt: Date.now(),

  loadTask: async (taskId) => {
    const { data } = await taskApi.getTask(taskId);
    set((s) => {
      s.currentTaskId = data.task_id;
      s.currentJobId = data.job_id;
      s.currentPageNo = data.page_number;
      s.elements = data.elements ?? [];
      s.ambiguousBindings = data.ambiguous_bindings ?? [];
      s.pageType = data.context?.page_type ?? null;
      s.layoutType = data.context?.layout_type ?? null;
      s.groups = [];
      s.selectedElementIds = [];
      s.selectedGroupId = null;
      s.pageTypeModified = false;
      s.layoutTypeModified = false;
    });
    useUndoStore.getState().clear();
  },

  // [V1.1 C3] 原子性：状态变更 + undo push 在同一个 immer 回合
  createGroup: (elementIds) => {
    const prevGroups = structuredClone(get().groups);
    const prevSelected = [...get().selectedElementIds];

    set((s) => {
      const groupId = `g-${Date.now()}`;
      s.groups.push({
        id: groupId,
        label: `分组 ${s.groups.length + 1}`,
        skuType: 'complete',
        elementIds: [...elementIds],
        skuAttributes: {},
        customAttributes: [],
        crossPageSkuId: null,
      });
      s.selectedElementIds = [];
      s.selectedGroupId = groupId;
    });

    // 原子推送 undo
    // [V1.2 修正] forward 不得调用 get().createGroup()（会导致重复 push undo）
    const snapshotGroups = structuredClone(get().groups);
    const snapshotSelected = [...get().selectedElementIds];
    const snapshotGroupId = get().selectedGroupId;
    useUndoStore.getState().push({
      type: 'CREATE_GROUP',
      description: `创建分组（${elementIds.length} 个元素）`,
      forward: () => set((s) => {
        s.groups = snapshotGroups;
        s.selectedElementIds = snapshotSelected;
        s.selectedGroupId = snapshotGroupId;
      }),
      backward: () => set((s) => {
        s.groups = prevGroups;
        s.selectedElementIds = prevSelected;
      }),
    });
  },

  deleteGroup: (groupId) => {
    const prevGroups = structuredClone(get().groups);
    set((s) => {
      s.groups = s.groups.filter(g => g.id !== groupId);
      if (s.selectedGroupId === groupId) s.selectedGroupId = null;
    });
    // [V1.2 修正] forward 直接 set 状态，不重新调用 deleteGroup
    const afterGroups = structuredClone(get().groups);
    useUndoStore.getState().push({
      type: 'DELETE_GROUP',
      description: '删除分组',
      forward: () => set((s) => { s.groups = afterGroups; }),
      backward: () => set((s) => { s.groups = prevGroups; }),
    });
  },

  moveElementToGroup: (elementId, groupId) => {
    const prevGroups = structuredClone(get().groups);
    set((s) => {
      // 从旧组移除
      for (const g of s.groups) {
        g.elementIds = g.elementIds.filter(id => id !== elementId);
      }
      // 加入新组
      const target = s.groups.find(g => g.id === groupId);
      if (target) target.elementIds.push(elementId);
    });
    // [V1.2 修正] forward 直接 set 状态
    const afterGroups = structuredClone(get().groups);
    useUndoStore.getState().push({
      type: 'MOVE_ELEMENT',
      description: '移动元素到分组',
      forward: () => set((s) => { s.groups = afterGroups; }),
      backward: () => set((s) => { s.groups = prevGroups; }),
    });
  },

  removeElementFromGroup: (elementId) => {
    const prevGroups = structuredClone(get().groups);
    set((s) => {
      for (const g of s.groups) {
        g.elementIds = g.elementIds.filter(id => id !== elementId);
      }
    });
    // [V1.2 修正] forward 直接 set 状态
    const afterGroupsRemove = structuredClone(get().groups);
    useUndoStore.getState().push({
      type: 'MOVE_ELEMENT',
      description: '从分组移除元素',
      forward: () => set((s) => { s.groups = afterGroupsRemove; }),
      backward: () => set((s) => { s.groups = prevGroups; }),
    });
  },

  updateSKUAttribute: (groupId, field, value) => {
    const group = get().groups.find(g => g.id === groupId);
    const prevValue = group?.skuAttributes[field] ?? '';
    set((s) => {
      const g = s.groups.find(g => g.id === groupId);
      if (g) g.skuAttributes[field] = value;
    });
    // [V1.2 修正] forward 直接 set 状态
    useUndoStore.getState().push({
      type: 'MODIFY_ATTRIBUTE',
      description: `修改 ${field}`,
      forward: () => set((s) => {
        const g = s.groups.find(g => g.id === groupId);
        if (g) g.skuAttributes[field] = value;
      }),
      backward: () => set((s) => {
        const g = s.groups.find(g => g.id === groupId);
        if (g) g.skuAttributes[field] = prevValue;
      }),
    });
  },

  setPageType: (type) => {
    const prev = get().pageType;
    set((s) => { s.pageType = type; s.pageTypeModified = true; });
    // [V1.2 修正] forward 直接 set 状态
    useUndoStore.getState().push({
      type: 'CHANGE_PAGE_TYPE',
      description: `页面类型 ${prev} → ${type}`,
      forward: () => set((s) => { s.pageType = type; s.pageTypeModified = true; }),
      backward: () => set((s) => { s.pageType = prev; }),
    });
  },

  setLayoutType: (type) => {
    const prev = get().layoutType;
    set((s) => { s.layoutType = type; s.layoutTypeModified = true; });
    // [V1.2 修正] forward 直接 set 状态
    useUndoStore.getState().push({
      type: 'CHANGE_LAYOUT_TYPE',
      description: `布局类型 ${prev} → ${type}`,
      forward: () => set((s) => { s.layoutType = type; s.layoutTypeModified = true; }),
      backward: () => set((s) => { s.layoutType = prev; }),
    });
  },

  resolveBinding: (elementId, selectedUri) => set((s) => {
    const binding = s.ambiguousBindings.find(b => b.elementId === elementId);
    if (binding) {
      binding.resolved = true;
      binding.selectedUri = selectedUri;
    }
  }),

  // [V1.1] POST /tasks/next 自动领取
  autoPickNext: async () => {
    try {
      const { data, status } = await taskApi.next();
      if (status === 204) return null;
      await get().loadTask(data.task_id);
      return data;
    } catch (e: any) {
      if (e.response?.status === 409) {
        // 并发冲突，重试一次
        const { data, status } = await taskApi.next();
        if (status === 204) return null;
        await get().loadTask(data.task_id);
        return data;
      }
      throw e;
    }
  },

  // [V1.1] POST /annotations 独立标注记录
  submitAnnotation: async (type, payload) => {
    const { currentJobId, currentPageNo, currentTaskId } = get();
    if (!currentJobId || currentPageNo == null) return;
    await annotationApi.create({
      job_id: currentJobId,
      page_number: currentPageNo,
      task_id: currentTaskId,
      type,
      payload,
    });
  },

  buildSubmitPayload: () => {
    const s = get();
    return {
      task_id: s.currentTaskId!,
      page_type: s.pageType!,
      layout_type: s.layoutType!,
      groups: s.groups.map(g => ({
        group_id: g.id,
        label: g.label,
        sku_type: g.skuType,
        elements: s.elements.filter(el => g.elementIds.includes(el.id)),
        sku_attributes: g.skuAttributes,
        custom_attributes: g.customAttributes,
        partial_contains: g.partialContains ?? [],
        cross_page_sku_id: g.crossPageSkuId,
        invalid_reason: g.invalidReason ?? null,
      })),
      ungrouped_elements: s.elements
        .filter(el => !s.groups.some(g => g.elementIds.includes(el.id)))
        .map(el => el.id),
      binding_confirmations: s.ambiguousBindings
        .filter(b => b.resolved)
        .map(b => ({
          element_id: b.elementId,
          selected_rank: b.candidates.find(c => c.imageUri === b.selectedUri)?.rank ?? 0,
        })),
      feedback: {
        page_type_modified: s.pageTypeModified,
        layout_type_modified: s.layoutTypeModified,
        new_image_role_observed: false,
        new_text_role_observed: false,
        notes: '',
      },
    };
  },

  selectAllUngrouped: () => set((s) => {
    const grouped = new Set(s.groups.flatMap(g => g.elementIds));
    s.selectedElementIds = s.elements.filter(el => !grouped.has(el.id)).map(el => el.id);
  }),
  openSubmitConfirm: () => { /* trigger modal */ },
  nextPage: () => { /* navigate to next page */ },
  prevPage: () => { /* navigate to previous page */ },
  skipPage: () => { /* call taskApi.skip */ },
  deleteSelectedGroup: () => {
    const gid = get().selectedGroupId;
    if (gid) get().deleteGroup(gid);
  },
  cancelCurrentAction: () => set((s) => {
    s.selectedElementIds = [];
    s.activeToolMode = 'select';
  }),
  toggleShortcutHelp: () => { /* toggle help overlay */ },
  setTool: (mode) => set((s) => { s.activeToolMode = mode; }),
  refreshFileList: () => { /* re-fetch task list */ },
  updateThumbnail: () => {},
  updateSLA: () => {},
  reset: () => set((s) => {
    s.currentTaskId = null; s.currentJobId = null; s.currentPageNo = null;
    s.elements = []; s.groups = []; s.selectedElementIds = [];
    s.selectedGroupId = null; s.ambiguousBindings = [];
    s.pageType = null; s.layoutType = null;
    s.pageTypeModified = false; s.layoutTypeModified = false;
  }),
}));
```

```typescript
// src/stores/undoStore.ts
// 操作栈 — 页面级，切换页面时清空
interface UndoAction {
  type: 'CREATE_GROUP' | 'DELETE_GROUP' | 'MOVE_ELEMENT' | 'MODIFY_ATTRIBUTE'
       | 'CHANGE_PAGE_TYPE' | 'CHANGE_LAYOUT_TYPE' | 'CHANGE_SKU_TYPE'
       | 'MERGE_GROUPS' | 'DRAG_TO_GROUP';
  forward: () => void;
  backward: () => void;
  description: string;
}

interface UndoStore {
  undoStack: UndoAction[];    // max 30
  redoStack: UndoAction[];    // max 30
  push: (action: UndoAction) => void;
  undo: () => void;
  redo: () => void;
  clear: () => void;
  canUndo: boolean;
  canRedo: boolean;
}

export const useUndoStore = createStore<UndoStore>((set, get) => ({
  undoStack: [],
  redoStack: [],
  canUndo: false,
  canRedo: false,
  push: (action) => set((s) => {
    s.undoStack.push(action);
    if (s.undoStack.length > 30) s.undoStack.shift();
    s.redoStack = [];
    s.canUndo = true;
    s.canRedo = false;
  }),
  undo: () => {
    const { undoStack } = get();
    if (undoStack.length === 0) return;
    const action = undoStack[undoStack.length - 1];
    action.backward();
    set((s) => {
      const a = s.undoStack.pop()!;
      s.redoStack.push(a);
      s.canUndo = s.undoStack.length > 0;
      s.canRedo = true;
    });
  },
  redo: () => {
    const { redoStack } = get();
    if (redoStack.length === 0) return;
    const action = redoStack[redoStack.length - 1];
    action.forward();
    set((s) => {
      const a = s.redoStack.pop()!;
      s.undoStack.push(a);
      s.canRedo = s.redoStack.length > 0;
      s.canUndo = true;
    });
  },
  clear: () => set((s) => {
    s.undoStack = []; s.redoStack = [];
    s.canUndo = false; s.canRedo = false;
  }),
}));
```

```typescript
// src/stores/sseStore.ts
interface SSEStore {
  status: 'connected' | 'reconnecting' | 'disconnected' | 'polling';
  retryCount: number;
  lastHeartbeat: number | null;         // [V1.1] heartbeat 时间戳
  connect: (jobId: string) => void;
  disconnect: () => void;
  setStatus: (s: SSEStore['status']) => void;
}
```

```typescript
// src/stores/notificationStore.ts
// [V1.1 A2] 三级优先级 → UI 行为映射
interface NotificationItem {
  id: string;
  level: 'urgent' | 'warning' | 'info';    // [V1.1 A2]
  message: string;
  timestamp: number;
  read: boolean;
  // 可选：关联资源
  jobId?: string;
  taskId?: string;
}

/**
 * 通知级别 → UI 行为映射（对齐 UI/UX §12）：
 * - urgent (🔴): 持久 banner + 声音提示 + 不自动消失
 * - warning (🟡): toast 5s 自动消失
 * - info (🔵): toast 3s 自动消失
 */

interface NotificationStore {
  items: NotificationItem[];     // max 100
  unreadCount: number;
  urgentCount: number;
  add: (item: Omit<NotificationItem, 'id' | 'timestamp' | 'read'>) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
}

export const useNotificationStore = createPersistStore<NotificationStore>(
  (set) => ({
    items: [],
    unreadCount: 0,
    urgentCount: 0,
    add: (item) => set((s) => {
      const newItem: NotificationItem = {
        ...item,
        id: crypto.randomUUID(),
        timestamp: Date.now(),
        read: false,
      };
      s.items.unshift(newItem);
      if (s.items.length > 100) s.items.pop();
      s.unreadCount++;
      if (item.level === 'urgent') s.urgentCount++;

      // [V1.1 A2] UI 行为触发（副作用在 React 层通过 subscription 实现）
      // urgent → GlobalBanner.show() + playAlertSound()
      // warning → antd message.warning(item.message, 5)
      // info → antd message.info(item.message, 3)
    }),
    markRead: (id) => set((s) => {
      const item = s.items.find(i => i.id === id);
      if (item && !item.read) {
        item.read = true;
        s.unreadCount--;
        if (item.level === 'urgent') s.urgentCount--;
      }
    }),
    markAllRead: () => set((s) => {
      s.items.forEach(i => { i.read = true; });
      s.unreadCount = 0;
      s.urgentCount = 0;
    }),
  }),
  { name: 'pdf-sku-notifications' }
);
```

```typescript
// src/stores/authStore.ts
// [V1.2] 完整认证状态 — JWT + 用户信息，persist 到 localStorage
interface User {
  user_id: string;
  username: string;
  display_name: string | null;
  role: 'admin' | 'uploader' | 'annotator';   // [V1.2] operator → uploader
  is_active: boolean;
  merchant_id: string | null;
  specialties: string[] | null;
}

interface AuthStore {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;

  // 认证方法
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  updateUser: (patch: Partial<User>) => void;
}

export const useAuthStore = createPersistStore<AuthStore>(
  (set) => ({
    token: null,
    user: null,
    isAuthenticated: false,
    setAuth: (token, user) => set((s) => {
      s.token = token;
      s.user = user;
      s.isAuthenticated = true;
    }),
    logout: () => set((s) => {
      s.token = null;
      s.user = null;
      s.isAuthenticated = false;
    }),
    updateUser: (patch) => set((s) => {
      if (s.user) Object.assign(s.user, patch);
    }),
  }),
  { name: 'pdf-sku-auth' }
);
```

```typescript
// src/stores/settingsStore.ts
// [V1.1 A6] 用户偏好持久化
interface SettingsStore {
  skipSubmitConfirm: boolean;          // [V1.1 A6] 跳过提交确认弹窗
  enableRestReminder: boolean;         // [V1.1 A4] 休息提醒开关
  restReminderMinutes: number;         // 默认 60
  enableSound: boolean;                // 通知声音
  annotationOnboarded: boolean;        // [V1.1 A3] 新手引导完成
  preferredPageSize: number;           // 默认 20
}

export const useSettingsStore = createPersistStore<SettingsStore>(
  (set) => ({
    skipSubmitConfirm: false,
    enableRestReminder: true,
    restReminderMinutes: 60,
    enableSound: true,
    annotationOnboarded: false,
    preferredPageSize: 20,
  }),
  { name: 'pdf-sku-settings' }
);
```

### 3.2 Store 交互流

```
用户提交标注
    │
    ▼
annotationStore.buildSubmitPayload()
    │
    ▼
taskApi.completeTask(taskId, payload)
    │                                    │
    ▼ (success)                          ▼ (failure)
undoStore.clear()                   ┌─ severity === 'error' ?
annotationStore.reset()             │   → notificationStore.add(urgent)
                                    │   → 保留当前状态，用户可重试
                                    └─ severity === 'warning' ?
                                        → toast 提示 + 自动重试
    │ (success 继续)
    ▼
settingsStore.skipSubmitConfirm ?
    ├─ true  → 直接提交
    └─ false → SubmitConfirmModal
    │
    ▼
prefetchCache → 加载下一页
sseStore 推送 page_completed
    │
    ▼
jobStore 更新进度（如果看板打开）
notificationStore.add({ level: 'info', message: "已提取 N 个 SKU" })
```

---

## 4. 标注画布（Canvas）技术方案

### 4.1 渲染架构

采用 **Canvas 底层 + DOM 覆盖层** 混合架构：

```
┌─────────────────────────────────────────────────────────┐
│  DOM 覆盖层 (position: absolute, pointer-events)         │  ← 可交互元素
│  ├── ElementOverlayContainer (事件委托) [V1.1 D4]       │
│  │   └── ElementOverlay[] (bbox 框 + 标签)              │
│  ├── GroupBoundingBox[] (分组边框)                       │
│  ├── LassoSVG (套索路径)                                 │
│  ├── DragGhost (拖拽幽灵)                                │
│  ├── BatchActionFloater (多选浮层) [V1.1 A5]            │
│  └── ContextMenu (右键菜单) [V1.1 A1]                   │
├─────────────────────────────────────────────────────────┤
│  Canvas 2D (z-index: 0)                                 │  ← 页面截图
│  └── 渲染截图 image + 离屏点阵背景 [V1.1 D5]           │
└─────────────────────────────────────────────────────────┘
```

**选择理由**：截图用 Canvas 保证大图渲染性能；元素覆盖层用 DOM 保证可交互性（hover/click/drag/右键菜单/ARIA）。

### 4.2 坐标系统

```typescript
// src/features/annotate/canvas-engine/CoordinateSystem.ts

export class CoordinateSystem {
  // 页面截图原始尺寸
  private imageWidth: number;
  private imageHeight: number;

  // 视口状态
  zoom: number = 1.0;       // 30% ~ 300%
  panX: number = 0;
  panY: number = 0;

  // 容器尺寸 + 偏移（[V1.1 D2] 用于套索坐标统一）
  containerWidth: number;
  containerHeight: number;
  private containerRect: DOMRect | null = null;  // [V1.1 D2]

  // [V1.1 D2] 更新容器位置（ResizeObserver 回调时调用）
  updateContainerRect(rect: DOMRect) {
    this.containerWidth = rect.width;
    this.containerHeight = rect.height;
    this.containerRect = rect;
  }

  // 归一化坐标（0.0~1.0）→ 屏幕像素（相对于容器）
  normalizedToScreen(nx: number, ny: number): [number, number] {
    const renderedW = this.imageWidth * this.fitScale * this.zoom;
    const renderedH = this.imageHeight * this.fitScale * this.zoom;
    const offsetX = (this.containerWidth - renderedW) / 2 + this.panX;
    const offsetY = (this.containerHeight - renderedH) / 2 + this.panY;
    return [
      nx * renderedW + offsetX,
      ny * renderedH + offsetY,
    ];
  }

  // 屏幕像素 → 归一化坐标
  screenToNormalized(sx: number, sy: number): [number, number] {
    const renderedW = this.imageWidth * this.fitScale * this.zoom;
    const renderedH = this.imageHeight * this.fitScale * this.zoom;
    const offsetX = (this.containerWidth - renderedW) / 2 + this.panX;
    const offsetY = (this.containerHeight - renderedH) / 2 + this.panY;
    return [
      (sx - offsetX) / renderedW,
      (sy - offsetY) / renderedH,
    ];
  }

  // [V1.1 D2] 全局鼠标事件坐标 → 容器相对坐标
  clientToContainer(clientX: number, clientY: number): [number, number] {
    if (!this.containerRect) return [clientX, clientY];
    return [
      clientX - this.containerRect.left,
      clientY - this.containerRect.top,
    ];
  }

  get renderedWidth(): number {
    return this.imageWidth * this.fitScale * this.zoom;
  }
  get renderedHeight(): number {
    return this.imageHeight * this.fitScale * this.zoom;
  }

  private get fitScale(): number {
    return Math.min(
      this.containerWidth / this.imageWidth,
      this.containerHeight / this.imageHeight
    );
  }
}
```

### 4.3 视口管理（缩放 + 平移）

```typescript
// src/features/annotate/canvas-engine/ViewportManager.ts

export class ViewportManager {
  private coords: CoordinateSystem;
  private MIN_ZOOM = 0.3;
  private MAX_ZOOM = 3.0;

  // 滚轮缩放：基于鼠标位置
  handleWheel(e: WheelEvent) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = clamp(this.coords.zoom * delta, this.MIN_ZOOM, this.MAX_ZOOM);

    // 以鼠标位置为中心缩放
    const [mx, my] = [e.offsetX, e.offsetY];
    const ratio = newZoom / this.coords.zoom;
    this.coords.panX = mx - (mx - this.coords.panX) * ratio;
    this.coords.panY = my - (my - this.coords.panY) * ratio;
    this.coords.zoom = newZoom;
    this.requestRender();
  }

  // Alt+拖拽 或 鼠标中键 平移
  handlePan(dx: number, dy: number) {
    this.coords.panX += dx;
    this.coords.panY += dy;
    this.requestRender();
  }

  // 适配窗口（Ctrl+Shift+0）
  fitToContainer() {
    this.coords.zoom = 1.0;
    this.coords.panX = 0;
    this.coords.panY = 0;
    this.requestRender();
  }

  get offsetX() { return (this.coords.containerWidth - this.coords.renderedWidth) / 2 + this.coords.panX; }
  get offsetY() { return (this.coords.containerHeight - this.coords.renderedHeight) / 2 + this.coords.panY; }
  get effectiveScale() { return this.coords.renderedWidth / (this.coords as any).imageWidth; }

  private requestRender = throttle(() => {
    requestAnimationFrame(() => this.renderAll());
  }, 16); // 60fps cap

  private renderAll() { /* 调用 CanvasRenderer.render() */ }
}
```

### 4.4 Canvas 渲染引擎

```typescript
// src/features/annotate/canvas-engine/CanvasRenderer.ts

export class CanvasRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private dpr: number;
  private image: HTMLImageElement | null = null;
  private resizeObserver: ResizeObserver;        // [V1.1 D1]
  private gridPattern: CanvasPattern | null = null; // [V1.1 D5]

  constructor(canvas: HTMLCanvasElement, private coords: CoordinateSystem) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d')!;
    this.dpr = window.devicePixelRatio || 1;
    this.setupRetina();

    // [V1.1 D1] ResizeObserver 监听容器尺寸变化
    this.resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        this.setupRetina();
        this.coords.updateContainerRect(entry.target.getBoundingClientRect());
        this.render();
      }
    });
    this.resizeObserver.observe(this.canvas.parentElement!);

    // [V1.1 D5] 离屏 Canvas 生成点阵背景 pattern
    this.gridPattern = this.createGridPattern();
  }

  // Retina 高清适配
  private setupRetina() {
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width * this.dpr;
    this.canvas.height = rect.height * this.dpr;
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
    this.ctx.scale(this.dpr, this.dpr);
  }

  // [V1.1 D5] 离屏 Canvas 生成静态点阵 pattern，不再每帧重绘
  private createGridPattern(): CanvasPattern | null {
    const offscreen = document.createElement('canvas');
    offscreen.width = 20;
    offscreen.height = 20;
    const offCtx = offscreen.getContext('2d')!;
    offCtx.fillStyle = 'rgba(255, 255, 255, 0.03)';
    offCtx.fillRect(0, 0, 1, 1);
    return this.ctx.createPattern(offscreen, 'repeat');
  }

  // 加载页面截图
  async loadImage(url: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => { this.image = img; resolve(); };
      img.onerror = reject;
      img.src = url;
    });
  }

  // 渲染帧
  render(viewport?: ViewportManager) {
    const { ctx } = this;
    const w = this.canvas.width / this.dpr;
    const h = this.canvas.height / this.dpr;

    ctx.clearRect(0, 0, w, h);

    // 1. [V1.1 D5] 点阵背景使用 pattern 填充（一次 fillRect 替代 N×M 个 fillRect）
    if (this.gridPattern) {
      ctx.fillStyle = this.gridPattern;
      ctx.fillRect(0, 0, w, h);
    }

    // 2. 页面截图
    if (this.image && viewport) {
      ctx.save();
      ctx.translate(viewport.offsetX, viewport.offsetY);
      ctx.scale(viewport.effectiveScale, viewport.effectiveScale);
      ctx.drawImage(this.image, 0, 0, this.image.width, this.image.height);
      ctx.restore();
    }
  }

  // [V1.1 D1] 清理
  destroy() {
    this.resizeObserver.disconnect();
  }
}
```

### 4.5 ElementOverlay（DOM 覆盖层）

> **[V1.1 D3]** 所有 ElementOverlay 改用 `transform: translate3d()` 替代 `left/top`，利用 GPU 合成层避免 layout reflow。  
> **[V1.1 D4]** 事件委托：在容器级别绑定一次事件，通过 `data-element-id` 查找目标元素。

```typescript
// src/features/annotate/canvas/ElementOverlayContainer.tsx
// [V1.1 D4] 事件委托容器

interface ElementOverlayContainerProps {
  elements: AnnotationElement[];
  coords: CoordinateSystem;
  groups: AnnotationGroup[];
  selectedElementIds: string[];
  onSelect: (id: string, multi: boolean) => void;
  onDragStart: (id: string) => void;
  onContextMenu: (id: string, x: number, y: number) => void;
}

const ElementOverlayContainer: React.FC<ElementOverlayContainerProps> = ({
  elements, coords, groups, selectedElementIds, onSelect, onDragStart, onContextMenu,
}) => {
  const dragTimerRef = useRef<number>();

  // [V1.1 D4] 容器级事件委托 — 1 个 listener 替代 N×3 个
  const findElementId = (e: React.MouseEvent | React.PointerEvent): string | null => {
    const target = (e.target as HTMLElement).closest('[data-element-id]');
    return target?.getAttribute('data-element-id') ?? null;
  };

  const handleClick = (e: React.MouseEvent) => {
    const id = findElementId(e);
    if (id) onSelect(id, e.ctrlKey || e.metaKey);
  };

  const handlePointerDown = (e: React.PointerEvent) => {
    const id = findElementId(e);
    if (!id) return;
    dragTimerRef.current = window.setTimeout(() => onDragStart(id), 200);
  };

  const handlePointerUp = () => {
    clearTimeout(dragTimerRef.current);
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    const id = findElementId(e);
    if (id) onContextMenu(id, e.clientX, e.clientY);
  };

  // 性能降级（§7.5）：>100 元素时简化样式
  const perfTier = usePerformanceTier();
  const simplified = perfTier === 'low' || elements.length > 100;

  // 为每个元素查找所属分组色
  const groupColorMap = useMemo(() => {
    const map = new Map<string, string>();
    groups.forEach((g, i) => {
      g.elementIds.forEach(eid => map.set(eid, GROUP_COLORS[i % GROUP_COLORS.length]));
    });
    return map;
  }, [groups]);

  return (
    <div
      className={styles.overlayContainer}
      onClick={handleClick}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onContextMenu={handleContextMenu}
    >
      {elements.map(el => (
        <ElementOverlay
          key={el.id}
          element={el}
          coords={coords}
          isSelected={selectedElementIds.includes(el.id)}
          groupColor={groupColorMap.get(el.id) ?? null}
          simplified={simplified}
        />
      ))}
    </div>
  );
};
```

```typescript
// src/features/annotate/canvas/ElementOverlay.tsx
// [V1.1 D3] 使用 transform: translate3d 替代 left/top

interface ElementOverlayProps {
  element: AnnotationElement;
  coords: CoordinateSystem;
  isSelected: boolean;
  groupColor: string | null;
  simplified: boolean;
}

const ElementOverlay: React.FC<ElementOverlayProps> = React.memo(({
  element, coords, isSelected, groupColor, simplified,
}) => {
  const [screenX, screenY] = coords.normalizedToScreen(element.bbox.x, element.bbox.y);
  const screenW = element.bbox.w * coords.renderedWidth;
  const screenH = element.bbox.h * coords.renderedHeight;

  return (
    <div
      className={classNames(styles.overlay, {
        [styles.selected]: isSelected,
        [styles.simplified]: simplified,
      })}
      // [V1.1 D3] GPU 合成层，避免 layout reflow
      style={{
        transform: `translate3d(${screenX}px, ${screenY}px, 0)`,
        width: screenW,
        height: screenH,
        borderColor: groupColor ?? 'var(--color-info)',
        position: 'absolute',
        left: 0,
        top: 0,
        willChange: 'transform',
      }}
      data-element-id={element.id}   // [V1.1 D4] 事件委托标识
      role={element.type === 'image' ? 'img' : 'article'}
      aria-label={`${element.type === 'image' ? '图片' : '文本'}元素 ${element.id}，
        AI 识别：${element.aiRole}，置信度 ${Math.round(element.confidence * 100)}%`}
    >
      <span className={styles.tag}>
        {element.type === 'image' ? 'IMG' : 'TXT'}
      </span>
      {!simplified && (
        <span className={styles.confidence}>
          {Math.round(element.confidence * 100)}%
        </span>
      )}
    </div>
  );
});
```

### 4.6 套索工具

```typescript
// src/features/annotate/canvas-engine/LassoGeometry.ts

export class LassoGeometry {
  private points: [number, number][] = [];
  private coords: CoordinateSystem;

  constructor(coords: CoordinateSystem) {
    this.coords = coords;
  }

  // [V1.1 D2] addPoint 统一使用容器相对坐标
  addPoint(clientX: number, clientY: number) {
    const [cx, cy] = this.coords.clientToContainer(clientX, clientY);
    this.points.push([cx, cy]);
  }

  getSVGPath(): string {
    if (this.points.length < 2) return '';
    return this.points.map((p, i) =>
      `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`
    ).join(' ') + ' Z';
  }

  containsPoint(px: number, py: number): boolean {
    let inside = false;
    const pts = this.points;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      const [xi, yi] = pts[i];
      const [xj, yj] = pts[j];
      if (((yi > py) !== (yj > py)) &&
          (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) {
        inside = !inside;
      }
    }
    return inside;
  }

  // [V1.1 D2] 捕获元素：统一坐标系（归一化→容器相对坐标 vs 套索容器相对坐标）
  captureElements(elements: AnnotationElement[]): string[] {
    return elements
      .filter(el => {
        const cx = el.bbox.x + el.bbox.w / 2;
        const cy = el.bbox.y + el.bbox.h / 2;
        // 元素中心归一化→容器相对坐标
        const [sx, sy] = this.coords.normalizedToScreen(cx, cy);
        // 套索路径也是容器相对坐标（addPoint 已统一）
        return this.containsPoint(sx, sy);
      })
      .map(el => el.id);
  }

  reset() { this.points = []; }
}
```

### 4.7 性能降级策略

```typescript
// src/features/annotate/canvas-engine/PerformanceMonitor.ts

export class PerformanceMonitor {
  private fpsBuffer: number[] = [];
  private lastFrame = 0;
  private degradeLevel: 'none' | 'mild' | 'heavy' = 'none';

  tick(timestamp: number) {
    if (this.lastFrame) {
      const fps = 1000 / (timestamp - this.lastFrame);
      this.fpsBuffer.push(fps);
      if (this.fpsBuffer.length > 300) this.fpsBuffer.shift(); // 5s window

      if (this.fpsBuffer.length >= 300) {
        const avg = this.fpsBuffer.reduce((a, b) => a + b) / this.fpsBuffer.length;
        if (avg < 30) this.degradeLevel = 'heavy';
        else if (avg < 45) this.degradeLevel = 'mild';
        else this.degradeLevel = 'none';
      }
    }
    this.lastFrame = timestamp;
  }

  get level() { return this.degradeLevel; }
}
```

---

## 5. API 集成层

### 5.1 Axios 客户端

> **[V1.1 E2]** 拦截器区分「全局处理的错误」和「需业务层处理的错误」。全局错误（401/429/500）处理后标记 `handled: true`，不再需要每个调用方重复 catch。业务错误（409 锁冲突/乐观锁）透传给调用方。  
> **[V1.1 V2.0]** ErrorResponse.severity 映射到 toast/modal/banner。

```typescript
// src/services/api/client.ts

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截：JWT
apiClient.interceptors.request.use((config) => {
  const { token } = useAuthStore.getState();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// [V1.1 E2] 响应拦截：分层错误处理 + severity 映射
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    const { status, data } = error.response ?? {};
    const notification = useNotificationStore.getState();

    // [V1.1 V2.0] 根据 ErrorResponse.severity 决定 UI 行为
    const severity: string = data?.severity ?? 'error';

    // ---- 全局处理的错误 ----
    switch (status) {
      case 401:
        window.location.href = '/login';
        error._handled = true;
        return Promise.reject(error);

      case 429:
        notification.add({ level: 'warning', message: '操作过于频繁，请稍后重试' });
        error._handled = true;
        return Promise.reject(error);

      case 503:
        // LLM_BUDGET_EXHAUSTED / LLM_CIRCUIT_OPEN / SERVICE_UNAVAILABLE
        notification.add({
          level: severity === 'critical' ? 'urgent' : 'warning',
          message: data?.message ?? '服务暂不可用',
        });
        error._handled = true;
        return Promise.reject(error);
    }

    if (status >= 500) {
      notification.add({ level: 'urgent', message: data?.message ?? '系统异常，请稍后重试' });
      error._handled = true;
      return Promise.reject(error);
    }

    // ---- 业务错误 → 透传给调用方 ----
    // 409（锁冲突/乐观锁）、400（校验失败）等
    return Promise.reject(error);
  }
);

/**
 * 调用方使用示例（业务错误）：
 *
 * try {
 *   await taskApi.lock(taskId);
 * } catch (e: any) {
 *   if (e._handled) return;  // 全局已处理
 *   if (e.response?.status === 409) {
 *     // 锁冲突 → 业务处理
 *     showLockedByModal(e.response.data.locked_by);
 *   }
 * }
 */
```

### 5.2 API 模块封装

> **[V1.1 V2.0]** 对齐 OpenAPI V2.0 的 12 个 Tag 分组。新增 `annotations.ts`、`eval.ts`、`ops.ts`。

```typescript
// src/services/api/jobs.ts

export const jobApi = {
  // 列表（[V1.1 V2.0] +created_after/created_before）
  list: (params: {
    status?: string; merchant_id?: string;
    created_after?: string; created_before?: string;   // [V1.1 V2.0]
    sort?: string; page?: number; size?: number;
  }) => apiClient.get<{ items: Job[]; meta: PaginationMeta }>('/jobs', { params }),

  // 创建
  create: (body: { upload_id: string; profile_id: string; merchant_id?: string; category?: string }) =>
    apiClient.post<Job & { frozen_config_version: string }>('/jobs', body),

  // 详情
  get: (jobId: string) => apiClient.get<JobDetail>(`/jobs/${jobId}`),

  // 页面列表
  getPages: (jobId: string) => apiClient.get<{ pages: PageInfo[] }>(`/jobs/${jobId}/pages`),

  // SKU 列表
  getSKUs: (jobId: string) => apiClient.get<{ skus: SKU[] }>(`/jobs/${jobId}/skus`),

  // 最终结果
  getResult: (jobId: string) => apiClient.get<object>(`/jobs/${jobId}/result`),

  // 进度
  getProgress: (jobId: string) => apiClient.get<ProgressResponse>(`/jobs/${jobId}/progress`),

  // 评估报告
  getEvaluation: (jobId: string) => apiClient.get<Evaluation>(`/jobs/${jobId}/evaluation`),

  // 取消
  cancel: (jobId: string) => apiClient.post(`/jobs/${jobId}/cancel`),

  // 重提（孤儿恢复）
  requeue: (jobId: string) => apiClient.post<Job>(`/jobs/${jobId}/requeue`),

  // [V1.1] 强制同步
  sync: (jobId: string) =>
    apiClient.post<{ synced_skus: number; confirmed: number; failed: number }>(`/jobs/${jobId}/sync`),

  // 跨页 SKU（[V1.1 B4]）
  getCrossPageSKUs: (jobId: string) =>
    apiClient.get<{ cross_page_skus: CrossPageSKU[] }>(`/jobs/${jobId}/cross-page-skus`),

  linkCrossPageSKU: (jobId: string, xskuId: string, body: { source_task_id: string; source_group_id: string }) =>
    apiClient.post(`/jobs/${jobId}/cross-page-skus/${xskuId}/link`, body),

  // 截图
  getScreenshot: (jobId: string, pageNo: number, w?: number) =>
    `${apiClient.defaults.baseURL}/jobs/${jobId}/pages/${pageNo}/screenshot${w ? `?w=${w}` : ''}`,

  // [V1.1 B3] 批量操作
  batchRetry: (jobIds: string[]) =>
    apiClient.post<{ success_count: number; failed_items: { job_id: string; reason: string; code: string }[] }>(
      '/ops/jobs/batch-retry', { job_ids: jobIds }),

  batchCancel: (jobIds: string[]) =>
    apiClient.post<{ success_count: number }>('/ops/jobs/batch-cancel', { job_ids: jobIds }),
};
```

```typescript
// src/services/api/tasks.ts

export const taskApi = {
  // 文件维度任务列表
  listByFile: () =>
    apiClient.get<{ files: TaskFileGroup[] }>('/tasks', { params: { group_by: 'file' } }),

  // [V1.1 V2.0] 自动领取下一个任务
  next: () =>
    apiClient.post<TaskDetail>('/tasks/next').then(res => res).catch(e => {
      if (e.response?.status === 204) return { data: null, status: 204 };
      throw e;
    }),

  // 任务详情
  getTask: (taskId: string) => apiClient.get<TaskDetail>(`/tasks/${taskId}`),

  // 领取（加锁）
  lock: (taskId: string) => apiClient.post(`/tasks/${taskId}/lock`),

  // 心跳续期
  heartbeat: (taskId: string) => apiClient.post(`/tasks/${taskId}/heartbeat`),

  // 释放锁
  release: (taskId: string) => apiClient.post(`/tasks/${taskId}/release`),

  // 提交标注（元素-分组模型）
  complete: (taskId: string, payload: TaskCompletePayload) =>
    apiClient.post<{ extracted_sku_count: number; imported_count: number }>(
      `/tasks/${taskId}/complete`, payload),

  // 跳过
  skip: (taskId: string) => apiClient.post(`/tasks/${taskId}/skip`),

  // AI 重处理
  retry: (taskId: string) => apiClient.post(`/tasks/${taskId}/retry`),

  // 撤销（组长权限）
  revert: (taskId: string, reason: string) =>
    apiClient.post(`/tasks/${taskId}/revert`, { reason }),

  // SKU 属性补全推荐
  suggest: (merchantId: string, field: string, prefix: string) =>
    apiClient.get<string[]>('/annotations/suggest', {
      params: { merchant_id: merchantId, field, prefix },
    }),

  // [V1.1 B3] 批量重分配
  batchReassign: (taskIds: string[], targetAnnotatorId: string) =>
    apiClient.post('/ops/tasks/batch-reassign', { task_ids: taskIds, target_annotator_id: targetAnnotatorId }),

  // [V1.1 V2.0] 批量跳过
  batchSkip: (taskIds: string[], reason?: string) =>
    apiClient.post<{ success_count: number; failed_count: number }>(
      '/ops/tasks/batch-skip', { task_ids: taskIds, reason }),
};
```

```typescript
// src/services/api/config.ts

export const configApi = {
  listProfiles: () => apiClient.get<ThresholdProfile[]>('/config/profiles'),

  getProfile: (profileId: string) =>
    apiClient.get<ThresholdProfile & { expected_version: string }>(`/config/profiles/${profileId}`),

  updateProfile: (profileId: string, body: ThresholdProfile & { expected_version: string }) =>
    apiClient.put(`/config/profiles/${profileId}`, body),

  // [V1.1 B2] 阈值影响预估
  getImpactPreview: (profileId: string, params: {
    threshold_a?: number; threshold_b?: number; threshold_pv?: number;
  }) => apiClient.get<ImpactPreviewResult>(`/config/profiles/${profileId}/impact-preview`, { params }),

  reload: () => apiClient.post('/config/reload'),

  getKeywords: () => apiClient.get<Record<string, string[]>>('/config/keywords'),

  updateKeywords: (category: string, keywords: string[]) =>
    apiClient.put(`/config/keywords/${category}`, { keywords }),

  getAuditLog: (params?: { page?: number; size?: number }) =>
    apiClient.get<{ items: AuditLogEntry[]; meta: PaginationMeta }>('/ops/config/audit-log', { params }),

  rollback: (profileId: string) => apiClient.post(`/ops/config/rollback/${profileId}`),
};
```

```typescript
// src/services/api/annotations.ts — [V1.1 V2.0] 独立标注端点

export const annotationApi = {
  // 提交标注记录（8 种 type，独立于 task complete）
  create: (body: CreateAnnotationRequest) =>
    apiClient.post<{ annotation_id: string }>('/annotations', body),
};
```

```typescript
// src/services/api/eval.ts — [V1.1 B5] 评测 API

export const evalApi = {
  listReports: () => apiClient.get<EvalReportSummary[]>('/ops/eval/reports'),

  getReport: (reportId: number) => apiClient.get<EvalReport>(`/ops/eval/reports/${reportId}`),

  run: (body: { golden_set_id: string; config_version: string }) =>
    apiClient.post('/ops/eval/run', body),
};
```

```typescript
// src/services/api/ops.ts — [V1.1 V2.0] 运维 API

export const opsApi = {
  // Dashboard
  getDashboard: () => apiClient.get<DashboardMetrics>('/ops/dashboard'),

  // 标注员
  listAnnotators: () => apiClient.get<AnnotatorSummary[]>('/ops/annotators'),
  getAnnotatorStats: (annotatorId: string) =>
    apiClient.get<AnnotatorDetail>(`/ops/annotators/${annotatorId}/stats`),
  getMyOutcomeStats: () => apiClient.get('/annotators/me/outcome-stats'),

  // 商家统计
  getMerchantStats: (merchantId: string) =>
    apiClient.get(`/merchants/${merchantId}/stats`),

  // [V1.1 V2.0] 自定义属性升级
  listCustomAttrUpgrades: (params?: { status?: string; merchant_id?: string; page?: number; size?: number }) =>
    apiClient.get('/ops/custom-attr-upgrades', { params }),

  reviewCustomAttrUpgrade: (body: { upgrade_id: string; action: 'approve' | 'reject'; comment?: string }) =>
    apiClient.post('/ops/custom-attr-upgrades', body),

  // SKU 对账
  reconcileSKU: (skuId: string) => apiClient.post(`/skus/${skuId}/reconcile`),
};
```

```typescript
// src/services/api/upload.ts

export const uploadApi = {
  // tus 上传由 tus-js-client 直接处理
  // 此处仅封装删除（[V1.1 E1] 上传后 Job 创建失败时回滚）
  deleteUpload: (uploadId: string) => apiClient.delete(`/uploads/${uploadId}`),
};
```

### 5.3 SSE 实时推送

> **[V1.1 B1]** 9 种事件完整处理（+heartbeat/pages_batch_update/job_failed/sla_auto_resolve/sla_auto_accepted）  
> **[V1.1 F2]** 降级轮询动态间隔：PROCESSING 5s / 其他 30s

```typescript
// src/services/sse/SSEManager.ts

export class SSEManager {
  private source: EventSource | null = null;
  private retryCount = 0;
  private maxRetry = 3;
  private pollFallbackTimer: number | null = null;
  private store = useSseStore.getState;

  connect(jobId: string) {
    this.disconnect();
    const url = `${API_BASE}/jobs/${jobId}/events`;
    this.source = new EventSource(url);

    this.source.onopen = () => {
      this.retryCount = 0;
      this.store().setStatus('connected');
    };

    // ========== 9 种事件 ==========

    // [V1.1] heartbeat（每 30s 服务端主动发送）
    this.source.addEventListener('heartbeat', (e) => {
      useSseStore.setState({ lastHeartbeat: Date.now() });
    });

    // page_completed
    this.source.addEventListener('page_completed', (e) => {
      const data: SSEPageCompleted = JSON.parse(e.data);
      useJobStore.getState().updatePageStatus(data.page_no, data.status);
      useAnnotationStore.getState().updateThumbnail(data.page_no, data.status);
    });

    // [V1.1] pages_batch_update（≤50 页/事件）
    this.source.addEventListener('pages_batch_update', (e) => {
      const data: { pages: { page_no: number; status: string }[] } = JSON.parse(e.data);
      const jobStore = useJobStore.getState();
      data.pages.forEach(p => jobStore.updatePageStatus(p.page_no, p.status));
    });

    // job_completed
    this.source.addEventListener('job_completed', (e) => {
      const data: SSEJobCompleted = JSON.parse(e.data);
      useJobStore.getState().updateJobStatus(data.job_id, data.status);
      useNotificationStore.getState().add({
        level: 'info',
        message: `Job 处理完成，共 ${data.total_skus} 个 SKU`,
        jobId: data.job_id,
      });
    });

    // [V1.1 B1] job_failed
    this.source.addEventListener('job_failed', (e) => {
      const data: SSEJobFailed = JSON.parse(e.data);
      useJobStore.getState().updateJobStatus(data.job_id, 'EVAL_FAILED');
      useNotificationStore.getState().add({
        level: 'urgent',
        message: `Job 处理失败：${data.error_message}`,
        jobId: data.job_id,
      });
    });

    // human_needed
    this.source.addEventListener('human_needed', (e) => {
      const data: SSEHumanNeeded = JSON.parse(e.data);
      useNotificationStore.getState().add({
        level: 'warning',
        message: `${data.task_count} 个任务需要人工标注`,
        jobId: data.job_id,
      });
      useAnnotationStore.getState().refreshFileList();
    });

    // sla_escalated
    this.source.addEventListener('sla_escalated', (e) => {
      const data: SSESlaEscalated = JSON.parse(e.data);
      useAnnotationStore.getState().updateSLA(data.task_id, data.sla_level);
      if (data.sla_level === 'CRITICAL') {
        useNotificationStore.getState().add({
          level: 'urgent',
          message: '任务 SLA 已升级至紧急',
          taskId: data.task_id,
        });
      }
    });

    // [V1.1 B1] sla_auto_resolve
    this.source.addEventListener('sla_auto_resolve', (e) => {
      const data: SSESlaEscalated = JSON.parse(e.data);
      useAnnotationStore.getState().updateSLA(data.task_id, 'AUTO_RESOLVE');
      useNotificationStore.getState().add({
        level: 'warning', message: '任务已进入 AI 质检处置流程',
      });
    });

    // [V1.1 B1] sla_auto_accepted
    this.source.addEventListener('sla_auto_accepted', (e) => {
      const data: SSESlaEscalated = JSON.parse(e.data);
      useAnnotationStore.getState().updateSLA(data.task_id, 'AUTO_RESOLVE');
      useNotificationStore.getState().add({
        level: 'info', message: '任务 SLA 超时，已自动接受 AI 结果',
      });
    });

    // 断线重连
    this.source.onerror = () => {
      this.store().setStatus('reconnecting');
      this.retryCount++;
      if (this.retryCount > this.maxRetry) {
        this.degradeToPoll(jobId);
      }
    };
  }

  // [V1.1 F2] 降级轮询 — 动态间隔
  private degradeToPoll(jobId: string) {
    this.disconnect();
    this.store().setStatus('polling');

    const poll = async () => {
      try {
        const { data } = await jobApi.get(jobId);
        useJobStore.getState().updateFromPoll(data);

        // [V1.1 F2] 根据 Job 状态动态调整间隔
        const isProcessing = ['UPLOADED', 'EVALUATING', 'EVALUATED', 'PROCESSING']
          .includes(data.status);
        const interval = isProcessing ? 5000 : 30000;

        this.pollFallbackTimer = window.setTimeout(poll, interval);
      } catch {
        this.pollFallbackTimer = window.setTimeout(poll, 30000);
      }
    };
    poll();
  }

  disconnect() {
    this.source?.close();
    this.source = null;
    if (this.pollFallbackTimer) {
      clearTimeout(this.pollFallbackTimer);
      this.pollFallbackTimer = null;
    }
  }
}
```

### 5.4 心跳机制

> **[V1.1 E3]** 连续心跳失败降级提示：≥2 次 warning toast，≥4 次 error banner。

```typescript
// src/features/annotate/hooks/useHeartbeat.ts

export function useHeartbeat(taskId: string | null) {
  const intervalRef = useRef<number>();
  const failCountRef = useRef(0);                // [V1.1 E3]

  useEffect(() => {
    if (!taskId) return;

    const sendHeartbeat = async () => {
      try {
        await taskApi.heartbeat(taskId);
        failCountRef.current = 0;                // 成功则重置
      } catch {
        failCountRef.current++;

        // [V1.1 E3] 降级提示
        if (failCountRef.current >= 4) {
          useNotificationStore.getState().add({
            level: 'urgent',
            message: '连接已断开，标注锁即将过期，请检查网络',
          });
        } else if (failCountRef.current >= 2) {
          useNotificationStore.getState().add({
            level: 'warning',
            message: '网络不稳定，标注锁可能过期',
          });
        }
      }
    };

    // 立即发一次
    sendHeartbeat();
    intervalRef.current = window.setInterval(sendHeartbeat, 30000);

    // Tab 切回时立即补发
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') sendHeartbeat();
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      clearInterval(intervalRef.current);
      document.removeEventListener('visibilitychange', handleVisibility);
      taskApi.release(taskId).catch(() => {});
    };
  }, [taskId]);
}
```

### 5.5 tus 断点续传

> **[V1.1 E1]** Job 创建失败时调用 DELETE /uploads/{id} 清理孤儿文件。  
> **[V1.1 E4]** Web Worker hashWorker 60s 超时保护。

```typescript
// src/features/upload/hooks/useTusUpload.ts
import * as tus from 'tus-js-client';

export function useTusUpload() {
  const { addFile, updateProgress, setStatus } = useUploadStore();

  const upload = useCallback((file: File, profileId: string) => {
    const uploadId = crypto.randomUUID();
    addFile({ id: uploadId, file, profileId, progress: 0, status: 'hashing' });

    // Web Worker 计算 SHA256（[V1.1 E4] 60s 超时保护）
    const hashWorker = new Worker(new URL('@/workers/hashWorker.ts', import.meta.url));
    let hashTimeout: number;

    const onHashComplete = (fileHash: string) => {
      clearTimeout(hashTimeout);
      setStatus(uploadId, 'uploading');

      const tusUpload = new tus.Upload(file, {
        endpoint: `${API_BASE}/uploads`,
        retryDelays: [0, 1000, 3000, 5000],
        chunkSize: 5 * 1024 * 1024,       // 5MB 分片
        parallelUploads: 3,
        metadata: {
          filename: file.name,
          filetype: file.type,
          filehash: fileHash,
          profile_id: profileId,
        },
        onProgress: (bytesUploaded, bytesTotal) => {
          updateProgress(uploadId, bytesUploaded / bytesTotal);
        },
        onSuccess: async () => {
          const tusUploadId = tusUpload.url!.split('/').pop()!;
          try {
            await jobApi.create({
              upload_id: tusUploadId,
              profile_id: profileId,
            });
            setStatus(uploadId, 'completed');
          } catch (e: any) {
            // [V1.1 E1] Job 创建失败 → 回滚：删除已上传文件
            await uploadApi.deleteUpload(tusUploadId).catch(() => {});
            setStatus(uploadId, 'error');

            if (e.response?.status === 409) {
              useNotificationStore.getState().add({
                level: 'warning', message: '文件已上传过（hash 重复）',
              });
            } else if (!e._handled) {
              useNotificationStore.getState().add({
                level: 'urgent', message: `Job 创建失败：${e.response?.data?.message ?? '未知错误'}`,
              });
            }
          }
        },
        onError: (error) => {
          setStatus(uploadId, 'error');
          useNotificationStore.getState().add({
            level: 'urgent', message: `上传失败：${error.message}`,
          });
        },
      });

      tusUpload.start();
    };

    hashWorker.onmessage = (e) => {
      hashWorker.terminate();
      onHashComplete(e.data);
    };

    // [V1.1 E4] 60s 超时 → 使用 fallback hash（文件名+大小）
    hashTimeout = window.setTimeout(() => {
      hashWorker.terminate();
      const fallbackHash = `fallback-${file.name}-${file.size}-${Date.now()}`;
      console.warn('Hash worker timeout, using fallback hash');
      onHashComplete(fallbackHash);
    }, 60000);

    hashWorker.postMessage(file);
  }, []);

  return { upload };
}
```

---

## 6. 组件拆分与交互规格

### 6.1 页面热力图（Canvas）

```typescript
// src/features/dashboard/components/job-detail/PageHeatmap.tsx
// 1000 页热力图使用 Canvas 渲染，非 DOM
// 每格 12×16px，根据 page_confidence + status 映色
// hover 时显示 tooltip（Canvas hitTest → DOM tooltip）

interface PageHeatmapProps {
  pages: PageStatus[];    // {page_no, status, confidence}
  onPageClick: (pageNo: number) => void;
}

const STATUS_COLOR_MAP: Record<string, string> = {
  AI_COMPLETED: '#52C41A',
  HUMAN_COMPLETED: '#52C41A',
  IMPORTED_CONFIRMED: '#1890FF',
  HUMAN_QUEUED: '#FAAD14',
  HUMAN_PROCESSING: '#FAAD14',
  AI_FAILED: '#FF4D4F',
  IMPORT_FAILED: '#FF4D4F',
  DEAD_LETTER: '#FF4D4F',
  BLANK: '#434343',
  PENDING: '#262626',
};
```

### 6.2 页面预加载

```typescript
// src/features/annotate/hooks/usePrefetch.ts

export function usePrefetch(currentTaskId: string | null, adjacentTasks: string[]) {
  const store = useAnnotationStore();

  useEffect(() => {
    if (!currentTaskId || adjacentTasks.length === 0) return;

    // 当前页加载完成后 2s → 预加载下一页截图
    const timer1 = setTimeout(async () => {
      const nextTaskId = adjacentTasks[0];
      if (store.prefetchCache.has(nextTaskId)) return;

      const [taskRes, screenshotBlob] = await Promise.all([
        taskApi.getTask(nextTaskId),
        fetch(jobApi.getScreenshot(store.currentJobId!, 0, 0)).then(r => r.blob()),
      ]);

      // immer 可直接操作 Map
      useAnnotationStore.setState((s) => {
        s.prefetchCache.set(nextTaskId, {
          screenshot: screenshotBlob,
          elements: taskRes.data.elements,
          lockStatus: null,
          fetchedAt: Date.now(),
        });
      });
    }, 2000);

    return () => clearTimeout(timer1);
  }, [currentTaskId]);

  // 缓存清理：保留前后各 2 页
  useEffect(() => {
    const keep = new Set(adjacentTasks.slice(0, 2));
    useAnnotationStore.setState((s) => {
      for (const key of s.prefetchCache.keys()) {
        if (!keep.has(key) && key !== currentTaskId) {
          s.prefetchCache.delete(key);
        }
      }
    });
  }, [currentTaskId]);
}
```

### 6.3 键盘快捷键

```typescript
// src/features/annotate/hooks/useKeyboardShortcuts.ts

export function useKeyboardShortcuts() {
  const annotation = useAnnotationStore();
  const undo = useUndoStore();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const inInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(
        (e.target as HTMLElement).tagName
      );

      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case 'z': e.shiftKey ? undo.redo() : undo.undo(); e.preventDefault(); break;
          case 'Z': undo.redo(); e.preventDefault(); break;
          case 'Enter': annotation.openSubmitConfirm(); e.preventDefault(); break;
          case 'a': if (!inInput) { annotation.selectAllUngrouped(); e.preventDefault(); } break;
        }
        return;
      }

      if (inInput) return;

      switch (e.key) {
        case 'v': case 'V': annotation.setTool('select'); break;
        case 'l': case 'L': annotation.setTool('lasso'); break;
        case 'g': case 'G': annotation.createGroup(annotation.selectedElementIds); break;
        case 'ArrowRight': case 'n': case 'N': annotation.nextPage(); break;
        case 'ArrowLeft': case 'p': case 'P': annotation.prevPage(); break;
        case 's': case 'S': annotation.skipPage(); break;
        case 'Delete': case 'Backspace': annotation.deleteSelectedGroup(); break;
        case 'Escape': annotation.cancelCurrentAction(); break;
        case '?': annotation.toggleShortcutHelp(); break;
        case '1': annotation.setPageType('A'); break;
        case '2': annotation.setPageType('B'); break;
        case '3': annotation.setPageType('C'); break;
        case '4': annotation.setPageType('D'); break;
      }
      if (e.shiftKey && ['1','2','3','4'].includes(e.key)) {
        annotation.setLayoutType(`L${e.key}` as LayoutType);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}
```

### 6.4 SLA 倒计时

```typescript
// src/features/annotate/hooks/useSLATimer.ts

export function useSLATimer(deadline: string | null, slaLevel: SLALevel) {
  const [remaining, setRemaining] = useState<string>('');
  const [urgency, setUrgency] = useState<'normal' | 'warning' | 'critical'>('normal');

  useEffect(() => {
    if (!deadline) return;
    const deadlineMs = new Date(deadline).getTime();

    let rafId: number;
    const tick = () => {
      const diff = deadlineMs - Date.now();
      if (diff <= 0) {
        setRemaining('00:00');
        setUrgency('critical');
        return;
      }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining(h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`);

      setUrgency(
        slaLevel === 'CRITICAL' || slaLevel === 'AUTO_RESOLVE' ? 'critical' :
        slaLevel === 'HIGH' ? 'warning' : 'normal'
      );

      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [deadline, slaLevel]);

  return { remaining, urgency };
}
```

### 6.5 上下文菜单 + 批量操作浮层

> **[V1.1 A1]** 右键上下文菜单完整规格（对齐 UI/UX §3.6）  
> **[V1.1 A5]** 多选批量操作浮层

```typescript
// src/shared/components/ContextMenu.tsx

interface ContextMenuProps {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}

interface ContextMenuItem {
  label: string;
  icon?: React.ReactNode;
  shortcut?: string;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

const ContextMenu: React.FC<ContextMenuProps> = ({ x, y, items, onClose }) => {
  const ref = useRef<HTMLDivElement>(null);

  // Viewport boundary clamp：菜单不超出视口
  const [pos, setPos] = useState({ x, y });
  useLayoutEffect(() => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const clampedX = Math.min(x, window.innerWidth - rect.width - 8);
    const clampedY = Math.min(y, window.innerHeight - rect.height - 8);
    setPos({ x: Math.max(8, clampedX), y: Math.max(8, clampedY) });
  }, [x, y]);

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = () => onClose();
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [onClose]);

  return (
    <div ref={ref} className={styles.contextMenu} style={{ left: pos.x, top: pos.y }}>
      {items.map((item, i) => (
        <button
          key={i}
          className={classNames(styles.menuItem, { [styles.danger]: item.danger })}
          disabled={item.disabled}
          onClick={() => { item.onClick(); onClose(); }}
        >
          {item.icon && <span className={styles.icon}>{item.icon}</span>}
          <span className={styles.label}>{item.label}</span>
          {item.shortcut && <span className={styles.shortcut}>{item.shortcut}</span>}
        </button>
      ))}
    </div>
  );
};

/**
 * 三种上下文菜单配置（对齐 UI/UX §3.6）：
 *
 * 1. 画布元素右键（6 项）：
 *    - 归入选中分组 (G) / 创建新分组 (Ctrl+G) / 标记角色→
 *    - 查看 AI 识别详情 / 缩放到元素 / 从分组移除
 *
 * 2. 分组卡片右键（5 项）：
 *    - 重命名分组 / 删除分组 (Del) / 标记 SKU 类型→
 *    - 拆分分组 / 设为跨页 SKU
 *
 * 3. Job 行右键（4 项）：
 *    - 查看详情 / 重新处理 / 取消 / 批量操作→
 */
```

```typescript
// src/features/annotate/canvas/BatchActionFloater.tsx
// [V1.1 A5] 多选后的批量操作浮层（对齐 UI/UX §6.3）

interface BatchActionFloaterProps {
  selectedCount: number;
  onCreateGroup: () => void;
  onAddToGroup: (groupId: string) => void;
  onSetRole: (role: string) => void;
  groups: AnnotationGroup[];
}

const BatchActionFloater: React.FC<BatchActionFloaterProps> = ({
  selectedCount, onCreateGroup, onAddToGroup, onSetRole, groups,
}) => {
  if (selectedCount <= 1) return null;

  return (
    <div className={styles.floater} role="toolbar" aria-label="批量操作">
      <span className={styles.count}>{selectedCount} 个元素已选中</span>
      <Button size="small" onClick={onCreateGroup}>创建新组 (G)</Button>
      <Dropdown menu={{
        items: groups.map(g => ({
          key: g.id, label: `归入「${g.label}」`, onClick: () => onAddToGroup(g.id),
        })),
      }}>
        <Button size="small">归入分组 →</Button>
      </Dropdown>
      <Dropdown menu={{
        items: ['PRODUCT_MAIN', 'DETAIL', 'SCENE', 'LOGO', 'DECORATION', 'SIZE_CHART']
          .map(r => ({ key: r, label: r, onClick: () => onSetRole(r) })),
      }}>
        <Button size="small">标记角色 →</Button>
      </Dropdown>
    </div>
  );
};
```

### 6.6 新手引导

> **[V1.1 A3]** react-joyride 5 步引导（对齐 UI/UX §6.9）

```typescript
// src/shared/components/OnboardingGuide.tsx
import Joyride, { Step, STATUS } from 'react-joyride';

const ONBOARDING_STEPS: Step[] = [
  {
    target: '[data-tour="page-grid"]',
    title: '1. 选择页面',
    content: '左侧面板展示 PDF 所有页面缩略图，点击选择要标注的页面。',
    placement: 'right',
  },
  {
    target: '[data-tour="canvas-workbench"]',
    title: '2. 查看 AI 识别结果',
    content: '中间画布展示页面截图和 AI 预识别的文本/图片元素。蓝色框 = 文本，绿色框 = 图片。',
    placement: 'bottom',
  },
  {
    target: '[data-tour="lasso-tool"]',
    title: '3. 使用套索工具',
    content: '按 L 键切换到套索模式，画圈选中属于同一个 SKU 的元素，然后按 G 创建分组。',
    placement: 'bottom',
  },
  {
    target: '[data-tour="group-editor"]',
    title: '4. 填写 SKU 属性',
    content: '右侧面板编辑每个分组的 SKU 属性（型号、名称、颜色、尺码等）。',
    placement: 'left',
  },
  {
    target: '[data-tour="submit-btn"]',
    title: '5. 提交标注',
    content: '确认无误后按 Ctrl+Enter 提交，系统会自动跳转到下一页。',
    placement: 'top',
  },
];

const OnboardingGuide: React.FC = () => {
  const { annotationOnboarded } = useSettingsStore();

  if (annotationOnboarded) return null;

  const handleComplete = (data: { status: string }) => {
    if ([STATUS.FINISHED, STATUS.SKIPPED].includes(data.status as any)) {
      useSettingsStore.setState((s) => { s.annotationOnboarded = true; });
    }
  };

  return (
    <Joyride
      steps={ONBOARDING_STEPS}
      continuous
      showSkipButton
      showProgress
      callback={handleComplete}
      styles={{
        options: {
          primaryColor: '#22D3EE',
          backgroundColor: '#1A1F2C',
          textColor: '#E2E8F4',
          zIndex: 10000,
        },
      }}
    />
  );
};
```

### 6.7 休息提醒

> **[V1.1 A4]** 连续标注 60 分钟后柔性提醒（对齐 UI/UX 附录 E §E.2）

```typescript
// src/features/annotate/hooks/useRestReminder.ts

export function useRestReminder() {
  const { enableRestReminder, restReminderMinutes } = useSettingsStore();
  const { sessionStartAt } = useAnnotationStore();
  const [showReminder, setShowReminder] = useState(false);

  useEffect(() => {
    if (!enableRestReminder) return;

    const checkInterval = setInterval(() => {
      const elapsed = (Date.now() - sessionStartAt) / 60000;
      if (elapsed >= restReminderMinutes) {
        setShowReminder(true);
      }
    }, 60000); // 每分钟检查

    return () => clearInterval(checkInterval);
  }, [enableRestReminder, restReminderMinutes, sessionStartAt]);

  const dismiss = () => {
    setShowReminder(false);
    // 重置计时器
    useAnnotationStore.setState((s) => { s.sessionStartAt = Date.now(); });
  };

  return { showReminder, dismiss };
}
```

```typescript
// src/shared/components/RestReminderFloat.tsx

const RestReminderFloat: React.FC<{ onDismiss: () => void }> = ({ onDismiss }) => (
  <div className={styles.restFloat} role="alert" aria-live="polite">
    <span>☕ 你已连续标注超过 1 小时，建议休息 5 分钟</span>
    <Button size="small" type="text" onClick={onDismiss}>知道了</Button>
  </div>
);
```

### 6.8 ImpactPreview 集成

> **[V1.1 B2]** 配置阈值滑块 onChange debounce 500ms 调用 impact-preview

```typescript
// src/features/config/components/ImpactPreviewPanel.tsx

interface ImpactPreviewPanelProps {
  profileId: string;
  thresholdA: number;
  thresholdB: number;
  thresholdPV: number;
}

const ImpactPreviewPanel: React.FC<ImpactPreviewPanelProps> = ({
  profileId, thresholdA, thresholdB, thresholdPV,
}) => {
  const [preview, setPreview] = useState<ImpactPreviewResult | null>(null);
  const [loading, setLoading] = useState(false);

  // [V1.1 B2] debounce 500ms
  const fetchPreview = useDebouncedCallback(async () => {
    setLoading(true);
    try {
      const { data } = await configApi.getImpactPreview(profileId, {
        threshold_a: thresholdA,
        threshold_b: thresholdB,
        threshold_pv: thresholdPV,
      });
      setPreview(data);
    } finally {
      setLoading(false);
    }
  }, 500);

  useEffect(() => { fetchPreview(); }, [thresholdA, thresholdB, thresholdPV]);

  if (!preview) return <Skeleton active />;

  return (
    <Card title="影响预估" loading={loading}>
      <Descriptions column={2}>
        <Descriptions.Item label="样本周期">{preview.sample_period_days} 天</Descriptions.Item>
        <Descriptions.Item label="样本 Job 数">{preview.sample_job_count}</Descriptions.Item>
        <Descriptions.Item label="当前自动化率">{(preview.current_auto_rate * 100).toFixed(1)}%</Descriptions.Item>
        <Descriptions.Item label="预测自动化率">{(preview.predicted_auto_rate * 100).toFixed(1)}%</Descriptions.Item>
        <Descriptions.Item label="当前日均人工任务">{preview.current_human_daily}</Descriptions.Item>
        <Descriptions.Item label="预测日均人工任务">{preview.predicted_human_daily}</Descriptions.Item>
      </Descriptions>
      {preview.capacity_warning && (
        <Alert type="warning" message="⚠️ 预测人工任务量可能超出当前标注员产能" />
      )}
    </Card>
  );
};
```

---

## 7. 性能优化与打包策略

### 7.1 Vite 构建配置

```typescript
// vite.config.ts
import { defineConfig, splitVendorChunkPlugin } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    react(),
    splitVendorChunkPlugin(),
    visualizer({ gzipSize: true }),
  ],
  resolve: {
    alias: { '@': '/src' },
  },
  build: {
    target: 'es2020',
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-antd': ['antd', '@ant-design/icons'],
          'vendor-charts': ['recharts'],
          'vendor-dnd': ['@dnd-kit/core', '@dnd-kit/sortable', '@dnd-kit/utilities'],
          'vendor-tus': ['tus-js-client'],
          'vendor-security': ['dompurify'],   // [V1.1 G1]
        },
      },
    },
    chunkSizeWarningLimit: 250,  // KB
  },
  css: {
    modules: { localsConvention: 'camelCase' },
  },
});
```

### 7.2 性能预算监控

> **[V1.1 F1]** 生产环境 PerformanceObserver longtask 监控

```typescript
// src/shared/hooks/useWebVitals.ts
import { onFCP, onLCP, onFID, onCLS, onTTFB } from 'web-vitals';

export function useWebVitals() {
  useEffect(() => {
    const report = (metric: { name: string; value: number }) => {
      navigator.sendBeacon?.('/api/v1/metrics/web-vitals', JSON.stringify(metric));
    };
    onFCP(report);
    onLCP(report);
    onFID(report);
    onCLS(report);
    onTTFB(report);
  }, []);
}
```

```typescript
// src/shared/hooks/useLongTaskMonitor.ts
// [V1.1 F1] 生产环境 long task 监控

export function useLongTaskMonitor(thresholdMs = 100) {
  useEffect(() => {
    if (!('PerformanceObserver' in window)) return;

    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > thresholdMs) {
          // 上报 > 100ms 的 long task
          navigator.sendBeacon?.('/api/v1/metrics/longtask', JSON.stringify({
            duration: entry.duration,
            startTime: entry.startTime,
            page: window.location.pathname,
            timestamp: Date.now(),
          }));
        }
      }
    });

    try {
      observer.observe({ entryTypes: ['longtask'] });
    } catch {
      // Safari 不支持 longtask → 忽略
    }

    return () => observer.disconnect();
  }, [thresholdMs]);
}
```

### 7.3 性能预算（对齐 UI/UX 附录 G）

| 页面 | FCP | TTI | JS Bundle | 内存 |
|------|-----|-----|-----------|------|
| /upload | < 1.0s | < 1.5s | < 120KB | — |
| /dashboard | < 1.5s | < 2.0s | < 200KB | — |
| /annotate | < 2.0s | < 2.5s | < 350KB | < 500MB |
| /annotate 页面切换 | — | < 0.5s | — | 缓存命中 < 0.3s |
| /config | < 1.0s | < 1.5s | < 100KB | — |
| long task 阈值 | — | — | — | < 100ms (95th percentile) |

### 7.4 缩略图虚拟滚动

```typescript
// src/features/annotate/components/left-panel/PageGrid.tsx
import { VirtuosoGrid } from 'react-virtuoso';

const PageGrid: React.FC<{ pages: PageInfo[] }> = ({ pages }) => {
  return (
    <VirtuosoGrid
      totalCount={pages.length}
      overscan={6}                     // 上下各 2 行预渲染
      listClassName={styles.grid}
      itemClassName={styles.gridItem}
      itemContent={(index) => (
        <PageThumbnail
          page={pages[index]}
          onSelect={() => handlePageSelect(pages[index].page_no)}
        />
      )}
    />
  );
};

// 缩略图懒加载
const PageThumbnail: React.FC<{ page: PageInfo; onSelect: () => void }> = ({ page, onSelect }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setLoaded(true); },
      { rootMargin: '200px' }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={styles.thumbnail} onClick={onSelect}>
      {loaded ? (
        <img
          src={jobApi.getScreenshot(page.jobId!, page.page_no, 120)}
          alt={`第 ${page.page_no} 页`}
        />
      ) : (
        <Skeleton.Image className={styles.skeleton} />
      )}
      <StatusDot status={page.status} />
    </div>
  );
};
```

### 7.5 自适应性能降级

```typescript
// src/shared/hooks/usePerformanceTier.ts

type PerfTier = 'high' | 'medium' | 'low';

export function usePerformanceTier(): PerfTier {
  const [tier, setTier] = useState<PerfTier>('high');

  useEffect(() => {
    const cores = navigator.hardwareConcurrency ?? 4;
    const memory = (navigator as any).deviceMemory ?? 8;

    if (cores <= 2 || memory <= 2) setTier('low');
    else if (cores <= 4 || memory <= 4) setTier('medium');

    const monitor = new PerformanceMonitor();
    let rafId: number;
    const tick = (ts: number) => {
      monitor.tick(ts);
      if (monitor.level === 'heavy') setTier('low');
      else if (monitor.level === 'mild') setTier('medium');
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, []);

  return tier;
}
```

### 7.6 Service Worker 缓存

> **[V1.1 F3]** 截图 URL 增加 `?v={attempt_no}` 版本参数，缓存自动失效

```typescript
// sw.ts
import { registerRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';

// 截图：Cache-First + 版本化 URL
// [V1.1 F3] 截图 URL 含 ?v=attempt_no，AI 重处理后 attempt_no+1 → 缓存自动失效
registerRoute(
  ({ url }) => url.pathname.includes('/screenshot'),
  new CacheFirst({
    cacheName: 'screenshots',
    plugins: [
      new ExpirationPlugin({ maxEntries: 500, maxAgeSeconds: 3600 }),
    ],
  })
);

// API 数据：Network-First（离线降级）
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/') && !url.pathname.includes('/screenshot'),
  new NetworkFirst({ cacheName: 'api-cache' })
);

// 静态资源：Cache-First + 版本化文件名（Vite 默认 contenthash）
registerRoute(
  ({ request }) => request.destination === 'script' || request.destination === 'style',
  new CacheFirst({ cacheName: 'static-assets' })
);
```

---

## 8. 交付清单与估算

### 8.1 文件清单

| 目录 | 文件数 | 预估代码行数 | V1.1 变更 |
|------|--------|------------|-----------|
| pages/ | 16 | ~800 | +2 (ops/eval) |
| features/upload/ | 6 | ~650 | hashWorker 超时 |
| features/dashboard/ | 14 | ~1700 | +ActionHintBadge, PrescanCard, EvaluationCard |
| features/annotate/ | 28 | ~4500 | +BatchActionFloater, OffscreenGrid, LockStatusIndicator, useRestReminder, useAutoPickTask |
| features/annotate/canvas-engine/ | 6 | ~900 | +OffscreenGrid.ts |
| features/config/ | 7 | ~1000 | +ImpactPreviewPanel |
| features/annotators/ | 4 | ~500 | — |
| features/eval/ | 4 | ~400 | [V1.1 新增] |
| shared/components/ | 13 | ~1100 | +ContextMenu, OnboardingGuide, RestReminderFloat |
| shared/hooks/ | 5 | ~250 | +useLongTaskMonitor, useDebouncedCallback |
| shared/ (security/a11y) | 2 | ~100 | [V1.1 新增] |
| services/api/ | 8 | ~700 | +annotations.ts, eval.ts, ops.ts |
| services/sse/ | 1 | ~200 | 9 事件 + 动态轮询 |
| stores/ | 8 | ~1500 | +settingsStore, immer 重构 |
| types/ + utils/ + hooks/ | 14 | ~700 | +events.ts, V2.0 类型 |
| workers/ | 1 | ~60 | 超时保护 |
| **合计** | **~137** | **~15060** | +20% vs V1.0 |

### 8.2 开发排期（1 前端 + 0.5 QA）

| Sprint | 内容 | 人天 |
|--------|------|------|
| S0 | 项目骨架 + 路由 + 设计 Token + 布局 + Auth + settingsStore | 3d |
| S1 | Upload 模块（tus + DropZone + 队列 + hashWorker 超时 + 创建失败回滚）| 5d |
| S1 | SSE 集成（9 事件 + 动态轮询）+ 通知中心（三级优先级）| 4d |
| S2 | Dashboard 列表（双轨状态 + action_hint + 批量操作 API）| 4d |
| S2 | Dashboard 详情（热力图 + SKU + 路由追溯 + PrescanCard + EvaluationCard）| 4d |
| S2 | 标注画布 Canvas 引擎（ResizeObserver + 离屏背景 + 坐标系修复）| 5d |
| S3 | 覆盖层（transform3d + 事件委托）+ 套索（坐标统一）+ 选择 + 快捷键 | 5d |
| S3 | 右栏编辑（GroupEditor + SKU 表单 + DOMPurify + 拖拽归组）| 4d |
| S3 | 右键菜单（3 种上下文 ContextMenu）+ 批量浮层 | 2d |
| S4 | 跨页合并（API 封装）+ 绑定歧义 + AI 辅助 + SLA 倒计时 | 4d |
| S4 | 心跳（失败降级）+ 锁管理（LockStatusIndicator）+ 预加载 + 提交确认 | 3d |
| S4 | 自动领取（/tasks/next）+ POST /annotations 标注记录 | 2d |
| S4 | Config 模块（编辑 + ImpactPreview debounce + 关键词 + 审计日志 + 回滚）| 4d |
| S5 | 标注员管理 + 个人面板 + 评测报告（API 封装 + 列表/详情页）| 3d |
| S5 | 运维页面（custom-attr-upgrades）| 1d |
| S5 | 新手引导（react-joyride 5 步）+ 休息提醒 + 跳过确认设置 | 2d |
| S5 | 性能优化（降级 + longtask 监控 + SW 版本化 + 打包调优 + web-vitals）| 3d |
| S5 | 安全（DOMPurify + ESLint no-danger + ARIA 对照表 + forced-colors）| 2d |
| S5 | 联调 + Bug 修复缓冲 | 4d |
| **合计** | | **64d** |

**较 V1.0（50d）增加 14d（+28%）**，主要增量：SSE 9 事件 + 批量 API + 安全加固 + 新手引导 + 评测模块 + ImpactPreview。

**与后端对齐**：前端 S0~S1 与后端 S0~S1 并行（后端先 DB+Gateway+Config，前端先骨架+Upload+SSE）。S2 起前端需后端 API 就绪（mock → 真实切换）。

---

## 9. 附录

### 9.1 Design Token 映射（Ant Design 5 ConfigProvider）

```typescript
// src/shared/design-tokens.ts
import { theme } from 'antd';

export const customTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#22D3EE',
    colorSuccess: '#4ADE80',
    colorWarning: '#FBBF24',
    colorError: '#F87171',
    colorBgBase: '#0F1117',
    colorBgContainer: '#1A1F2C',
    colorBgElevated: '#242B3D',
    colorText: '#E2E8F4',
    colorTextSecondary: '#94A3B8',
    colorBorder: '#2D3548',
    fontFamily: "'Inter', -apple-system, sans-serif",
    fontFamilyCode: "'JetBrains Mono', 'Fira Code', monospace",
    fontSize: 13,
    borderRadius: 6,
  },
};

// 分组色池（10 色，循环使用）
export const GROUP_COLORS = [
  '#22D3EE', '#A78BFA', '#34D399', '#F472B6', '#FBBF24',
  '#FB923C', '#818CF8', '#2DD4BF', '#F87171', '#A3E635',
];
```

```css
/* [V1.1 G4] forced-colors 高对比度适配 */
@media (forced-colors: active) {
  .overlay { border-color: CanvasText !important; }
  .overlay.selected { border-color: Highlight !important; }
  .tag, .confidence { color: CanvasText !important; background: Canvas !important; }
  .groupBoundingBox { border-color: Highlight !important; }
  .contextMenu { background: Canvas !important; color: CanvasText !important; border: 1px solid CanvasText !important; }
  .slaBar.critical { color: LinkText !important; }
}
```

### 9.2 TypeScript 核心类型（对齐 OpenAPI V2.0）

```typescript
// src/types/models.ts

// ======== Job ========
export interface Job {
  job_id: string;
  source_file: string;
  file_hash: string;
  merchant_id: string;
  category: string | null;
  status: JobInternalStatus;
  user_status: JobUserStatus;        // [V1.1 V2.0] 双轨
  action_hint: string | null;        // [V1.1 V2.0]
  route: 'AUTO' | 'HYBRID' | 'HUMAN_ALL' | null;
  degrade_reason: string | null;
  total_pages: number;
  total_skus: number;
  total_images: number;
  created_at: string;
  updated_at: string;
}

export type JobInternalStatus =
  | 'UPLOADED' | 'EVALUATING' | 'EVAL_FAILED' | 'EVALUATED'
  | 'PROCESSING' | 'PARTIAL_FAILED' | 'PARTIAL_IMPORTED'
  | 'DEGRADED_HUMAN' | 'FULL_IMPORTED' | 'REJECTED'
  | 'ORPHANED' | 'CANCELLED';

export type JobUserStatus = 'processing' | 'partial_success' | 'completed' | 'needs_manual' | 'failed';

export interface JobDetail extends Job {
  frozen_config_version: string;
  worker_id: string;
  completion_source: 'AI_ONLY' | 'HUMAN_ONLY' | 'HYBRID' | 'DEGRADED_HUMAN' | null;
  uploaded_at: string;
  eval_started_at: string | null;        // [V1.1 V2.0]
  eval_completed_at: string | null;
  process_started_at: string | null;
  process_completed_at: string | null;
  blank_pages: number[];
  ai_pages: number[];
  human_pages: number[];
  failed_pages: number[];
  token_consumption: { eval_tokens: number; process_tokens: number; total_api_calls: number };
  error_message: string | null;
}

// ======== Page ========
export type PageStatus =
  | 'PENDING' | 'BLANK' | 'AI_QUEUED' | 'AI_PROCESSING'
  | 'AI_COMPLETED' | 'AI_FAILED' | 'HUMAN_QUEUED' | 'HUMAN_PROCESSING'
  | 'HUMAN_COMPLETED' | 'IMPORTED_CONFIRMED' | 'IMPORTED_ASSUMED'
  | 'IMPORT_FAILED' | 'SKIPPED' | 'DEAD_LETTER';

export type PageType = 'A' | 'B' | 'C' | 'D';
export type LayoutType = 'L1' | 'L2' | 'L3' | 'L4';
export type SLALevel = 'NORMAL' | 'HIGH' | 'CRITICAL' | 'AUTO_RESOLVE';

export interface PageInfo {
  page_no: number;
  status: PageStatus;
  page_type: PageType | null;
  layout_type: LayoutType | null;
  confidence: number | null;
  task_id: string | null;
  parser_backend: string;
  jobId?: string; // client-side enrichment
}

// ======== SKU ========
export type SKUStatus = 'EXTRACTED' | 'VALIDATED' | 'CONFIRMED' | 'BOUND' | 'EXPORTED'
  | 'SUPERSEDED' | 'PARTIAL' | 'INVALID';          // [V1.1 V2.0] +SUPERSEDED/PARTIAL/INVALID

export interface SKU {
  sku_id: string;
  page_number: number;
  validity: 'valid' | 'invalid';
  attributes: Record<string, string>;
  custom_attributes: { key: string; value: string }[];
  attribute_source: 'AI_EXTRACTED' | 'HUMAN_CORRECTED' | 'CROSS_PAGE_MERGED' | 'PROMOTED';
  import_status: string;
  import_confirmation: 'confirmed' | 'assumed' | 'failed' | 'pending';
  images: SKUImage[];
  status: SKUStatus;
}

export interface SKUImage {
  image_uri: string;
  image_id: string;
  role: 'PRODUCT_MAIN' | 'DETAIL' | 'SCENE' | 'LOGO' | 'DECORATION' | 'SIZE_CHART' | null;
  binding_method: 'spatial_proximity' | 'grid_alignment' | 'id_matching' | 'page_inheritance';  // [V1.1 V2.0]
  bound_confidence: number;
  is_ambiguous: boolean;
  is_duplicate: boolean;           // [V1.1 V2.0]
  image_hash: string | null;      // [V1.1 V2.0]
  rank: number;
  extracted_path: string;
  resolution: [number, number];
  search_eligible: boolean;
  quality_grade: 'HIGH' | 'LOW_QUALITY' | 'UNASSESSED';
  short_edge_px: number;
}

// ======== Task ========
export interface TaskDetail {
  task_id: string;
  job_id: string;
  page_number: number;
  task_type: string;
  status: string;
  priority: 'NORMAL' | 'HIGH' | 'URGENT' | 'CRITICAL' | 'AUTO_RESOLVE';
  sla_deadline: string | null;
  sla_level: SLALevel;
  locked_by: string | null;               // [V1.1 V2.0]
  locked_at: string | null;               // [V1.1 V2.0]
  timeout_at: string | null;              // [V1.1 V2.0]
  assigned_to: string | null;
  assigned_at: string | null;
  rework_count: number;                    // [V1.1 V2.0]
  created_at: string;
  completed_at: string | null;
  context: {
    page_type: string;
    layout_type: string;
    screenshot_url: string;
    ai_result: object;
    cross_page_table: object | null;
  };
  elements: AnnotationElement[];
  ambiguous_bindings: AmbiguousBinding[];
}

// ======== Annotation ========
export interface AnnotationElement {
  id: string;
  type: 'image' | 'text';
  bbox: { x: number; y: number; w: number; h: number };
  aiRole: string;
  confidence: number;
}

export interface AnnotationGroup {
  id: string;
  label: string;
  skuType: 'complete' | 'partial' | 'invalid';
  elementIds: string[];
  skuAttributes: Record<string, string>;
  customAttributes: { key: string; value: string }[];
  crossPageSkuId: string | null;
  partialContains?: string[];
  invalidReason?: string;
}

export interface AmbiguousBinding {
  elementId: string;
  candidates: { imageUri: string; confidence: number; rank: number }[];
  resolved: boolean;
  selectedUri: string | null;
}

// ======== Cross-Page SKU ========
export interface CrossPageSKU {
  xsku_id: string;
  fragments: { page_number: number; task_id: string; group_id: string; partial_contains: string[] }[];
  status: 'pending' | 'merged';
}

// ======== Evaluation ========
export interface Evaluation {
  file_hash: string;
  config_version: string;
  doc_confidence: number;
  route: 'AUTO' | 'HYBRID' | 'HUMAN_ALL';
  route_reason: string | null;                  // [V1.1 V2.0]
  degrade_reason: string | null;
  dimension_scores: Record<string, number>;
  weights_snapshot: Record<string, number>;
  thresholds_used: Record<string, number> | null;  // [V1.1 V2.0]
  page_evaluations: Record<string, number>;
  model_used: string;
  prompt_version: string | null;                // [V1.1 V2.0]
  sampling: { sampled_pages: number[]; sample_ratio: number } | null;  // [V1.1 V2.0]
  evaluated_at: string | null;
  prescan_result: {
    passed: boolean;
    penalties: { rule: string; deduction: number; reason: string }[];
    total_deduction: number;
    raw_metrics: {                               // [V1.1 V2.0]
      total_pages: number;
      blank_page_count: number;
      blank_rate: number;
      ocr_rate: number;
      image_count: number;
    };
  };
}

// ======== Config ========
export interface ThresholdProfile {
  profile_id: string;
  version: string;
  previous_version: string | null;
  category: string | null;
  industry: string | null;
  thresholds: { A: number; B: number; PV: number };
  confidence_weights: Record<string, number>;
  sku_validity_mode: 'strict' | 'lenient';
  is_active: boolean;
  effective_from: string;
  change_reason: string | null;
}

export interface ImpactPreviewResult {
  sample_period_days: number;
  sample_job_count: number;
  current_auto_rate: number;
  predicted_auto_rate: number;
  current_human_daily: number;
  predicted_human_daily: number;
  capacity_warning: boolean;
}

// ======== Pagination ========
export interface PaginationMeta {
  page: number;
  size: number;
  total: number;
  total_pages: number;
}

// ======== Task Submit (元素-分组模型) ========
export interface TaskCompletePayload {
  task_id: string;
  page_type: PageType;
  layout_type: LayoutType;
  groups: {
    group_id: string;
    label: string;
    sku_type: 'complete' | 'partial' | 'invalid';
    elements: AnnotationElement[];
    sku_attributes: Record<string, string>;
    custom_attributes: { key: string; value: string }[];
    partial_contains: string[];
    cross_page_sku_id: string | null;
    invalid_reason: string | null;
  }[];
  ungrouped_elements: string[];
  binding_confirmations: { element_id: string; selected_rank: number }[];
  feedback: {
    page_type_modified: boolean;
    layout_type_modified: boolean;
    new_image_role_observed: boolean;
    new_text_role_observed: boolean;
    notes: string;
  };
}

// ======== Annotation Request (V2.0) ========
export type AnnotationType =
  | 'PAGE_TYPE_CORRECTION' | 'TEXT_ROLE_CORRECTION' | 'IMAGE_ROLE_CORRECTION'
  | 'SKU_ATTRIBUTE_CORRECTION' | 'BINDING_CORRECTION' | 'CUSTOM_ATTR_CONFIRM'
  | 'NEW_TYPE_REPORT' | 'LAYOUT_CORRECTION';

export interface CreateAnnotationRequest {
  task_id: string | null;
  job_id: string;
  page_number: number;
  type: AnnotationType;
  payload: Record<string, unknown>;
}

// ======== Error ========
export interface ErrorResponse {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  severity: 'info' | 'warning' | 'error' | 'critical';
}
```

```typescript
// src/types/events.ts — [V1.1] SSE 9 事件类型

export interface SSEPageCompleted {
  page_no: number;
  status: string;
  confidence: number | null;
  sku_count: number;
}

export interface SSEJobCompleted {
  job_id: string;
  status: string;
  total_skus: number;
  total_images: number;
  duration_sec: number;
}

export interface SSEJobFailed {
  job_id: string;
  error_code: string;
  error_message: string;
}

export interface SSEHumanNeeded {
  job_id: string;
  task_count: number;
  priority: string;
}

export interface SSESlaEscalated {
  task_id: string;
  sla_level: 'HIGH' | 'CRITICAL' | 'AUTO_RESOLVE';
  deadline: string;
}
```

### 9.3 安全

> **[V1.1 G1]** XSS 防护  
> **[V1.1 G3]** CSRF：后端使用纯 JWT Bearer Token 方案（无 Cookie），不需要 CSRF Token

```typescript
// src/shared/security.ts
import DOMPurify from 'dompurify';

/**
 * 所有用户输入的 SKU 属性值在提交前经过 sanitize。
 * React 默认转义渲染，此为额外防御层。
 */
export function sanitize(value: string): string {
  return DOMPurify.sanitize(value, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
}

/**
 * ESLint 规则配置（.eslintrc）：
 * "react/no-danger": "error"
 *
 * 全局禁止 dangerouslySetInnerHTML。
 * 如确需使用（如 markdown 渲染），须通过 DOMPurify.sanitize() + Code Review。
 */
```

### 9.4 ARIA 无障碍对照表

> **[V1.1 G2]** 对齐 UI/UX 附录 D.3 的 8 种组件 ARIA 规则

| 组件 | role | aria-label / aria-* | 备注 |
|------|------|---------------------|------|
| Sidebar nav | `navigation` | `aria-label="主导航"` | 当前项 `aria-current="page"` |
| MetricCard | `status` | `aria-label="今日 Job 数: {value}"` | live region: `aria-live="polite"` |
| ProgressBar | `progressbar` | `aria-valuenow={percent}`, `aria-valuemin=0`, `aria-valuemax=100` | — |
| ElementOverlay | `img` / `article` | `aria-label="图片/文本元素 {id}, AI: {role}, {confidence}%"` | 选中时 `aria-selected="true"` |
| GroupEditor | `region` | `aria-label="分组 {label} 编辑区"` | — |
| SLABar | `timer` | `aria-label="SLA 剩余时间: {remaining}"` | `aria-live="assertive"` when critical |
| ContextMenu | `menu` | `aria-label="上下文菜单"` | 菜单项 `role="menuitem"` |
| BatchActionFloater | `toolbar` | `aria-label="批量操作"` | — |

### 9.5 评审修复追溯表

| 评审 ID | 优先级 | 本文档修复位置 | 验证方式 |
|---------|--------|---------------|---------|
| A1 | P0 | §6.5 ContextMenu | 搜索 "ContextMenu" 验证三种上下文 |
| A2 | P1 | §3.1 notificationStore | 搜索 "level: 'urgent'" |
| A3 | P1 | §6.6 OnboardingGuide | 搜索 "ONBOARDING_STEPS" |
| A4 | P1 | §6.7 useRestReminder | 搜索 "restReminderMinutes" |
| A5 | P2 | §6.5 BatchActionFloater | 搜索 "BatchActionFloater" |
| A6 | P2 | §3.1 settingsStore | 搜索 "skipSubmitConfirm" |
| B1 | P0 | §5.3 SSEManager | 搜索 "job_failed" + "sla_auto" |
| B2 | P0 | §6.8 ImpactPreviewPanel | 搜索 "getImpactPreview" |
| B3 | P1 | §5.2 jobs.ts + tasks.ts | 搜索 "batchRetry" + "batchSkip" |
| B4 | P1 | §5.2 jobs.ts | 搜索 "getCrossPageSKUs" |
| B5 | P2 | §5.2 eval.ts | 搜索 "evalApi" |
| C1 | P0 | §3.1 helpers.ts | 搜索 "immer" |
| C2 | P1 | §3.1 annotationStore | 搜索 "string[]" 替代 Set |
| C3 | P1 | §3.1 annotationStore | 搜索 "useUndoStore.getState().push" |
| C4 | P2 | §3.1 jobStore.fetchJobs | 搜索 "selectedIds.filter" |
| D1 | P0 | §4.4 CanvasRenderer | 搜索 "ResizeObserver" |
| D2 | P1 | §4.2 + §4.6 | 搜索 "clientToContainer" |
| D3 | P1 | §4.5 ElementOverlay | 搜索 "translate3d" |
| D4 | P1 | §4.5 ElementOverlayContainer | 搜索 "data-element-id" |
| D5 | P2 | §4.4 CanvasRenderer | 搜索 "createGridPattern" |
| E1 | P0 | §5.5 useTusUpload | 搜索 "deleteUpload" |
| E2 | P1 | §5.1 client.ts | 搜索 "_handled" |
| E3 | P1 | §5.4 useHeartbeat | 搜索 "failCountRef" |
| E4 | P2 | §5.5 useTusUpload | 搜索 "hashTimeout" |
| F1 | P1 | §7.2 useLongTaskMonitor | 搜索 "longtask" |
| F2 | P1 | §5.3 SSEManager | 搜索 "isProcessing ? 5000" |
| F3 | P2 | §7.6 sw.ts | 搜索 "attempt_no" |
| G1 | P0 | §9.3 security.ts | 搜索 "DOMPurify" |
| G2 | P1 | §9.4 ARIA 表 | 完整 8 行对照表 |
| G3 | P1 | §9.3 | 搜索 "CSRF" |
| G4 | P2 | §9.1 CSS | 搜索 "forced-colors" |
