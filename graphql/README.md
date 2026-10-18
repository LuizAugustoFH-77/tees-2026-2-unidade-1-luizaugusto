# Rede social em GraphQL

Projeto **GraphQL** da Atividade 02 (Tópicos Especiais em Engenharia de Software).
O mesmo domínio também está exposto em REST/JSON no projeto
[`../rest-json/`](../rest-json/README.md); a comparação final está no
[README da raiz](../README.md).

> **Em uma linha — o que o GraphQL faz melhor que o REST neste domínio:**
> o cliente monta a resposta sob medida em uma única requisição, pedindo só os campos e
> as relações que vai usar — o feed completo com autor, contadores e comentários sai em
> **1 requisição e 1062 bytes**, contra **5 requisições e 2813 bytes** no REST.
> Em REST isso vira *over-fetching* (campos que ninguém pediu) e *N+1 de rede*
> (uma chamada por post).

---

## 1. O que é este projeto

Um servidor GraphQL (Strawberry + FastAPI) que expõe a rede social simplificada
(**Usuario, Perfil, Post, Comentario, Curtida e Seguidor**) em **uma única rota**:
`POST /graphql`. O cliente manda uma consulta dizendo o que quer; o servidor resolve o
grafo de tipos e devolve exatamente aquilo.

| Arquivo | Papel |
| --- | --- |
| `armazenamento.py` | Domínio: entidades, regras e validação. **Não conhece GraphQL.** (Cópia quase idêntica à do projeto REST.) |
| `aplicacao.py` | O schema GraphQL: tipos, campos aninhados, queries e mutations. |
| `esquema.graphql` | SDL gerado por `exportar_esquema.py` — o "contrato" que o cliente lê. |
| `exportar_esquema.py` | Escreve o SDL a partir do schema Python. |
| `demonstracao.py` | Roda as 10 operações obrigatórias e mede dois cenários (N+1 e over-fetching). |
| `exemplos/*.json` | Corpos `{"query": ...}` prontos, usados no `curl` **e** pelo `demonstracao.py`. |
| `dependencias.txt` | Dependências do projeto. |

### Entidades e relacionamentos

```
Usuario 1:1 Perfil                 Usuario 1:N Post (autor)
Usuario N:M Post   via Curtida     Usuario N:M Usuario via Seguidor (auto-relacionamento)
Usuario N:M Post   via Comentario (com atributo texto)
```

A diferença de modelagem em relação ao REST está no schema (abaixo): além das consultas
"de raiz", cada tipo tem campos de navegação (`Post.autor`, `Post.comentarios`,
`Usuario.seguidores`, `Usuario.posts`, `Comentario.autor`, ...). É por eles que o cliente
atravessa o grafo sem chamadas extras.

---

## 2. Como executar do zero

Pré-requisito: **Python 3.10 ou superior** (`python --version`). Nada de banco de dados.

### Windows (PowerShell ou `cmd`), dentro da pasta `graphql/`

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r dependencias.txt
.\.venv\Scripts\python.exe -m uvicorn aplicacao:aplicacao --port 8001
```

Não é preciso "ativar" o ambiente virtual: chamar o Python de dentro de `.venv` já basta.

### Linux / macOS, dentro da pasta `graphql/`

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r dependencias.txt
.venv/bin/python -m uvicorn aplicacao:aplicacao --port 8001
```

Saída esperada (o servidor fica no ar nesse terminal):

```
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
```

Teste rápido — abra <http://localhost:8001/graphql> no navegador: é o **GraphiQL**, um
IDE que conhece o schema, autocompleta os campos e mostra a documentação sozinho
(introspecção). O mesmo teste por linha de comando, em **outro** terminal, dentro de
`graphql/`:

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/06-buscar-usuario.json
```

No **cmd**, no **PowerShell** e no **Git Bash** os comandos deste README funcionam iguais:
por isso eles estão em uma linha só e usam `curl.exe` (no PowerShell, `curl` sozinho é um
apelido para `Invoke-WebRequest` e não entende `--data-binary`).

Para regerar o SDL depois de mexer no schema:

```bash
.\.venv\Scripts\python.exe exportar_esquema.py     # escreve esquema.graphql
```

---

## 3. O schema (contrato do protocolo)

Conteúdo de `esquema.graphql`:

```graphql
schema {
  query: Consulta
  mutation: Mutacao
}

