# Atividade 03: Webhooks

**Disciplina:** Tópicos Especiais em Engenharia de Software (2026.2)
**Aluno:** Luiz Augusto Farias Hora

Implementação completa das duas pontas de uma arquitetura orientada a eventos via webhooks: um **emissor** de mudanças de estado de pedidos e um **receptor** consumidor das notificações, executados como dois programas independentes em processos separados.

Inclui também os dois requisitos de pontuação extra: **autenticação de payload via assinatura HMAC-SHA256** e **idempotência por identificador único de evento**.

---

## Estrutura do Projeto

```text
exercicio-3-webhooks/
├── .gitignore
├── README.md
├── emissor/
│   ├── main.py
│   └── requirements.txt
└── receptor/
    ├── main.py
    └── requirements.txt
```

---

## Emissor e Receptor

- **Emissor (`emissor/main.py`, porta padrão `8000`):** API REST em FastAPI que recebe o cadastro de pedidos (`POST /pedidos/{pedido_id}`) com status inicial `"recebido"`. Um processador em segundo plano (`asyncio` background task) avança automaticamente o estado de cada pedido em intervalos regulares e envia um `POST` assinado ao receptor a cada transição. Também disponibiliza `GET /pedidos`, `GET /pedidos/{pedido_id}` e `POST /eventos/{evento_id}/reenviar` (para simular reentregas mantendo o mesmo `id` do evento).
- **Receptor (`receptor/main.py`, porta padrão `8001`):** API REST em FastAPI que expõe `POST /webhook` para validar a assinatura HMAC-SHA256 sobre os bytes crus da requisição, garantir idempotência pelo `id` do evento e registrar a notificação em memória. Os eventos registrados podem ser consultados em `GET /eventos` (com filtro opcional `?pedido_id=...`).

---

## Evento que Dispara a Notificação

1. Um pedido é cadastrado no emissor por meio de `POST /pedidos/{pedido_id}` e salvo com status `"recebido"`.
2. O worker em segundo plano verifica os pedidos periodicamente e avança cada pedido na sequência fixa:

   ```text
   recebido -> aprovado -> enviado -> entregue
   ```

3. A cada **mudança de status** (`recebido -> aprovado`, `aprovado -> enviado`, `enviado -> entregue`), o emissor gera um novo evento com `id` único (`evt_<12_hex>`) e dispara um `POST` para o webhook do receptor.

---

## Endpoint Receptor, Cabeçalhos e Payload

- **Endpoint receptor:** `POST http://127.0.0.1:8001/webhook`
- **Cabeçalhos enviados pelo emissor:**
  - `Content-Type: application/json`
  - `X-Assinatura: sha256=<64 caracteres hexadecimais>`

### Exemplo de payload JSON enviado pelo emissor

```json
{
  "id": "evt_587bc93a0495",
  "pedido_id": "ped_1",
  "status": "aprovado",
  "ocorrido_em": "2026-11-23T00:41:27.321612+00:00"
}
```

---

## Segurança (HMAC-SHA256) e Idempotência

### 1. Assinatura HMAC-SHA256
- O emissor calcula o HMAC-SHA256 exatamente sobre os **bytes UTF-8** do corpo JSON que será enviado e inclui o cabeçalho `X-Assinatura: sha256=<64 caracteres hexadecimais>`.
- O receptor lê os bytes brutos (`await request.body()`) **antes** de converter para JSON, recalcula o HMAC-SHA256 com o mesmo segredo e compara usando comparação em tempo constante (`hmac.compare_digest`).
- Requisições com assinatura ausente ou inválida são recusadas com **HTTP `401 Unauthorized`** e **não** são registradas.
- O segredo compartilhado é lido exclusivamente da variável de ambiente `WEBHOOK_SECRET` (nunca versionado nem hardcoded no código; arquivos `.env` estão listados no `.gitignore`). Caso `WEBHOOK_SECRET` não esteja definida, ambos os serviços recusam iniciar.

Exemplo fictício de configuração da variável de ambiente (não utilize valores reais no repositório):

