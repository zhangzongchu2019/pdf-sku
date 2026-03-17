"""
第1轮集成测试: 上传 PDF → 创建 Job → 查询状态

验证:
1. TUS 上传协议 (Creation + PATCH + HEAD)
2. Job 创建 (文件校验 + 安全检查 + 预筛 + 落库)
3. Job 列表/详情查询
4. Page 列表查询
5. Health 端点
6. SSE 连接建立
"""
import asyncio
import base64
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture
async def test_client(db_url, db_schema, redis_url, init_db, tmp_path, fake_redis):
    """创建带完整 lifespan 的测试客户端。"""
    import os
    os.environ["DATABASE_URL"] = db_url
    os.environ["REDIS_URL"] = redis_url
    os.environ["TUS_UPLOAD_DIR"] = str(tmp_path / "tus")
    os.environ["JOB_DATA_DIR"] = str(tmp_path / "jobs")
    os.environ["APP_ENV"] = "test"
    os.environ["WORKER_ID"] = "test-worker-1"
    os.environ["MINIO_ENDPOINT"] = "localhost:9000"  # 不需要真实连接

    (tmp_path / "tus").mkdir()
    (tmp_path / "jobs").mkdir()

    from pdf_sku.settings import Settings
    import pdf_sku.settings
    pdf_sku.settings.settings = Settings()

    from pdf_sku.main import create_app
    app = create_app()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def test_lifespan(app):
        """简化 lifespan: 跳过 MinIO。"""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

        engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={"server_settings": {"search_path": db_schema}},
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        redis = fake_redis

        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.redis = redis
        app.state.services_ready = {
            "database": True,
            "redis": True,
            "minio": True,
        }

        # Gateway 组件
        import pdf_sku.gateway._deps as deps
        from pdf_sku.gateway.tus_store import TusStore
        from pdf_sku.gateway.tus_handler import TusHandler
        from pdf_sku.gateway.file_validator import FileValidator
        from pdf_sku.gateway.pdf_security import SecurityResult
        from pdf_sku.gateway.prescanner import PrescanResult
        from pdf_sku.gateway.job_factory import JobFactory
        from pdf_sku.gateway.sse_manager import SSEManager

        class StubSecurityChecker:
            async def check(self, file_path: str) -> SecurityResult:
                return SecurityResult(safe=True, security_issues=[])

        class StubPrescanner:
            async def scan(self, file_path: str) -> PrescanResult:
                return PrescanResult(
                    all_blank=False,
                    blank_pages=[],
                    penalties=[],
                    total_penalty=0.0,
                    raw_metrics={
                        "total_pages": 2,
                        "blank_page_count": 0,
                        "blank_rate": 0.0,
                        "ocr_rate": 1.0,
                        "image_count": 0,
                    },
                )

        deps.tus_store = TusStore(redis)
        deps.tus_handler = TusHandler(deps.tus_store)
        deps.job_factory = JobFactory(
            validator=FileValidator(),
            security_checker=StubSecurityChecker(),
            prescanner=StubPrescanner(),
        )
        deps.sse_manager = SSEManager()

        # DI override
        from pdf_sku.auth.dependencies import get_current_user
        from pdf_sku.common.dependencies import get_db, get_redis
        from pdf_sku.common.models import User
        import uuid

        async def _get_db():
            async with session_factory() as session:
                yield session

        async def _get_redis():
            return redis

        test_user = User(
            user_id=uuid.uuid4(),
            username="integration-user",
            display_name="Integration User",
            password_hash="not-used",
            role="uploader",
            merchant_id="M_AUTH",
            is_active=True,
        )

        async with session_factory() as session:
            session.add(test_user)
            await session.commit()

        async def _get_current_user():
            return test_user

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_redis] = _get_redis
        app.dependency_overrides[get_current_user] = _get_current_user

        yield

        await engine.dispose()

    app.router.lifespan_context = test_lifespan

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


@pytest.fixture
def pdf_bytes(sample_pdf) -> bytes:
    return sample_pdf.read_bytes()


# ═══════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_ok(self, test_client: AsyncClient):
        resp = await test_client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["services"]["database"] is True
        assert data["services"]["redis"] is True


