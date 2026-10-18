# Rede social em REST/JSON

Projeto **REST** da Atividade 02 (Tópicos Especiais em Engenharia de Software).
O mesmo domínio também está exposto em GraphQL no projeto [`../graphql/`](../graphql/README.md);
a comparação final está no [README da raiz](../README.md).

> **Em uma linha — o que o REST faz melhor que o GraphQL neste domínio:**
> cada operação é um recurso com URL própria, então o resultado pode ser cacheado e
> depurado por qualquer ferramenta que já entende HTTP (navegador, `curl`, CDN, proxy,
> APM), com o resultado da operação visível no código de status — coisa que o GraphQL,
> atrás de uma única URL com corpo variável, não dá de graça.

---

## 1. O que é este projeto

Uma API REST/JSON (FastAPI + Pydantic) que expõe uma rede social simplificada com as
entidades **Usuario, Perfil, Post, Comentario, Curtida e Seguidor**. O estado fica em
memória (reiniciou o servidor, voltou para a semente de dados) e cada arquivo do projeto
tem um papel claro:

| Arquivo | Papel |
| --- | --- |
| `armazenamento.py` | Domínio: entidades, regras e validação. **Não conhece HTTP.** |
| `aplicacao.py` | A camada REST: rotas, métodos, códigos de status, corpos JSON. |
| `demonstracao.py` | Roda as 10 operações obrigatórias e mede dois cenários (N+1 e over-fetching). |
| `exemplos/*.json` | Corpos de requisição prontos, usados no `curl` **e** pelo `demonstracao.py`. |
| `dependencias.txt` | Dependências do projeto. |

O projeto `graphql/` tem uma cópia quase idêntica de `armazenamento.py`: é de propósito.
Assim, as diferenças que aparecem nos exemplos vêm do protocolo, e não de um domínio
escrito de outra forma.

### Entidades e relacionamentos

```
Usuario 1:1 Perfil                 Usuario 1:N Post (autor)
Usuario N:M Post   via Curtida     Usuario N:M Usuario via Seguidor (auto-relacionamento)
Usuario N:M Post   via Comentario (com atributo texto)
```

---

## 2. Como executar do zero

Pré-requisito: **Python 3.10 ou superior** (`python --version`). Nada de banco de dados.

### Windows (PowerShell ou `cmd`), dentro da pasta `rest-json/`

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r dependencias.txt
.\.venv\Scripts\python.exe -m uvicorn aplicacao:aplicacao --port 8000
```

Não é preciso "ativar" o ambiente virtual: chamar o Python de dentro de `.venv` já basta.

### Linux / macOS, dentro da pasta `rest-json/`

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r dependencias.txt
.venv/bin/python -m uvicorn aplicacao:aplicacao --port 8000
```

Saída esperada (o servidor fica no ar nesse terminal):

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Teste rápido — em **outro** terminal, dentro de `rest-json/`:

```bash
curl.exe -s http://localhost:8000/usuarios/1
```

No **cmd**, no **PowerShell** e no **Git Bash** os comandos deste README funcionam iguais:
por isso eles estão em uma linha só e usam `curl.exe` (no PowerShell, `curl` sozinho é um
apelido para `Invoke-WebRequest` e não entende `-X`/`--data-binary`).

Bônus do REST: a documentação interativa é gerada de graça pelo FastAPI em
<http://localhost:8000/docs> — outro cliente HTTP podendo descobrir e testar a API.

---

## 3. Mapa do domínio para REST

Todas as 5 operações obrigatórias e as 5 consultas, do jeito que o enunciado as nomeia
para o jeito REST de expor:

| Operação do domínio | REST | Sucesso
| --- | --- | --- |
| `criar_usuario(nome, email)` | `POST /usuarios` | 201 |
| `criar_post(usuario_id, texto)` | `POST /posts` | 201 |
| `comentar(usuario_id, post_id, texto)` | `POST /posts/{post_id}/comentarios` | 201 |
| `curtir(usuario_id, post_id)` | `POST /posts/{post_id}/curtidas` | 201 |
| `seguir(usuario_id, alvo_id)` | `POST /usuarios/{usuario_id}/seguindo` | 201 |
| `buscar_usuario(id)` | `GET /usuarios/{id}` | 200 |
| `posts_do_usuario(usuario_id)` | `GET /usuarios/{usuario_id}/posts` | 200 |
| `buscar_post(id)` | `GET /posts/{id}` | 200 |
| `seguidores_de(id)` | `GET /usuarios/{id}/seguidores` | 200 |
| `seguindo_de(id)` | `GET /usuarios/{id}/seguindo` | 200 |
| `feed_do_usuario(usuario_id)` | `GET /usuarios/{usuario_id}/feed` | 200 |

