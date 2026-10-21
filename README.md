<p align="center">
  <img src="docs/images/logo.png" width="220" alt="Argo">
</p>

<h1 align="center">Argo<br><sub><sup><sup><sub>Copyright (©) 2026 Erik Pimenta</sub></sup></sup></sub></h1>

<p align="center">
  Plataforma de microserviços para vendas: vários vendedores cadastram produtos, o estoque muda em tempo real e cada pedido é confirmado por uma fila, sem travar a compra.<br>
  Pronta para usar, estudar ou adaptar ao seu negócio.
</p>

<p align="center">
  Python 3.13 · Django 6 · Django REST Framework · Celery · Redis · MySQL 8.4 · Java 21 · Spring Boot 4 · Docker Compose · Pytest · JUnit
</p>

---

> **Manual completo:** [`Manual-Argo.pdf`](Manual-Argo.pdf) explica a arquitetura, instalação, configuração, cada tela, a API, as filas, a segurança, os testes e a solução de problemas, passo a passo (cópia em [`docs/`](docs/Manual-Argo.pdf)).

> **Banco de dados:** [`Banco-de-Dados-Argo.pdf`](Banco-de-Dados-Argo.pdf) traz o diagrama de relacionamentos que cada banco deve seguir, todas as tabelas com campos, tipos e chaves, as regras de cada uma e como parear o MySQL.

<p align="center">
  <img src="docs/images/tela-painel.png" alt="Visão geral do vendedor com vendas por dia, mais vendidos e situação dos pedidos">
</p>

## O que o Argo faz

- **Cadastro e papéis:** qualquer pessoa cria conta de Cliente ou Vendedor. O Administrador cria outros administradores, troca papéis e bloqueia contas.
- **Catálogo multivendedor:** cada vendedor cuida dos próprios produtos, com preço, categoria, estoque mínimo e histórico de toda movimentação (entrada, saída, contagem, venda e devolução).
- **Estoque em tempo real:** toda alteração é publicada no Redis e chega na hora a todas as telas abertas por Server-Sent Events.
- **Checkout assíncrono:** o pedido responde `202 Accepted` em milissegundos. A baixa no estoque, o e-mail de confirmação e a nota fiscal acontecem na fila do Celery.
- **Faturamento em Java:** um serviço Spring Boot emite e cancela as notas, com o valor aproximado dos tributos, aceitando o mesmo token emitido pelo serviço de identidade em Django.
- **Painel por papel:** faturamento, ticket médio, vendas por dia, mais vendidos e pedidos por situação, cada um vendo só o que lhe cabe.
- **Documentação viva:** Swagger dos quatro serviços em uma única página (OpenAPI 3.1 gerado pelo drf-spectacular nos serviços Django), com exemplos, erros documentados e botão de autorização.

## Arquitetura

```mermaid
flowchart LR
    UI["Navegador<br/>HTML, CSS e JS"] -->|HTTPS| GW["Gateway Nginx<br/>/api/*"]
    GW --> ID["Identidade<br/>Django · DRF"]
    GW --> CAT["Catálogo e estoque<br/>Django · DRF"]
    GW --> ORD["Pedidos<br/>Django · DRF"]
    GW --> BIL["Faturamento<br/>Spring Boot"]
    ORD -- "consulta preço" --> CAT
    ORD -- "publica tarefa" --> R[("Redis<br/>fila + pub/sub")]
    R --> W["Worker Celery<br/>settings do Django"]
    W -- "baixa estoque" --> CAT
    W -- "confirma pedido" --> ORD
    W -- "emite nota" --> BIL
    W -- "SMTP" --> M["E-mail"]
    CAT -- "eventos de estoque" --> R
    ID --- P1[("argo_identity")]
    CAT --- P2[("argo_catalog")]
    ORD --- P3[("argo_orders")]
    BIL --- P4[("argo_billing")]
```

| Serviço | Linguagem | Responsabilidade |
|---|---|---|
| `identity` | Python · Django · DRF | Cadastro, login, JWT de acesso, refresh token com rotação e gestão de usuários |
| `catalog` | Python · Django · DRF | Produtos, estoque com trava de linha, histórico e eventos em tempo real (view assíncrona com SSE) |
| `orders` | Python · Django · DRF | Checkout, situação dos pedidos, cancelamento e indicadores |
| `worker` | Python · Celery | Baixa no estoque, e-mail de confirmação (`django.core.mail`), nota fiscal e devoluções |
| `billing` | Java · Spring Boot | Emissão e cancelamento das notas fiscais |
| `gateway` | Nginx | Interface web, documentação e roteamento de `/api/<serviço>` |

