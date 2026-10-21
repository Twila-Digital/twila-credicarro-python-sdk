import re

_ACCESS_TOKEN_PATH = "v1/authentication/accesstoken"

_AUTOMATIC_KEY_PATTERN = re.compile(
    r"^(?:"
    r"v1/customer(?:/address|/professional)?"
    r"|v[12]/proposal/simulation/(?:financing|refinancing)"
    r"|v[12]/proposal"
    r"|v2/proposal/[^/]+/document"
    r")$"
)

_MANDATORY_KEY_PATTERN = re.compile(r"^v2/proposal/[^/]+/document$")

_REPLACEMENT_POST_PATTERN = re.compile(r"^v2/proposal/[^/]+/(?:vehicle-detail|deposit-account)$")

_WEBHOOK_ITEM_PATTERN = re.compile(r"^v1/webhook/[^/]+$")


def normalize_path(path: str) -> str:
    return path.split("?", 1)[0].strip("/")


def requires_idempotency_key(method: str, path: str) -> bool:
    if method.upper() != "POST":
        return False

    return _AUTOMATIC_KEY_PATTERN.match(normalize_path(path)) is not None


def idempotency_key_is_mandatory(method: str, path: str) -> bool:
    if method.upper() != "POST":
        return False

    return _MANDATORY_KEY_PATTERN.match(normalize_path(path)) is not None


def is_retry_safe(method: str, path: str, has_idempotency_key: bool) -> bool:
    upper_method = method.upper()
    normalized = normalize_path(path)

    if upper_method in ("GET", "HEAD", "OPTIONS"):
        return True

    if upper_method in ("PUT", "DELETE"):
        return _WEBHOOK_ITEM_PATTERN.match(normalized) is not None

    if upper_method != "POST":
        return False

    if normalized == _ACCESS_TOKEN_PATH:
        return True

    if _REPLACEMENT_POST_PATTERN.match(normalized):
        return True

    return has_idempotency_key
