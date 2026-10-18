"""Novas tentativas de abertura, sem preenchimento ou envio de solicitacoes."""

from __future__ import annotations

import json
import time
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


@dataclass(frozen=True)
class RespostaHTTP:
    status: int
    url: str
    metodo: str | None


def aguardar_resposta_http(driver, acao) -> RespostaHTTP:
    frame = driver.execute_cdp_cmd("Page.getFrameTree", {})["frameTree"]["frame"]["id"]
    driver.get_log("performance")
    requisicoes = {}
    respostas = {}
    extras = {}
    falhas = {}
    atual = None

    def verificar(navegador):
        nonlocal atual
        for registro in navegador.get_log("performance"):
            evento = json.loads(registro["message"])["message"]
            nome = evento["method"]
            dados = evento.get("params", {})
            identificador = dados.get("requestId")
            if (
                nome == "Network.requestWillBeSent"
                and dados.get("type") == "Document"
                and dados.get("frameId") == frame
            ):
                atual = identificador
                requisicoes[atual] = dados["request"]
                respostas.pop(atual, None)
                falhas.pop(atual, None)
            elif (
                nome == "Network.responseReceived"
                and dados.get("type") == "Document"
                and dados.get("frameId") == frame
            ):
                respostas[identificador] = dados["response"]
            elif nome == "Network.responseReceivedExtraInfo":
                extras.setdefault(identificador, []).append(dados["statusCode"])
            elif nome == "Network.loadingFailed":
                falhas[identificador] = dados.get("errorText", "Falha de rede sem detalhe")

        if atual is None:
            return False
        requisicao = requisicoes[atual]
        if requisicao["method"] != "GET":
            raise RuntimeError("A navegacao principal nao foi GET. Nenhuma repeticao sera feita.")
        resposta = respostas.get(atual)
        status = resposta["status"] if resposta else None
        if status is None and atual in falhas:
            status = next(
                (codigo for codigo in reversed(extras.get(atual, [])) if not 300 <= codigo <= 399),
                None,
            )
        if status is not None and 200 <= status <= 599 and not 300 <= status <= 399:
            return RespostaHTTP(int(status), resposta["url"] if resposta else requisicao["url"], "GET")
        if atual in falhas:
            if falhas[atual] == "net::ERR_HTTP_RESPONSE_CODE_FAILURE":
                return False
            raise RuntimeError(f"Navegacao sem status HTTP final confirmado: {falhas[atual]}")
        return False

    try:
        acao()
    except TimeoutException:
        print("Tempo de navegacao excedido; conferindo a resposta HTTP capturada.", flush=True)
    return WebDriverWait(driver, 30).until(
        verificar,
        message="Sem resposta HTTP final do GET do documento principal em 30 segundos. "
        "O clique pode nao ter navegado ou a rede pode estar indisponivel.",
    )


def resposta_inicial(driver) -> RespostaHTTP:
    url = driver.current_url
    navegacao = driver.execute_script(
        "const entrada = performance.getEntriesByType('navigation')[0];"
        "return entrada ? {status: entrada.responseStatus, url: entrada.name} : null;"
    )
    if (
        navegacao
        and navegacao.get("url") == url
        and isinstance(navegacao.get("status"), (int, float))
        and 200 <= navegacao["status"] <= 599
        and not 300 <= navegacao["status"] <= 399
    ):
        return RespostaHTTP(int(navegacao["status"]), url, None)
    print(
        "Status da navegacao anterior indisponivel. Fazendo um GET de conferencia "
        "na mesma URL, sem adicionar uma entrada ao historico.",
        flush=True,
    )
    return aguardar_resposta_http(
        driver,
        lambda: driver.execute_script("window.location.replace(arguments[0]);", url),
    )


