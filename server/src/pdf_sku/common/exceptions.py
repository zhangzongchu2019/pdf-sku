"""
异常体系。对齐: Data Dictionary §4.3 错误码。
每个异常携带 code + http_status + severity。
"""
from __future__ import annotations


class PDFSKUError(Exception):
    """基类异常。"""
    code: str = "UNKNOWN_ERROR"
    http_status: int = 400
    severity: str = "error"

    def __init__(self, message: str = "", code: str | None = None):
        self.message = message
        if code:
            self.code = code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error_code": self.code, "message": self.message, "severity": self.severity}


# === 文件校验 ===
class FileSizeExceededError(PDFSKUError):
    code = "FILE_SIZE_EXCEEDED"; http_status = 413

class PageCountExceededError(PDFSKUError):
    code = "PAGE_COUNT_EXCEEDED"; http_status = 413

class SecurityJavascriptError(PDFSKUError):
    code = "SECURITY_JAVASCRIPT"; http_status = 422

class SecurityEncryptedError(PDFSKUError):
    code = "SECURITY_ENCRYPTED"; http_status = 422

class FileHashDuplicateError(PDFSKUError):
    code = "FILE_HASH_DUPLICATE"; http_status = 409


# === Job 操作 ===
class JobNotFoundError(PDFSKUError):
    code = "JOB_NOT_FOUND"; http_status = 404

class JobNotOrphanedError(PDFSKUError):
    code = "JOB_NOT_ORPHANED"; http_status = 409


# === Task 操作 ===
class TaskAlreadyLockedError(PDFSKUError):
    code = "TASK_ALREADY_LOCKED"; http_status = 409

class TaskLockExpiredError(PDFSKUError):
    code = "TASK_LOCK_EXPIRED"; http_status = 410

class TaskNotRevertableError(PDFSKUError):
    code = "TASK_NOT_REVERTABLE"; http_status = 409

class AnnotationValidationError(PDFSKUError):
    code = "ANNOTATION_VALIDATION"; http_status = 422


# === Config ===
class ConfigVersionConflictError(PDFSKUError):
    code = "CONFIG_VERSION_CONFLICT"; http_status = 409

class ConfigThresholdInvalidError(PDFSKUError):
    code = "CONFIG_THRESHOLD_INVALID"; http_status = 422

class ConfigNotFoundError(PDFSKUError):
    code = "CONFIG_NOT_FOUND"; http_status = 404


# === LLM ===
class LLMBudgetExhaustedError(PDFSKUError):
    code = "LLM_BUDGET_EXHAUSTED"; http_status = 503; severity = "critical"

class LLMCircuitOpenError(PDFSKUError):
    code = "LLM_CIRCUIT_OPEN"; http_status = 503; severity = "critical"

class LLMRateLimitedError(PDFSKUError):
    code = "LLM_RATE_LIMITED"; http_status = 429; severity = "warning"


# === Pipeline ===
class RetryableError(PDFSKUError):
    code = "RETRYABLE_ERROR"; http_status = 500

class DegradeError(PDFSKUError):
    code = "DEGRADE_ERROR"; http_status = 500

class EvalFailedError(PDFSKUError):
    code = "EVAL_FAILED"; http_status = 500
