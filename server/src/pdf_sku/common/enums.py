"""全系统 28 种枚举 — 单一真理源。对齐: 数据字典 V1.0 §2"""
from enum import StrEnum

# §2.1 核心实体状态
class JobInternalStatus(StrEnum):
    UPLOADED = "UPLOADED"; EVALUATING = "EVALUATING"; EVAL_FAILED = "EVAL_FAILED"
    EVALUATED = "EVALUATED"; PROCESSING = "PROCESSING"; PARTIAL_FAILED = "PARTIAL_FAILED"
    PARTIAL_IMPORTED = "PARTIAL_IMPORTED"; DEGRADED_HUMAN = "DEGRADED_HUMAN"
    FULL_IMPORTED = "FULL_IMPORTED"; REJECTED = "REJECTED"; ORPHANED = "ORPHANED"
    CANCELLED = "CANCELLED"

class JobUserStatus(StrEnum):
    PROCESSING = "processing"; PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"; NEEDS_MANUAL = "needs_manual"; FAILED = "failed"

USER_STATUS_MAP: dict["JobInternalStatus", "JobUserStatus"] = {
    JobInternalStatus.UPLOADED: JobUserStatus.PROCESSING,
    JobInternalStatus.EVALUATING: JobUserStatus.PROCESSING,
    JobInternalStatus.EVALUATED: JobUserStatus.PROCESSING,
    JobInternalStatus.PROCESSING: JobUserStatus.PROCESSING,
    JobInternalStatus.PARTIAL_IMPORTED: JobUserStatus.PARTIAL_SUCCESS,
    JobInternalStatus.PARTIAL_FAILED: JobUserStatus.PARTIAL_SUCCESS,
    JobInternalStatus.FULL_IMPORTED: JobUserStatus.COMPLETED,
    JobInternalStatus.DEGRADED_HUMAN: JobUserStatus.NEEDS_MANUAL,
    JobInternalStatus.EVAL_FAILED: JobUserStatus.FAILED,
    JobInternalStatus.REJECTED: JobUserStatus.FAILED,
    JobInternalStatus.ORPHANED: JobUserStatus.FAILED,
    JobInternalStatus.CANCELLED: JobUserStatus.FAILED,
}

def compute_user_status(status: JobInternalStatus) -> JobUserStatus:
    """INV-10: user_status = f(status)"""
    return USER_STATUS_MAP[status]

ACTION_HINT_MAP: dict["JobUserStatus", str] = {
    JobUserStatus.PROCESSING: "等待处理中…",
    JobUserStatus.PARTIAL_SUCCESS: "部分完成，有页面待人工处理",
    JobUserStatus.COMPLETED: "可下载结果",
    JobUserStatus.NEEDS_MANUAL: "请检查标注队列",
    JobUserStatus.FAILED: "处理失败",
}

class PageStatus(StrEnum):
    PENDING = "PENDING"; BLANK = "BLANK"; AI_QUEUED = "AI_QUEUED"
    AI_PROCESSING = "AI_PROCESSING"; AI_COMPLETED = "AI_COMPLETED"; AI_FAILED = "AI_FAILED"
    HUMAN_QUEUED = "HUMAN_QUEUED"; HUMAN_PROCESSING = "HUMAN_PROCESSING"
    HUMAN_COMPLETED = "HUMAN_COMPLETED"; IMPORTED_CONFIRMED = "IMPORTED_CONFIRMED"
    IMPORTED_ASSUMED = "IMPORTED_ASSUMED"; IMPORT_FAILED = "IMPORT_FAILED"
    SKIPPED = "SKIPPED"; DEAD_LETTER = "DEAD_LETTER"

class SKUStatus(StrEnum):
    EXTRACTED = "EXTRACTED"; VALIDATED = "VALIDATED"; CONFIRMED = "CONFIRMED"
    BOUND = "BOUND"; EXPORTED = "EXPORTED"; SUPERSEDED = "SUPERSEDED"
    PARTIAL = "PARTIAL"; INVALID = "INVALID"

class TaskStatus(StrEnum):
    CREATED = "CREATED"; ASSIGNED = "ASSIGNED"; PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"; EXPIRED = "EXPIRED"; ESCALATED = "ESCALATED"

