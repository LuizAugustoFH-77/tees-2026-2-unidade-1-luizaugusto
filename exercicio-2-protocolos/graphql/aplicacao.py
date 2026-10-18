"""API GraphQL da rede social (Strawberry + FastAPI).

Diferença central em relação ao projeto `rest-json/`:

- REST expõe *recursos* em várias rotas; o cliente monta o resultado com
  várias requisições (ou recebe mais do que pediu).
- GraphQL expõe *um grafo de tipos* em uma única rota (`POST /graphql`); o
  cliente escreve a consulta dizendo exatamente quais campos e quais relações
  quer, e o servidor resolve tudo numa requisição.

O domínio (arquivo `armazenamento.py`) é o mesmo nos dois projetos; aqui ele é
ligado ao schema assim:

    criar_usuario(nome, email) -> mutation criarUsuario(nome, email)
    criar_post(usuario_id, texto) -> mutation criarPost(usuarioId, texto)
    comentar(usuario_id, post_id, texto) -> mutation comentar(usuarioId, postId, texto)
    curtir(usuario_id, post_id) -> mutation curtir(usuarioId, postId)
    seguir(usuario_id, alvo_id) -> mutation seguir(usuarioId, alvoId)

    buscar_usuario(id) -> query usuario(id)
    posts_do_usuario(usuario_id) -> query postsDoUsuario(usuarioId)
    buscar_post(id) -> query post(id)
    seguidores_de(id) -> query seguidoresDe(id)
    seguindo_de(id) -> query seguindoDe(id)
    feed_do_usuario(usuario_id) -> query feedDoUsuario(usuarioId)

Campos aninhados (autor de um post, comentários, curtidas, seguidores de um
usuário) não são argumentos: são campos do tipo, resolvidos só se o cliente
pedir. O Strawberry converte nomes snake_case do Python para camelCase no
schema, que é a convenção do GraphQL.

Para subir: `uvicorn aplicacao:aplicacao --port 8001`
Interface de exploração (GraphiQL): http://localhost:8001/graphql
"""

from __future__ import annotations

from datetime import datetime

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

import armazenamento as dom
from armazenamento import Armazenamento, ErroDominio
from armazenamento import Perfil as PerfilDominio

bd = Armazenamento()


# --------------------------------------------------------------------------
# Tipos do domínio
# --------------------------------------------------------------------------
# Campos "Private" existem só no Python (chaves estrangeiras): eles não
# aparecem no schema e servem para os resolvers aninhados consultarem o
# armazenamento sob demanda.
@strawberry.type
class Perfil:
    bio: str
    avatar_url: str
    localizacao: str
    site: str


@strawberry.type
class Usuario:
    id: int
    nome: str
    email: str
    criado_em: datetime

    @strawberry.field
    def perfil(self) -> Perfil:
        u = bd.buscar_usuario(self.id)
        return Perfil(
            bio=u.perfil.bio,
            avatar_url=u.perfil.avatar_url,
            localizacao=u.perfil.localizacao,
            site=u.perfil.site,
        )

    @strawberry.field
    def total_seguidores(self) -> int:
        return bd.total_seguidores(self.id)

    @strawberry.field
    def total_seguindo(self) -> int:
        return bd.total_seguindo(self.id)

    @strawberry.field
    def total_posts(self) -> int:
        return bd.total_posts(self.id)

    @strawberry.field
    def posts(self) -> list[Post]:
        return [para_post(p) for p in bd.posts_do_usuario(self.id)]

    @strawberry.field
    def seguidores(self) -> list[Usuario]:
        return [para_usuario(u) for u in bd.seguidores_de(self.id)]

    @strawberry.field
    def seguindo(self) -> list[Usuario]:
        return [para_usuario(u) for u in bd.seguindo_de(self.id)]


@strawberry.type
class Comentario:
    id: int
    texto: str
    criado_em: datetime
    autor_id: strawberry.Private[int]
    post_id: strawberry.Private[int]

    @strawberry.field
    def autor(self) -> Usuario:
        return para_usuario(bd.usuario_ou_erro(self.autor_id))

    @strawberry.field
    def post(self) -> Post:
        return para_post(bd.post_ou_erro(self.post_id))


@strawberry.type
class Curtida:
    criado_em: datetime
    usuario_id: strawberry.Private[int]
    post_id: strawberry.Private[int]

    @strawberry.field
    def usuario(self) -> Usuario:
        return para_usuario(bd.usuario_ou_erro(self.usuario_id))

    @strawberry.field
    def post(self) -> Post:
        return para_post(bd.post_ou_erro(self.post_id))


@strawberry.type
class Post:
    id: int
    texto: str
    criado_em: datetime
    autor_id: strawberry.Private[int]

    @strawberry.field
    def autor(self) -> Usuario:
        return para_usuario(bd.usuario_ou_erro(self.autor_id))

    @strawberry.field
    def comentarios(self) -> list[Comentario]:
        return [para_comentario(c) for c in bd.comentarios_do_post(self.id)]

    @strawberry.field
    def curtidas(self) -> list[Curtida]:
        return [para_curtida(c) for c in bd.curtidas_do_post(self.id)]

    @strawberry.field
    def total_curtidas(self) -> int:
        return bd.total_curtidas(self.id)

    @strawberry.field
    def total_comentarios(self) -> int:
        return bd.total_comentarios(self.id)


@strawberry.type
class Seguidor:
    criado_em: datetime
    seguidor_id: strawberry.Private[int]
    seguido_id: strawberry.Private[int]

    @strawberry.field
    def seguidor(self) -> Usuario:
        return para_usuario(bd.usuario_ou_erro(self.seguidor_id))

    @strawberry.field
    def seguido(self) -> Usuario:
        return para_usuario(bd.usuario_ou_erro(self.seguido_id))


