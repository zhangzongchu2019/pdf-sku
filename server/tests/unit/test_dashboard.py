"""DashboardService 测试。"""
from pdf_sku.gateway.dashboard import DashboardService


def test_dashboard_importable():
    svc = DashboardService()
    assert callable(svc.get_overview)