class TestTUSUpload:
    @pytest.mark.asyncio
    async def test_create_upload(self, test_client: AsyncClient, pdf_bytes):
        filename_b64 = base64.b64encode(b"test.pdf").decode()
        filetype_b64 = base64.b64encode(b"application/pdf").decode()

        resp = await test_client.post(
            "/api/v1/uploads",
            headers={
                "Upload-Length": str(len(pdf_bytes)),
                "Upload-Metadata": f"filename {filename_b64},filetype {filetype_b64}",
                "Tus-Resumable": "1.0.0",
            },
        )
        assert resp.status_code == 201
        assert "Location" in resp.headers
        upload_id = resp.headers["Location"].split("/")[-1]
        assert upload_id.startswith("upl_")
        return upload_id

    @pytest.mark.asyncio
    async def test_full_upload_flow(self, test_client: AsyncClient, pdf_bytes):
        """完整 TUS 上传: CREATE → PATCH → HEAD 验证。"""
        filename_b64 = base64.b64encode(b"test.pdf").decode()
        filetype_b64 = base64.b64encode(b"application/pdf").decode()

        # 1. CREATE
        resp = await test_client.post(
            "/api/v1/uploads",
            headers={
                "Upload-Length": str(len(pdf_bytes)),
                "Upload-Metadata": f"filename {filename_b64},filetype {filetype_b64}",
                "Tus-Resumable": "1.0.0",
            },
        )
        assert resp.status_code == 201
        upload_id = resp.headers["Location"].split("/")[-1]

        # 2. PATCH (单次，小文件)
        resp = await test_client.patch(
            f"/api/v1/uploads/{upload_id}",
            content=pdf_bytes,
            headers={
                "Upload-Offset": "0",
                "Content-Type": "application/offset+octet-stream",
                "Tus-Resumable": "1.0.0",
            },
        )
        assert resp.status_code == 204
        assert int(resp.headers["Upload-Offset"]) == len(pdf_bytes)

        # 3. HEAD — 确认完成
        resp = await test_client.head(f"/api/v1/uploads/{upload_id}")
        assert resp.status_code == 200
        assert int(resp.headers["Upload-Offset"]) == len(pdf_bytes)

        return upload_id

    @pytest.mark.asyncio
    async def test_reject_non_pdf(self, test_client: AsyncClient):
        """拒绝非 PDF 文件。"""
        filename_b64 = base64.b64encode(b"test.txt").decode()
        resp = await test_client.post(
            "/api/v1/uploads",
            headers={
                "Upload-Length": "100",
                "Upload-Metadata": f"filename {filename_b64}",
                "Tus-Resumable": "1.0.0",
            },
        )
        assert resp.status_code == 400


