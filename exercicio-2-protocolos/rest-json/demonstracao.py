"""Demonstração automatizada da API REST/JSON.

Roda as 10 operações obrigatórias (5 comandos + 5 consultas) mostrando a
requisição e a resposta, e no fim mede dois cenários para comparar com o
projeto GraphQL:

  Cenário A -- "feed detalhado": o feed do usuário e, para cada post do feed,
               os comentários completos de cada post.
  Cenário B -- "só os textos do feed": o cliente quer apenas o texto dos posts.

Os corpos dos comandos vêm de `exemplos/` (os mesmos arquivos usados nos
comandos `curl` do README), para que README e demonstração nunca fiquem diferentes.

Uso:
    python demonstracao.py                     # usa http://localhost:8000
    python demonstracao.py http://localhost:8000

Requisito: servidor recém-iniciado (o demo cria um usuário novo; se já existir,
ele avisa e pede para reiniciar o servidor). Depende só da biblioteca padrão.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

# O console do Windows costuma ser cp1252/cp850: evita quebrar ao imprimir
# respostas com caracteres fora dessa tabela.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

PASTA_EXEMPLOS = Path(__file__).with_name("exemplos")
ENDERECO_BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"

# (título, método, rota, arquivo do corpo em exemplos/ ou None)
OPERACOES = [
    ("COMANDO 1/5 - criar_usuario(nome, email)", "POST", "/usuarios", "01-criar-usuario.json"),
    ("COMANDO 2/5 - criar_post(usuario_id, texto)", "POST", "/posts", "02-criar-post.json"),
    ("COMANDO 3/5 - comentar(usuario_id, post_id, texto)", "POST", "/posts/1/comentarios", "03-comentar.json"),
    ("COMANDO 4/5 - curtir(usuario_id, post_id)", "POST", "/posts/3/curtidas", "04-curtir.json"),
    ("COMANDO 5/5 - seguir(usuario_id, alvo_id)", "POST", "/usuarios/4/seguindo", "05-seguir.json"),
    ("CONSULTA 1/5 - buscar_usuario(id)", "GET", "/usuarios/1", None),
    ("CONSULTA 2/5 - posts_do_usuario(usuario_id)", "GET", "/usuarios/2/posts", None),
    ("CONSULTA 3/5 - buscar_post(id)", "GET", "/posts/1", None),
    ("CONSULTA 4/5 - seguidores_de(id)", "GET", "/usuarios/1/seguidores", None),
    ("CONSULTA 4/5 (b) - seguindo_de(id)", "GET", "/usuarios/1/seguindo", None),
    ("CONSULTA 5/5 - feed_do_usuario(usuario_id)", "GET", "/usuarios/4/feed", None),
    ("EXTRA - erro: curtir duas vezes o mesmo post (409 Conflict)", "POST", "/posts/3/curtidas", "04-curtir.json"),
]


class Medidor:
    """Conta requisições HTTP e bytes de resposta de um cenário."""

    def __init__(self, nome: str) -> None:
        self.nome = nome
        self.requisicoes = 0
        self.bytes = 0

    def registrar(self, tamanho: int) -> None:
        self.requisicoes += 1
        self.bytes += tamanho

    def relatorio(self) -> str:
        return (
            f"{self.nome}: {self.requisicoes} requisição(ões) HTTP, "
            f"{self.bytes} bytes de resposta"
        )


def chamar(
    metodo: str,
    caminho: str,
    corpo: dict | None = None,
    medidor: Medidor | None = None,
) -> tuple[int, object]:
    """Faz a chamada HTTP e devolve (status, corpo já decodificado)."""
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    requisicao = urllib.request.Request(ENDERECO_BASE + caminho, data=dados, method=metodo)
    if dados is not None:
        requisicao.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(requisicao) as resposta:
            status, bruto = resposta.status, resposta.read()
    except urllib.error.HTTPError as erro:  # 4xx/5xx também viram resposta
        status, bruto = erro.code, erro.read()
    except urllib.error.URLError as erro:
        print(f"ERRO: não consegui falar com {ENDERECO_BASE} ({erro.reason}).")
        print("Suba o servidor com: uvicorn aplicacao:aplicacao --port 8000")
        raise SystemExit(1)

    if medidor is not None:
        medidor.registrar(len(bruto))
    return status, json.loads(bruto or b"null")


def ler_exemplo(arquivo: str) -> dict:
    return json.loads((PASTA_EXEMPLOS / arquivo).read_text(encoding="utf-8"))


def mostrar(
    titulo: str,
    metodo: str,
    caminho: str,
    arquivo: str | None,
    corpo: dict | None,
    status: int,
    resposta: object,
) -> None:
    print(f"\n{'=' * 72}\n{titulo}\n{'=' * 72}")
    print(f"  {metodo} {caminho}")
    if arquivo:
        print(f"  corpo: exemplos/{arquivo} -> {json.dumps(corpo, ensure_ascii=False)}")
    print(f"  -> {status}")
    print("  " + json.dumps(resposta, ensure_ascii=False, indent=2).replace("\n", "\n  "))


def principal() -> None:
    print(f"REST/JSON - {ENDERECO_BASE}")
    print("Estado inicial do servidor (seed): usuários 1=Ana, 2=Bruno, 3=Carla; posts 1..4.")

    for indice, (titulo, metodo, caminho, arquivo) in enumerate(OPERACOES):
        corpo = ler_exemplo(arquivo) if arquivo else None
        status, resposta = chamar(metodo, caminho, corpo)
        mostrar(titulo, metodo, caminho, arquivo, corpo, status, resposta)
        if indice == 0 and status != 201:
            print("\nAVISO: o usuário de exemplo não pôde ser criado (o servidor não está limpo).")
            print("Reinicie o servidor (Ctrl+C e suba o uvicorn de novo) e rode o demo outra vez.")
            raise SystemExit(1)

    # ------------------------------------------------------------- medições
    medidor_a = Medidor("Cenário A (feed detalhado, 4 posts)")
    _, feed = chamar("GET", "/usuarios/1/feed", medidor=medidor_a)
    ids = [post["id"] for post in feed["posts"]]  # type: ignore[index]
    for post_id in ids:
        chamar("GET", f"/posts/{post_id}", medidor=medidor_a)

    medidor_b = Medidor("Cenário B (só os textos do feed)")
    chamar("GET", "/usuarios/1/feed", medidor=medidor_b)

    print(f"\n{'=' * 72}\nRELATÓRIO DESTA EXECUÇÃO\n{'=' * 72}")
    print(f"  {medidor_a.relatorio()}")
    print(f"  {medidor_b.relatorio()}")
    print(f"  Cenário A: {1 + len(ids)} chamadas para montar o feed com comentários "
          f"(1 feed + 1 por post: é aqui que aparece o N+1 do REST)")
    print("  Cenário B: o feed devolve autor, e-mail e contadores que o cliente "
          "não pediu (over-fetching).")
    print("\n  Compare com o relatório do projeto graphql/.")


if __name__ == "__main__":
    principal()