```text
WEBHOOK_SECRET=segredo-ficticio-para-demonstracao
```

### 2. Idempotência
- Cada transição de estado gera um `id` próprio de evento (ex.: `"id": "evt_587bc93a0495"`), distinto para cada mudança de estado do mesmo pedido (`aprovado`, `enviado`, `entregue` recebem IDs diferentes).
- O receptor mantém o conjunto de `id`s já processados. Se uma reentrega do mesmo evento (mesmo `id`) chegar novamente, o receptor responde **`200 OK`** (`2xx`) informando `"duplicado": true` e **não** registra o evento pela segunda vez.

---

## Como Subir os Dois Programas (na ordem)

### 1. Instalar dependências

No diretório `exercicio-3-webhooks/`:

```bash
pip install -r receptor/requirements.txt
pip install -r emissor/requirements.txt
```

### 2. Terminal 1: Subir o Receptor primeiro (porta `8001`)

**PowerShell (Windows):**

```powershell
cd exercicio-3-webhooks\receptor
$env:WEBHOOK_SECRET = "segredo-ficticio-para-demonstracao"
python main.py
```

**Bash (Linux/macOS):**

```bash
cd exercicio-3-webhooks/receptor
export WEBHOOK_SECRET="segredo-ficticio-para-demonstracao"
python3 main.py
```

### 3. Terminal 2: Subir o Emissor em seguida (porta `8000`)

Variáveis opcionais do emissor: `WEBHOOK_URL` (padrão `http://127.0.0.1:8001/webhook`) e `INTERVALO_SEGUNDOS` (padrão `3.0`).

**PowerShell (Windows):**

```powershell
cd exercicio-3-webhooks\emissor
$env:WEBHOOK_SECRET = "segredo-ficticio-para-demonstracao"
$env:INTERVALO_SEGUNDOS = "2"
python main.py
```

**Bash (Linux/macOS):**

```bash
cd exercicio-3-webhooks/emissor
export WEBHOOK_SECRET="segredo-ficticio-para-demonstracao"
export INTERVALO_SEGUNDOS="2"
python3 main.py
```

### 4. Terminal 3: Cadastrar um pedido e verificar os eventos

**Usando `curl`:**

```bash
# Cadastrar pedido (inicia como "recebido")
curl -X POST http://127.0.0.1:8000/pedidos/ped_1

# Aguardar ~7 segundos para o ciclo completo (aprovado -> enviado -> entregue)
# Consultar status final do pedido no emissor
curl http://127.0.0.1:8000/pedidos/ped_1

# Listar eventos registrados no receptor
curl http://127.0.0.1:8001/eventos
```

**Usando PowerShell (`Invoke-RestMethod`):**

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/pedidos/ped_1
Start-Sleep -Seconds 7
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/pedidos/ped_1
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8001/eventos
```

---

## Evidências de Funcionamento

Todas as saídas abaixo foram capturadas diretamente da execução real dos dois serviços em processos separados (receptor na porta `8001` e emissor na porta `8000`, com `INTERVALO_SEGUNDOS=2` e `WEBHOOK_SECRET="segredo-ficticio-para-demonstracao"`).

### 1. Ciclo completo de um pedido (`ped_1`: `recebido -> aprovado -> enviado -> entregue`)

**Cadastro inicial (`POST http://127.0.0.1:8000/pedidos/ped_1`), HTTP `201 Created`:**

```json
{
  "pedido_id": "ped_1",
  "status": "recebido",
  "criado_em": "2026-11-23T00:41:25.107532+00:00",
  "atualizado_em": "2026-11-23T00:41:25.107532+00:00",
  "eventos": []
}
```

**Saída do terminal do Emissor durante o ciclo completo:**

