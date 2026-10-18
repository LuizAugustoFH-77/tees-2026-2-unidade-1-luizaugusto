"""Demonstração automatizada da API GraphQL.

Roda as 10 operações obrigatórias lendo os corpos JSON de `exemplos/` (os
mesmos arquivos usados nos comandos `curl` do README) e, no fim, mede os dois
cenários que aparecem na comparação final:

  Cenário A -- "feed detalhado": feed do usuário + autor + contadores +
               comentários de cada post.
  Cenário B -- "só os textos do feed".

Uso:
    python demonstracao.py                        # usa http://localhost:8001
    python demonstracao.py http://localhost:8001

Requisito: servidor recém-iniciado (o demo cria um usuário novo; se já existir,
ele avisa e pede para reiniciar o servidor). Depende só da biblioteca padrão.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

PASTA_EXEMPLOS = Path(__file__).with_name("exemplos")
ENDERECO_BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8001"

# (título, arquivo em exemplos/)
OPERACOES = [
    ("COMANDO 1/5 - criar_usuario(nome, email) -> mutation criarUsuario", "01-criar-usuario.json"),
    ("COMANDO 2/5 - criar_post(usuario_id, texto) -> mutation criarPost", "02-criar-post.json"),
    ("COMANDO 3/5 - comentar(usuario_id, post_id, texto) -> mutation comentar", "03-comentar.json"),
    ("COMANDO 4/5 - curtir(usuario_id, post_id) -> mutation curtir", "04-curtir.json"),
    ("COMANDO 5/5 - seguir(usuario_id, alvo_id) -> mutation seguir", "05-seguir.json"),
    ("CONSULTA 1/5 - buscar_usuario(id) -> query usuario(id)", "06-buscar-usuario.json"),
    ("CONSULTA 2/5 - posts_do_usuario(usuario_id) -> query postsDoUsuario", "07-posts-do-usuario.json"),
    ("CONSULTA 3/5 - buscar_post(id) -> query post(id)", "08-buscar-post.json"),
    ("CONSULTA 4/5 - seguidores_de(id) -> query seguidoresDe(id)", "09-seguidores-de.json"),
    ("CONSULTA 4/5 (b) - seguindo_de(id) -> query seguindoDe(id)", "10-seguindo-de.json"),
    ("CONSULTA 5/5 - feed_do_usuario(usuario_id) -> query feedDoUsuario", "11-feed-do-usuario.json"),
    ("EXTRA - erro: curtir duas vezes o mesmo post (HTTP segue 200)", "12-extra-erro-curtir-duas-vezes.json"),
    ("EXTRA - buscar um usuário que não existe (null em vez de 404)", "13-extra-usuario-nao-encontrado.json"),
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


def chamar(corpo: dict, medidor: Medidor | None = None) -> tuple[int, object]:
    """Envia a operação GraphQL e devolve (status, corpo decodificado)."""
    dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
    requisicao = urllib.request.Request(
        ENDERECO_BASE + "/graphql", data=dados, method="POST"
    )
    requisicao.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(requisicao) as resposta:
            status, bruto = resposta.status, resposta.read()
    except urllib.error.HTTPError as erro:
        status, bruto = erro.code, erro.read()
    except urllib.error.URLError as erro:
        print(f"ERRO: não consegui falar com {ENDERECO_BASE} ({erro.reason}).")
        print("Suba o servidor com: uvicorn aplicacao:aplicacao --port 8001")
        raise SystemExit(1)

    if medidor is not None:
        medidor.registrar(len(bruto))
    return status, json.loads(bruto or b"null")


def ler_exemplo(arquivo: str) -> dict:
    return json.loads((PASTA_EXEMPLOS / arquivo).read_text(encoding="utf-8"))


def mostrar(titulo: str, arquivo: str, corpo: dict, status: int, resposta: object) -> None:
    print(f"\n{'=' * 72}\n{titulo}\n{'=' * 72}")
    print(f"  arquivo: exemplos/{arquivo}")
    print(f"  query: {corpo['query']}")
    if corpo.get("variables"):
        print(f"  variables: {json.dumps(corpo['variables'], ensure_ascii=False)}")
    print(f"  -> HTTP {status}")
    print("  " + json.dumps(resposta, ensure_ascii=False, indent=2).replace("\n", "\n  "))


def principal() -> None:
    print(f"GraphQL - {ENDERECO_BASE}/graphql")
    print("Estado inicial do servidor (seed): usuários 1=Ana, 2=Bruno, 3=Carla; posts 1..4.")

    for titulo, arquivo in OPERACOES:
        corpo = ler_exemplo(arquivo)
        status, resposta = chamar(corpo)
        mostrar(titulo, arquivo, corpo, status, resposta)
        if arquivo == "01-criar-usuario.json" and isinstance(resposta, dict) and resposta.get("errors"):
            print("\nAVISO: o usuário de exemplo não pôde ser criado (o servidor não está limpo).")
            print("Reinicie o servidor (Ctrl+C e suba o uvicorn de novo) e rode o demo outra vez.")
            raise SystemExit(1)

    # ------------------------------------------------------------- medições
    medidor_a = Medidor("Cenário A (feed detalhado, 4 posts)")
    _, resposta_a = chamar(ler_exemplo("14-cenario-a-feed-detalhado.json"), medidor=medidor_a)
    posts = resposta_a.get("data", {}).get("feedDoUsuario") or []

    medidor_b = Medidor("Cenário B (só os textos do feed)")
    chamar(ler_exemplo("15-cenario-b-so-textos.json"), medidor=medidor_b)

    print(f"\n{'=' * 72}\nRELATÓRIO DESTA EXECUÇÃO\n{'=' * 72}")
    print(f"  {medidor_a.relatorio()}")
    print(f"  {medidor_b.relatorio()}")
    print(f"  Cenário A: 1 requisição para {len(posts)} posts com autor, contadores e "
          f"comentários (sem N+1 de round-trips)")
    print("  Cenário B: o cliente pediu só `texto` e só `texto` voltou (sem over-fetching).")
    print("\n  Compare com o relatório do projeto rest-json/.")


if __name__ == "__main__":
    principal()
