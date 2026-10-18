"""API REST/JSON da rede social (FastAPI).

Regra de ouro deste projeto: o armazenamento expõe operações nomeadas
(`criar_post`, `feed_do_usuario`, ...); aqui elas viram *recursos HTTP* com
método, rota, código de status e cabeçalhos.

    comando/consulta do domínio  ->  REST
    ------------------------------------------------------------------
    criar_usuario(nome, email)   ->  POST   /usuarios
    criar_post(id, texto)        ->  POST   /posts
    comentar(id, post_id, texto) ->  POST   /posts/{post_id}/comentarios
    curtir(id, post_id)          ->  POST   /posts/{post_id}/curtidas
    seguir(id, alvo_id)          ->  POST   /usuarios/{id}/seguindo
    buscar_usuario(id)           ->  GET    /usuarios/{id}
    posts_do_usuario(id)         ->  GET    /usuarios/{id}/posts
    buscar_post(id)              ->  GET    /posts/{id}
    seguidores_de(id)            ->  GET    /usuarios/{id}/seguidores
    seguindo_de(id)              ->  GET    /usuarios/{id}/seguindo
    feed_do_usuario(id)          ->  GET    /usuarios/{id}/feed

Para subir: `uvicorn aplicacao:aplicacao --port 8000`
Documentação interativa gerada de graça: http://localhost:8000/docs
"""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from armazenamento import Armazenamento, ErroDominio, Perfil

bd = Armazenamento()

aplicacao = FastAPI(
    title="Rede Social — REST/JSON",
    version="1.0.0",
    description="Mesmo domínio do projeto graphql/, exposto como recursos HTTP.",
)


# --------------------------------------------------------------------------
# Erros de domínio -> códigos de status HTTP
# --------------------------------------------------------------------------
# Em REST o erro também é uma informação de protocolo: o cliente decide o que
# fazer olhando o status, sem precisar interpretar o corpo da resposta.
MAPA_STATUS = {
    "NAO_ENCONTRADO": 404,   # Not Found
    "EMAIL_JA_EXISTE": 409,  # Conflict
    "JA_CURTIU": 409,        # Conflict
    "JA_SEGUE": 409,         # Conflict
    "AUTO_SEGUIR": 422,      # Unprocessable Entity
    "DADOS_INVALIDOS": 422,  # Unprocessable Entity
}


@aplicacao.exception_handler(ErroDominio)
async def tratar_erro_de_dominio(requisicao: Request, erro: ErroDominio) -> JSONResponse:
    return JSONResponse(
        status_code=MAPA_STATUS.get(erro.codigo, 400),
        content={"erro": {"codigo": erro.codigo, "mensagem": erro.mensagem}},
    )


# --------------------------------------------------------------------------
# Corpos aceitos nos comandos
# --------------------------------------------------------------------------
class EntradaPerfil(BaseModel):
    bio: str | None = None
    avatar_url: str | None = None
    localizacao: str | None = None
    site: str | None = None


class EntradaCriarUsuario(BaseModel):
    nome: str
    email: str
    perfil: EntradaPerfil | None = None  # opcional: só para preencher o Perfil 1:1


class EntradaCriarPost(BaseModel):
    usuario_id: int
    texto: str


class EntradaComentar(BaseModel):
    usuario_id: int
    texto: str


class EntradaCurtir(BaseModel):
    usuario_id: int


class EntradaSeguir(BaseModel):
    alvo_id: int


# --------------------------------------------------------------------------
# Formatos de saída (o `response_model` também gera a documentação Swagger)
# --------------------------------------------------------------------------
class PerfilSaida(BaseModel):
    bio: str
    avatar_url: str
    localizacao: str
    site: str


class UsuarioResumoSaida(BaseModel):
    id: int
    nome: str
    email: str


class UsuarioSaida(UsuarioResumoSaida):
    criado_em: datetime
    perfil: PerfilSaida
    total_seguidores: int
    total_seguindo: int
    total_posts: int


class PostResumoSaida(BaseModel):
    id: int
    texto: str
    criado_em: datetime
    autor: UsuarioResumoSaida
    total_curtidas: int
    total_comentarios: int


