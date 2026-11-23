"""Serviço emissor de pedidos com processamento em segundo plano e envio de webhooks."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import sys
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
import uvicorn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SEQUENCIA_STATUS = ("recebido", "aprovado", "enviado", "entregue")

EMISSOR_HOST = os.environ.get("EMISSOR_HOST", "127.0.0.1")
EMISSOR_PORT = int(os.environ.get("EMISSOR_PORT", "8000"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://127.0.0.1:8001/webhook")
INTERVALO_SEGUNDOS = float(os.environ.get("INTERVALO_SEGUNDOS", "3.0"))

lock = asyncio.Lock()
pedidos: dict[str, dict] = {}
eventos_enviados: dict[str, dict] = {}
http_client: httpx.AsyncClient | None = None


def log(mensagem: str) -> None:
    """Imprime mensagem de log com flush imediato."""
    print(mensagem, flush=True)


def obter_segredo() -> str:
    """Lê o segredo compartilhado da variável de ambiente WEBHOOK_SECRET."""
    segredo = os.environ.get("WEBHOOK_SECRET", "").strip()
    if not segredo:
        raise RuntimeError(
            "Variável de ambiente WEBHOOK_SECRET não definida. "
            "Defina WEBHOOK_SECRET antes de iniciar o emissor."
        )
    return segredo


def calcular_assinatura(body_bytes: bytes, segredo: str) -> str:
    """Calcula a assinatura HMAC-SHA256 no formato sha256=<64 hex>."""
    digest = hmac.new(segredo.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def serializar_evento(evento: dict) -> bytes:
    """Serializa o payload do evento em JSON UTF-8 compacto e determinístico."""
    return json.dumps(evento, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def formatar_pedido_publico(pedido: dict) -> dict:
    """Retorna os campos públicos de um pedido sem metadados internos de controle."""
    return {
        "pedido_id": pedido["pedido_id"],
        "status": pedido["status"],
        "criado_em": pedido["criado_em"],
        "atualizado_em": pedido["atualizado_em"],
        "eventos": list(pedido["eventos"]),
    }


def extrair_corpo_resposta(response: httpx.Response) -> dict:
    """Extrai o JSON da resposta HTTP ou encapsula o texto bruto."""
    try:
        conteudo = response.json()
        if isinstance(conteudo, dict):
            return conteudo
        return {"resposta": conteudo}
    except ValueError:
        return {"detail": response.text}


async def disparar_webhook(
    client: httpx.AsyncClient,
    evento: dict,
    body_bytes: bytes,
    tentativas: int = 3,
) -> dict:
    """Envia POST assinado para WEBHOOK_URL com retry para falhas de rede ou 5xx."""
    assinatura = calcular_assinatura(body_bytes, obter_segredo())
    headers = {
        "Content-Type": "application/json",
        "X-Assinatura": assinatura,
    }
    evento_id = evento["id"]
    pedido_id = evento["pedido_id"]
    status = evento["status"]

    for tentativa in range(1, tentativas + 1):
        try:
            response = await client.post(WEBHOOK_URL, content=body_bytes, headers=headers)
            corpo = extrair_corpo_resposta(response)

            if 200 <= response.status_code < 300:
                log(
                    f"[EMISSOR] Webhook entregue: id={evento_id} pedido_id={pedido_id} "
                    f"status={status} | HTTP {response.status_code}"
                )
                return {
                    "ok": True,
                    "status_code": response.status_code,
                    "resposta": corpo,
                }

            if 400 <= response.status_code < 500:
                log(
                    f"[EMISSOR] Webhook recusado pelo receptor: id={evento_id} "
                    f"pedido_id={pedido_id} status={status} | HTTP {response.status_code} | {corpo}"
                )
                return {
                    "ok": False,
                    "status_code": response.status_code,
                    "resposta": corpo,
                }

            log(
                f"[EMISSOR] Erro {response.status_code} do receptor (tentativa {tentativa}/{tentativas}): "
                f"id={evento_id}"
            )
        except httpx.HTTPError as exc:
            log(
                f"[EMISSOR] Falha de conexão ao enviar webhook (tentativa {tentativa}/{tentativas}): "
                f"id={evento_id} erro={exc}"
            )

        if tentativa < tentativas:
            await asyncio.sleep(1.0)

    return {
        "ok": False,
        "status_code": 502,
        "resposta": {"detail": f"Não foi possível entregar o evento {evento_id} ao receptor."},
    }


async def processador_pedidos(client: httpx.AsyncClient) -> None:
    """Avança periodicamente os pedidos em aberto e dispara um webhook a cada transição."""
    while True:
        await asyncio.sleep(0.5)
        agora_monotonic = time.monotonic()
        transicoes_pendentes: list[tuple[dict, bytes]] = []

        async with lock:
            for pedido in pedidos.values():
                indice_atual = pedido["indice_status"]
                if indice_atual >= len(SEQUENCIA_STATUS) - 1:
                    continue
                if agora_monotonic - pedido["ultimo_avanco_monotonic"] < INTERVALO_SEGUNDOS:
                    continue

                status_anterior = pedido["status"]
                novo_indice = indice_atual + 1
                novo_status = SEQUENCIA_STATUS[novo_indice]
                agora_iso = datetime.now(timezone.utc).isoformat()
                evento_id = f"evt_{uuid.uuid4().hex[:12]}"

                evento = {
                    "id": evento_id,
                    "pedido_id": pedido["pedido_id"],
                    "status": novo_status,
                    "ocorrido_em": agora_iso,
                }
                body_bytes = serializar_evento(evento)

                pedido["indice_status"] = novo_indice
                pedido["status"] = novo_status
                pedido["atualizado_em"] = agora_iso
                pedido["ultimo_avanco_monotonic"] = agora_monotonic
                pedido["eventos"].append(
                    {
                        "id": evento_id,
                        "status": novo_status,
                        "ocorrido_em": agora_iso,
                    }
                )

                eventos_enviados[evento_id] = {
                    "payload": evento,
                    "body_bytes": body_bytes,
                }
                transicoes_pendentes.append((evento, body_bytes))

                log(
                    f"[EMISSOR] Transição: pedido_id={pedido['pedido_id']} "
                    f"{status_anterior} -> {novo_status} | Evento id={evento_id}"
                )

        for evento, body_bytes in transicoes_pendentes:
            await disparar_webhook(client, evento, body_bytes)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Inicializa cliente HTTP e worker em segundo plano."""
    global http_client
    obter_segredo()
    http_client = httpx.AsyncClient(timeout=10.0)
    worker = asyncio.create_task(processador_pedidos(http_client))
    log(
        f"[EMISSOR] Iniciado em http://{EMISSOR_HOST}:{EMISSOR_PORT} | "
        f"Destino webhook: {WEBHOOK_URL} | Intervalo: {INTERVALO_SEGUNDOS}s"
    )
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        await http_client.aclose()
        http_client = None
        log("[EMISSOR] Encerrado.")


