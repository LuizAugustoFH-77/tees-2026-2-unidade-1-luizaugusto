"""Domínio da rede social + armazenamento em memória (projeto GraphQL).

Este arquivo NÃO conhece GraphQL: ele só guarda o estado e aplica as regras do
domínio. Quem traduz as operações para um schema GraphQL (campos, argumentos,
mutations) é o `aplicacao.py`.

O projeto `rest-json/` tem uma cópia quase idêntica deste arquivo: é de propósito.
Assim, qualquer diferença percebida nos exemplos vem do protocolo, e não de um
domínio escrito de forma diferente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


# --------------------------------------------------------------------------
# Erros de domínio, independentes de protocolo
# --------------------------------------------------------------------------
class ErroDominio(Exception):
    """Erro de regra de negócio.

    `codigo` é um identificador estável (ex.: NAO_ENCONTRADO, JA_CURTIU).
    Cada camada de protocolo decide como expor isso:

    - REST    -> código de status HTTP (ver MAPA_STATUS em aplicacao.py, no
                 projeto rest-json)
    - GraphQL -> item em `errors[]` com `extensions.code`

    O atributo `extensions` existe para o GraphQL ler o código; em REST ele
    simplesmente não é usado.
    """

    def __init__(self, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.extensions = {"code": codigo}


# --------------------------------------------------------------------------
# Entidades do domínio (o mesmo desenho nos dois protocolos)
# --------------------------------------------------------------------------
@dataclass
class Perfil:
    """1 : 1 com Usuario."""

    bio: str = ""
    avatar_url: str = ""
    localizacao: str = ""
    site: str = ""


@dataclass
class Usuario:
    id: int
    nome: str
    email: str
    criado_em: datetime
    perfil: Perfil


@dataclass
class Post:
    """1 : N com Usuario (autor)."""

    id: int
    autor_id: int
    texto: str
    criado_em: datetime


@dataclass
class Comentario:
    """Liga Usuario e Post (N : M com atributo `texto`)."""

    id: int
    post_id: int
    autor_id: int
    texto: str
    criado_em: datetime


@dataclass
class Curtida:
    """Usuario x Post (N : M com atributo `criado_em`)."""

    id: int
    post_id: int
    usuario_id: int
    criado_em: datetime


@dataclass
class Seguidor:
    """Usuario x Usuario (N : M puro, auto-relacionamento)."""

    seguidor_id: int
    seguido_id: int
    criado_em: datetime


# --------------------------------------------------------------------------
# Validação
# --------------------------------------------------------------------------
def _exigir_texto(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroDominio("DADOS_INVALIDOS", f"o campo '{campo}' é obrigatório")
    return valor.strip()


def _exigir_email(valor: object) -> str:
    email = _exigir_texto(valor, "email").lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ErroDominio("DADOS_INVALIDOS", f"e-mail inválido: {email}")
    return email


def agora() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Armazenamento
# --------------------------------------------------------------------------
class Armazenamento:
    """Estado global em memória (reinicia quando o servidor reinicia)."""

    def __init__(self) -> None:
        self.usuarios: dict[int, Usuario] = {}
        self.posts: dict[int, Post] = {}
        self.comentarios: dict[int, Comentario] = {}
        self.curtidas: list[Curtida] = []
        self.seguidores: list[Seguidor] = []
        self._sequencias = {"usuario": 0, "post": 0, "comentario": 0, "curtida": 0}
        self.semear()

    # ---------------- comandos (escrita) ----------------
    def criar_usuario(
        self,
        nome: str,
        email: str,
        perfil: Perfil | None = None,
        momento: datetime | None = None,
    ) -> Usuario:
        """criar_usuario(nome, email).

        `perfil` é opcional e serve só para preencher o Perfil 1:1, já que o
        enunciado não pede uma operação de editar perfil.
        """
        nome = _exigir_texto(nome, "nome")
        email = _exigir_email(email)
        if any(u.email == email for u in self.usuarios.values()):
            raise ErroDominio("EMAIL_JA_EXISTE", f"já existe usuário com o e-mail {email}")

        usuario = Usuario(
            id=self._proximo_id("usuario"),
            nome=nome,
            email=email,
            criado_em=momento or agora(),
            perfil=perfil or Perfil(),
        )
        self.usuarios[usuario.id] = usuario
        return usuario

    def criar_post(self, usuario_id: int, texto: str, momento: datetime | None = None) -> Post:
        """criar_post(usuario_id, texto)."""
        autor = self.usuario_ou_erro(usuario_id)
        post = Post(
            id=self._proximo_id("post"),
            autor_id=autor.id,
            texto=_exigir_texto(texto, "texto"),
            criado_em=momento or agora(),
        )
        self.posts[post.id] = post
        return post

    def comentar(
        self, usuario_id: int, post_id: int, texto: str, momento: datetime | None = None
    ) -> Comentario:
        """comentar(usuario_id, post_id, texto)."""
        autor = self.usuario_ou_erro(usuario_id)
        post = self.post_ou_erro(post_id)
        comentario = Comentario(
            id=self._proximo_id("comentario"),
            post_id=post.id,
            autor_id=autor.id,
            texto=_exigir_texto(texto, "texto"),
            criado_em=momento or agora(),
        )
        self.comentarios[comentario.id] = comentario
        return comentario

    def curtir(self, usuario_id: int, post_id: int, momento: datetime | None = None) -> Curtida:
        """curtir(usuario_id, post_id) — curtiu duas vezes, dá erro."""
        usuario = self.usuario_ou_erro(usuario_id)
        post = self.post_ou_erro(post_id)
        if self.curtida_existente(usuario.id, post.id):
            raise ErroDominio("JA_CURTIU", f"{usuario.nome} já curtiu o post {post.id}")

        curtida = Curtida(
            id=self._proximo_id("curtida"),
            post_id=post.id,
            usuario_id=usuario.id,
            criado_em=momento or agora(),
        )
        self.curtidas.append(curtida)
        return curtida

    def seguir(self, usuario_id: int, alvo_id: int, momento: datetime | None = None) -> Seguidor:
        """seguir(usuario_id, alvo_id) — não dá para seguir a si mesmo nem repetir."""
        seguidor = self.usuario_ou_erro(usuario_id)
        alvo = self.usuario_ou_erro(alvo_id)
        if seguidor.id == alvo.id:
            raise ErroDominio("AUTO_SEGUIR", "um usuário não pode seguir a si mesmo")
        if self.segue(seguidor.id, alvo.id):
            raise ErroDominio("JA_SEGUE", f"{seguidor.nome} já segue {alvo.nome}")

        registro = Seguidor(seguidor_id=seguidor.id, seguido_id=alvo.id, criado_em=momento or agora())
        self.seguidores.append(registro)
        return registro

    # ---------------- consultas (leitura) ----------------
    def buscar_usuario(self, usuario_id: int) -> Usuario:
        """buscar_usuario(id)."""
        return self.usuario_ou_erro(usuario_id)

    def buscar_post(self, post_id: int) -> Post:
        """buscar_post(id)."""
        return self.post_ou_erro(post_id)

    def posts_do_usuario(self, usuario_id: int) -> list[Post]:
        """posts_do_usuario(usuario_id), mais recentes primeiro."""
        usuario = self.usuario_ou_erro(usuario_id)
        return self._mais_recentes(p for p in self.posts.values() if p.autor_id == usuario.id)

    def seguidores_de(self, usuario_id: int) -> list[Usuario]:
        """seguidores_de(id): quem segue esse usuário."""
        usuario = self.usuario_ou_erro(usuario_id)
        ids = [s.seguidor_id for s in self.seguidores if s.seguido_id == usuario.id]
        return [self.usuarios[i] for i in ids]

    def seguindo_de(self, usuario_id: int) -> list[Usuario]:
        """seguindo_de(id): quem esse usuário segue."""
        usuario = self.usuario_ou_erro(usuario_id)
        ids = [s.seguido_id for s in self.seguidores if s.seguidor_id == usuario.id]
        return [self.usuarios[i] for i in ids]

    def feed_do_usuario(self, usuario_id: int) -> list[Post]:
        """feed_do_usuario(usuario_id): posts de quem eu sigo + os meus, recentes primeiro."""
        usuario = self.usuario_ou_erro(usuario_id)
        seguidos = {s.seguido_id for s in self.seguidores if s.seguidor_id == usuario.id}
        autorelevantes = seguidos | {usuario.id}
        return self._mais_recentes(p for p in self.posts.values() if p.autor_id in autorelevantes)

    # ---------------- derivados / apoio ----------------
    def comentarios_do_post(self, post_id: int) -> list[Comentario]:
        post = self.post_ou_erro(post_id)
        return sorted(
            (c for c in self.comentarios.values() if c.post_id == post.id),
            key=lambda c: (c.criado_em, c.id),
        )

    def curtidas_do_post(self, post_id: int) -> list[Curtida]:
        post = self.post_ou_erro(post_id)
        return [c for c in self.curtidas if c.post_id == post.id]

    def total_curtidas(self, post_id: int) -> int:
        return len([c for c in self.curtidas if c.post_id == post_id])

    def total_comentarios(self, post_id: int) -> int:
        return len([c for c in self.comentarios.values() if c.post_id == post_id])

    def total_posts(self, usuario_id: int) -> int:
        return len([p for p in self.posts.values() if p.autor_id == usuario_id])

    def total_seguidores(self, usuario_id: int) -> int:
        return len([s for s in self.seguidores if s.seguido_id == usuario_id])

    def total_seguindo(self, usuario_id: int) -> int:
        return len([s for s in self.seguidores if s.seguidor_id == usuario_id])

    def usuario_ou_erro(self, usuario_id: int) -> Usuario:
        usuario = self.usuarios.get(usuario_id)
        if usuario is None:
            raise ErroDominio("NAO_ENCONTRADO", f"usuário {usuario_id} não existe")
        return usuario

    def post_ou_erro(self, post_id: int) -> Post:
        post = self.posts.get(post_id)
        if post is None:
            raise ErroDominio("NAO_ENCONTRADO", f"post {post_id} não existe")
        return post

    # ---------------- interno ----------------
    def _proximo_id(self, tipo: str) -> int:
        self._sequencias[tipo] += 1
        return self._sequencias[tipo]

    @staticmethod
    def _mais_recentes(posts) -> list[Post]:
        return sorted(posts, key=lambda p: (p.criado_em, p.id), reverse=True)

    def curtida_existente(self, usuario_id: int, post_id: int) -> Curtida | None:
        for curtida in self.curtidas:
            if curtida.usuario_id == usuario_id and curtida.post_id == post_id:
                return curtida
        return None

    def segue(self, seguidor_id: int, seguido_id: int) -> bool:
        return any(s.seguidor_id == seguidor_id and s.seguido_id == seguido_id for s in self.seguidores)

    # ---------------- dados de exemplo ----------------
    def semear(self) -> None:
        """Estado inicial fixo: os exemplos do README usam esses IDs (1, 2, 3...)."""
        base = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)

        def em(minuto: int) -> datetime:
            return base + timedelta(minutes=minuto)

        ana = self.criar_usuario(
            "Ana Souza",
            "ana@exemplo.com",
            Perfil(
                bio="Backend, APIs e protocolos",
                avatar_url="https://exemplo.com/avatares/ana.png",
                localizacao="Goiânia, GO",
                site="https://ana.dev",
            ),
            momento=em(0),
        )
        bruno = self.criar_usuario(
            "Bruno Lima",
            "bruno@exemplo.com",
            Perfil(
                bio="Frontend e GraphQL",
                avatar_url="https://exemplo.com/avatares/bruno.png",
                localizacao="Goiânia, GO",
            ),
            momento=em(1),
        )
        carla = self.criar_usuario(
            "Carla Dias",
            "carla@exemplo.com",
            Perfil(
                bio="Dados e observabilidade",
                avatar_url="https://exemplo.com/avatares/carla.png",
                localizacao="Anápolis, GO",
            ),
            momento=em(2),
        )

        self.seguir(ana.id, bruno.id, momento=em(3))
        self.seguir(ana.id, carla.id, momento=em(4))
        self.seguir(bruno.id, ana.id, momento=em(5))
        self.seguir(carla.id, ana.id, momento=em(6))

        primeiro = self.criar_post(bruno.id, "Primeiro post do Bruno: testando a API", momento=em(10))
        self.criar_post(carla.id, "Carla estreando no feed", momento=em(12))
        terceiro = self.criar_post(ana.id, "Escrevendo sobre REST x GraphQL", momento=em(14))
        quarto = self.criar_post(bruno.id, "GraphQL resolve o feed em uma requisição", momento=em(16))

        self.comentar(carla.id, primeiro.id, "Boa, Bruno!", momento=em(20))
        self.comentar(ana.id, primeiro.id, "Gostei do formato do feed", momento=em(21))
        self.comentar(bruno.id, terceiro.id, "Concordo, Ana", momento=em(22))

        self.curtir(ana.id, primeiro.id, momento=em(30))
        self.curtir(carla.id, primeiro.id, momento=em(31))
        self.curtir(bruno.id, terceiro.id, momento=em(32))
        self.curtir(ana.id, quarto.id, momento=em(33))