class ComentarioSaida(BaseModel):
    id: int
    texto: str
    criado_em: datetime
    autor: UsuarioResumoSaida


class CurtidaSaida(BaseModel):
    criado_em: datetime
    usuario: UsuarioResumoSaida


class PostDetalhadoSaida(PostResumoSaida):
    comentarios: list[ComentarioSaida]
    curtidas: list[CurtidaSaida]


class PostsDoUsuarioSaida(BaseModel):
    usuario: UsuarioResumoSaida
    total: int
    posts: list[PostResumoSaida]


class SeguidoresSaida(BaseModel):
    usuario: UsuarioResumoSaida
    total: int
    seguidores: list[UsuarioResumoSaida]


class SeguindoSaida(BaseModel):
    usuario: UsuarioResumoSaida
    total: int
    seguindo: list[UsuarioResumoSaida]


class FeedSaida(BaseModel):
    usuario: UsuarioResumoSaida
    total: int
    posts: list[PostResumoSaida]


# --------------------------------------------------------------------------
# Conversão domínio -> JSON
# --------------------------------------------------------------------------
def resumo_usuario(usuario_id: int) -> dict:
    usuario = bd.usuario_ou_erro(usuario_id)
    return {"id": usuario.id, "nome": usuario.nome, "email": usuario.email}


def saida_usuario(usuario_id: int) -> dict:
    usuario = bd.buscar_usuario(usuario_id)
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "criado_em": usuario.criado_em,
        "perfil": {
            "bio": usuario.perfil.bio,
            "avatar_url": usuario.perfil.avatar_url,
            "localizacao": usuario.perfil.localizacao,
            "site": usuario.perfil.site,
        },
        "total_seguidores": bd.total_seguidores(usuario.id),
        "total_seguindo": bd.total_seguindo(usuario.id),
        "total_posts": bd.total_posts(usuario.id),
    }


def saida_post_resumo(post_id: int) -> dict:
    post = bd.post_ou_erro(post_id)
    return {
        "id": post.id,
        "texto": post.texto,
        "criado_em": post.criado_em,
        "autor": resumo_usuario(post.autor_id),
        "total_curtidas": bd.total_curtidas(post.id),
        "total_comentarios": bd.total_comentarios(post.id),
    }


def saida_comentario(comentario_id: int) -> dict:
    comentario = bd.comentarios[comentario_id]
    return {
        "id": comentario.id,
        "texto": comentario.texto,
        "criado_em": comentario.criado_em,
        "autor": resumo_usuario(comentario.autor_id),
    }


# --------------------------------------------------------------------------
# Comandos
# --------------------------------------------------------------------------
@aplicacao.post("/usuarios", response_model=UsuarioSaida, status_code=201, tags=["comandos"])
def criar_usuario(entrada: EntradaCriarUsuario):
    """criar_usuario(nome, email).

    201 Created + cabeçalho Location apontando para o recurso recém-criado.
    """
    dados_perfil = entrada.perfil.model_dump() if entrada.perfil else None
    usuario = bd.criar_usuario(
        entrada.nome,
        entrada.email,
        Perfil(**dados_perfil) if dados_perfil else None,
    )
    return saida_usuario(usuario.id)


@aplicacao.post("/posts", response_model=PostResumoSaida, status_code=201, tags=["comandos"])
def criar_post(entrada: EntradaCriarPost):
    """criar_post(usuario_id, texto)."""
    post = bd.criar_post(entrada.usuario_id, entrada.texto)
    return saida_post_resumo(post.id)


@aplicacao.post(
    "/posts/{post_id}/comentarios",
    response_model=ComentarioSaida,
    status_code=201,
    tags=["comandos"],
)
def comentar(post_id: int, entrada: EntradaComentar):
    """comentar(usuario_id, post_id, texto)."""
    comentario = bd.comentar(entrada.usuario_id, post_id, entrada.texto)
    return saida_comentario(comentario.id)


@aplicacao.post(
    "/posts/{post_id}/curtidas",
    response_model=CurtidaSaida,
    status_code=201,
    tags=["comandos"],
)
def curtir(post_id: int, entrada: EntradaCurtir):
    """curtir(usuario_id, post_id) — curtir duas vezes devolve 409 Conflict."""
    curtida = bd.curtir(entrada.usuario_id, post_id)
    return {"criado_em": curtida.criado_em, "usuario": resumo_usuario(curtida.usuario_id)}