Cada serviço tem o **próprio banco** dentro do mesmo MySQL e nunca lê o banco de outro. O que um serviço precisa de outro chega por HTTP com `X-Internal-Token` ou pela fila.

### Como o Django está organizado

Os três serviços Python são **um único projeto Django** (`backend/`). A variável `ARGO_SERVICE` decide qual serviço o processo vira: ele instala só o app daquele serviço, liga só o banco dele e responde só em `/api/<serviço>/`.

| Parte | Onde | O que faz |
|---|---|---|
| Configuração | `argo/settings.py` | Tudo vem das variáveis `ARGO_*`. `ARGO_SERVICE` = `identity`, `catalog`, `orders`, `worker` ou `all` (os três juntos, para desenvolvimento e testes) |
| Modelos e migrações | `argo/<serviço>/models.py` · `migrations/` | Tabelas com CHECK, índices nomeados e `ON DELETE CASCADE` no próprio banco (`DB_CASCADE` do Django 6.1) |
| API REST | `views.py` · `serializers.py` · `urls.py` | Django REST Framework com JWT, permissões por papel e erros num formato único (`argo/common/security.py` e `errors.py`) |
| Documentação | drf-spectacular | OpenAPI 3.1 de cada serviço em `/api/<serviço>/openapi.json`, lido pela página `/docs/` |
| Tempo real | `argo/catalog/views.py` | `GET /stock/stream` é uma view assíncrona do Django, servida pelo Daphne (ASGI), que repassa o Pub/Sub do Redis por Server-Sent Events |
| Fila | `argo/worker/` · `argo/orders/dispatch.py` | Celery configurado pelas settings do Django (`CELERY_*`). O pedido só entra na fila depois do COMMIT (`transaction.on_commit`) |
| Concorrência | `argo/catalog/stock.py` | `select_for_update()` dentro de `transaction.atomic()`, sempre na mesma ordem de produtos |
| E-mail | `argo/worker/mailer.py` | `django.core.mail` com o `MAILERS` do Django 6.1 (SMTP em produção, memória nos testes) |
| Comandos | `argo/common/management/commands/` | `python manage.py serve` aplica as migrações, cria os dados de demonstração e sobe o Daphne; `seed` só cria os dados |
| Banco por serviço | `argo/common/routers.py` | Roteador de bancos do Django: no modo `all` cada app grava no seu banco (`default`, `catalog` e `orders`) |

### Do clique à nota fiscal

1. O cliente fecha o carrinho e o serviço de pedidos confere preço e disponibilidade no catálogo.
2. O pedido é gravado como **Processando** e a resposta volta na hora (`202 Accepted`).
3. O worker baixa o estoque de todos os itens de uma vez, com `SELECT ... FOR UPDATE` em ordem fixa (sem deadlock). Se faltar algum item, nada é baixado e o pedido é **Recusado**.
4. Com o estoque reservado, o pedido vira **Confirmado**, o e-mail sai e o serviço Java emite a nota.
5. Toda tarefa é idempotente e repetida com espera exponencial se outro serviço estiver fora do ar.

<p align="center">
  <img src="docs/images/tela-pedido.png" alt="Pedido confirmado pela fila, com e-mail enviado e nota fiscal emitida">
</p>

## Como rodar

Você só precisa do **Docker** com Docker Compose.

**Windows:** dê dois cliques em `iniciar.cmd`.

**Linux ou macOS:**

```bash
./iniciar.sh
```

Na primeira vez o script cria o arquivo `.env` com senhas e segredos aleatórios, sobe os 10 contêineres e abre **http://localhost:8080**. A primeira execução demora alguns minutos para baixar as imagens; as próximas sobem em segundos.

| Endereço | O que é |
|---|---|
| http://localhost:8080 | Aplicação |
| http://localhost:8080/docs/ | Documentação da API (Swagger) dos quatro serviços |
| http://localhost:8025 | Caixa de entrada dos e-mails de teste (Mailpit) |
| http://localhost:5555 | Monitor das filas (Flower) |

Para rodar sem o script:

```bash
cp .env.example .env
docker compose up -d --build
```

Para mexer só no código Python, sem Docker (precisa de um Redis local para a fila e o tempo real):

