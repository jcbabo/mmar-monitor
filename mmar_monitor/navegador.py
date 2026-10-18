"""Conexao ao Chrome remoto e selecao da aba existente."""

from __future__ import annotations

import json
import re
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def detectar_versao(host: str, porta: int) -> str | None:
    """Consulta a versao do navegador para selecionar o ChromeDriver."""
    try:
        with urllib.request.urlopen(
            f"http://{host}:{porta}/json/version", timeout=5
        ) as resposta:
            dados = json.load(resposta)
    except (OSError, ValueError):
        return None
    match = re.search(r"Chrome/(\d+)", dados.get("Browser", ""))
    return match.group(1) if match else None


def conectar(host: str, porta: int) -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("debuggerAddress", f"{host}:{porta}")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    versao = detectar_versao(host, porta)
    if versao:
        options.browser_version = versao
    return webdriver.Chrome(options=options)


def selecionar_aba(driver: webdriver.Chrome, fragmento_url: str) -> str:
    """Seleciona uma unica aba correspondente, sem carregar outra pagina."""
    handle_original = driver.current_window_handle
    candidatos = []
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if fragmento_url.lower() in driver.current_url.lower():
            candidatos.append(handle)
    if len(candidatos) != 1:
        driver.switch_to.window(handle_original)
        raise RuntimeError(
            f"Encontradas {len(candidatos)} abas contendo '{fragmento_url}'. "
            "Deixe uma unica aba correspondente aberta ou refine --url."
        )
    driver.switch_to.window(candidatos[0])
    return candidatos[0]
