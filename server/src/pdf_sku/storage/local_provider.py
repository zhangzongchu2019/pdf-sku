"""本地文件存储（开发环境）。对齐: 接口契约 §2.9 StorageProvider"""
import os
import aiofiles

class LocalStorageProvider:
    def __init__(self, base_dir: str = "/tmp/pdf-sku-storage"):
        self.base_dir = base_dir; os.makedirs(base_dir, exist_ok=True)

    async def save_file(self, path: str, data: bytes) -> str:
        full = os.path.join(self.base_dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        async with aiofiles.open(full, "wb") as f:
            await f.write(data)
        return full

    async def read_file(self, path: str) -> bytes:
        async with aiofiles.open(os.path.join(self.base_dir, path), "rb") as f:
            return await f.read()

    async def delete_file(self, path: str) -> bool:
        try: os.remove(os.path.join(self.base_dir, path)); return True
        except FileNotFoundError: return False

    async def get_url(self, path: str, expires: int = 3600) -> str:
        return f"file://{os.path.join(self.base_dir, path)}"
