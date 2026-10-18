# Atividade 02 — APIs e protocolos: o mesmo domínio em REST/JSON e em GraphQL

**Disciplina:** Tópicos Especiais em Engenharia de Software
**Aluno:** Luiz Augusto
**Objetivo da atividade:** sentir na prática a diferença entre dois protocolos ao expor
o **mesmo domínio** (uma rede social simplificada) e saber quando cada um serve.

Os dois protocolos escolhidos foram **REST/JSON** e **GraphQL** — escolhidos justamente
por serem diferentes no que importa: um expõe *recursos* com verbos e status HTTP, o outro
expõe um *grafo de tipos* consultável pelo cliente em uma única rota.

| Projeto | Protocolo | Stack | Porta | README |
| --- | --- | --- | --- | --- |
| [`rest-json/`](rest-json/README.md) | REST/JSON | Python + FastAPI | 8000 | recurso, status, rotas |
| [`graphql/`](graphql/README.md) | GraphQL | Python + Strawberry | 8001 | schema, queries, mutations |

---

## 1. Como executar (resumo)

Os dois projetos são independentes e **podem rodar ao mesmo tempo** (portas diferentes).
Cada um tem instruções completas no seu README; o resumo é:

```powershell
# terminal 1 — REST/JSON  (http://localhost:8000)
cd rest-json
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r dependencias.txt
.\.venv\Scripts\python.exe -m uvicorn aplicacao:aplicacao --port 8000

# terminal 2 — GraphQL   (http://localhost:8001/graphql)
cd graphql
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r dependencias.txt
.\.venv\Scripts\python.exe -m uvicorn aplicacao:aplicacao --port 8001
```

No Linux/macOS, troque `.\.venv\Scripts\python.exe` por `.venv/bin/python`.

Depois, em cada pasta, `demonstracao.py` roda as 10 operações obrigatórias e imprime o relatório
de medição (é o que alimenta a seção 4 deste README):

```bash
cd rest-json  && python demonstracao.py      # (use o python do .venv)
cd graphql    && python demonstracao.py
```

Roteiro sugerido para "sentir" a diferença em 2 minutos:

1. REST: abra <http://localhost:8000/docs> e veja as rotas; depois
   `curl.exe -s http://localhost:8000/usuarios/1` — repare no `404` se trocar o id.
2. GraphQL: abra <http://localhost:8001/graphql> (GraphiQL), aperte `Ctrl+Espaço` dentro das
   chaves e peça `feedDoUsuario(usuarioId: 1) { texto autor { nome } comentarios { texto } }`
   — **uma** requisição, campos escolhidos por você, comentários inclusos.

---

## 2. O domínio (o mesmo nos dois projetos)

Entidades: **Usuario, Perfil, Post, Comentario, Curtida e Seguidor**.

```
Usuario 1:1 Perfil                 Usuario 1:N Post (autor)
Usuario N:M Post   via Curtida     Usuario N:M Usuario via Seguidor (auto-relacionamento)
Usuario N:M Post   via Comentario (com atributo texto)
```

O arquivo de domínio (`armazenamento.py`) é uma **cópia quase idêntica** nos dois projetos,
de propósito: assim as diferenças observadas vêm do protocolo, e não de um domínio escrito
de duas formas diferentes. Os dois usam a **mesma semente de dados** (Ana, Bruno e Carla;
4 posts; comentários; curtidas; seguidores), então os exemplos dos dois READMEs descrevem
exatamente o mesmo estado.

As operações obrigatórias e onde elas estão em cada protocolo:

| Operação | REST/JSON | GraphQL |
| --- | --- | --- |
| `criar_usuario(nome, email)` | `POST /usuarios` | `mutation criarUsuario(nome, email)` |
| `criar_post(usuario_id, texto)` | `POST /posts` | `mutation criarPost(usuarioId, texto)` |
| `comentar(usuario_id, post_id, texto)` | `POST /posts/{id}/comentarios` | `mutation comentar(usuarioId, postId, texto)` |
| `curtir(usuario_id, post_id)` | `POST /posts/{id}/curtidas` | `mutation curtir(usuarioId, postId)` |
| `seguir(usuario_id, alvo_id)` | `POST /usuarios/{id}/seguindo` | `mutation seguir(usuarioId, alvoId)` |
| `buscar_usuario(id)` | `GET /usuarios/{id}` | `query usuario(id)` |
| `posts_do_usuario(usuario_id)` | `GET /usuarios/{id}/posts` | `query postsDoUsuario(usuarioId)` |
| `buscar_post(id)` | `GET /posts/{id}` | `query post(id)` |
| `seguidores_de(id)` | `GET /usuarios/{id}/seguidores` | `query seguidoresDe(id)` |
| `seguindo_de(id)` | `GET /usuarios/{id}/seguindo` | `query seguindoDe(id)` |
| `feed_do_usuario(usuario_id)` | `GET /usuarios/{id}/feed` | `query feedDoUsuario(usuarioId)` |

Checklist do enunciado:

