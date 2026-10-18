"""CLI inicial do monitor MMAR. Ainda nao atualiza nem monitora paginas."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Base do monitor Anatel/MMAR (sem refresh ou envio)."
    )
    parser.add_argument("--host", default="localhost",
                        help="host do Chrome com depuracao remota")
    parser.add_argument("--porta", type=int, default=9222,
                        help="porta de depuracao remota (padrao: 9222)")
    parser.add_argument(
        "--url",
        default="https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir",
        help="fragmento da URL de uma unica aba aberta do MMAR (padrao: %(default)s)",
    )
    args = parser.parse_args()

    if not 1 <= args.porta <= 65535:
        parser.error("--porta deve estar entre 1 e 65535")
    if not args.url.strip():
        parser.error("--url nao pode estar vazia")

    try:
        from selenium.common.exceptions import WebDriverException
        from mmar_monitor.navegador import conectar, selecionar_aba
    except ModuleNotFoundError as exc:
        if exc.name != "selenium":
            raise
        print("Instale as dependencias: python -m pip install -r requirements.txt",
              file=sys.stderr)
        return 1

    try:
        driver = conectar(args.host, args.porta)
    except WebDriverException as exc:
        print(f"Nao consegui conectar em {args.host}:{args.porta}: {exc.msg}",
              file=sys.stderr)
        return 1

    try:
        selecionar_aba(driver, args.url.strip())
        print(f"Aba selecionada: {driver.current_url}")
        print("Conexao conferida. Nenhum refresh ou envio foi realizado.")
        print("A deteccao de mudancas ainda sera implementada.")
        return 0
    except (RuntimeError, WebDriverException) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        driver.service.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Encerrado pelo usuario.")
        sys.exit(130)