def normalizar_rotulo(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return " ".join(texto.casefold().replace("+", " ").split())


def aguardar_pagina(driver) -> None:
    espera = WebDriverWait(driver, 30)
    espera.until(
        lambda navegador: navegador.execute_script("return document.readyState") == "complete",
        message="A pagina nao concluiu o carregamento (document.readyState) em 30 segundos.",
    )


def localizar_botao(driver):
    candidatos = [
        elemento
        for elemento in driver.find_elements(
            By.CSS_SELECTOR, "a, button, input[type='button'], input[type='submit']"
        )
        if elemento.is_displayed()
        and elemento.is_enabled()
        and normalizar_rotulo(elemento.text or elemento.get_attribute("value") or "")
        == "nova solicitacao"
    ]
    if len(candidatos) != 1:
        raise RuntimeError(
            f"Encontrados {len(candidatos)} botoes 'Nova Solicitacao'. "
            "Monitor interrompido sem clicar."
        )
    return candidatos[0]


def avisar(driver, mensagem: str) -> None:
    print(mensagem, flush=True)
    driver.execute_script("window.alert(arguments[0]);", mensagem)


def monitorar(driver, intervalo: float) -> None:
    destino = urlsplit(driver.current_url)
    driver.set_page_load_timeout(30)
    driver.execute_cdp_cmd("Network.enable", {})
    resposta = resposta_inicial(driver)
    tentativa = 0
    while True:
        print(f"Status HTTP confirmado: {resposta.status}.", flush=True)
        if resposta.status != 500:
            avisar(
                driver,
                f"MMAR: resposta HTTP {resposta.status}, diferente de 500. "
                "Monitor parado; confira o navegador. Nenhum formulario foi enviado.",
            )
            return
        if urlsplit(resposta.url) != destino:
            avisar(driver, "MMAR: a resposta 500 veio de outra URL. Monitor parado; confira a aba.")
            return

        historico = driver.execute_cdp_cmd("Page.getNavigationHistory", {})
        indice = historico["currentIndex"]
        if indice < 1:
            raise RuntimeError("Sem pagina anterior no historico. Volte manualmente a listagem.")
        anterior = urlsplit(historico["entries"][indice - 1]["url"])
        if (
            (anterior.scheme, anterior.netloc) != (destino.scheme, destino.netloc)
            or not anterior.path.startswith("/se/modulos/radioamador/")
            or anterior.path == destino.path
        ):
            raise RuntimeError("Pagina anterior inesperada. Monitor interrompido sem voltar.")

        print(f"Erro 500 confirmado. Nova tentativa em {intervalo:g}s. Ctrl+C para parar.", flush=True)
        documento = driver.execute_cdp_cmd("Page.getFrameTree", {})["frameTree"]["frame"]["loaderId"]
        time.sleep(intervalo)
        documento_atual = driver.execute_cdp_cmd("Page.getFrameTree", {})["frameTree"]["frame"]["loaderId"]
        if driver.current_url != destino.geturl() or documento_atual != documento:
            avisar(driver, "MMAR: a tela mudou durante a espera. Monitor parado; confira a aba.")
            return
        driver.back()
        aguardar_pagina(driver)
        localizar_botao(driver)
        driver.refresh()
        aguardar_pagina(driver)
        botao = localizar_botao(driver)
        tentativa += 1
        print(f"Tentativa {tentativa}: clicando em Nova Solicitacao.", flush=True)
        resposta = aguardar_resposta_http(driver, botao.click)


def executar_monitoramento(driver, intervalo: float) -> None:
    try:
        monitorar(driver, intervalo)
    except (RuntimeError, WebDriverException) as exc:
        detalhe = f"{type(exc).__name__}: {str(exc).strip() or 'Sem mensagem adicional.'}"
        print(f"Diagnostico da interrupcao: {detalhe}", flush=True)
        try:
            avisar(
                driver,
                f"MMAR: monitor interrompido por seguranca.\n{detalhe}\nConfira a aba.",
            )
        except WebDriverException:
            pass
        raise RuntimeError(f"Monitor interrompido: {detalhe}") from exc