```bash
cd backend
pip install -r requirements-dev.txt
ARGO_SERVICE=all python manage.py serve                              # API em http://localhost:8000/api/<serviço>/
ARGO_SERVICE=worker celery -A argo.worker.celery_app:celery worker -Q orders   # em outro terminal
```

## Contas de demonstração

Todas usam a senha **`Argo@2026`**. Elas existem só para testes e estão no código de propósito, para qualquer pessoa conseguir entrar logo depois de baixar o projeto. Os nomes são fictícios e os e-mails usam o domínio de exemplo `argo.dev`.

| Papel | E-mail | O que pode fazer |
|---|---|---|
| Administrador | `admin@argo.dev` | Tudo, incluindo usuários e pedidos de qualquer vendedor |
| Vendedor | `vendedor@argo.dev` | Produtos, estoque, pedidos com seus produtos e suas notas |
| Cliente | `cliente@argo.dev` | Loja, carrinho, pedidos e notas fiscais próprias |

Os dados de demonstração trazem 2 lojas, 16 produtos em 4 categorias, 5 clientes e 64 pedidos dos últimos 30 dias. Para usar de verdade, troque as senhas dessas contas ou suba com `ARGO_SEED=false` em bancos vazios.

| Tela | |
|---|---|
| <img src="docs/images/tela-login.png" alt="Entrada com as contas de demonstração"> | <img src="docs/images/tela-loja.png" alt="Loja com estoque em tempo real"> |
| <img src="docs/images/tela-carrinho.png" alt="Carrinho em gaveta lateral"> | <img src="docs/images/tela-estoque-ao-vivo.png" alt="Movimentações de estoque ao vivo"> |
| <img src="docs/images/tela-produtos.png" alt="Produtos do vendedor"> | <img src="docs/images/tela-usuarios.png" alt="Gestão de usuários"> |

## Segurança

| Regra | Como funciona |
|---|---|
| Token de acesso | JWT HS256 de 15 minutos com `sub`, `role`, `name`, `email`, `iss`, `exp` e `jti`. Validado por todos os serviços, inclusive o Java. |
| Refresh token | Opaco, de uso único e válido por 7 dias. Só o SHA-256 fica no banco. Cada troca gera um novo e invalida o anterior. |
| Detecção de roubo | Reapresentar um refresh token já trocado encerra todas as sessões daquela família. |
| RBAC | Três papéis (`ADMIN`, `SELLER`, `CUSTOMER`) checados em cada rota. Vendedor só altera os próprios produtos; cliente só vê os próprios pedidos e notas. |
| Senhas | Hash bcrypt do Django (`BCryptSHA256PasswordHasher`, custo 12), no mínimo 8 caracteres com letras e números. Cinco erros seguidos bloqueiam a conta por 5 minutos. |
| Telas | Toda tela exige login. Os tokens ficam só na memória da aba: recarregar ou ficar 20 minutos sem uso pede um novo login. |
| Entre serviços | Rotas `/internal/*` só aceitam chamadas com o cabeçalho `X-Internal-Token`; sem ele respondem 403 (Django) ou 401 (Java). |
| Dados pessoais | Nenhum dado pessoal real no repositório. Segredos só em `.env`, que fica fora do Git. |

## Configuração

Todas as variáveis ficam no arquivo `.env` (modelo em [`.env.example`](.env.example)).

| Variável | Padrão | Para que serve |
|---|---|---|
| `ARGO_PORT` | `8080` | Porta da aplicação no seu computador |
| `ARGO_DB_USER` / `ARGO_DB_PASSWORD` | `argo` / gerada | Usuário do MySQL |
| `ARGO_JWT_SECRET` | gerado | Segredo que assina os tokens (o mesmo para Django e Java) |
| `ARGO_INTERNAL_TOKEN` | gerado | Segredo das chamadas entre serviços |
| `ARGO_SEED` | `true` | Cadastra os dados de demonstração quando o banco está vazio |
| `ARGO_BILLING_TAX_RATE` | `0.1645` | Alíquota aproximada de tributos exibida nas notas |
| `ARGO_SMTP_HOST` / `ARGO_SMTP_PORT` | `mailpit` / `1025` | Servidor de e-mail. Troque pelo seu SMTP para enviar de verdade |
| `ARGO_SMTP_USER` / `ARGO_SMTP_PASSWORD` / `ARGO_SMTP_TLS` | vazio | Credenciais do SMTP |
| `ARGO_PUBLIC_URL` | `http://localhost:8080` | Endereço usado nos links dos e-mails |