| Requisito | Onde está |
| --- | --- |
| 5 comandos + 5 consultas nos dois protocolos | [REST §3](rest-json/README.md#3-mapa-do-domínio-para-rest) · [GraphQL §3](graphql/README.md#3-o-schema-contrato-do-protocolo) |
| Exemplo de requisição e de resposta, copiável, para cada operação | [REST §4–§5](rest-json/README.md#4-exemplos-copiáveis--comandos) · [GraphQL §4–§6](graphql/README.md#4-exemplos-copiáveis--os-5-comandos-mutations) |
| Instruções para executar do zero | [REST §2](rest-json/README.md#2-como-executar-do-zero) · [GraphQL §2](graphql/README.md#2-como-executar-do-zero) |
| Uma linha dizendo o que **esse** protocolo faz melhor | [REST (topo)](rest-json/README.md) · [GraphQL (topo)](graphql/README.md) |
| README próprio em cada protocolo | `rest-json/README.md` · `graphql/README.md` |
| README com visão geral + comparação final | este arquivo |

**Convenção de nomenclatura:** nomes de arquivos e identificadores do código estão em
português (`armazenamento.py`, `aplicacao.py`, `demonstracao.py`, `criar_post`,
`total_curtidas`, ...). Ficou como o protocolo manda apenas o vocabulário que é do próprio
protocolo: verbos e códigos HTTP no REST (`POST`, `201`, `ETag`), nomes de tipo e campo do
GraphQL em camelCase (`criarUsuario`, `usuarioId`) e a chave `extensions` do formato de
erro do GraphQL.

---

## 3. Teste controlado (o que foi medido e como)

Para a comparação não virar opinião, os dois `demonstracao.py` executam **o mesmo roteiro**:
as 10 operações obrigatórias na mesma ordem (1 usuário novo, 1 post, 1 comentário, 1
curtida, 1 seguidor) e, com o estado idêntico nos dois servidores, medem dois cenários.
Contagem de bytes = tamanho do corpo da resposta; requisições = chamadas HTTP que o
**cliente** precisou fazer.

| Cenário | REST/JSON | GraphQL | Vencedor |
| --- | --- | --- | --- |
| **A** — "o feed da Ana com autor, contadores e os comentários de cada post" (4 posts) | **5 requisições** · **2813 bytes** | **1 requisição** · **1062 bytes** | GraphQL (5x menos ida e volta, 2,6x menos bytes) |
| **B** — "só os textos do feed da Ana" | **1 requisição** · **860 bytes** | **1 requisição** · **222 bytes** | GraphQL (3,9x menos bytes) |

Como ler cada cenário:

- **Cenário A — o N+1 *de rede* do REST.** `GET /usuarios/1/feed` devolve os posts, mas os
  comentários só existem em `GET /posts/{id}`; o cliente faz 1 + N chamadas. Em GraphQL,
  `comentarios` é campo do tipo `Post`, então tudo vem na mesma resposta.
  Num link com 100 ms de latência, isso é 1 × 100 ms contra 5 × 100 ms.
- **Cenário B — over-fetching do REST.** O recurso `/usuarios/1/feed` devolve sempre a
  mesma forma (autor com e-mail, contadores, envelope com o usuário); no GraphQL o cliente
  pediu `texto` e recebeu só `texto`.

Honestidade metodológica: os bytes do cenário A **não** são "o mesmo payload" — o REST
devolve, além do que o cliente pediu, os campos fixos da rota (e-mail do autor, envelope).
Isso é exatamente o over-fetching que se quer mostrar, não um erro de medição. E o ganho do
GraphQL é de **forma da resposta**, não de velocidade do servidor: no cenário A o GraphQL
faz *mais* trabalho interno (resolve campo a campo, o que num banco relacional viraria N+1
de consulta e pediria `DataLoader`), mas conversa menos pela rede.

Dois detalhes de serialização, dos dois lados, que também mexem (pouco) nos bytes e que
não estão "otimizados" em favor de nenhum dos projetos: o FastAPI manda acentos em UTF-8
cru (`Goiânia`), enquanto o Strawberry escapa (`Goi\u00e2nia`, 6 bytes em vez de 2); e o
REST escreve `criado_em`/`total_curtidas` em `snake_case` com `Z` no fuso, enquanto o
GraphQL usa `camelCase` com `+00:00`. Ambos são ISO-8601/JSON válidos — a diferença de
bytes é pequena e fica **a favor do REST** na contagem.

---

## 4. Comparação final

| Dimensão | REST/JSON | GraphQL |
| --- | --- | --- |
| Modelo mental | recursos + verbos + status | grafo de tipos + consultas declarativas |
| Endereçamento | uma URL por recurso (`/posts/1/comentarios`) | uma única rota (`POST /graphql`) |
| O que o cliente recebe | a forma fixa daquela rota | exatamente os campos que pediu |
| Contrato | implícito, documentado (aqui, OpenAPI/Swagger gerado) | explícito e tipado, no SDL, com introspecção |
| Tipagem/validação | tipos do framework (Pydantic) + regras do domínio | schema valida a consulta **antes** de executar + regras do domínio |
| Sucesso | `201`/`200` + JSON | `200` + `{"data": ...}` |
| Erro de regra | status próprio (`409`) + corpo `{"erro": {...}}` | `200` + `errors[]` com `extensions.code` |
| Não encontrado | `404 Not Found` | `null` no campo |
| Round-trips (cenário A) | 5 | 1 |
| Bytes (cenário A / B) | 2813 / 860 | 1062 / 222 |
| Cache HTTP (CDN, proxy, `ETag`) | nativo, de graça, por URL | não existe "de graça" (todo POST na mesma URL) |
| Observabilidade | cada rota/erro é um status, o APM já mede sozinho | tudo `200`: métrica por rota não distingue sucesso de erro |
| Ferramentas | `curl`, navegador, Swagger UI, Postman, qualquer cliente HTTP | GraphiQL, clientes e *codegen* a partir do schema |
| Evolução do contrato | nova rota/versão; campos fixos crescem para todos | adicionar campo/argumento não quebra quem não pede; `@deprecated` no schema |
| Curva de aprendizado | baixa (HTTP já é conhecido) | média (schema, resolvers, N+1 interno, erro em `200`) |
| Força no domínio | leitura pública previsível e cacheável, escrita com semântica de status | montagem sob medida de respostas aninhadas (perfil, feed, comentários) |
| Fraqueza no domínio | N+1 de rede e over-fetching nas telas que juntam várias relações | sem cache HTTP, tudo `POST`, erro fora do status |

### O que cada protocolo faz melhor que o outro, neste domínio (uma linha cada)

- **REST/JSON:** cada operação é um recurso com URL própria, então o resultado é cacheável
  e depurável com qualquer ferramenta que entende HTTP (navegador, `curl`, CDN, proxy,
  APM), com o desfecho visível no código de status — coisas que o GraphQL não oferece
  de graça atrás de uma rota única com corpo variável.
- **GraphQL:** o cliente monta a resposta sob medida em uma única requisição, pedindo só
  os campos e relações que vai usar — o feed completo com autor, contadores e comentários
  sai em 1 requisição e 1062 bytes, contra 5 requisições e 2813 bytes no REST.

### Quando usar cada um (a resposta prática)

- **REST** quando: a API é um conjunto de recursos com leituras previsíveis e cacheáveis
  (catálogo, perfil público, feed de leitura), os clientes são muitos e heterogêneos
  (web, mobile, integrações de terceiros), a equipe já tem ferramentas/proxies/gateways
  prontos e você quer que erro seja status HTTP, não campo do corpo.
- **GraphQL** quando: existem **várias telas diferentes** consumindo o mesmo backend
  (web, app, painel) e cada uma quer pedaços diferentes do grafo; quando a tela junta
  muitas relações (feed com autor + comentários + contadores) e as idas e voltas do REST
  já estão doendo; quando o frontend evolui rápido e você quer adicionar campo sem
  versionar rota. O custo é: schema para manter, cache HTTP que você perde, e N+1 interno
  para vigiar.
- **Nos dois casos**: nenhum dos dois é "melhor"; REST otimiza *operação e cache*,
  GraphQL otimiza *forma da resposta e evolução do contrato*. Neste domínio específico
  (rede social, telas que misturam relações, cliente mobile), o GraphQL atacou melhor a
  dor medida; o REST custou quase nada para subir e testar.

### O que ficou claro na prática

1. **A diferença apareceu na leitura, não na escrita.** Os cinco comandos ficaram
   parecidos nos dois protocolos (um `POST` bem-sucedido contra um `200` com `data`) e
   ambos deram praticamente o mesmo trabalho. A separação real veio nas consultas.
2. **O que muda é quem decide a forma da resposta.** No REST, quem decide é o servidor
   (a rota tem forma fixa). No GraphQL, quem decide é o cliente. Isso explica o N+1 e o
   over-fetching de um lado, e a ausência de cache HTTP do outro.
3. **Erro é a diferença mais desconfortável.** No REST, `409 Conflict` diz o que houve sem
   ler o corpo; no GraphQL, o status é `200` e o cliente precisa olhar `errors[]` — a
   convenção de `extensions.code` existe justamente por isso.
4. **GraphQL não elimina o N+1 — ele o move.** Tirar as idas e voltas do cliente empurra a
   resolução de cada campo para dentro do servidor. Com memória isso é irrelevante; com
   banco, seria N+1 de SQL e a resposta seria `DataLoader`.
5. **Modelar o domínio foi igual nos dois.** O mesmo `armazenamento.py` funcionou para os
   dois protocolos sem uma linha de diferença nas regras: o custo está todo na camada de
   protocolo, não no domínio.

---

## 5. Limitações conscientes dos dois projetos

Estado em memória (sem banco), sem autenticação/autorização, sem paginação, sem
`PUT`/`PATCH`/`DELETE` (o enunciado pede cinco comandos e nenhum deles foi inventado), sem
`DataLoader` no GraphQL, sem *subscriptions*, sem `ETag` no REST. O objetivo é comparar
protocolos com o mesmo domínio, não entregar um sistema de produção.
