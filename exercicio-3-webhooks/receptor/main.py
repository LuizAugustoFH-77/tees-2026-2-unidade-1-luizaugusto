"""Serviço receptor de webhooks com verificação HMAC-SHA256 e idempotência."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RECEPTOR_HOST = os.environ.get("RECEPTOR_HOST", "127.0.0.1")
RECEPTOR_PORT = int(os.environ.get("RECEPTOR_PORT", "8001"))

lock = asyncio.Lock()
eventos_registrados: list[dict] = []
ids_processados: set[str] = set()


def log(mensagem: str) -> None:
    """Imprime mensagem de log com flush imediato."""
    print(mensagem, flush=True)


def obter_segredo() -> str:
    """Lê o segredo compartilhado da variável de ambiente WEBHOOK_SECRET."""
    segredo = os.environ.get("WEBHOOK_SECRET", "").strip()
    if not segredo:
        raise RuntimeError(
            "Variável de ambiente WEBHOOK_SECRET não definida. "
            "Defina WEBHOOK_SECRET antes de iniciar o receptor."
        )
    return segredo


def calcular_assinatura(body_bytes: bytes, segredo: str) -> str:
    """Calcula a assinatura HMAC-SHA256 no formato sha256=<64 hex>."""
    digest = hmac.new(segredo.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def validar_assinatura(raw_body: bytes, assinatura_recebida: str | None) -> tuple[bool, str | None]:
    """Valida a assinatura HMAC-SHA256 em tempo constante antes do parse JSON."""
    if not assinatura_recebida or not assinatura_recebida.strip():
        return False, "Cabeçalho X-Assinatura ausente."

    assinatura_esperada = calcular_assinatura(raw_body, obter_segredo())
    assinatura_valida = hmac.compare_digest(
        assinatura_recebida.strip().encode("utf-8"),
        assinatura_esperada.encode("utf-8"),
    )
    if not assinatura_valida:
        return False, "Assinatura HMAC inválida."
    return True, None


def extrair_dados_evento(raw_body: bytes) -> tuple[dict | None, str | None]:
    """Faz parse do JSON bruto e valida os campos obrigatórios do evento."""
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "Corpo da requisição não é um JSON UTF-8 válido."

    if not isinstance(payload, dict):
        return None, "Payload JSON deve ser um objeto."

    for campo in ("id", "pedido_id", "status"):
        valor = payload.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            return None, f"Campo obrigatório '{campo}' ausente ou inválido."

    return payload, None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Valida a configuração obrigatória na inicialização do receptor."""
    obter_segredo()
    log(f"[RECEPTOR] Iniciado em http://{RECEPTOR_HOST}:{RECEPTOR_PORT}")
    yield
    log("[RECEPTOR] Encerrado.")


app = FastAPI(
    title="Receptor de Webhooks",
    description="Recebe notificações de mudança de status com validação HMAC-SHA256 e idempotência.",
    lifespan=lifespan,
)


@app.post("/webhook")
async def receber_webhook(request: Request) -> JSONResponse:
    """Recebe, autentica via HMAC-SHA256 e registra eventos de webhook com idempotência."""
    raw_body = await request.body()
    assinatura_recebida = request.headers.get("X-Assinatura")

    valida, motivo_erro = validar_assinatura(raw_body, assinatura_recebida)
    if not valida:
        if motivo_erro == "Cabeçalho X-Assinatura ausente.":
            log("[RECEPTOR] Recusado (401): cabeçalho X-Assinatura ausente")
        else:
            log("[RECEPTOR] Recusado (401): assinatura HMAC-SHA256 inválida")
        return JSONResponse(status_code=401, content={"detail": motivo_erro})

    payload, erro_payload = extrair_dados_evento(raw_body)
    if erro_payload is not None or payload is None:
        log(f"[RECEPTOR] Recusado (400): {erro_payload}")
        return JSONResponse(status_code=400, content={"detail": erro_payload})

    evento_id = payload["id"].strip()
    pedido_id = payload["pedido_id"].strip()
    status = payload["status"].strip()

    async with lock:
        if evento_id in ids_processados:
            log(
                f"[RECEPTOR] Evento duplicado ignorado (200): "
                f"id={evento_id} pedido_id={pedido_id} status={status}"
            )
            return JSONResponse(
                status_code=200,
                content={
                    "mensagem": "Evento já processado anteriormente (idempotência).",
                    "id": evento_id,
                    "duplicado": True,
                },
            )

        ids_processados.add(evento_id)
        registro = {
            "id": evento_id,
            "pedido_id": pedido_id,
            "status": status,
            "ocorrido_em": payload.get("ocorrido_em"),
            "recebido_em": datetime.now(timezone.utc).isoformat(),
        }
        eventos_registrados.append(registro)

    log(
        f"[RECEPTOR] Evento registrado (201): "
        f"id={evento_id} pedido_id={pedido_id} status={status}"
    )
    return JSONResponse(
        status_code=201,
        content={
            "mensagem": "Evento recebido e registrado.",
            "evento": registro,
            "duplicado": False,
        },
    )


@app.get("/eventos")
async def listar_eventos(pedido_id: str | None = None) -> dict:
    """Lista os eventos registrados pelo receptor, opcionalmente filtrados por pedido_id."""
    async with lock:
        if pedido_id is not None:
            filtrados = [dict(ev) for ev in eventos_registrados if ev["pedido_id"] == pedido_id]
        else:
            filtrados = [dict(ev) for ev in eventos_registrados]

    return {
        "total": len(filtrados),
        "eventos": filtrados,
    }


@app.get("/health")
async def health() -> dict:
    """Verifica a saúde do serviço receptor."""
    return {"status": "ok", "servico": "receptor"}


if __name__ == "__main__":
    obter_segredo()
    uvicorn.run(app, host=RECEPTOR_HOST, port=RECEPTOR_PORT)
