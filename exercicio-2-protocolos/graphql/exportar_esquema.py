"""Exporta o schema GraphQL (SDL) para o arquivo `esquema.graphql`.

O arquivo gerado é a "documentação" do protocolo: é ele que um cliente lê
(ou descobre sozinho, via introspecção) para saber o que pode pedir.

Uso: python exportar_esquema.py
"""

from __future__ import annotations

from pathlib import Path

from aplicacao import esquema

destino = Path(__file__).with_name("esquema.graphql")
destino.write_text(esquema.as_str() + "\n", encoding="utf-8")
print(f"esquema escrito em {destino}")