type Comentario {
  id: Int!
  texto: String!
  criadoEm: DateTime!
  autor: Usuario!
  post: Post!
}

type Consulta {
  usuario(id: Int!): Usuario
  postsDoUsuario(usuarioId: Int!): [Post!]!
  post(id: Int!): Post
  seguidoresDe(id: Int!): [Usuario!]!
  seguindoDe(id: Int!): [Usuario!]!
  feedDoUsuario(usuarioId: Int!): [Post!]!
}

type Curtida {
  criadoEm: DateTime!
  usuario: Usuario!
  post: Post!
}

"""Date with time (isoformat)"""
scalar DateTime

input EntradaPerfil {
  bio: String! = ""
  avatarUrl: String! = ""
  localizacao: String! = ""
  site: String! = ""
}

type Mutacao {
  criarUsuario(nome: String!, email: String!, perfil: EntradaPerfil = null): Usuario!
  criarPost(usuarioId: Int!, texto: String!): Post!
  comentar(usuarioId: Int!, postId: Int!, texto: String!): Comentario!
  curtir(usuarioId: Int!, postId: Int!): Curtida!
  seguir(usuarioId: Int!, alvoId: Int!): Seguidor!
}

type Perfil {
  bio: String!
  avatarUrl: String!
  localizacao: String!
  site: String!
}

type Post {
  id: Int!
  texto: String!
  criadoEm: DateTime!
  autor: Usuario!
  comentarios: [Comentario!]!
  curtidas: [Curtida!]!
  totalCurtidas: Int!
  totalComentarios: Int!
}

type Seguidor {
  criadoEm: DateTime!
  seguidor: Usuario!
  seguido: Usuario!
}

