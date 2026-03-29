"""
图片相似度匹配器 — GPU 加速。

用于 GT 仅有图片无名称/型号时，通过视觉相似度匹配 Pipeline 输出。
使用 torchvision ResNet50 提取特征向量 + 余弦相似度。
"""
from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from PIL import Image

logger = structlog.get_logger()

# ── 延迟加载 torch（仅在需要时初始化 GPU）──
_model = None
_transform = None
_device = None


def _init_model():
    """延迟初始化 ResNet50 特征提取器。"""
    global _model, _transform, _device
    if _model is not None:
        return

    import torch
    import torchvision.models as models
    import torchvision.transforms as T

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ResNet50 去掉最后分类层，输出 2048 维特征向量
    resnet = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
    resnet.fc = torch.nn.Identity()
    resnet = resnet.to(_device).eval()
    _model = resnet

    _transform = T.Compose([
        T.Resize(256),
        T.CenterCrop(224),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    logger.info("image_matcher_initialized", device=str(_device))


def extract_feature(img: Image.Image) -> np.ndarray:
    """提取单张图片的特征向量 (2048-d)。"""
    import torch

    _init_model()
    tensor = _transform(img.convert("RGB")).unsqueeze(0).to(_device)
    with torch.no_grad():
        feat = _model(tensor).cpu().numpy().flatten()
    # L2 归一化
    norm = np.linalg.norm(feat)
    if norm > 0:
        feat = feat / norm
    return feat


def extract_features_batch(images: list[Image.Image], batch_size: int = 32) -> np.ndarray:
    """批量提取特征向量，返回 (N, 2048) 矩阵。"""
    import torch

    _init_model()
    all_feats = []
    for i in range(0, len(images), batch_size):
        batch_imgs = images[i:i + batch_size]
        tensors = torch.stack([_transform(img.convert("RGB")) for img in batch_imgs])
        tensors = tensors.to(_device)
        with torch.no_grad():
            feats = _model(tensors).cpu().numpy()
        all_feats.append(feats)

    features = np.vstack(all_feats)
    # L2 归一化
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    norms[norms == 0] = 1
    features = features / norms
    return features


def cosine_similarity_matrix(feats_a: np.ndarray, feats_b: np.ndarray) -> np.ndarray:
    """计算两组特征向量的余弦相似度矩阵 (M, N)。"""
    return feats_a @ feats_b.T


# ── Excel 图片提取 ──

_CELL_IMAGES_NS = {
    "etc": "http://www.wps.cn/officeDocument/2017/etCustomData",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def extract_excel_images(excel_path: Path) -> dict[str, list[Image.Image]]:
    """从 Excel 提取 DISPIMG 嵌入的产品图片。

    Returns:
        dict: DISPIMG_ID → PIL Image 列表
    """
    result: dict[str, Image.Image] = {}
    try:
        with zipfile.ZipFile(excel_path, "r") as zf:
            # 1. 解析 cellimages.xml → DISPIMG_ID → rId
            if "xl/cellimages.xml" not in zf.namelist():
                return {}
            ci_xml = zf.read("xl/cellimages.xml")
            ci_tree = ET.fromstring(ci_xml)

            dispimg_to_rid: dict[str, str] = {}
            for ci in ci_tree.findall(".//etc:cellImage", _CELL_IMAGES_NS):
                pic = ci.find(".//xdr:nvPicPr/xdr:cNvPr", _CELL_IMAGES_NS)
                blip = ci.find(".//a:blip", _CELL_IMAGES_NS)
                if pic is not None and blip is not None:
                    name = pic.get("name")
                    rid = blip.get(f"{{{_CELL_IMAGES_NS['r']}}}embed")
                    if name and rid:
                        dispimg_to_rid[name] = rid

            # 2. 解析 rels → rId → image file
            rels_path = "xl/_rels/cellimages.xml.rels"
            if rels_path not in zf.namelist():
                return {}
            rels_xml = zf.read(rels_path)
            rels_tree = ET.fromstring(rels_xml)

            rid_to_file: dict[str, str] = {}
            for rel in rels_tree.findall(f"{{{_RELS_NS}}}Relationship"):
                rid_to_file[rel.get("Id")] = rel.get("Target")

            # 3. 加载图片
            for dispimg_id, rid in dispimg_to_rid.items():
                img_path = rid_to_file.get(rid)
                if not img_path:
                    continue
                full_path = f"xl/{img_path}"
                if full_path in zf.namelist():
                    try:
                        img_data = zf.read(full_path)
                        img = Image.open(io.BytesIO(img_data))
                        result[dispimg_id] = img
                    except Exception:
                        pass

    except Exception as e:
        logger.warning("extract_excel_images_failed", error=str(e))

    return result


def extract_gt_images_by_row(
    excel_path: Path,
) -> list[list[Image.Image]]:
    """按行提取 GT 图片，返回 list[行] → list[该行的图片]。

    通过解析 Excel 中每个单元格的 DISPIMG 公式，将图片按行分组。
    """
    import openpyxl

    # Step 1: 提取所有 DISPIMG 图片
    all_images = extract_excel_images(excel_path)
    if not all_images:
        return []

    # Step 2: 解析每行每个单元格的 DISPIMG ID
    wb = openpyxl.load_workbook(excel_path, read_only=True)
    ws = wb.active
    if ws is None:
        return []

    rows_data = list(ws.iter_rows(min_row=1, values_only=False))
    wb.close()

    if len(rows_data) < 2:
        return []

    # 找到图片列范围（标题为"商品图片"的列）
    header_row = rows_data[0]
    img_cols: list[int] = []
    for i, cell in enumerate(header_row):
        val = str(cell.value) if cell.value else ""
        if "商品图片" in val or "图片" in val:
            img_cols.append(i)

    # 重新读取，这次获取公式
    wb2 = openpyxl.load_workbook(excel_path, read_only=True, data_only=False)
    ws2 = wb2.active
    rows_formula = list(ws2.iter_rows(min_row=2, values_only=True))
    wb2.close()

    result: list[list[Image.Image]] = []
    import re
    dispimg_pattern = re.compile(r'DISPIMG\("([^"]+)"')

    for row in rows_formula:
        row_images: list[Image.Image] = []
        for i, val in enumerate(row):
            if val and "DISPIMG" in str(val):
                m = dispimg_pattern.search(str(val))
                if m:
                    dispimg_id = m.group(1)
                    img = all_images.get(dispimg_id)
                    if img is not None:
                        row_images.append(img)
        if row_images:
            result.append(row_images)

    return result


# ── 匹配接口 ──

def match_by_image_similarity(
    gt_images_by_row: list[list[Image.Image]],
    pred_images_by_sku: list[list[Image.Image]],
    threshold: float = 0.70,
) -> list[tuple[int, int, float]]:
    """通过图片相似度匹配 GT 行与 Pipeline SKU。

    匹配策略: GT 每张图单独与 Pipeline 每张图比较，
    取最高 sim 作为该 GT-Pred 对的相似度。
    只要 GT 行中有任意一张图与 Pred 的某张图 sim > threshold 即可匹配。

    Args:
        gt_images_by_row: GT 每行的图片列表
        pred_images_by_sku: Pipeline 每个 SKU 的图片列表
        threshold: 匹配阈值 (余弦相似度)

    Returns:
        匹配结果列表: (gt_row_idx, pred_sku_idx, similarity)
    """
    if not gt_images_by_row or not pred_images_by_sku:
        return []

    _init_model()

    # 提取所有 GT 图片特征（展平，记录所属行）
    gt_flat_feats: list[np.ndarray] = []
    gt_flat_row: list[int] = []  # 每个特征属于哪一行
    for ri, row_imgs in enumerate(gt_images_by_row):
        if not row_imgs:
            continue
        feats = extract_features_batch(row_imgs)
        for f in feats:
            gt_flat_feats.append(f)
            gt_flat_row.append(ri)

    # 提取所有 Pred 图片特征（展平，记录所属 SKU）
    pred_flat_feats: list[np.ndarray] = []
    pred_flat_sku: list[int] = []
    for si, sku_imgs in enumerate(pred_images_by_sku):
        if not sku_imgs:
            continue
        feats = extract_features_batch(sku_imgs)
        for f in feats:
            pred_flat_feats.append(f)
            pred_flat_sku.append(si)

    if not gt_flat_feats or not pred_flat_feats:
        return []

    gt_mat = np.array(gt_flat_feats)
    pred_mat = np.array(pred_flat_feats)

    # 图片级余弦相似度矩阵 (N_gt_imgs × N_pred_imgs)
    sim_matrix = cosine_similarity_matrix(gt_mat, pred_mat)

    # 聚合到行-SKU级别: 取每对 (gt_row, pred_sku) 的最大图片相似度
    n_rows = len(gt_images_by_row)
    n_skus = len(pred_images_by_sku)
    row_sku_max_sim = np.full((n_rows, n_skus), -1.0)

    for gi in range(len(gt_flat_feats)):
        for pi in range(len(pred_flat_feats)):
            ri = gt_flat_row[gi]
            si = pred_flat_sku[pi]
            if sim_matrix[gi, pi] > row_sku_max_sim[ri, si]:
                row_sku_max_sim[ri, si] = sim_matrix[gi, pi]

    # 贪心匹配: 每次选最高相似度的 (gt_row, pred_sku) 对
    matches: list[tuple[int, int, float]] = []
    matched_gt: set[int] = set()
    matched_pred: set[int] = set()

    flat = []
    for ri in range(n_rows):
        for si in range(n_skus):
            if row_sku_max_sim[ri, si] >= threshold:
                flat.append((row_sku_max_sim[ri, si], ri, si))
    flat.sort(key=lambda x: -x[0])

    for sim, ri, si in flat:
        if ri in matched_gt or si in matched_pred:
            continue
        matches.append((ri, si, float(sim)))
        matched_gt.add(ri)
        matched_pred.add(si)

    logger.info("image_matching_done",
                gt_rows=n_rows, gt_images=len(gt_flat_feats),
                pred_skus=n_skus, pred_images=len(pred_flat_feats),
                matched=len(matches), threshold=threshold)

    return matches


def match_gt_pred_images(
    excel_path: Path,
    cache_path: Path,
    image_base: Path = Path("/data/benchmark_images"),
    threshold: float = 0.70,
) -> dict:
    """完整的 GT-Pipeline 图片匹配流程。

    Args:
        excel_path: GT Excel 文件路径
        cache_path: Pipeline benchmark cache JSON 路径
        image_base: Pipeline 图片存储根目录
        threshold: 匹配阈值

    Returns:
        dict: {matched, total_gt, total_pred, match_rate, details}
    """
    import json

    # 1. 提取 GT 图片
    gt_rows = extract_gt_images_by_row(excel_path)
    if not gt_rows:
        return {"matched": 0, "total_gt": 0, "total_pred": 0,
                "match_rate": 0, "error": "no_gt_images"}

    # 2. 加载 Pipeline 图片
    cache_data = json.loads(cache_path.read_text())
    pred_images_by_sku: list[list[Image.Image]] = []

    for page in cache_data.get("pages", []):
        for sku in page.get("skus", []):
            sku_imgs: list[Image.Image] = []
            for ip in sku.get("image_paths", []):
                img_file = image_base / ip.replace("/images/benchmark/", "")
                if img_file.exists():
                    try:
                        sku_imgs.append(Image.open(img_file))
                    except Exception:
                        pass
            pred_images_by_sku.append(sku_imgs)

    # 3. 匹配
    matches = match_by_image_similarity(gt_rows, pred_images_by_sku, threshold)
    match_rate = len(matches) / len(gt_rows) if gt_rows else 0

    return {
        "matched": len(matches),
        "total_gt": len(gt_rows),
        "total_pred": len(pred_images_by_sku),
        "match_rate": match_rate,
        "matches": [(gi, pi, f"{sim:.3f}") for gi, pi, sim in matches],
    }