Note que **toda** operação tem URL própria e é um recurso (`/posts/1/comentarios` é "os
comentários do post 1"), e que o resultado vem também no status HTTP.

### Erros viram códigos de status

O corpo de erro é sempre `{"erro": {"codigo": ..., "mensagem": ...}}`, mas o cliente já
sabe o que aconteceu pelo status — o mesmo código aparece nas duas camadas:

| `codigo` | Status HTTP | Quando acontece |
| --- | --- | --- |
| `NAO_ENCONTRADO` | `404 Not Found` | id de usuário/post inexistente |
| `EMAIL_JA_EXISTE` | `409 Conflict` | criar usuário com e-mail repetido |
| `JA_CURTIU` | `409 Conflict` | curtir o mesmo post duas vezes |
| `JA_SEGUE` | `409 Conflict` | seguir alguém que já é seguido |
| `AUTO_SEGUIR` | `422 Unprocessable Entity` | seguir a si mesmo |
| `DADOS_INVALIDOS` | `422 Unprocessable Entity` | texto vazio, e-mail inválido etc. |

### Semente de dados (o que já existe quando o servidor sobe)

| id | Usuário | Perfil |
| --- | --- | --- |
| 1 | Ana Souza (`ana@exemplo.com`) | Backend, APIs e protocolos — Goiânia, GO |
| 2 | Bruno Lima (`bruno@exemplo.com`) | Frontend e GraphQL — Goiânia, GO |
| 3 | Carla Dias (`carla@exemplo.com`) | Dados e observabilidade — Anápolis, GO |

Posts: `1` e `4` do Bruno, `2` da Carla, `3` da Ana.
Segue: Ana → Bruno e Carla; Bruno → Ana; Carla → Ana.
Comentários nos posts 1 e 3; curtidas nos posts 1, 3 e 4.

Os exemplos abaixo assumem o servidor **recém-iniciado** (por isso o usuário criado no
primeiro exemplo recebe `id: 4`). Os horários dos itens da semente são fixos; os horários
dos itens criados durante a execução mudam a cada rodada.

> Nas respostas os JSONs estão indentados para leitura; o servidor devolve tudo em uma
> linha só, sem espaços. Os cabeçalhos (`date`, `server`, `content-length`,
> `content-type`) aparecem por extenso só no primeiro exemplo, e ficam omitidos nos
> demais para o README não virar um despejo de `date`.

---

## 4. Exemplos copiáveis — comandos

Rode estes comandos **dentro da pasta `rest-json/`** (os caminhos `@exemplos/...` são
relativos a ela).

### 4.1 `criar_usuario(nome, email)` → `POST /usuarios`

Requisição (corpo em `exemplos/01-criar-usuario.json`):

```json
{
  "nome": "Davi Rocha",
  "email": "davi@exemplo.com"
}
```

```bash
curl.exe -s -i -X POST http://localhost:8000/usuarios -H "Content-Type: application/json" --data-binary @exemplos/01-criar-usuario.json
```

Resposta — `HTTP/1.1 201 Created`:

```
HTTP/1.1 201 Created
date: Sun, 18 Oct 2026 16:07:30 GMT
server: uvicorn
content-length: 216
content-type: application/json

{"id":4,"nome":"Davi Rocha", ...}
```

```json
{
  "id": 4,
  "nome": "Davi Rocha",
  "email": "davi@exemplo.com",
  "criado_em": "2026-10-18T16:07:30.057308Z",
  "perfil": {
    "bio": "",
    "avatar_url": "",
    "localizacao": "",
    "site": ""
  },
  "total_seguidores": 0,
  "total_seguindo": 0,
  "total_posts": 0
}
```

O `Perfil` nasce vazio porque o enunciado só pede `criar_usuario(nome, email)`.
Opcionalmente dá para preenchê-lo na criação (o `Perfil` é 1:1 com o usuário):

```bash
curl.exe -s -X POST http://localhost:8000/usuarios -H "Content-Type: application/json" -d "{\"nome\":\"Eve Martins\",\"email\":\"eve@exemplo.com\",\"perfil\":{\"bio\":\"Só olhando\",\"localizacao\":\"Goiânia, GO\"}}"
```

Tentar criar o mesmo e-mail de novo devolve `409 Conflict`:

```json
{ "erro": { "codigo": "EMAIL_JA_EXISTE", "mensagem": "já existe usuário com o e-mail davi@exemplo.com" } }
```

### 4.2 `criar_post(usuario_id, texto)` → `POST /posts`

```json
{
  "usuario_id": 4,
  "texto": "Chegando agora na rede de exemplo!"
}
```

```bash
curl.exe -s -i -X POST http://localhost:8000/posts -H "Content-Type: application/json" --data-binary @exemplos/02-criar-post.json
```

Resposta — `201 Created`:

```json
{
  "id": 5,
  "texto": "Chegando agora na rede de exemplo!",
  "criado_em": "2026-10-18T16:07:32.098390Z",
  "autor": {
    "id": 4,
    "nome": "Davi Rocha",
    "email": "davi@exemplo.com"
  },
  "total_curtidas": 0,
  "total_comentarios": 0
}
```

### 4.3 `comentar(usuario_id, post_id, texto)` → `POST /posts/{post_id}/comentarios`

O post faz parte da URL (o "recurso pai"); o autor e o texto vão no corpo.

```json
{
  "usuario_id": 4,
  "texto": "Boa, Bruno!"
}
```

```bash
curl.exe -s -i -X POST http://localhost:8000/posts/1/comentarios -H "Content-Type: application/json" --data-binary @exemplos/03-comentar.json
```

Resposta — `201 Created`:

```json
{
  "id": 4,
  "texto": "Boa, Bruno!",
  "criado_em": "2026-10-18T16:07:34.136666Z",
  "autor": {
    "id": 4,
    "nome": "Davi Rocha",
    "email": "davi@exemplo.com"
  }
}
```

### 4.4 `curtir(usuario_id, post_id)` → `POST /posts/{post_id}/curtidas`

```json
{
  "usuario_id": 4
}
```

```bash
curl.exe -s -i -X POST http://localhost:8000/posts/3/curtidas -H "Content-Type: application/json" --data-binary @exemplos/04-curtir.json
```

Resposta — `201 Created`:

```json
{
  "criado_em": "2026-10-18T16:07:36.182870Z",
  "usuario": {
    "id": 4,
    "nome": "Davi Rocha",
    "email": "davi@exemplo.com"
  }
}
```

Curtir de novo o mesmo post devolve `409 Conflict` (o `POST` cria uma curtida, e ela não
pode existir duas vezes):

```json
{ "erro": { "codigo": "JA_CURTIU", "mensagem": "Davi Rocha já curtiu o post 3" } }
```

### 4.5 `seguir(usuario_id, alvo_id)` → `POST /usuarios/{usuario_id}/seguindo`

```json
{
  "alvo_id": 1
}
```

```bash
curl.exe -s -i -X POST http://localhost:8000/usuarios/4/seguindo -H "Content-Type: application/json" --data-binary @exemplos/05-seguir.json
```

Resposta — `201 Created` (devolve a lista `seguindo` já atualizada, para o cliente não
precisar de uma segunda requisição):

```json
{
  "usuario": {
    "id": 4,
    "nome": "Davi Rocha",
    "email": "davi@exemplo.com"
  },
  "total": 1,
  "seguindo": [
    {
      "id": 1,
      "nome": "Ana Souza",
      "email": "ana@exemplo.com"
    }
  ]
}
```

Seguir a si mesmo devolve `422 Unprocessable Entity`:
`{"erro": {"codigo": "AUTO_SEGUIR", "mensagem": "um usuário não pode seguir a si mesmo"}}`.

---

## 5. Exemplos copiáveis — consultas

### 5.1 `buscar_usuario(id)` → `GET /usuarios/{id}`

```bash
curl.exe -s http://localhost:8000/usuarios/1
```

Resposta — `200 OK`:

```json
{
  "id": 1,
  "nome": "Ana Souza",
  "email": "ana@exemplo.com",
  "criado_em": "2026-10-18T09:00:00Z",
  "perfil": {
    "bio": "Backend, APIs e protocolos",
    "avatar_url": "https://exemplo.com/avatares/ana.png",
    "localizacao": "Goiânia, GO",
    "site": "https://ana.dev"
  },
  "total_seguidores": 3,
  "total_seguindo": 2,
  "total_posts": 1
}
```

Repare que a resposta traz **sempre os mesmos campos**: um cliente que só queria
`nome` e `id` recebeu também e-mail, perfil e três contadores. É o *over-fetching*
clássico do REST — e é o ponto onde o GraphQL leva vantagem (ver comparação final).

Não existe — `404 Not Found`:

```bash
curl.exe -s http://localhost:8000/usuarios/999
```

```json
{ "erro": { "codigo": "NAO_ENCONTRADO", "mensagem": "usuário 999 não existe" } }
```

### 5.2 `posts_do_usuario(usuario_id)` → `GET /usuarios/{usuario_id}/posts`

```bash
curl.exe -s http://localhost:8000/usuarios/2/posts
```

Resposta — `200 OK` (mais recentes primeiro):

```json
{
  "usuario": {
    "id": 2,
    "nome": "Bruno Lima",
    "email": "bruno@exemplo.com"
  },
  "total": 2,
  "posts": [
    {
      "id": 4,
      "texto": "GraphQL resolve o feed em uma requisição",
      "criado_em": "2026-10-18T09:16:00Z",
      "autor": {
        "id": 2,
        "nome": "Bruno Lima",
        "email": "bruno@exemplo.com"
      },
      "total_curtidas": 1,
      "total_comentarios": 0
    },
    {
      "id": 1,
      "texto": "Primeiro post do Bruno: testando a API",
      "criado_em": "2026-10-18T09:10:00Z",
      "autor": {
        "id": 2,
        "nome": "Bruno Lima",
        "email": "bruno@exemplo.com"
      },
      "total_curtidas": 2,
      "total_comentarios": 3
    }
  ]
}
```

### 5.3 `buscar_post(id)` → `GET /posts/{id}`

```bash
curl.exe -s http://localhost:8000/posts/1
```

Resposta — `200 OK` (traz autor, contadores, comentários com autor e quem curtiu):

```json
{
  "id": 1,
  "texto": "Primeiro post do Bruno: testando a API",
  "criado_em": "2026-10-18T09:10:00Z",
  "autor": {
    "id": 2,
    "nome": "Bruno Lima",
    "email": "bruno@exemplo.com"
  },
  "total_curtidas": 2,
  "total_comentarios": 3,
  "comentarios": [
    {
      "id": 1,
      "texto": "Boa, Bruno!",
      "criado_em": "2026-10-18T09:20:00Z",
      "autor": {
        "id": 3,
        "nome": "Carla Dias",
        "email": "carla@exemplo.com"
      }
    },
    {
      "id": 2,
      "texto": "Gostei do formato do feed",
      "criado_em": "2026-10-18T09:21:00Z",
      "autor": {
        "id": 1,
        "nome": "Ana Souza",
        "email": "ana@exemplo.com"
      }
    },
    {
      "id": 4,
      "texto": "Boa, Bruno!",
      "criado_em": "2026-10-18T16:07:34.136666Z",
      "autor": {
        "id": 4,
        "nome": "Davi Rocha",
        "email": "davi@exemplo.com"
      }
    }
  ],
  "curtidas": [
    {
      "criado_em": "2026-10-18T09:30:00Z",
      "usuario": {
        "id": 1,
        "nome": "Ana Souza",
        "email": "ana@exemplo.com"
      }
    },
    {
      "criado_em": "2026-10-18T09:31:00Z",
      "usuario": {
        "id": 3,
        "nome": "Carla Dias",
        "email": "carla@exemplo.com"
      }
    }
  ]
}
```

### 5.4 `seguidores_de(id)` → `GET /usuarios/{id}/seguidores`

```bash
curl.exe -s http://localhost:8000/usuarios/1/seguidores
```

Resposta — `200 OK`:

```json
{
  "usuario": {
    "id": 1,
    "nome": "Ana Souza",
    "email": "ana@exemplo.com"
  },
  "total": 3,
  "seguidores": [
    { "id": 2, "nome": "Bruno Lima", "email": "bruno@exemplo.com" },
    { "id": 3, "nome": "Carla Dias", "email": "carla@exemplo.com" },
    { "id": 4, "nome": "Davi Rocha", "email": "davi@exemplo.com" }
  ]
}
```

### 5.5 `seguindo_de(id)` → `GET /usuarios/{id}/seguindo`

```bash
curl.exe -s http://localhost:8000/usuarios/1/seguindo
```

Resposta — `200 OK`:

```json
{
  "usuario": {
    "id": 1,
    "nome": "Ana Souza",
    "email": "ana@exemplo.com"
  },
  "total": 2,
  "seguindo": [
    { "id": 2, "nome": "Bruno Lima", "email": "bruno@exemplo.com" },
    { "id": 3, "nome": "Carla Dias", "email": "carla@exemplo.com" }
  ]
}
```

### 5.6 `feed_do_usuario(usuario_id)` → `GET /usuarios/{usuario_id}/feed`

```bash
curl.exe -s http://localhost:8000/usuarios/4/feed
```

Resposta — `200 OK` (posts de quem eu sigo + os meus, mais recentes primeiro):

```json
{
  "usuario": {
    "id": 4,
    "nome": "Davi Rocha",
    "email": "davi@exemplo.com"
  },
  "total": 2,
  "posts": [
    {
      "id": 5,
      "texto": "Chegando agora na rede de exemplo!",
      "criado_em": "2026-10-18T16:07:32.098390Z",
      "autor": {
        "id": 4,
        "nome": "Davi Rocha",
        "email": "davi@exemplo.com"
      },
      "total_curtidas": 0,
      "total_comentarios": 0
    },
    {
      "id": 3,
      "texto": "Escrevendo sobre REST x GraphQL",
      "criado_em": "2026-10-18T09:14:00Z",
      "autor": {
        "id": 1,
        "nome": "Ana Souza",
        "email": "ana@exemplo.com"
      },
      "total_curtidas": 2,
      "total_comentarios": 1
    }
  ]
}
```

---

## 6. Demonstração automatizada

O `demonstracao.py` roda **exatamente** os exemplos acima (lendo os mesmos arquivos de
`exemplos/`) e, no fim, mede dois cenários. Com o servidor no ar e recém-iniciado:

```powershell
# Windows, dentro de rest-json/
.\.venv\Scripts\python.exe demonstracao.py
```

```bash
# Linux / macOS, dentro de rest-json/
.venv/bin/python demonstracao.py
```

Saída final de uma execução real:

```
========================================================================
RELATÓRIO DESTA EXECUÇÃO
========================================================================
  Cenário A (feed detalhado, 4 posts): 5 requisição(ões) HTTP, 2813 bytes de resposta
  Cenário B (só os textos do feed): 1 requisição(ões) HTTP, 860 bytes de resposta
  Cenário A: 5 chamadas para montar o feed com comentários (1 feed + 1 por post: é aqui que aparece o N+1 do REST)
  Cenário B: o feed devolve autor, e-mail e contadores que o cliente não pediu (over-fetching).
```

- **Cenário A** — "quero o feed com os comentários de cada post": `GET /usuarios/1/feed`
  devolve os 4 posts, mas os comentários só existem em `GET /posts/{id}`. O cliente faz
  **1 + N** requisições (1 feed + 1 por post). Isso é o N+1 *de rede* do REST: o servidor
  responde rápido, mas a conversa cliente↔servidor se multiplica pela latência.
- **Cenário B** — "quero só os textos do feed": 1 requisição, mas 860 bytes, porque o
  recurso `/usuarios/1/feed` devolve autor, e-mail e contadores que ninguém pediu
  (over-fetching).

Se o `demonstracao.py` avisar que o servidor não está limpo, é porque ele já rodou nesse servidor:
pare o servidor (`Ctrl+C`), suba de novo e rode o `demonstracao.py` outra vez.

---

## 7. Detalhes que valem nota

- **O status faz parte da resposta.** `201 Created` para criação, `404` para id
  inexistente, `409` para conflito de regra, `422` para dado inválido. Um cliente burro
  (ou um balanceador, ou um APM) entende o que aconteceu sem ler o corpo.
- **Cacheável por natureza.** `GET /usuarios/1`, `GET /usuarios/2/posts` etc. são URLs
  estáveis; poderiam receber `Cache-Control`/`ETag` e ser servidos por CDN ou proxy sem
  o servidor participar.
- **HATEOAS/OData não estão aqui.** Esta API é REST "de recursos e verbos", sem
  hipermídia (`_links`) e sem paginação — nenhuma das duas foi pedida no enunciado.
- **Validação em dois lugares.** O FastAPI valida tipos e a presença do corpo (erros dele
  são `422` no formato do framework); as regras de negócio (e-mail repetido, curtir duas
  vezes, seguir a si mesmo) ficam no domínio e viram `ErroDominio`.
- **A resposta é fixa por rota.** Qualquer mudança de forma (renomear um campo, juntar
  duas listas, esconder um campo de um cliente) exige mexer na rota ou criar uma nova —
  é aí que entra a discussão de versionamento (`/v2/...`).

## 8. Limitações conscientes

Estado em memória (sem banco), sem autenticação/autorização, sem paginação, sem
`If-None-Match`/`ETag`, sem `PATCH`/`DELETE` (o enunciado pede cinco comandos, e este
projeto não inventou outros). O objetivo é comparar protocolos, não entregar produção.