```text
INFO:     Started server process [3240]
INFO:     Waiting for application startup.
[EMISSOR] Iniciado em http://127.0.0.1:8000 | Destino webhook: http://127.0.0.1:8001/webhook | Intervalo: 2.0s
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
[EMISSOR] Pedido cadastrado: pedido_id=ped_1 status=recebido
INFO:     127.0.0.1:57867 - "POST /pedidos/ped_1 HTTP/1.1" 201 Created
[EMISSOR] Transição: pedido_id=ped_1 recebido -> aprovado | Evento id=evt_587bc93a0495
[EMISSOR] Webhook entregue: id=evt_587bc93a0495 pedido_id=ped_1 status=aprovado | HTTP 201
[EMISSOR] Transição: pedido_id=ped_1 aprovado -> enviado | Evento id=evt_8e9b6bc1daea
[EMISSOR] Webhook entregue: id=evt_8e9b6bc1daea pedido_id=ped_1 status=enviado | HTTP 201
[EMISSOR] Transição: pedido_id=ped_1 enviado -> entregue | Evento id=evt_3ac380acb261
[EMISSOR] Webhook entregue: id=evt_3ac380acb261 pedido_id=ped_1 status=entregue | HTTP 201
```

**Saída do terminal do Receptor recebendo as notificações do ciclo:**

```text
INFO:     Started server process [19176]
INFO:     Waiting for application startup.
[RECEPTOR] Iniciado em http://127.0.0.1:8001
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
[RECEPTOR] Evento registrado (201): id=evt_587bc93a0495 pedido_id=ped_1 status=aprovado
INFO:     127.0.0.1:57876 - "POST /webhook HTTP/1.1" 201 Created
[RECEPTOR] Evento registrado (201): id=evt_8e9b6bc1daea pedido_id=ped_1 status=enviado
INFO:     127.0.0.1:57876 - "POST /webhook HTTP/1.1" 201 Created
[RECEPTOR] Evento registrado (201): id=evt_3ac380acb261 pedido_id=ped_1 status=entregue
INFO:     127.0.0.1:57876 - "POST /webhook HTTP/1.1" 201 Created
INFO:     127.0.0.1:57885 - "GET /eventos HTTP/1.1" 200 OK
```

**Resposta de `GET http://127.0.0.1:8001/eventos` após o ciclo completo (`200 OK`):**

```json
{
  "total": 3,
  "eventos": [
    {
      "id": "evt_587bc93a0495",
      "pedido_id": "ped_1",
      "status": "aprovado",
      "ocorrido_em": "2026-11-23T00:41:27.321612+00:00",
      "recebido_em": "2026-11-23T00:41:27.333827+00:00"
    },
    {
      "id": "evt_8e9b6bc1daea",
      "pedido_id": "ped_1",
      "status": "enviado",
      "ocorrido_em": "2026-11-23T00:41:29.353162+00:00",
      "recebido_em": "2026-11-23T00:41:29.353712+00:00"
    },
    {
      "id": "evt_3ac380acb261",
      "pedido_id": "ped_1",
      "status": "entregue",
      "ocorrido_em": "2026-11-23T00:41:31.417072+00:00",
      "recebido_em": "2026-11-23T00:41:31.418077+00:00"
    }
  ]
}
```

---

### 2. Evidências da Pontuação Extra (HMAC-SHA256 e Idempotência)

#### a) Assinatura válida aceita (`201 Created`)

Além das 3 entregas reais feitas pelo emissor acima (todas autenticadas com `X-Assinatura`), uma requisição direta assinada com `WEBHOOK_SECRET="segredo-ficticio-para-demonstracao"` foi aceita e registrada normalmente:

- **Cabeçalho enviado:** `X-Assinatura: sha256=59b2855abbfa8f17eeef9c7dd5cb9bc2363fc63e29b99abdded5e5dc614ba5ad`
- **Corpo enviado (`POST http://127.0.0.1:8001/webhook`):**

```json
{
  "id": "evt_assinatura_valida_demo",
  "pedido_id": "ped_demo_hmac",
  "status": "aprovado",
  "ocorrido_em": "2026-11-23T00:45:00+00:00"
}
```

- **Resposta do receptor (`201 Created`):**

