"""Benchmark 结果可视化 — 列表页 + 详情页，纯 JSON 文件驱动，不依赖数据库。"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

import os

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent.parent
CACHE_DIR = _SERVER_DIR / "data" / "benchmark_cache"
JOB_DATA_DIR = Path(os.environ.get("JOB_DATA_DIR", "/data/jobs"))

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
#  API
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/benchmark/datasets")
async def list_datasets():
    if not CACHE_DIR.exists():
        return JSONResponse([])
    results = []
    for f in sorted(CACHE_DIR.glob("*.json")):
        try:
            raw = json.loads(f.read_text("utf-8"))
            results.append({
                "name": f.stem,
                "total_pages": raw.get("total_pages", 0),
                "total_skus": raw.get("total_skus", 0),
                "elapsed_seconds": raw.get("elapsed_seconds", 0),
            })
        except Exception:
            continue
    return JSONResponse(results)


@router.get("/api/v1/benchmark/datasets/{name}")
async def get_dataset(name: str):
    safe = Path(name).name
    target = CACHE_DIR / f"{safe}.json"
    if not target.exists():
        raise HTTPException(404, f"Dataset '{name}' not found")
    raw = json.loads(target.read_text("utf-8"))
    return JSONResponse(raw)


@router.get("/api/v1/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """读取 job 目录下的 result.json 供前端可视化。"""
    safe = Path(job_id).name
    result_path = JOB_DATA_DIR / safe / "result.json"
    if not result_path.exists():
        raise HTTPException(404, "该任务尚无处理结果")
    raw = json.loads(result_path.read_text("utf-8"))
    return JSONResponse(raw)


# ═══════════════════════════════════════════════════════════════════════════
#  HTML 页面
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/benchmark/viewer", response_class=HTMLResponse)
async def list_page():
    return HTMLResponse(_LIST_HTML)


@router.get("/benchmark/viewer/{name}", response_class=HTMLResponse)
async def detail_page(name: str):
    safe = Path(name).name
    target = CACHE_DIR / f"{safe}.json"
    if not target.exists():
        raise HTTPException(404, f"Dataset '{name}' not found")
    return HTMLResponse(_DETAIL_HTML)


# ── 共享 CSS ────────────────────────────────────────────────────────────
_SHARED_CSS = """\
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f5f5;color:#333}
a{color:#1565c0;text-decoration:none}
a:hover{text-decoration:underline}
.container{max-width:1400px;margin:0 auto;padding:20px}
h1{font-size:1.5rem;margin-bottom:16px;display:flex;align-items:center;gap:12px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500;white-space:nowrap}
.badge-green{background:#e6f7e6;color:#1a7a1a}
.badge-yellow{background:#fff8e1;color:#8a6d00}
.badge-red{background:#fde8e8;color:#c0392b}
.badge-blue{background:#e3f2fd;color:#1565c0}
.badge-gray{background:#f0f0f0;color:#666}
.badge-purple{background:#f3e5f5;color:#7b1fa2}
"""

# ── 列表页 ──────────────────────────────────────────────────────────────
_LIST_HTML = f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>任务列表</title>
<style>
{_SHARED_CSS}
.job-table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.job-table th,.job-table td{{padding:12px 16px;text-align:left;border-bottom:1px solid #eee}}
.job-table th{{background:#fafafa;font-weight:600;font-size:13px;color:#666;text-transform:uppercase;letter-spacing:.5px}}
.job-table tr:hover{{background:#f8f9ff;cursor:pointer}}
.job-table td{{font-size:14px}}
.num{{font-variant-numeric:tabular-nums}}
.empty{{text-align:center;padding:60px;color:#aaa;font-size:15px}}
</style>
</head>
<body>
<div class="container">
<h1>任务列表</h1>
<table class="job-table">
  <thead><tr>
    <th>#</th><th>任务名称</th><th>页数</th><th>SKU 数</th><th>耗时</th>
  </tr></thead>
  <tbody id="tbody"><tr><td colspan="5" class="empty">加载中...</td></tr></tbody>
</table>
</div>
<script>
fetch('/api/v1/benchmark/datasets')
  .then(r => r.json())
  .then(list => {{
    const tbody = document.getElementById('tbody');
    if (!list.length) {{ tbody.innerHTML = '<tr><td colspan="5" class="empty">暂无任务数据</td></tr>'; return; }}
    tbody.innerHTML = '';
    list.forEach((d, i) => {{
      const tr = document.createElement('tr');
      tr.onclick = () => location.href = '/benchmark/viewer/' + encodeURIComponent(d.name);
      tr.innerHTML = `
        <td class="num">${{i+1}}</td>
        <td><strong>${{esc(d.name)}}</strong></td>
        <td class="num">${{d.total_pages}}</td>
        <td class="num">${{d.total_skus}}</td>
        <td class="num">${{d.elapsed_seconds.toFixed(1)}}s</td>
      `;
      tbody.appendChild(tr);
    }});
  }});
function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}
</script>
</body>
</html>
"""

# ── 详情页 ──────────────────────────────────────────────────────────────
_DETAIL_HTML = f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>任务详情</title>
<style>
{_SHARED_CSS}

/* 摘要 */
.summary{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}}
.stat{{background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:14px 20px;min-width:130px}}
.stat .label{{font-size:12px;color:#888;margin-bottom:2px}}
.stat .value{{font-size:1.3rem;font-weight:700}}

/* 页面区域 */
.page-section{{background:#fff;border:1px solid #e0e0e0;border-radius:8px;margin-bottom:16px;overflow:hidden}}
.page-header{{display:flex;align-items:center;gap:10px;padding:12px 18px;cursor:pointer;user-select:none;background:#fafafa;border-bottom:1px solid #eee}}
.page-header:hover{{background:#f0f0f0}}
.page-header .arrow{{transition:transform .2s;font-size:12px;color:#888}}
.page-header .arrow.open{{transform:rotate(90deg)}}
.page-header h3{{font-size:14px;font-weight:600;min-width:60px}}
.page-body{{display:none;padding:0}}
.page-body.open{{display:block}}

/* SKU 卡片 */
.sku-list{{display:flex;flex-direction:column}}
.sku-card{{display:flex;gap:16px;padding:16px 20px;border-bottom:1px solid #f0f0f0;align-items:flex-start}}
.sku-card:last-child{{border-bottom:none}}
.sku-card:hover{{background:#fafcff}}
.sku-index{{width:28px;height:28px;border-radius:50%;background:#e3f2fd;color:#1565c0;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;margin-top:2px}}
.sku-info{{flex:1;min-width:0}}
.sku-name{{font-size:15px;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.sku-attrs{{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:#555;margin-bottom:6px}}
.sku-attrs .attr-label{{color:#999;margin-right:2px}}
.sku-meta{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.conf-bar{{width:60px;height:6px;background:#eee;border-radius:3px;overflow:hidden;display:inline-block;vertical-align:middle}}
.conf-fill{{height:100%;border-radius:3px}}
.conf-high{{background:#43a047}}
.conf-mid{{background:#f9a825}}
.conf-low{{background:#e53935}}
.sku-images{{display:flex;gap:8px;flex-wrap:wrap;flex-shrink:0;align-items:flex-start}}
.sku-images img{{width:80px;height:80px;object-fit:cover;border-radius:6px;border:2px solid #e0e0e0;cursor:pointer;transition:all .2s}}
.sku-images img:hover{{border-color:#1565c0;transform:scale(2);z-index:100;position:relative;box-shadow:0 4px 20px rgba(0,0,0,.25)}}
.no-img{{width:80px;height:80px;border-radius:6px;border:2px dashed #ddd;display:flex;align-items:center;justify-content:center;color:#ccc;font-size:11px;flex-shrink:0}}
.empty{{color:#aaa;font-style:italic;padding:40px;text-align:center}}
.error-msg{{color:#c0392b;background:#fde8e8;padding:10px 16px;border-radius:4px;margin:12px 20px;font-size:13px}}
.back-link{{font-size:14px;color:#888}}
.back-link:hover{{color:#1565c0}}

/* 图片弹窗 */
.lightbox{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.8);z-index:9999;align-items:center;justify-content:center;cursor:zoom-out}}
.lightbox.show{{display:flex}}
.lightbox img{{max-width:90%;max-height:90%;border-radius:8px;box-shadow:0 8px 40px rgba(0,0,0,.5)}}
</style>
</head>
<body>
<div class="container">
  <h1>
    <a href="/benchmark/viewer" class="back-link">&larr; 返回列表</a>
    <span id="title">加载中...</span>
  </h1>
  <div class="summary" id="summary"></div>
  <div id="pages"></div>
</div>

<!-- 图片弹窗 -->
<div class="lightbox" id="lightbox" onclick="this.classList.remove('show')">
  <img id="lightbox-img" src="" alt="preview">
</div>

<script>
const name = decodeURIComponent(location.pathname.split('/').pop());

fetch('/api/v1/benchmark/datasets/' + encodeURIComponent(name))
  .then(r => {{ if (!r.ok) throw new Error(r.status); return r.json(); }})
  .then(render)
  .catch(() => {{
    document.getElementById('title').textContent = '加载失败';
    document.getElementById('pages').innerHTML = '<div class="empty">未找到该任务数据</div>';
  }});

function render(data) {{
  document.title = data.dataset + ' — 任务详情';
  document.getElementById('title').textContent = data.dataset;

  // 摘要
  const s = document.getElementById('summary');
  s.innerHTML = `
    <div class="stat"><div class="label">总页数</div><div class="value">${{data.total_pages}}</div></div>
    <div class="stat"><div class="label">总 SKU</div><div class="value">${{data.total_skus}}</div></div>
    <div class="stat"><div class="label">处理耗时</div><div class="value">${{data.elapsed_seconds.toFixed(1)}}s</div></div>
    <div class="stat"><div class="label">有图 SKU</div><div class="value">${{countWithImages(data)}}</div></div>
  `;

  // 页面
  const pagesEl = document.getElementById('pages');
  pagesEl.innerHTML = '';
  (data.pages || []).forEach((page, pi) => {{
    const sec = document.createElement('div');
    sec.className = 'page-section';

    const isFirst = pi === 0;
    sec.innerHTML = `
      <div class="page-header" onclick="togglePage(this)">
        <span class="arrow${{isFirst ? ' open' : ''}}">&#9654;</span>
        <h3>第 ${{page.page_no}} 页</h3>
        ${{statusBadge(page.status)}}
        ${{page.page_type ? '<span class="badge badge-blue">类型 ' + page.page_type + '</span>' : ''}}
        ${{page.extraction_method ? '<span class="badge badge-purple">' + page.extraction_method + '</span>' : ''}}
        ${{page.fitz_page_class ? '<span class="badge badge-gray">' + page.fitz_page_class + '</span>' : ''}}
        <span style="margin-left:auto;font-size:13px;color:#666;font-weight:600">${{page.sku_count}} SKUs</span>
      </div>
      <div class="page-body${{isFirst ? ' open' : ''}}">${{renderPage(page)}}</div>
    `;
    pagesEl.appendChild(sec);
  }});
}}

function renderPage(page) {{
  let html = '';
  if (page.error) html += '<div class="error-msg">&#9888; ' + esc(String(page.error)) + '</div>';
  const skus = page.skus || [];
  if (!skus.length) return html + '<div class="empty">该页无 SKU 数据</div>';

  html += '<div class="sku-list">';
  skus.forEach((sku, i) => {{
    const a = sku.attributes || {{}};
    const conf = sku.confidence || 0;
    const confCls = conf >= 0.7 ? 'conf-high' : conf >= 0.5 ? 'conf-mid' : 'conf-low';
    const validBadge = sku.validity === 'valid'
      ? '<span class="badge badge-green">valid</span>'
      : '<span class="badge badge-red">invalid</span>';

    // 图片
    const imgs = sku.image_paths || [];
    let imgHtml = '';
    if (imgs.length) {{
      imgs.forEach(p => {{
        imgHtml += `<img src="${{esc(p)}}" alt="商品图" loading="lazy" onerror="this.style.display='none'" onclick="showImg(event, this.src)">`;
      }});
    }} else {{
      imgHtml = '<div class="no-img">无图</div>';
    }}

    // 属性行
    const attrParts = [];
    if (a.model_number) attrParts.push('<span class="attr-label">型号</span>' + esc(a.model_number));
    if (a.price) attrParts.push('<span class="attr-label">价格</span>' + esc(a.price));
    if (a.specs) attrParts.push('<span class="attr-label">规格</span>' + esc(a.specs));
    if (a.color) attrParts.push('<span class="attr-label">颜色</span>' + esc(a.color));
    if (a.tag) attrParts.push('<span class="attr-label">标签</span>' + esc(a.tag));
    if (a.source) attrParts.push('<span class="attr-label">来源</span>' + esc(a.source));

    html += `
      <div class="sku-card">
        <div class="sku-index">${{i + 1}}</div>
        <div class="sku-info">
          <div class="sku-name">
            ${{esc(a.product_name || '未知商品')}}
            ${{validBadge}}
          </div>
          ${{attrParts.length ? '<div class="sku-attrs">' + attrParts.join('<span style="color:#ddd">|</span>') + '</div>' : ''}}
          <div class="sku-meta">
            <span class="badge badge-gray">${{esc(sku.extraction_method || '')}}</span>
            <span style="font-size:12px;color:#888">置信度</span>
            <div class="conf-bar"><div class="conf-fill ${{confCls}}" style="width:${{(conf*100).toFixed(0)}}%"></div></div>
            <span style="font-size:12px;font-weight:600" class="${{confCls}}-text">${{conf.toFixed(2)}}</span>
            <span style="font-size:11px;color:#bbb">${{esc(sku.sku_id || '')}}</span>
          </div>
        </div>
        <div class="sku-images">${{imgHtml}}</div>
      </div>
    `;
  }});
  html += '</div>';
  return html;
}}

function countWithImages(data) {{
  let n = 0;
  (data.pages || []).forEach(p => (p.skus || []).forEach(s => {{ if ((s.image_paths || []).length) n++; }}));
  return n;
}}

function togglePage(header) {{
  header.querySelector('.arrow').classList.toggle('open');
  header.nextElementSibling.classList.toggle('open');
}}

function statusBadge(status) {{
  const m = {{'AI_COMPLETED':'badge-green','SKIPPED':'badge-gray','AI_FAILED':'badge-red','HUMAN_QUEUED':'badge-yellow'}};
  return '<span class="badge ' + (m[status]||'badge-gray') + '">' + (status||'unknown') + '</span>';
}}

function showImg(e, src) {{
  e.stopPropagation();
  const lb = document.getElementById('lightbox');
  document.getElementById('lightbox-img').src = src;
  lb.classList.add('show');
}}

function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}
</script>
</body>
</html>
"""
