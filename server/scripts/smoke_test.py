#!/usr/bin/env python3
"""
端到端冒烟测试 — docker compose up 后运行。
用法: python3 scripts/smoke_test.py [base_url]
默认: http://localhost:8000
"""
import sys
import json
import time
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
API = f"{BASE}/api/v1"

passed = 0
failed = 0
errors = []


def test(name: str, method: str, path: str, body=None, expect_status=200):
    global passed, failed
    url = f"{API}{path}"
    try:
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"} if body else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        resp = urllib.request.urlopen(req)
        status = resp.status
        result = json.loads(resp.read().decode()) if resp.read else {}
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            result = json.loads(e.read().decode())
        except Exception:
            result = {}
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        failed += 1
        errors.append(name)
        return None

    ok = status == expect_status
    icon = "✅" if ok else "❌"
    print(f"  {icon} {name}: HTTP {status} {'(expected)' if ok else f'(expected {expect_status})'}")
    if ok:
        passed += 1
    else:
        failed += 1
        errors.append(name)
    return result


print(f"\n{'='*60}")
print(f"  PDF-SKU 冒烟测试  ({API})")
print(f"{'='*60}\n")

# Wait for server
print("[1/7] 等待服务启动...")
for i in range(30):
    try:
        urllib.request.urlopen(f"{API}/health", timeout=2)
        print(f"  ✅ 服务已就绪 ({i+1}s)\n")
        break
    except Exception:
        time.sleep(1)
else:
    print("  ❌ 服务未启动，退出")
    sys.exit(1)

# Health
print("[2/7] 健康检查")
r = test("Health endpoint", "GET", "/health")
if r:
    services = r.get("services", {})
    for svc, ok in services.items():
        icon = "✅" if ok else "⚠️"
        print(f"       {icon} {svc}: {ok}")

# Dashboard
print("\n[3/7] Dashboard")
test("Dashboard metrics", "GET", "/dashboard/metrics")

# Jobs list
print("\n[4/7] Jobs")
test("List jobs (empty)", "GET", "/jobs")
test("List jobs with filter", "GET", "/jobs?status=PROCESSING")

# Config
print("\n[5/7] Config")
test("List profiles", "GET", "/config/profiles")

# Tasks
print("\n[6/7] Tasks")
test("List tasks", "GET", "/tasks")

# Calibrations
print("\n[7/7] Feedback")
test("List calibrations", "GET", "/calibrations")

# Summary
print(f"\n{'='*60}")
print(f"  结果: {passed} 通过, {failed} 失败")
if errors:
    print(f"  失败项: {', '.join(errors)}")
print(f"{'='*60}\n")

sys.exit(0 if failed == 0 else 1)
