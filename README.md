<p align="center">
  <img src="https://raw.githubusercontent.com/Twila-Digital/twila-credicarro-python-sdk/production/assets/logo-light.svg" alt="Credicarro" width="220" style="max-width: 100%;">
</p>

<p align="center">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/Twila-Digital/twila-credicarro-python-sdk"></a>
  <a href="https://github.com/Twila-Digital/twila-credicarro-python-sdk/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Twila-Digital/twila-credicarro-python-sdk/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/Twila-Digital/twila-credicarro-python-sdk/actions/workflows/quality.yml"><img alt="Quality" src="https://github.com/Twila-Digital/twila-credicarro-python-sdk/actions/workflows/quality.yml/badge.svg"></a>
  <a href="https://github.com/Twila-Digital/twila-credicarro-python-sdk/security/code-scanning"><img alt="Security" src="https://github.com/Twila-Digital/twila-credicarro-python-sdk/actions/workflows/security.yml/badge.svg"></a>
  <a href="https://codecov.io/gh/Twila-Digital/twila-credicarro-python-sdk"><img alt="Coverage" src="https://codecov.io/gh/Twila-Digital/twila-credicarro-python-sdk/branch/production/graph/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-539E43">
</p>

# twila-credicarro

SDK oficial em Python para a API do [Credicarro](https://documentacao.credicarro.com.br) — financiamento e refinanciamento de veículos: cadastro do cliente, simulação, proposta, envio de documentos e webhooks.

> Uso restrito a server-side. O `client_secret` nunca deve ser embarcado em um app mobile, SPA ou qualquer código que rode no navegador/dispositivo do usuário final.

## Compatibilidade

| Runtime | Versões aceitas |
| --- | --- |
| Python | 3.9 ou superior (CI cobre 3.9, 3.10, 3.11, 3.12, 3.13 e 3.14) |

Cliente síncrono, baseado em [httpx](https://www.python-httpx.org/), com tipos totalmente anotados (`py.typed`, PEP 561).

## Instalação

```bash
pip install twila-credicarro
```

## Quick start

```python
from twila_credicarro import CredicarroClient, CredicarroClientOptions, CredicarroEnvironment

client = CredicarroClient(
    CredicarroClientOptions(
        client_id="<seu-client-id>",
        client_secret="<seu-client-secret>",
        environment=CredicarroEnvironment.STAGING,  # o padrão é PRODUCTION
    )
)
```

`CredicarroClient` é thread-safe e deve ser reaproveitado como singleton na sua aplicação — ele mantém o cache do token de acesso e o estado do circuit breaker. Feche-o só no shutdown (`client.close()`, ou use como context manager: `with CredicarroClient(options) as client:`).

O token é gerado e renovado sozinho: fica em cache até o `expira_em` devolvido pela API (sem `expira_em`, vale `agora + max(expira_em_segundos / 2, expira_em_segundos − 60)`) e, se uma rota responder `401`, o SDK renova o token e repete a chamada uma única vez.

### Fluxo completo: cliente, simulação e proposta

```python
from twila_credicarro import (
    CreateFinancingSimulationRequest,
    CreateProposalRequest,
    CustomerAddress,
    OccupationType,
    ProfessionalData,
    UpsertCustomerRequest,
)

cpf = "12345678909"

# 1. Cadastre o cliente (dados pessoais, endereço e ocupação/renda em uma chamada).
client.customers.upsert(
    UpsertCustomerRequest(
        cpf=cpf,
        first_name="Maria",
        last_name="Souza",
        email="maria.souza@exemplo.com.br",
        phone_number="+55 (11) 99876-5432",
        date_of_birth="1990-05-20T00:00:00-03:00",
        address=CustomerAddress(
            street="Av. Paulista",
            number="1578",
            neighborhood="Bela Vista",
            city="São Paulo",
            state="SP",
            postal_code="01311000",
        ),
        professional_data=ProfessionalData(occupation=OccupationType.EMPLOYEE, monthly_income=6500.0),
    )
)

# 2. Simule: uma opção por prazo.
opcoes = client.simulations.create_financing(
    CreateFinancingSimulationRequest(
        cpf=cpf,
        license_plate="ABC1D23",
        vehicle_amount=45000,
        down_payment=9000,
        state="SP",
        is_zero_km=False,
        store_cnpj="11.222.333/0001-81",
    )
)

# 3. Crie a proposta com a opção escolhida.
proposal_id = client.proposals.create(CreateProposalRequest(cpf=cpf, simulation_id=opcoes[0].simulation_id))
```

Os identificadores (`proposal_id`, `simulation_id`, `webhook_id`) são aceitos como `str` ou `uuid.UUID`, e as respostas devolvem `str`. `date_of_birth` aceita texto ISO-8601 com offset, `date` ou `datetime` (sem fuso, o SDK usa `-03:00`, o horário de Brasília da documentação).

### O que o integrador precisa fazer agora

```python
proposta = client.proposals.get(proposal_id)

for acao in proposta.get_pending_actions():
    print(acao.participant, acao.kind, acao.document_types)
```

`get_pending_actions()` olha a etapa ativa de cada participante (comprador, vendedor e loja) e devolve só o que depende do integrador (`ActionOwner.INTEGRATOR`):

| Etapa | `PendingActionKind` | O que enviar |
| --- | --- | --- |
| 6 `ENVIO_DOCUMENTOS` | `SEND_DOCUMENTS` | documentos com status `PENDING` (`document_types`) |
| 7 `CORRECAO_DOCUMENTOS` | `CORRECT_DOCUMENTS` | documentos com status `INVALID` (`document_types`) |
| 8 `DADOS_VEICULO` | `SEND_VEHICLE_DETAILS` | `client.proposals.send_vehicle_details(...)` |
| 5 `CONTA_RECEBIMENTO` | `SEND_DEPOSIT_ACCOUNT` | `client.proposals.send_deposit_account(...)` (refinanciamento) |

### Enviando documentos

```python
from twila_credicarro import DocumentFile, DocumentType, ProposalDocumentUpload, ProposalParticipant

client.proposals.upload_document(
    proposal_id,
    ProposalDocumentUpload(
        participant=ProposalParticipant.BUYER,
        document_type=DocumentType.CNH,
        file=DocumentFile.from_file("cnh-comprador.pdf"),  # ou from_bytes(bytes, nome) / from_stream(stream, nome)
    ),
    idempotency_key="envio-7f3c2a10-comprador-cnh",  # recomendado: guarde uma chave por envio
)
```

`DocumentFile` valida o arquivo antes de chamar a API (também na construção direta): nome sem caminho com até 255 caracteres, extensão `.pdf`, `.jpg`, `.jpeg` ou `.png`, de 1 byte a 10 MiB, e Base64 puro. `from_file` e `from_stream` leem em laço com limite de 10 MiB + 1 byte (não confiam no tamanho informado). O conteúdo é guardado uma só vez e o corpo é serializado uma só vez: as tentativas e o replay do 401 reaproveitam os mesmos bytes. A `Idempotency-Key` é **obrigatória** na API: persista uma chave por envio e reaproveite-a nas retentativas desse envio; use uma chave **nova** ao reenviar um documento recusado. Sem `idempotency_key`, o SDK gera uma e a repete em todas as tentativas daquela chamada. A chave explícita tem de 1 a 200 caracteres ASCII imprimíveis (não só espaços); senão a chamada lança `ValueError` antes de qualquer requisição. O orçamento total do upload é `document_upload_attempt_timeout_ms × max_retry_attempts` (padrão 180 s); as demais chamadas usam `total_timeout_ms` (30 s).

## Clientes por recurso

| Cliente | Métodos |
| --- | --- |
| `client.customers` | `upsert`, `create`, `upsert_address`, `upsert_professional_data` |
| `client.simulations` | `get_financing_range`, `get_refinancing_range`, `create_financing`, `create_refinancing`, `get`, `list` |
| `client.proposals` | `create`, `get`, `list`, `send_vehicle_details`, `send_deposit_account`, `upload_document` |
| `client.webhooks` | `create`, `list`, `update`, `delete` |
| `client.v1.simulations` | `get_financing_range`, `get_refinancing_range`, `create_financing`, `create_refinancing` (sem `cnpjLoja`) |
| `client.v1.proposals` | `create`, `get` (retorna `ProposalSummary`) |

Todas as rotas públicas do `openapi.yaml` (v1 e v2) têm um método. Prefira a v2 (`client.simulations`, `client.proposals`), que seleciona a loja pelo CNPJ e traz o retrato completo da proposta; `client.v1` existe para integrações que ainda usam as rotas v1.

## Idempotência e repetição de chamadas

- **`Idempotency-Key` automática** (um UUID por chamada lógica, **o mesmo em todas as tentativas**): `customers.create`, `upsert_address`, `upsert_professional_data`, as simulações (v1 e v2), `proposals.create` (v1 e v2) e `upload_document`.
- **`customers.upsert` nunca recebe chave automática.** Com chave, a rota só cria (CPF existente → `409 Cpf.CpfAlreadyAdded`); sem chave, faz upsert. Por isso, sem `idempotency_key` explícita a chamada **não é repetida** em caso de falha; com ela, passa a ser repetida com a mesma chave.
- **Repetições seguras:** `GET`, a geração do token, `POST` com `Idempotency-Key`, `send_vehicle_details` e `send_deposit_account` (reenviar substitui), `PUT`/`DELETE` de webhook. `webhooks.create` **nunca** é repetido.
- **Status repetidos:** `408`, `429` (respeitando `Retry-After` em segundos ou data HTTP; valor inválido, ≤ 0 ou não finito é ignorado, e o máximo considerado é 24 h), `500` (padrão `retry_on_500=True`, porque a documentação manda repetir `500` com a mesma chave), `502`, `503`, `504`, falha de rede e timeout da tentativa. Nenhum outro `4xx` é repetido.
- Se o `Retry-After` for maior que o orçamento restante, o SDK **não espera**: lança logo o `CredicarroRateLimitError` com `retry_after_ms`. Toda espera é limitada ao orçamento restante.
- Redirecionamentos (`3xx`) não são seguidos, na API e no token: viram `CredicarroApiError`.
- Com `disable_automatic_idempotency_key=True` o SDK não gera chaves (exceto no envio de documento, onde o header é obrigatório) e essas rotas deixam de ser repetidas.

```python
from twila_credicarro import CredicarroClientOptions, CredicarroResilienceOptions

options = CredicarroClientOptions(
    client_id="...",
    client_secret="...",
    resilience=CredicarroResilienceOptions(
        total_timeout_ms=30_000,  # padrão
        attempt_timeout_ms=10_000,  # padrão
        document_upload_attempt_timeout_ms=60_000,  # padrão
        max_retry_attempts=3,  # padrão
        retry_base_delay_ms=500,  # padrão (com jitter)
        retry_on_500=True,  # padrão
        # circuit breaker: 50% de falhas, janela de 30 s, mínimo de 10 chamadas, aberto por 15 s
    ),
)
```

## Paginação

`proposals.list`, `simulations.list` e `webhooks.list` retornam um `PagedResult[T]` — sem auto-paginação, você controla o avanço de página. `ListRequest(page=1, page_size=10)` aceita `page >= 1` e `page_size` de 1 a 100 (`pagina_inicial` e `limite` na API) e lança `ValueError` fora disso.

```python
from twila_credicarro import ListRequest

page = client.proposals.list(ListRequest(page=1, page_size=20))

for proposta in page.items:
    print(proposta.id, proposta.status)

if page.has_next:
    proxima = client.proposals.list(ListRequest(page=page.page + 1, page_size=20))
```

## Enums

Todos os enums lidos da API (`ProposalStatus`, `ProposalStep`, `StepSituation`, `ActionOwner`, `BiometryStatus`, `DocumentStatus`, `DocumentType`, `WebhookType`, ...) têm o membro `UNKNOWN = -1`: um valor novo da API nunca quebra a leitura. O valor bruto fica ao lado (`status_raw`, `status_name`, `step_raw`, `type_raw`, ...).

## Tratamento de erros

| Erro | Quando |
| --- | --- |
| `CredicarroConfigurationError` | Configuração inválida (ex.: `client_id`/`client_secret` ausentes, `base_url` fora de https) |
| `CredicarroAuthenticationError` | Falha ao gerar o token (`401 Integration.Authentication.InvalidCredentials`, `400`) ou `401` persistente |
| `CredicarroValidationError` | `400` — dados inválidos, com `field` e `errors` |
| `CredicarroBusinessRuleError` | `422` — regra de negócio (ex.: `Store.Integration.Intermediation`) |
| `CredicarroRateLimitError` | `429`, com `retry_after_ms` |
| `CredicarroTimeoutError` | Timeout de rede, timeout total, ou circuit breaker aberto |
| `CredicarroApiError` | Qualquer outro erro de API (`403`, `404`, `409`, `5xx`) — base de `Validation`, `BusinessRule` e `RateLimit` |
| `CredicarroWebhookSignatureError` | Assinatura de webhook inválida, fora da tolerância ou corpo ilegível |

Todos herdam de `CredicarroError`. Trate pelo `error_code` (o campo `tipo`, código estável como `Customer.Account.NotFound`), não pela mensagem:

```python
from twila_credicarro import CredicarroApiError, CredicarroBusinessRuleError

try:
    client.proposals.create(CreateProposalRequest(cpf=cpf, simulation_id=simulation_id))
except CredicarroBusinessRuleError as error:
    if error.error_code == "Proposal.SimulationAlreadyExpired":
        ...  # faça uma nova simulação
except CredicarroApiError as error:
    print(error.status_code, error.error_code, error.title)
```

A mensagem da exceção traz só o status, o `tipo` e o `titulo`. `detail`, `field`, `errors` e `raw_body` (que podem conter dados pessoais) ficam em propriedades — não os registre em log. Quando a API responde no formato padrão (`type`, `title`, `detail`) o SDK usa esses campos no lugar dos em português, e um `401` sem corpo vira `CredicarroAuthenticationError`. O `client_secret` e o token nunca aparecem em `repr`, mensagem ou log do SDK, nem em variáveis locais comuns (ficam em objetos com `repr` mascarado). O `repr` das requisições e respostas mascara CPF (`***.456.789-**`), e-mail, celular, data de nascimento, renda, dados da conta bancária e credenciais (`***`); `detail`, `errors` e `raw_body` não entram em `repr` nem em `str`.

Falha de rede (conexão recusada, DNS, reset) ou timeout, depois das tentativas, vira `CredicarroTimeoutError` ("Falha de rede ou timeout"), inclusive na geração do token. A exceção guarda só o nome do tipo do erro: o objeto de requisição do httpx (com `Authorization` e corpo) nunca fica como causa nem contexto. Quando o circuit breaker está aberto a chamada também lança `CredicarroTimeoutError`; a tentativa de meia-abertura é sempre encerrada, mesmo que termine por exceção.

## Webhooks

### Cadastro

```python
from twila_credicarro import CreateWebhookRequest, WebhookAuthenticationType, WebhookType

resultado = client.webhooks.create(
    CreateWebhookRequest(
        type=WebhookType.PROPOSAL,
        url="https://parceiro.com.br/webhooks/credicarro",
        authentication_type=WebhookAuthenticationType.BASIC,
        credential="dXN1YXJpbzpzZW5oYQ==",  # Base64 de usuario:senha (Basic) ou o token (Jwt)
    )
)

guarde_com_seguranca(resultado.signing_secret)  # só vem nesta resposta
```

### Validando as notificações

Valide sempre contra o **corpo bruto** da requisição (nunca reformate o JSON) e responda `401` se a assinatura for inválida:

```python
from twila_credicarro import CredicarroWebhookSignatureError, parse_webhook_event

try:
    evento = parse_webhook_event(
        corpo_bruto,  # str ou bytes, exatamente como recebido
        request.headers.get("X-CrediCarro-Signature"),  # t={timestamp},v1={assinatura}
        segredo_assinatura,
    )
except CredicarroWebhookSignatureError:
    ...  # responda 401

print(evento.proposal_id, evento.status, evento.is_detailed)
```

- Assinatura: HMAC-SHA256 de `"{t}.{corpo bruto}"` com o `segredo_assinatura` em UTF-8, em hexadecimal minúsculo, comparada em tempo constante. Segredo vazio é sempre inválido.
- `t` ou `v1` repetidos no cabeçalho tornam a assinatura inválida. O corpo precisa trazer `id_proposta` em formato UUID. `tolerance` precisa ser um `timedelta` ≥ 0 (senão `ValueError`).
- O timestamp `t` (1 a 10 dígitos ASCII) precisa estar a até 5 minutos de agora, nos dois sentidos (`tolerance=` ajusta; `now=` permite injetar o relógio nos testes).
- `verify_webhook_signature(...)` devolve `bool` sem lançar exceção; `verify_webhook_authorization(recebido, esperado)` compara o SHA-256 dos dois valores do header `Authorization` (Basic/Jwt) em tempo constante (esperado vazio nunca é aceito); `parse_webhook_payload(corpo)` interpreta sem verificar (só para testes).
- O mesmo `ProposalWebhookEvent` cobre os dois formatos: o payload v1 (`id_proposta`, `enum_status`, `status` em inglês) e o payload v2 (`is_detailed=True`, com `event_reason`, `refusal_reason`, `event_date` e os participantes `buyer`, `seller` e `store`, no mesmo formato de `ProposalDetails`).
- `evento.get_pending_actions()` (ou `get_pending_actions(evento)`) lista as ações do integrador no payload v2; o payload v1 não traz participantes, então consulte a proposta (`client.proposals.get`).
- Deduplique pelo header `Idempotency-Key` da notificação e responda `2xx` rápido, processando de forma assíncrona.

## Samples

- `samples/sample_plain` — script standalone: cliente, simulação, proposta e ações pendentes
- `samples/sample_flask` — `CredicarroClient` como singleton na app factory e receptor de webhook com assinatura verificada

## Qualidade, segurança e cobertura

- **Build/Test** (`ci.yml`) — `ruff`, `mypy --strict` e a suíte de testes (`pytest` + `respx`) em Python 3.9–3.14.
- **Contract tests** (`contract-tests.yml`) — conferem os wire types do SDK contra o `openapi.yaml` público (`https://documentacao.credicarro.com.br/openapi.yaml`); rodam todo dia e antes de cada release.
- **Quality** (`quality.yml`) — análise estática via Codacy CLI (pylint), resultados publicados na aba **Security → Code scanning** do repositório.
- **Security** (`security.yml`) — [CodeQL](https://codeql.github.com/) para Python, rodando a cada PR/push e semanalmente.
- **Coverage** — cobertura de testes coletada via `pytest-cov` e publicada no [Codecov](https://codecov.io/gh/Twila-Digital/twila-credicarro-python-sdk).

## Documentação completa

[documentacao.credicarro.com.br](https://documentacao.credicarro.com.br) — referência de todos os endpoints, autenticação, erros, etapas e status, documentos e webhooks.

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md).

## Código de conduta

Este projeto segue o [Código de Conduta](CODE_OF_CONDUCT.md).

## Licença

[MIT](LICENSE)