class ImageStatus(StrEnum):
    EXTRACTED = "EXTRACTED"; QUALITY_ASSESSED = "QUALITY_ASSESSED"
    ROLE_CLASSIFIED = "ROLE_CLASSIFIED"; DELIVERABLE = "DELIVERABLE"
    NOT_DELIVERABLE = "NOT_DELIVERABLE"

class WorkerStatus(StrEnum):
    ALIVE = "ALIVE"; SUSPECT = "SUSPECT"; DEAD = "DEAD"

class CalibrationStatus(StrEnum):
    PENDING = "PENDING"; APPROVED = "APPROVED"; REJECTED = "REJECTED"; APPLIED = "APPLIED"

class UpgradeStatus(StrEnum):
    PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"; APPLIED = "applied"

# §2.2 路由与评估
class RouteDecision(StrEnum):
    AUTO = "AUTO"; HYBRID = "HYBRID"; HUMAN_ALL = "HUMAN_ALL"

class DegradeReason(StrEnum):
    EVAL_FAILED = "eval_failed"; PRESCAN_REJECT = "prescan_reject"
    LOW_CONFIDENCE = "low_confidence"; BUDGET_EXHAUSTED = "budget_exhausted"
    CIRCUIT_OPEN = "circuit_open"

class CompletionSource(StrEnum):
    AI_ONLY = "AI_ONLY"; HUMAN_ONLY = "HUMAN_ONLY"
    HYBRID = "HYBRID"; DEGRADED_HUMAN = "DEGRADED_HUMAN"

# §2.3 页面分类
class PageType(StrEnum):
    A = "A"; B = "B"; C = "C"; D = "D"

class LayoutType(StrEnum):
    L1 = "L1"; L2 = "L2"; L3 = "L3"; L4 = "L4"

# §2.4 图片与绑定
class ImageRole(StrEnum):
    PRODUCT_MAIN = "PRODUCT_MAIN"; DETAIL = "DETAIL"; SCENE = "SCENE"
    LOGO = "LOGO"; DECORATION = "DECORATION"; SIZE_CHART = "SIZE_CHART"
    @property
    def is_deliverable(self) -> bool:
        return self in (ImageRole.PRODUCT_MAIN, ImageRole.DETAIL, ImageRole.SCENE, ImageRole.SIZE_CHART)

class QualityGrade(StrEnum):
    HIGH = "HIGH"; LOW_QUALITY = "LOW_QUALITY"; UNASSESSED = "UNASSESSED"

class BindingMethod(StrEnum):
    SPATIAL_PROXIMITY = "spatial_proximity"; GRID_ALIGNMENT = "grid_alignment"
    ID_MATCHING = "id_matching"; PAGE_INHERITANCE = "page_inheritance"

# §2.5 SKU 属性
class SKUValidity(StrEnum):
    VALID = "valid"; INVALID = "invalid"

class AttributeSource(StrEnum):
    AI_EXTRACTED = "AI_EXTRACTED"; HUMAN_CORRECTED = "HUMAN_CORRECTED"
    CROSS_PAGE_MERGED = "CROSS_PAGE_MERGED"; PROMOTED = "PROMOTED"

class ImportConfirmation(StrEnum):
    CONFIRMED = "confirmed"; ASSUMED = "assumed"; FAILED = "failed"; PENDING = "pending"

# §2.6 人工协作
class TaskPriority(StrEnum):
    NORMAL = "NORMAL"; HIGH = "HIGH"; URGENT = "URGENT"
    CRITICAL = "CRITICAL"; AUTO_RESOLVE = "AUTO_RESOLVE"

class SLALevel(StrEnum):
    NORMAL = "NORMAL"; HIGH = "HIGH"; CRITICAL = "CRITICAL"; AUTO_RESOLVE = "AUTO_RESOLVE"

class HumanTaskType(StrEnum):
    PAGE_PROCESS = "PAGE_PROCESS"; SKU_CONFIRM = "SKU_CONFIRM"
    ATTRIBUTE_CONFIRM = "ATTRIBUTE_CONFIRM"; BINDING_CONFIRM = "BINDING_CONFIRM"
    CLASSIFICATION_REVIEW = "CLASSIFICATION_REVIEW"