type Usuario {
  id: Int!
  nome: String!
  email: String!
  criadoEm: DateTime!
  perfil: Perfil!
  totalSeguidores: Int!
  totalSeguindo: Int!
  totalPosts: Int!
  posts: [Post!]!
  seguidores: [Usuario!]!
  seguindo: [Usuario!]!
}
```

Três observações sobre o contrato:

- Os nomes de campos e argumentos saem em **camelCase** (`criarPost`, `usuarioId`,
  `criadoEm`): é a convenção do GraphQL, e o Strawberry converte os nomes snake_case do
  Python automaticamente. As *palavras* continuam em português.
- As raízes do schema se chamam `Consulta` e `Mutacao`, não `Query` e `Mutation`. Isso é
  permitido pelo GraphQL, e o bloco `schema { ... }` no começo do arquivo declara esse
  mapeamento — é ele que faz o GraphiQL e os clientes saberem qual tipo é a raiz de leitura
  e qual é a de escrita.
- `usuario(id)` e `post(id)` são **nuláveis** de propósito: "não achei" é `null`, não um
  erro — diferente do `404` do REST (ver seção 6.2).

### Mapa das operações obrigatórias

| Operação do domínio | GraphQL | Tipo |
| --- | --- | --- |
| `criar_usuario(nome, email)` | `mutation criarUsuario(nome, email, perfil?)` | mutation |
| `criar_post(usuario_id, texto)` | `mutation criarPost(usuarioId, texto)` | mutation |
| `comentar(usuario_id, post_id, texto)` | `mutation comentar(usuarioId, postId, texto)` | mutation |
| `curtir(usuario_id, post_id)` | `mutation curtir(usuarioId, postId)` | mutation |
| `seguir(usuario_id, alvo_id)` | `mutation seguir(usuarioId, alvoId)` | mutation |
| `buscar_usuario(id)` | `query usuario(id)` | query |
| `posts_do_usuario(usuario_id)` | `query postsDoUsuario(usuarioId)` | query |
| `buscar_post(id)` | `query post(id)` | query |
| `seguidores_de(id)` | `query seguidoresDe(id)` | query |
| `seguindo_de(id)` | `query seguindoDe(id)` | query |
| `feed_do_usuario(usuario_id)` | `query feedDoUsuario(usuarioId)` | query |

### Semente de dados (igual à do projeto REST)

| id | Usuário | Perfil |
| --- | --- | --- |
| 1 | Ana Souza (`ana@exemplo.com`) | Backend, APIs e protocolos — Goiânia, GO |
| 2 | Bruno Lima (`bruno@exemplo.com`) | Frontend e GraphQL — Goiânia, GO |
| 3 | Carla Dias (`carla@exemplo.com`) | Dados e observabilidade — Anápolis, GO |

Posts: `1` e `4` do Bruno, `2` da Carla, `3` da Ana.
Segue: Ana → Bruno e Carla; Bruno → Ana; Carla → Ana.
Comentários nos posts 1 e 3; curtidas nos posts 1, 3 e 4.

Os exemplos abaixo assumem o servidor **recém-iniciado** (por isso o usuário criado no
primeiro exemplo recebe `id: 4`).

> Nas respostas os JSONs estão indentados para leitura; o servidor devolve tudo em uma
> linha só. Erros de regra **não** mudam o status: a resposta continua `200 OK` e o
> problema aparece em `errors[]` (ver seção 6.1).

---

## 4. Exemplos copiáveis — os 5 comandos (mutations)

Rode estes comandos **dentro da pasta `graphql/`** (os caminhos `@exemplos/...` são
relativos a ela).

### 4.1 `criar_usuario(nome, email)` → `mutation criarUsuario`

Requisição (`exemplos/01-criar-usuario.json`):

```json
{
  "query": "mutation { criarUsuario(nome: \"Davi Rocha\", email: \"davi@exemplo.com\") { id nome email criadoEm totalPosts } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/01-criar-usuario.json
```

Resposta — `200 OK`:

```json
{
  "data": {
    "criarUsuario": {
      "id": 4,
      "nome": "Davi Rocha",
      "email": "davi@exemplo.com",
      "criadoEm": "2026-10-18T16:08:07.054092+00:00",
      "totalPosts": 0
    }
  }
}
```

Repare: os campos que o cliente **não** pediu (perfil, criadoEm, contadores de seguidores)
não vieram. O `Perfil` 1:1 nasce vazio; se quiser preencher na criação, use o argumento
opcional `perfil` (input `EntradaPerfil`):

```json
{
  "query": "mutation { criarUsuario(nome: \"Eve Martins\", email: \"eve@exemplo.com\", perfil: {bio: \"Só olhando\", localizacao: \"Goiânia, GO\"}) { id nome perfil { bio localizacao } } }"
}
```

### 4.2 `criar_post(usuario_id, texto)` → `mutation criarPost`

```json
{
  "query": "mutation { criarPost(usuarioId: 4, texto: \"Chegando agora na rede de exemplo!\") { id texto criadoEm autor { id nome } } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/02-criar-post.json
```

Resposta — `200 OK`:

```json
{
  "data": {
    "criarPost": {
      "id": 5,
      "texto": "Chegando agora na rede de exemplo!",
      "criadoEm": "2026-10-18T16:08:09.095319+00:00",
      "autor": {
        "id": 4,
        "nome": "Davi Rocha"
      }
    }
  }
}
```

### 4.3 `comentar(usuario_id, post_id, texto)` → `mutation comentar`

```json
{
  "query": "mutation { comentar(usuarioId: 4, postId: 1, texto: \"Boa, Bruno!\") { id texto criadoEm autor { id nome } post { id } } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/03-comentar.json
```

Resposta — `200 OK`:

```json
{
  "data": {
    "comentar": {
      "id": 4,
      "texto": "Boa, Bruno!",
      "criadoEm": "2026-10-18T16:08:11.141843+00:00",
      "autor": {
        "id": 4,
        "nome": "Davi Rocha"
      },
      "post": {
        "id": 1
      }
    }
  }
}
```

### 4.4 `curtir(usuario_id, post_id)` → `mutation curtir`

```json
{
  "query": "mutation { curtir(usuarioId: 4, postId: 3) { criadoEm usuario { id nome } post { id totalCurtidas } } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/04-curtir.json
```

Resposta — `200 OK`:

```json
{
  "data": {
    "curtir": {
      "criadoEm": "2026-10-18T16:08:13.193119+00:00",
      "usuario": {
        "id": 4,
        "nome": "Davi Rocha"
      },
      "post": {
        "id": 3,
        "totalCurtidas": 2
      }
    }
  }
}
```

A `Curtida` criada é um tipo com relações (`usuario`, `post`), então na mesma mutation dá
para já ver o contador atualizado do post — sem uma segunda requisição.

### 4.5 `seguir(usuario_id, alvo_id)` → `mutation seguir`

```json
{
  "query": "mutation { seguir(usuarioId: 4, alvoId: 1) { criadoEm seguidor { id nome } seguido { id nome } } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/05-seguir.json
```

Resposta — `200 OK`:

```json
{
  "data": {
    "seguir": {
      "criadoEm": "2026-10-18T16:08:15.238468+00:00",
      "seguidor": {
        "id": 4,
        "nome": "Davi Rocha"
      },
      "seguido": {
        "id": 1,
        "nome": "Ana Souza"
      }
    }
  }
}
```

A relação N:M pura do domínio (`Seguidor`) virou um tipo GraphQL com dois lados:
`seguidor` e `seguido`.

---

## 5. Exemplos copiáveis — as 5 consultas (queries)

### 5.1 `buscar_usuario(id)` → `query usuario(id)`

```json
{
  "query": "query { usuario(id: 1) { id nome email criadoEm perfil { bio avatarUrl localizacao site } totalSeguidores totalSeguindo totalPosts } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/06-buscar-usuario.json
```

Resposta — `200 OK`:

```json
{
  "data": {
    "usuario": {
      "id": 1,
      "nome": "Ana Souza",
      "email": "ana@exemplo.com",
      "criadoEm": "2026-10-18T09:00:00+00:00",
      "perfil": {
        "bio": "Backend, APIs e protocolos",
        "avatarUrl": "https://exemplo.com/avatares/ana.png",
        "localizacao": "Goiânia, GO",
        "site": "https://ana.dev"
      },
      "totalSeguidores": 3,
      "totalSeguindo": 2,
      "totalPosts": 1
    }
  }
}
```

A mesma consulta pedindo **só** o que interessa (note a diferença de tamanho):

```json
{
  "query": "query { usuario(id: 1) { nome perfil { bio } } }"
}
```

```json
{ "data": { "usuario": { "nome": "Ana Souza", "perfil": { "bio": "Backend, APIs e protocolos" } } } }
```

### 5.2 `posts_do_usuario(usuario_id)` → `query postsDoUsuario`

```json
{
  "query": "query { postsDoUsuario(usuarioId: 2) { id texto criadoEm autor { id nome } totalCurtidas totalComentarios } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/07-posts-do-usuario.json
```

Resposta — `200 OK` (mais recentes primeiro):

```json
{
  "data": {
    "postsDoUsuario": [
      {
        "id": 4,
        "texto": "GraphQL resolve o feed em uma requisição",
        "criadoEm": "2026-10-18T09:16:00+00:00",
        "autor": {
          "id": 2,
          "nome": "Bruno Lima"
        },
        "totalCurtidas": 1,
        "totalComentarios": 0
      },
      {
        "id": 1,
        "texto": "Primeiro post do Bruno: testando a API",
        "criadoEm": "2026-10-18T09:10:00+00:00",
        "autor": {
          "id": 2,
          "nome": "Bruno Lima"
        },
        "totalCurtidas": 2,
        "totalComentarios": 3
      }
    ]
  }
}
```

### 5.3 `buscar_post(id)` → `query post(id)`

```json
{
  "query": "query { post(id: 1) { id texto criadoEm autor { id nome } totalCurtidas totalComentarios comentarios { id texto criadoEm autor { id nome } } curtidas { criadoEm usuario { id nome } } } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/08-buscar-post.json
```

Resposta — `200 OK` (post + autor + comentários com autor + quem curtiu, **tudo em uma
requisição**):

```json
{
  "data": {
    "post": {
      "id": 1,
      "texto": "Primeiro post do Bruno: testando a API",
      "criadoEm": "2026-10-18T09:10:00+00:00",
      "autor": {
        "id": 2,
        "nome": "Bruno Lima"
      },
      "totalCurtidas": 2,
      "totalComentarios": 3,
      "comentarios": [
        {
          "id": 1,
          "texto": "Boa, Bruno!",
          "criadoEm": "2026-10-18T09:20:00+00:00",
          "autor": {
            "id": 3,
            "nome": "Carla Dias"
          }
        },
        {
          "id": 2,
          "texto": "Gostei do formato do feed",
          "criadoEm": "2026-10-18T09:21:00+00:00",
          "autor": {
            "id": 1,
            "nome": "Ana Souza"
          }
        },
        {
          "id": 4,
          "texto": "Boa, Bruno!",
          "criadoEm": "2026-10-18T16:08:11.141843+00:00",
          "autor": {
            "id": 4,
            "nome": "Davi Rocha"
          }
        }
      ],
      "curtidas": [
        {
          "criadoEm": "2026-10-18T09:30:00+00:00",
          "usuario": {
            "id": 1,
            "nome": "Ana Souza"
          }
        },
        {
          "criadoEm": "2026-10-18T09:31:00+00:00",
          "usuario": {
            "id": 3,
            "nome": "Carla Dias"
          }
        }
      ]
    }
  }
}
```

### 5.4 `seguidores_de(id)` → `query seguidoresDe(id)`

```json
{
  "query": "query { seguidoresDe(id: 1) { id nome email totalSeguidores } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/09-seguidores-de.json
```

Resposta — `200 OK` (de quebra, traz o total de seguidores de cada seguidor, porque o
cliente pediu):

```json
{
  "data": {
    "seguidoresDe": [
      { "id": 2, "nome": "Bruno Lima", "email": "bruno@exemplo.com", "totalSeguidores": 1 },
      { "id": 3, "nome": "Carla Dias", "email": "carla@exemplo.com", "totalSeguidores": 1 },
      { "id": 4, "nome": "Davi Rocha", "email": "davi@exemplo.com", "totalSeguidores": 0 }
    ]
  }
}
```

### 5.5 `seguindo_de(id)` → `query seguindoDe(id)`

```json
{
  "query": "query { seguindoDe(id: 1) { id nome email totalSeguindo } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/10-seguindo-de.json
```

Resposta — `200 OK`:

```json
{
  "data": {
    "seguindoDe": [
      { "id": 2, "nome": "Bruno Lima", "email": "bruno@exemplo.com", "totalSeguindo": 1 },
      { "id": 3, "nome": "Carla Dias", "email": "carla@exemplo.com", "totalSeguindo": 1 }
    ]
  }
}
```

### 5.6 `feed_do_usuario(usuario_id)` → `query feedDoUsuario(usuarioId)`

```json
{
  "query": "query { feedDoUsuario(usuarioId: 4) { id texto autor { id nome } totalCurtidas totalComentarios } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/11-feed-do-usuario.json
```

Resposta — `200 OK` (posts de quem eu sigo + os meus):

```json
{
  "data": {
    "feedDoUsuario": [
      {
        "id": 5,
        "texto": "Chegando agora na rede de exemplo!",
        "autor": { "id": 4, "nome": "Davi Rocha" },
        "totalCurtidas": 0,
        "totalComentarios": 0
      },
      {
        "id": 3,
        "texto": "Escrevendo sobre REST x GraphQL",
        "autor": { "id": 1, "nome": "Ana Souza" },
        "totalCurtidas": 2,
        "totalComentarios": 1
      }
    ]
  }
}
```

### 5.7 O mesmo feed "detalhado", com variáveis (1 requisição só)

Este é o cenário usado na medição da seção 6. Note o uso de **variáveis** (em vez de
valores embutidos na consulta) — e note que os comentários de todos os posts vêm juntos,
sem uma chamada por post:

`exemplos/14-cenario-a-feed-detalhado.json`:

```json
{
  "query": "query FeedDetalhado($usuarioId: Int!) { feedDoUsuario(usuarioId: $usuarioId) { id texto criadoEm totalCurtidas totalComentarios autor { id nome } comentarios { id texto autor { id nome } } } }",
  "variables": { "usuarioId": 1 }
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/14-cenario-a-feed-detalhado.json
```

Resposta — `200 OK`:

```json
{
  "data": {
    "feedDoUsuario": [
      {
        "id": 4,
        "texto": "GraphQL resolve o feed em uma requisição",
        "criadoEm": "2026-10-18T09:16:00+00:00",
        "totalCurtidas": 1,
        "totalComentarios": 0,
        "autor": { "id": 2, "nome": "Bruno Lima" },
        "comentarios": []
      },
      {
        "id": 3,
        "texto": "Escrevendo sobre REST x GraphQL",
        "criadoEm": "2026-10-18T09:14:00+00:00",
        "totalCurtidas": 2,
        "totalComentarios": 1,
        "autor": { "id": 1, "nome": "Ana Souza" },
        "comentarios": [
          { "id": 3, "texto": "Concordo, Ana", "autor": { "id": 2, "nome": "Bruno Lima" } }
        ]
      },
      {
        "id": 2,
        "texto": "Carla estreando no feed",
        "criadoEm": "2026-10-18T09:12:00+00:00",
        "totalCurtidas": 0,
        "totalComentarios": 0,
        "autor": { "id": 3, "nome": "Carla Dias" },
        "comentarios": []
      },
      {
        "id": 1,
        "texto": "Primeiro post do Bruno: testando a API",
        "criadoEm": "2026-10-18T09:10:00+00:00",
        "totalCurtidas": 2,
        "totalComentarios": 3,
        "autor": { "id": 2, "nome": "Bruno Lima" },
        "comentarios": [
          { "id": 1, "texto": "Boa, Bruno!", "autor": { "id": 3, "nome": "Carla Dias" } },
          { "id": 2, "texto": "Gostei do formato do feed", "autor": { "id": 1, "nome": "Ana Souza" } },
          { "id": 4, "texto": "Boa, Bruno!", "autor": { "id": 4, "nome": "Davi Rocha" } }
        ]
      }
    ]
  }
}
```

---

## 6. Exemplos de erro e de casos-limite

### 6.1 `JA_CURTIU` — erro de regra **sem** mudar o status

```json
{
  "query": "mutation { curtir(usuarioId: 4, postId: 3) { criadoEm } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/12-extra-erro-curtir-duas-vezes.json
```

Resposta — **`200 OK`** (mesmo tendo falhado):

```json
{
  "data": null,
  "errors": [
    {
      "message": "Davi Rocha já curtiu o post 3",
      "locations": [{ "line": 1, "column": 12 }],
      "path": ["curtir"],
      "extensions": { "code": "JA_CURTIU" }
    }
  ]
}
```

Compare com o REST, que responde `409 Conflict` e o corpo de erro
`{"erro": {"codigo": "JA_CURTIU", ...}}`. Aqui o status HTTP é sempre `200`: quem quiser
reagir a erro precisa inspecionar `errors[]` — e é por isso que se convencionou colocar um
código estável em `extensions.code` (as bibliotecas clientes leem isso, não a mensagem).

### 6.2 Usuário que não existe → `null`, não erro

```json
{
  "query": "query { usuario(id: 999) { id nome } }"
}
```

```bash
curl.exe -s -X POST http://localhost:8001/graphql -H "Content-Type: application/json" --data-binary @exemplos/13-extra-usuario-nao-encontrado.json
```

Resposta — `200 OK`:

```json
{ "data": { "usuario": null } }
```

No REST, o mesmo caso é `404 Not Found` com corpo de erro. Aqui `null` é uma resposta
legítima (os campos `usuario(id)` e `post(id)` são nuláveis no schema): quem consulta
pediu, então "não achei" é um resultado possível para aquele campo.

---

## 7. Demonstração automatizada

O `demonstracao.py` roda **exatamente** os exemplos das seções 4 e 5 (lendo os mesmos arquivos de
`exemplos/`) e, no fim, mede dois cenários. Com o servidor no ar e recém-iniciado:

```powershell
# Windows, dentro de graphql/
.\.venv\Scripts\python.exe demonstracao.py
```

```bash
# Linux / macOS, dentro de graphql/
.venv/bin/python demonstracao.py
```

Saída final de uma execução real:

```
========================================================================
RELATÓRIO DESTA EXECUÇÃO
========================================================================
  Cenário A (feed detalhado, 4 posts): 1 requisição(ões) HTTP, 1062 bytes de resposta
  Cenário B (só os textos do feed): 1 requisição(ões) HTTP, 222 bytes de resposta
  Cenário A: 1 requisição para 4 posts com autor, contadores e comentários (sem N+1 de round-trips)
  Cenário B: o cliente pediu só `texto` e só `texto` voltou (sem over-fetching).
```

- **Cenário A** — "quero o feed com os comentários de cada post": **1 requisição**, porque
  `comentarios` é um campo do tipo `Post` e o servidor resolve os 4 posts e seus
  comentários na mesma resposta. O REST precisaria de 1 + 4 requisições.
- **Cenário B** — "quero só os textos do feed": 1 requisição e **222 bytes**, contra 860
  bytes do REST, porque aqui dá para pedir apenas `texto`.

Se o `demonstracao.py` avisar que o servidor não está limpo, é porque ele já rodou nesse servidor:
pare o servidor (`Ctrl+C`), suba de novo e rode o `demonstracao.py` outra vez.

---

## 8. Detalhes que valem nota

- **Uma rota, um verbo.** Tudo é `POST /graphql` com `{"query": ..., "variables": ...}`.
  Não há `GET /usuarios/1` para cachear nem status por operação: cache de HTTP e
  balanceamento por URL simplesmente não têm onde se apoiar (o "cache" possível é do
  cliente, por campo, ou automático via persisted queries).
- **Tipos em vez de convenção.** O contrato é o schema, com tipos não-nulos (`Usuario!`),
  listas (`[Post!]!`), enums e inputs. O `curl` mal-escrito costuma falhar na **validação
  do schema**, não no servidor — inclusive com status `400` e `errors[]` quando a consulta
  nem é executada.
- **Introspecção.** O cliente não precisa de documentação escrita à mão: `GET /graphql`
  no navegador abre o GraphiQL, que lê o schema e autocompleta. É a mesma informação do
  `esquema.graphql`.
- **Variáveis e aliases.** `query Feed($usuarioId: Int!)` evita concatenar strings e
  permite reaproveitar a mesma consulta; aliases (`naoAchou: usuario(id: 999)`) permitem
  pedir o mesmo campo com argumentos diferentes na mesma requisição.
- **Sem N+1 de rede, mas com N+1 interno.** Os campos aninhados são resolvidos campo a
  campo no servidor; aqui, com armazenamento em memória, isso é barato. Num banco
  relacional isso viraria N+1 *de banco* — a solução usual é `DataLoader` (batching) no
  servidor. Ou seja: o GraphQL resolve o problema de **round-trips da rede**, não o de
  consultas do banco.
- **`criadoEm` é o scalar `DateTime`** (ISO-8601). O REST devolve `...Z` (Pydantic); aqui
  sai `...+00:00` (Strawberry) — ambos ISO-8601, só muda a forma do fuso.
- **Tudo GET/leitura é POST.** Isso quebra a semântica de idempotência segura do HTTP:
  proxies e retries enxergam uma mutation como um POST opaco.

## 9. Limitações conscientes

Estado em memória (sem banco), sem autenticação/autorização, sem paginação (nem
`first`/`after` estilo Relay), sem `DataLoader`, sem persisted queries, sem assinaturas
(subscriptions — que exigiriam WebSockets e não fazem parte do escopo). O objetivo é
comparar protocolos, não entregar produção.