```json
{
  "mensagem": "Evento recebido e registrado.",
  "evento": {
    "id": "evt_assinatura_valida_demo",
    "pedido_id": "ped_demo_hmac",
    "status": "aprovado",
    "ocorrido_em": "2026-11-23T00:45:00+00:00",
    "recebido_em": "2026-11-23T00:41:32.159282+00:00"
  },
  "duplicado": false
}
```

- **Log do receptor:**

```text
[RECEPTOR] Evento registrado (201): id=evt_assinatura_valida_demo pedido_id=ped_demo_hmac status=aprovado
INFO:     127.0.0.1:57885 - "POST /webhook HTTP/1.1" 201 Created
```

#### b) Assinatura errada (e ausente) recusada com `401 Unauthorized` sem registrar

Ao enviar `POST /webhook` com assinatura HMAC incorreta (`X-Assinatura: sha256=0000...0000`) e sem o cabeçalho `X-Assinatura`, ambos foram recusados com `401` e o total de eventos em `GET /eventos` permaneceu inalterado (`total: 3`):

- **Resposta para assinatura errada (`401 Unauthorized`):**

```json
{
  "detail": "Assinatura HMAC inválida."
}
```

- **Resposta para assinatura ausente (`401 Unauthorized`):**

```json
{
  "detail": "Cabeçalho X-Assinatura ausente."
}
```

- **Log do receptor:**

```text
[RECEPTOR] Recusado (401): assinatura HMAC-SHA256 inválida
INFO:     127.0.0.1:57885 - "POST /webhook HTTP/1.1" 401 Unauthorized
[RECEPTOR] Recusado (401): cabeçalho X-Assinatura ausente
INFO:     127.0.0.1:57885 - "POST /webhook HTTP/1.1" 401 Unauthorized
```

#### c) Mesmo evento enviado duas vezes registrado uma única vez (Idempotência)

O evento `evt_587bc93a0495` (já entregue anteriormente) foi reenviado exatamente com o mesmo `id` e os mesmos bytes via `POST http://127.0.0.1:8000/eventos/evt_587bc93a0495/reenviar`. O receptor respondeu `200 OK` (`2xx`) sem duplicar o registro:

- **Log do emissor:**

```text
[EMISSOR] Reenviando evento existente: id=evt_587bc93a0495 pedido_id=ped_1 status=aprovado
[EMISSOR] Webhook entregue: id=evt_587bc93a0495 pedido_id=ped_1 status=aprovado | HTTP 200
INFO:     127.0.0.1:57867 - "POST /eventos/evt_587bc93a0495/reenviar HTTP/1.1" 200 OK
```

- **Log do receptor:**

```text
[RECEPTOR] Evento duplicado ignorado (200): id=evt_587bc93a0495 pedido_id=ped_1 status=aprovado
INFO:     127.0.0.1:57876 - "POST /webhook HTTP/1.1" 200 OK
```

- **Resposta do receptor no reenvio (`200 OK`):**

```json
{
  "mensagem": "Evento já processado anteriormente (idempotência).",
  "id": "evt_587bc93a0495",
  "duplicado": true
}
```

- **Consulta em `GET http://127.0.0.1:8001/eventos` após o reenvio (continua com `total: 3`, sem duplicação de `evt_587bc93a0495`):**

```json
{
  "total": 3,
  "eventos": [
    {
      "id": "evt_587bc93a0495",
      "pedido_id": "ped_1",
      "status": "aprovado",
      "ocorrido_em": "2026-11-23T00:41:27.321612+00:00",
      "recebido_em": "2026-11-23T00:41:27.333827+00:00"
    },
    {
      "id": "evt_8e9b6bc1daea",
      "pedido_id": "ped_1",
      "status": "enviado",
      "ocorrido_em": "2026-11-23T00:41:29.353162+00:00",
      "recebido_em": "2026-11-23T00:41:29.353712+00:00"
    },
    {
      "id": "evt_3ac380acb261",
      "pedido_id": "ped_1",
      "status": "entregue",
      "ocorrido_em": "2026-11-23T00:41:31.417072+00:00",
      "recebido_em": "2026-11-23T00:41:31.418077+00:00"
    }
  ]
}
```