class AnnotationType(StrEnum):
    PAGE_TYPE_CORRECTION = "PAGE_TYPE_CORRECTION"
    TEXT_ROLE_CORRECTION = "TEXT_ROLE_CORRECTION"
    IMAGE_ROLE_CORRECTION = "IMAGE_ROLE_CORRECTION"
    SKU_ATTRIBUTE_CORRECTION = "SKU_ATTRIBUTE_CORRECTION"
    BINDING_CORRECTION = "BINDING_CORRECTION"
    CUSTOM_ATTR_CONFIRM = "CUSTOM_ATTR_CONFIRM"
    NEW_TYPE_REPORT = "NEW_TYPE_REPORT"
    LAYOUT_CORRECTION = "LAYOUT_CORRECTION"

# §2.7 配置与阈值
class SKUValidityMode(StrEnum):
    STRICT = "strict"; LENIENT = "lenient"

class CalibrationType(StrEnum):
    THRESHOLD = "THRESHOLD"; ATTR_PROMOTION = "ATTR_PROMOTION"

# §2.8 系统运维
class HealthStatus(StrEnum):
    HEALTHY = "healthy"; DEGRADED = "degraded"; UNHEALTHY = "unhealthy"

class ComponentStatus(StrEnum):
    OK = "ok"; DEGRADED = "degraded"; DOWN = "down"; CIRCUIT_OPEN = "circuit_open"

class ErrorSeverity(StrEnum):
    INFO = "info"; WARNING = "warning"; ERROR = "error"; CRITICAL = "critical"

# §2.9 SSE 事件
class SSEEventType(StrEnum):
    HEARTBEAT = "heartbeat"; PAGE_COMPLETED = "page_completed"
    PAGES_BATCH_UPDATE = "pages_batch_update"; JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"; HUMAN_NEEDED = "human_needed"
    SLA_ESCALATED = "sla_escalated"; SLA_AUTO_RESOLVE = "sla_auto_resolve"
    SLA_AUTO_ACCEPTED = "sla_auto_accepted"


# ===================================================================
# §INV-10 user_status 映射 (12 internal → 5 user)
# ===================================================================
USER_STATUS_MAP: dict[str, JobUserStatus] = {
    JobInternalStatus.UPLOADED:         JobUserStatus.PROCESSING,
    JobInternalStatus.EVALUATING:       JobUserStatus.PROCESSING,
    JobInternalStatus.EVAL_FAILED:      JobUserStatus.FAILED,
    JobInternalStatus.EVALUATED:        JobUserStatus.PROCESSING,
    JobInternalStatus.PROCESSING:       JobUserStatus.PROCESSING,
    JobInternalStatus.PARTIAL_FAILED:   JobUserStatus.PARTIAL_SUCCESS,
    JobInternalStatus.PARTIAL_IMPORTED: JobUserStatus.PARTIAL_SUCCESS,
    JobInternalStatus.DEGRADED_HUMAN:   JobUserStatus.NEEDS_MANUAL,
    JobInternalStatus.FULL_IMPORTED:    JobUserStatus.COMPLETED,
    JobInternalStatus.CANCELLED:        JobUserStatus.FAILED,
    JobInternalStatus.REJECTED:         JobUserStatus.FAILED,
    JobInternalStatus.ORPHANED:         JobUserStatus.PROCESSING,
}


def compute_user_status(internal: JobInternalStatus | str) -> JobUserStatus:
    """将内部状态映射为面向用户的 5 态。"""
    key = internal if isinstance(internal, str) else internal.value
    return USER_STATUS_MAP.get(key, JobUserStatus.PROCESSING)


ACTION_HINT_MAP: dict[str | JobUserStatus, str] = {
    JobUserStatus.PROCESSING:      "文件正在处理中，请稍候查看结果",
    JobUserStatus.PARTIAL_SUCCESS:  "部分页面处理完成，可查看已提取的 SKU",
    JobUserStatus.COMPLETED:        "所有 SKU 提取完成，请确认导入",
    JobUserStatus.NEEDS_MANUAL:     "需要人工协助，请前往标注队列处理",
    JobUserStatus.FAILED:           "处理失败，请检查文件后重新上传",
}
