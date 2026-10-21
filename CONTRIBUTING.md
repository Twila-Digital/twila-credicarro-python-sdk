# Contribuindo

## Pré-requisitos

- Python 3.9+
- `pip`

## Build e testes

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

mypy
ruff check .
pytest
```

Os contract tests (`contract_tests/`) baixam o `openapi.yaml` público (`https://documentacao.credicarro.com.br/openapi.yaml`) e conferem os wire types do SDK contra ele. Não rodam por padrão e precisam de rede:

```bash
pytest contract_tests

# outra fonte do contrato (URL ou caminho de arquivo)
CREDICARRO_CONTRACT_TESTS_OPENAPI_URL=./openapi.yaml pytest contract_tests
```

## Instalando a partir do código-fonte

Enquanto o pacote não é publicado no PyPI, instale direto do repositório:

```bash
pip install git+https://github.com/Twila-Digital/twila-credicarro-python-sdk.git@production
```

Ou clone e instale em modo editável (`pip install -e .`) a partir de uma cópia local.

## Abrindo um PR

1. Crie uma branch a partir de `production`
2. Adicione testes para qualquer mudança de comportamento
3. Rode `mypy && ruff check . && pytest` localmente antes de abrir o PR
4. Abra o PR contra `production` — o CI roda testes automaticamente

Regras do projeto: mensagens de erro e documentação em português do Brasil; nada de segredos reais em código, testes ou exemplos; o `client_secret` nunca pode aparecer em `repr`, mensagem de erro ou log.

## Release (publicação no PyPI)

O PyPI suporta **Trusted Publishing (OIDC)** desde 2023 — o mais maduro entre os registries que usamos. A action oficial [`pypa/gh-action-pypi-publish`](https://github.com/pypa/gh-action-pypi-publish) troca o token OIDC do GitHub Actions por uma credencial de publish de curta duração, sem precisar de um token de longa duração guardado como secret.

Antes do primeiro release, alguém com acesso à conta/organização do PyPI precisa configurar um **Trusted Publisher** (funciona mesmo com o projeto ainda não existindo no PyPI — "pending publisher"):

- Em [pypi.org](https://pypi.org/manage/account/publishing/) (ou na página do projeto, se ele já existir): **Add a pending publisher**
  - **PyPI Project Name:** `twila-credicarro`
  - **Owner:** `Twila-Digital`
  - **Repository name:** `twila-credicarro-python-sdk`
  - **Workflow name:** `release.yml`
  - **Environment name:** `production`

No repositório do GitHub, criar o [environment](https://docs.github.com/actions/deployment/targeting-different-environments/using-environments-for-deployment) `production` (Settings → Environments) com **Required reviewers** configurado. Nenhum secret de registry é necessário — a credencial de publish inteira vem do OIDC em runtime.

Com isso configurado, `git push --tags` numa tag `v*` (ex.: `v1.0.0`) dispara build → testes → contract tests → **pausa esperando aprovação manual do `environment` `production`** → publish no PyPI (Trusted Publishing) → GitHub Release.

O primeiro `pypi-publish` via OIDC contra um "pending publisher" já cria o projeto no PyPI — não precisa de um publish manual prévio (diferente do npm).

## Reportando problemas

Abra uma [issue](https://github.com/Twila-Digital/twila-credicarro-python-sdk/issues) com passos para reproduzir, versão do pacote/Python e o comportamento esperado vs. observado. Nunca inclua `client_id`/`client_secret` reais no relato.