# --------------------------------------------------------------------------
# Conversão domínio -> tipo GraphQL
# --------------------------------------------------------------------------
def para_usuario(obj: dom.Usuario) -> Usuario:
    return Usuario(id=obj.id, nome=obj.nome, email=obj.email, criado_em=obj.criado_em)


def para_post(obj: dom.Post) -> Post:
    return Post(id=obj.id, texto=obj.texto, criado_em=obj.criado_em, autor_id=obj.autor_id)


def para_comentario(obj: dom.Comentario) -> Comentario:
    return Comentario(
        id=obj.id,
        texto=obj.texto,
        criado_em=obj.criado_em,
        autor_id=obj.autor_id,
        post_id=obj.post_id,
    )


def para_curtida(obj: dom.Curtida) -> Curtida:
    return Curtida(criado_em=obj.criado_em, usuario_id=obj.usuario_id, post_id=obj.post_id)


def para_seguidor(obj: dom.Seguidor) -> Seguidor:
    return Seguidor(
        criado_em=obj.criado_em,
        seguidor_id=obj.seguidor_id,
        seguido_id=obj.seguido_id,
    )


# --------------------------------------------------------------------------
# Entrada de dados
# --------------------------------------------------------------------------
@strawberry.input
class EntradaPerfil:
    """Opcional em criarUsuario: só serve para preencher o Perfil 1:1."""

    bio: str = ""
    avatar_url: str = ""
    localizacao: str = ""
    site: str = ""


# --------------------------------------------------------------------------
# Consultas (queries)
# --------------------------------------------------------------------------
@strawberry.type
class Consulta:
    """Raiz de leitura.

    O GraphQL chama esta raiz de `Query`; aqui ela é `Consulta`, e o SDL gerado
    registra o mapeamento (`schema { query: Consulta }`).
    """

    @strawberry.field
    def usuario(self, id: int) -> Usuario | None:
        """buscar_usuario(id) — devolve `null` se o usuário não existir.

        No GraphQL "não achei" normalmente é `null` no campo, e não um erro:
        quem consulta pede justamente para poder receber nada.
        """
        try:
            return para_usuario(bd.buscar_usuario(id))
        except ErroDominio as erro:
            if erro.codigo == "NAO_ENCONTRADO":
                return None
            raise

    @strawberry.field
    def posts_do_usuario(self, usuario_id: int) -> list[Post]:
        """posts_do_usuario(usuario_id)."""
        return [para_post(p) for p in bd.posts_do_usuario(usuario_id)]

    @strawberry.field
    def post(self, id: int) -> Post | None:
        """buscar_post(id) — devolve `null` se o post não existir."""
        try:
            return para_post(bd.buscar_post(id))
        except ErroDominio as erro:
            if erro.codigo == "NAO_ENCONTRADO":
                return None
            raise

    @strawberry.field
    def seguidores_de(self, id: int) -> list[Usuario]:
        """seguidores_de(id)."""
        return [para_usuario(u) for u in bd.seguidores_de(id)]

    @strawberry.field
    def seguindo_de(self, id: int) -> list[Usuario]:
        """seguindo_de(id)."""
        return [para_usuario(u) for u in bd.seguindo_de(id)]

    @strawberry.field
    def feed_do_usuario(self, usuario_id: int) -> list[Post]:
        """feed_do_usuario(usuario_id)."""
        return [para_post(p) for p in bd.feed_do_usuario(usuario_id)]


# --------------------------------------------------------------------------
# Comandos (mutations)
# --------------------------------------------------------------------------
@strawberry.type
class Mutacao:
    """Raiz de escrita (o GraphQL chama esta raiz de `Mutation`)."""

    @strawberry.mutation
    def criar_usuario(self, nome: str, email: str, perfil: EntradaPerfil | None = None) -> Usuario:
        """criar_usuario(nome, email)."""
        dados_perfil = (
            PerfilDominio(
                bio=perfil.bio,
                avatar_url=perfil.avatar_url,
                localizacao=perfil.localizacao,
                site=perfil.site,
            )
            if perfil
            else None
        )
        return para_usuario(bd.criar_usuario(nome, email, dados_perfil))

    @strawberry.mutation
    def criar_post(self, usuario_id: int, texto: str) -> Post:
        """criar_post(usuario_id, texto)."""
        return para_post(bd.criar_post(usuario_id, texto))

    @strawberry.mutation
    def comentar(self, usuario_id: int, post_id: int, texto: str) -> Comentario:
        """comentar(usuario_id, post_id, texto)."""
        return para_comentario(bd.comentar(usuario_id, post_id, texto))

    @strawberry.mutation
    def curtir(self, usuario_id: int, post_id: int) -> Curtida:
        """curtir(usuario_id, post_id)."""
        return para_curtida(bd.curtir(usuario_id, post_id))

    @strawberry.mutation
    def seguir(self, usuario_id: int, alvo_id: int) -> Seguidor:
        """seguir(usuario_id, alvo_id)."""
        return para_seguidor(bd.seguir(usuario_id, alvo_id))


# --------------------------------------------------------------------------
# Schema + aplicação HTTP
# --------------------------------------------------------------------------
esquema = strawberry.Schema(query=Consulta, mutation=Mutacao)

# O GraphQL sempre responde 200: um erro de regra de negócio aparece em
# `errors[]` com `extensions.code` (o ErroDominio já carrega esse dicionário).
aplicacao = FastAPI(title="Rede Social — GraphQL", version="1.0.0")
aplicacao.include_router(GraphQLRouter(esquema), prefix="/graphql")