class TestJobCreation:
    @pytest.mark.asyncio
    async def test_create_job_full_flow(self, test_client: AsyncClient, pdf_bytes):
        """完整链路: 上传 → 创建 Job → 查询。"""

        # 1. TUS 上传
        filename_b64 = base64.b64encode(b"catalog.pdf").decode()
        filetype_b64 = base64.b64encode(b"application/pdf").decode()

        resp = await test_client.post("/api/v1/uploads", headers={
            "Upload-Length": str(len(pdf_bytes)),
            "Upload-Metadata": f"filename {filename_b64},filetype {filetype_b64}",
            "Tus-Resumable": "1.0.0",
        })
        upload_id = resp.headers["Location"].split("/")[-1]

        resp = await test_client.patch(f"/api/v1/uploads/{upload_id}", content=pdf_bytes, headers={
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
            "Tus-Resumable": "1.0.0",
        })
        assert resp.status_code == 204

        # 2. 创建 Job
        resp = await test_client.post("/api/v1/jobs", json={
            "upload_id": upload_id,
            "merchant_id": "M001",
            "category": "electronics",
        })
        assert resp.status_code == 201, f"Failed: {resp.text}"
        job_data = resp.json()
        job_id = job_data["job_id"]

        assert job_data["source_file"] == "catalog.pdf"
        assert job_data["status"] == "UPLOADED"
        assert job_data["user_status"] == "processing"
        assert job_data["total_pages"] == 2
        assert job_data["action_hint"] != ""

        # 3. 查询 Job 详情
        resp = await test_client.get(f"/api/v1/jobs/{job_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["merchant_id"] == "M001"
        assert detail["category"] == "electronics"
        assert detail["file_hash"]  # 非空
        assert detail["processing_trace"] is not None
        assert "prescan" in detail["processing_trace"]

        # 4. 查询 Job 列表
        resp = await test_client.get("/api/v1/jobs")
        assert resp.status_code == 200
        list_data = resp.json()
        assert list_data["pagination"]["total_count"] >= 1
        assert any(j["job_id"] == job_id for j in list_data["data"])

        # 5. 查询 Pages
        resp = await test_client.get(f"/api/v1/jobs/{job_id}/pages")
        assert resp.status_code == 200
        pages = resp.json()
        assert len(pages["data"]) == 2
        assert pages["data"][0]["page_number"] == 1
        assert pages["data"][0]["status"] == "PENDING"

        return job_id

    @pytest.mark.asyncio
    async def test_duplicate_upload_rejected(self, test_client: AsyncClient, pdf_bytes):
        """同一用户重复上传相同文件时返回已有 Job。"""
        async def upload_and_create(merchant: str):
            filename_b64 = base64.b64encode(b"dup.pdf").decode()
            filetype_b64 = base64.b64encode(b"application/pdf").decode()

            resp = await test_client.post("/api/v1/uploads", headers={
                "Upload-Length": str(len(pdf_bytes)),
                "Upload-Metadata": f"filename {filename_b64},filetype {filetype_b64}",
                "Tus-Resumable": "1.0.0",
            })
            uid = resp.headers["Location"].split("/")[-1]
            await test_client.patch(f"/api/v1/uploads/{uid}", content=pdf_bytes, headers={
                "Upload-Offset": "0",
                "Content-Type": "application/offset+octet-stream",
                "Tus-Resumable": "1.0.0",
            })
            return await test_client.post("/api/v1/jobs", json={
                "upload_id": uid, "merchant_id": merchant,
            })

        # 第一次: 成功
        resp1 = await upload_and_create("M_DUP")
        assert resp1.status_code == 201

        # 第二次: 返回已有 Job
        resp2 = await upload_and_create("M_DUP")
        assert resp2.status_code == 200
        assert resp2.json()["is_duplicate"] is True


class TestJobOperations:
    @pytest.mark.asyncio
    async def test_cancel_job(self, test_client: AsyncClient, pdf_bytes):
        """取消 Job。"""
        # 创建
        filename_b64 = base64.b64encode(b"cancel_test.pdf").decode()
        filetype_b64 = base64.b64encode(b"application/pdf").decode()
        resp = await test_client.post("/api/v1/uploads", headers={
            "Upload-Length": str(len(pdf_bytes)),
            "Upload-Metadata": f"filename {filename_b64},filetype {filetype_b64}",
            "Tus-Resumable": "1.0.0",
        })
        uid = resp.headers["Location"].split("/")[-1]
        await test_client.patch(f"/api/v1/uploads/{uid}", content=pdf_bytes, headers={
            "Upload-Offset": "0", "Content-Type": "application/offset+octet-stream",
            "Tus-Resumable": "1.0.0",
        })
        resp = await test_client.post("/api/v1/jobs", json={
            "upload_id": uid, "merchant_id": "M_CANCEL",
        })
        job_id = resp.json()["job_id"]

        # 取消
        resp = await test_client.post(f"/api/v1/jobs/{job_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"
        assert resp.json()["user_status"] == "failed"

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, test_client: AsyncClient):
        """查询不存在的 Job。"""
        import uuid
        resp = await test_client.get(f"/api/v1/jobs/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestDashboard:
    @pytest.mark.asyncio
    async def test_dashboard_metrics(self, test_client: AsyncClient):
        resp = await test_client.get("/api/v1/dashboard/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "timestamp" in data
        assert "job_stats" in data
        assert "page_stats" in data
        assert "task_stats" in data
        assert "import_stats" in data
