"""CLI do monitor MMAR com novas tentativas opcionais de abertura."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor Anatel/MMAR (sem preenchimento ou envio de formularios)."
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
    parser.add_argument("--monitorar", action="store_true",
                        help="repetir a abertura de Nova Solicitacao somente apos HTTP ERROR 500")
    parser.add_argument("--intervalo", type=int, default=60,
                        help="segundos entre tentativas (padrao: %(default)s; minimo: 30)")
    args = parser.parse_args()

    if not 1 <= args.porta <= 65535:
        parser.error("--porta deve estar entre 1 e 65535")
    if not args.url.strip():
        parser.error("--url nao pode estar vazia")
    if args.intervalo < 30:
        parser.error("--intervalo deve ser de pelo menos 30 segundos")

    try:
        from selenium.common.exceptions import WebDriverException
        from mmar_monitor.navegador import conectar, selecionar_aba
        from mmar_monitor.monitoramento import executar_monitoramento
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
        if args.monitorar:
            executar_monitoramento(driver, args.intervalo)
        else:
            print("Conexao conferida. Nenhum refresh ou envio foi realizado.")
            print("Use --monitorar para iniciar as novas tentativas de abertura.")
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
