from typing import Any

from ..masking import MASK, SecretStr


class TokenCredentials:
    """`clientId`/`clientSecret` da integração. O segredo não aparece em `repr`, `str` nem em variáveis locais
    (só o corpo é montado, no último instante, dentro da chamada)."""

    __slots__ = ("_client_id", "_client_secret")

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = SecretStr(client_secret)

    def as_request_body(self) -> dict[str, Any]:
        return {"clientId": self._client_id, "clientSecret": str(self._client_secret)}

    def __repr__(self) -> str:
        return f"TokenCredentials(client_id={self._client_id!r}, client_secret='{MASK}')"

    __str__ = __repr__

    def __reduce__(self) -> Any:
        raise TypeError("TokenCredentials não pode ser serializado.")