@aplicacao.post(
    "/usuarios/{usuario_id}/seguindo",
    response_model=SeguindoSaida,
    status_code=201,
    tags=["comandos"],
)
def seguir(usuario_id: int, entrada: EntradaSeguir):
    """seguir(usuario_id, alvo_id) — devolve a lista `seguindo` atualizada."""
    bd.seguir(usuario_id, entrada.alvo_id)
    return {
        "usuario": resumo_usuario(usuario_id),
        "total": bd.total_seguindo(usuario_id),
        "seguindo": [resumo_usuario(u.id) for u in bd.seguindo_de(usuario_id)],
    }


# --------------------------------------------------------------------------
# Consultas
# --------------------------------------------------------------------------
@aplicacao.get("/usuarios/{usuario_id}", response_model=UsuarioSaida, tags=["consultas"])
def buscar_usuario(usuario_id: int):
    """buscar_usuario(id)."""
    return saida_usuario(usuario_id)


@aplicacao.get(
    "/usuarios/{usuario_id}/posts",
    response_model=PostsDoUsuarioSaida,
    tags=["consultas"],
)
def posts_do_usuario(usuario_id: int):
    """posts_do_usuario(usuario_id), mais recentes primeiro."""
    usuario = bd.usuario_ou_erro(usuario_id)
    posts = bd.posts_do_usuario(usuario.id)
    return {
        "usuario": {"id": usuario.id, "nome": usuario.nome, "email": usuario.email},
        "total": len(posts),
        "posts": [saida_post_resumo(p.id) for p in posts],
    }


@aplicacao.get("/posts/{post_id}", response_model=PostDetalhadoSaida, tags=["consultas"])
def buscar_post(post_id: int):
    """buscar_post(id) — traz autor, comentários e curtidas do post."""
    detalhado = saida_post_resumo(post_id)
    detalhado["comentarios"] = [
        saida_comentario(c.id) for c in bd.comentarios_do_post(post_id)
    ]
    detalhado["curtidas"] = [
        {"criado_em": c.criado_em, "usuario": resumo_usuario(c.usuario_id)}
        for c in bd.curtidas_do_post(post_id)
    ]
    return detalhado


@aplicacao.get(
    "/usuarios/{usuario_id}/seguidores",
    response_model=SeguidoresSaida,
    tags=["consultas"],
)
def seguidores_de(usuario_id: int):
    """seguidores_de(id): quem segue esse usuário."""
    usuario = bd.usuario_ou_erro(usuario_id)
    seguidores = bd.seguidores_de(usuario.id)
    return {
        "usuario": {"id": usuario.id, "nome": usuario.nome, "email": usuario.email},
        "total": len(seguidores),
        "seguidores": [
            {"id": u.id, "nome": u.nome, "email": u.email} for u in seguidores
        ],
    }


@aplicacao.get(
    "/usuarios/{usuario_id}/seguindo",
    response_model=SeguindoSaida,
    tags=["consultas"],
)
def seguindo_de(usuario_id: int):
    """seguindo_de(id): quem esse usuário segue."""
    usuario = bd.usuario_ou_erro(usuario_id)
    seguindo = bd.seguindo_de(usuario.id)
    return {
        "usuario": {"id": usuario.id, "nome": usuario.nome, "email": usuario.email},
        "total": len(seguindo),
        "seguindo": [{"id": u.id, "nome": u.nome, "email": u.email} for u in seguindo],
    }


@aplicacao.get("/usuarios/{usuario_id}/feed", response_model=FeedSaida, tags=["consultas"])
def feed_do_usuario(usuario_id: int):
    """feed_do_usuario(usuario_id): posts de quem eu sigo + os meus."""
    usuario = bd.usuario_ou_erro(usuario_id)
    posts = bd.feed_do_usuario(usuario.id)
    return {
        "usuario": {"id": usuario.id, "nome": usuario.nome, "email": usuario.email},
        "total": len(posts),
        "posts": [saida_post_resumo(p.id) for p in posts],
    }