app = FastAPI(
    title="Emissor de Webhooks",
    description="Cadastra pedidos, evolui estados em segundo plano e notifica o receptor via webhook assinado.",
    lifespan=lifespan,
)


@app.post("/pedidos/{pedido_id}")
async def criar_pedido(pedido_id: str) -> JSONResponse:
    """Cadastra um novo pedido com status inicial 'recebido'."""
    pedido_id_limpo = pedido_id.strip()
    if not pedido_id_limpo:
        return JSONResponse(status_code=400, content={"detail": "pedido_id inválido."})

    agora_iso = datetime.now(timezone.utc).isoformat()
    agora_monotonic = time.monotonic()

    async with lock:
        if pedido_id_limpo in pedidos:
            return JSONResponse(
                status_code=409,
                content={"detail": f"Pedido '{pedido_id_limpo}' já cadastrado."},
            )

        novo_pedido = {
            "pedido_id": pedido_id_limpo,
            "status": SEQUENCIA_STATUS[0],
            "indice_status": 0,
            "criado_em": agora_iso,
            "atualizado_em": agora_iso,
            "ultimo_avanco_monotonic": agora_monotonic,
            "eventos": [],
        }
        pedidos[pedido_id_limpo] = novo_pedido
        resposta = formatar_pedido_publico(novo_pedido)

    log(f"[EMISSOR] Pedido cadastrado: pedido_id={pedido_id_limpo} status={SEQUENCIA_STATUS[0]}")
    return JSONResponse(status_code=201, content=resposta)


@app.get("/pedidos")
async def listar_pedidos() -> dict:
    """Lista todos os pedidos cadastrados e seu estado atual."""
    async with lock:
        lista = [formatar_pedido_publico(p) for p in pedidos.values()]
    return {"total": len(lista), "pedidos": lista}


@app.get("/pedidos/{pedido_id}")
async def obter_pedido(pedido_id: str) -> JSONResponse:
    """Consulta os detalhes e eventos disparados de um pedido específico."""
    async with lock:
        pedido = pedidos.get(pedido_id)
        if pedido is None:
            return JSONResponse(
                status_code=404,
                content={"detail": f"Pedido '{pedido_id}' não encontrado."},
            )
        resposta = formatar_pedido_publico(pedido)
    return JSONResponse(status_code=200, content=resposta)


@app.post("/eventos/{evento_id}/reenviar")
async def reenviar_evento(evento_id: str) -> JSONResponse:
    """Reenvia exatamente o mesmo evento (mesmo id e bytes) ao receptor para testar idempotência."""
    async with lock:
        registro_evento = eventos_enviados.get(evento_id)
        if registro_evento is None:
            return JSONResponse(
                status_code=404,
                content={"detail": f"Evento '{evento_id}' não encontrado."},
            )
        evento = dict(registro_evento["payload"])
        body_bytes = registro_evento["body_bytes"]

    if http_client is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "Cliente HTTP ainda não inicializado."},
        )

    log(
        f"[EMISSOR] Reenviando evento existente: id={evento['id']} "
        f"pedido_id={evento['pedido_id']} status={evento['status']}"
    )
    resultado = await disparar_webhook(http_client, evento, body_bytes, tentativas=1)
    return JSONResponse(status_code=resultado["status_code"], content=resultado["resposta"])


@app.get("/health")
async def health() -> dict:
    """Verifica a saúde do serviço emissor."""
    return {"status": "ok", "servico": "emissor"}


if __name__ == "__main__":
    obter_segredo()
    uvicorn.run(app, host=EMISSOR_HOST, port=EMISSOR_PORT)