## API

Todas as rotas passam pelo gateway em `/api/<serviço>`, respondem JSON e exigem `Authorization: Bearer <token>`, exceto login, cadastro, refresh e saúde.

| Serviço | Rotas principais |
|---|---|
| Identidade | `POST /auth/register` · `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /auth/me` · `PUT /auth/me/password` · `GET`, `POST` e `PATCH /users` |
| Catálogo | `GET /products` · `GET /products/categories` · `GET`, `POST`, `PUT` e `DELETE /products/{id}` · `POST /products/{id}/stock` · `GET /products/{id}/movements` · `GET /stock/summary` · `GET /stock/stream` |
| Pedidos | `POST /orders` · `GET /orders` · `GET /orders/stats` · `GET /orders/{id}` · `POST /orders/{id}/cancel` · `PATCH /orders/{id}/status` |
| Faturamento | `GET /invoices` · `GET /invoices/summary` · `GET /invoices/{número}` |

Erros seguem sempre o mesmo formato nos quatro serviços: `{ "code": "...", "message": "...", "fields": { "campo": "mensagem" } }`.

```bash
TOKEN=$(curl -s -X POST localhost:8080/api/identity/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"cliente@argo.dev","password":"Argo@2026"}' | jq -r .access_token)

curl -s localhost:8080/api/catalog/products -H "Authorization: Bearer $TOKEN" | jq '.items[0]'
```

## Estrutura

```
E-commerce-Microservices-Platform/
├── backend/                     projeto Django dos serviços Python (um processo por serviço)
│   ├── manage.py                migrate, serve, seed e os demais comandos do Django
│   ├── argo/
│   │   ├── settings.py          configuração (ARGO_*) e escolha do serviço (ARGO_SERVICE)
│   │   ├── common/              JWT, permissões do DRF, erros, eventos, roteador de bancos e comandos
│   │   ├── identity/            cadastro, login, refresh tokens e usuários
│   │   ├── catalog/             produtos, estoque e Server-Sent Events
│   │   ├── orders/              checkout, situação e indicadores
│   │   └── worker/              tarefas Celery e e-mail
│   └── tests/                   testes de unidade e integração (pytest-django)
├── billing/                     serviço de faturamento em Java 21 + Spring Boot
├── web/                         interface web e página do Swagger
├── gateway/                     configuração do Nginx
├── database/                    criação dos bancos e SQL de cada serviço
├── scripts/                     geração do esquema e criação do .env
├── docs/                        manual, guia do banco e imagens
└── docker-compose.yml           os 10 contêineres da plataforma
```

## Testes

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

São 65 testes com pytest-django e cobertura acima de 90% (mínimo exigido: 80%). Os três serviços rodam no mesmo processo, cada um com o seu banco SQLite, e as chamadas entre eles passam pela aplicação Django de verdade. Para rodar no MySQL, defina `ARGO_DATABASE_URL`, `ARGO_CATALOG_DATABASE_URL` e `ARGO_ORDERS_DATABASE_URL` (no formato `mysql://usuario:senha@localhost:3306/argo_identity`) antes do `pytest`. Cobrem tokens e papéis, bloqueio de login, rotação e reuso de refresh token, permissões de cada rota, estoque com concorrência otimista, baixa tudo ou nada, idempotência das filas, cancelamento no meio do processamento, queda do faturamento e do SMTP, e o fluxo inteiro de pedido → fila → estoque → e-mail → nota fiscal.

```bash
cd billing
mvn -B verify
```

O serviço Java tem testes de integração com H2 em modo MySQL que validam emissão idempotente, cálculo dos tributos, cancelamento, visibilidade por papel e tokens inválidos, expirados ou com outro emissor.

O workflow [`ci.yml`](.github/workflows/ci.yml) roda os testes Python no SQLite e num MySQL 8.4, a suíte Java e monta as imagens Docker a cada envio e uma vez por dia.

## Licença

[MIT](LICENSE). Use, copie, altere e distribua à vontade. A fonte Public Sans é distribuída sob a [SIL Open Font License](https://github.com/uswds/public-sans/blob/develop/LICENSE.md) e o Swagger UI sob a [Apache License 2.0](web/docs/vendor/LICENSE).

## **Muito Obrigado pela sua atenção!**
