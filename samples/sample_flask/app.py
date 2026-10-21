"""Sample Flask: CredicarroClient como singleton e receptor de webhook seguro.

Variáveis de ambiente: CREDICARRO_CLIENT_ID, CREDICARRO_CLIENT_SECRET e CREDICARRO_WEBHOOK_SECRET (o
`segredo_assinatura` devolvido uma única vez no cadastro do webhook; obrigatório). Se o webhook usa Basic ou Jwt,
defina também CREDICARRO_WEBHOOK_AUTHORIZATION com o valor completo esperado do header Authorization.
"""

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from flask import Flask, Response, request

from twila_credicarro import (
    CredicarroApiError,
    CredicarroClient,
    CredicarroClientOptions,
    CredicarroEnvironment,
    CredicarroWebhookSignatureError,
    parse_webhook_event,
    verify_webhook_authorization,
    verify_webhook_signature,
)


class MemoryDedupStore:
    """Deduplicação atômica. Em produção: Redis `SET chave 1 NX EX <ttl>` (claim) e `DEL chave` (release)."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def claim(self, key: str) -> bool:
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            return True

    def release(self, key: str) -> None:
        with self._lock:
            self._seen.discard(key)


def create_app() -> Flask:
    signing_secret = os.environ.get("CREDICARRO_WEBHOOK_SECRET")
    if not signing_secret:
        raise RuntimeError("CREDICARRO_WEBHOOK_SECRET é obrigatória")
    expected_authorization = os.environ.get("CREDICARRO_WEBHOOK_AUTHORIZATION")

    client = CredicarroClient(
        CredicarroClientOptions(
            client_id=os.environ["CREDICARRO_CLIENT_ID"],
            client_secret=os.environ["CREDICARRO_CLIENT_SECRET"],
            environment=CredicarroEnvironment.STAGING,
        )
    )
    dedup = MemoryDedupStore()
    executor = ThreadPoolExecutor(max_workers=4)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

    @app.errorhandler(413)
    def payload_too_large(_error: Exception) -> Response:
        return Response(status=413)

    def process(proposal_id: str) -> None:
        proposal = client.proposals.get(proposal_id)
        print(f"proposta {proposal.id}: {len(proposal.get_pending_actions())} ação(ões) pendente(s)")

    def log_failure(proposal_id: str, future: "Future[None]") -> None:
        error = future.exception()
        if error is not None:
            code = error.error_code if isinstance(error, CredicarroApiError) else None
            print(f"falha ao processar webhook | Proposta: {proposal_id} | {type(error).__name__} | {code}")

    @app.post("/webhooks/credicarro")
    def credicarro_webhook() -> Response:
        raw = request.get_data()
        signature = request.headers.get("X-CrediCarro-Signature", "")

        if expected_authorization and not verify_webhook_authorization(
            request.headers.get("Authorization"), expected_authorization
        ):
            return Response(status=401)

        if not verify_webhook_signature(raw, signature, signing_secret):
            return Response(status=401)

        try:
            event = parse_webhook_event(raw, signature, signing_secret)
        except CredicarroWebhookSignatureError:
            return Response(status=400)

        idempotency_key = request.headers.get("Idempotency-Key", "")
        if idempotency_key and not dedup.claim(idempotency_key):
            return Response(status=200)

        try:
            future = executor.submit(process, event.proposal_id)
            future.add_done_callback(lambda done: log_failure(event.proposal_id, done))
        except RuntimeError:
            if idempotency_key:
                dedup.release(idempotency_key)
            return Response(status=503)

        return Response(status=200)

    return app


if __name__ == "__main__":
    create_app().run()
