import json
import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from mmar_monitor.monitoramento import (
    aguardar_pagina,
    aguardar_resposta_http,
    RespostaHTTP,
    executar_monitoramento,
    localizar_botao,
    monitorar,
    normalizar_rotulo,
    resposta_inicial,
)


class MonitoramentoTests(unittest.TestCase):
    def capturar(self, eventos, acao=None, posteriores=()):
        driver = Mock()
        driver.execute_cdp_cmd.return_value = {"frameTree": {"frame": {"id": "principal"}}}
        driver.get_log.side_effect = [[], *[
            [{"message": json.dumps({"message": evento})} for evento in lote]
            for lote in [eventos, *posteriores]
        ]]
        return aguardar_resposta_http(driver, acao or Mock())

    def requisicao(self, identificador="documento", frame="principal", metodo="GET"):
        return {"method": "Network.requestWillBeSent", "params": {
            "requestId": identificador, "frameId": frame, "type": "Document",
            "request": {"method": metodo, "url": "https://sistemas.anatel.gov.br/incluir"},
        }}

    def resposta(self, status, identificador="documento", frame="principal", tipo="Document"):
        return {"method": "Network.responseReceived", "params": {
            "requestId": identificador, "frameId": frame, "type": tipo,
            "response": {"status": status, "url": "https://sistemas.anatel.gov.br/incluir"},
        }}

    def test_captura_status_do_documento_ignora_api_e_iframe(self):
        resultado = self.capturar([
            self.requisicao(), self.resposta(500),
            self.resposta(200, "api", tipo="Fetch"),
            self.requisicao("iframe", "secundario"),
            self.resposta(200, "iframe", "secundario"),
        ])
        self.assertEqual(resultado.status, 500)

    def test_redirect_considera_apenas_resposta_final(self):
        resultado = self.capturar([
            self.requisicao(), self.resposta(302), self.requisicao(), self.resposta(200),
        ])
        self.assertEqual(resultado.status, 200)

    def test_erro_nativo_do_chrome_preserva_status_dos_cabecalhos(self):
        resultado = self.capturar([
            self.requisicao(),
            {"method": "Network.responseReceivedExtraInfo", "params": {
                "requestId": "documento", "statusCode": 500,
            }},
            {"method": "Network.loadingFailed", "params": {
                "requestId": "documento", "errorText": "net::ERR_HTTP_RESPONSE_CODE_FAILURE",
            }},
        ])
        self.assertEqual(resultado.status, 500)

    def test_cabecalhos_podem_chegar_antes_da_requisicao(self):
        resultado = self.capturar([
            {"method": "Network.responseReceivedExtraInfo", "params": {
                "requestId": "documento", "statusCode": 500,
            }},
            self.requisicao(),
            {"method": "Network.loadingFailed", "params": {
                "requestId": "documento", "errorText": "net::ERR_HTTP_RESPONSE_CODE_FAILURE",
            }},
        ])
        self.assertEqual(resultado.status, 500)

    def test_cabecalhos_podem_chegar_depois_da_falha_do_chrome(self):
        resultado = self.capturar([
            self.requisicao(),
            {"method": "Network.loadingFailed", "params": {
                "requestId": "documento", "errorText": "net::ERR_HTTP_RESPONSE_CODE_FAILURE",
            }},
        ], posteriores=[[
            {"method": "Network.responseReceivedExtraInfo", "params": {
                "requestId": "documento", "statusCode": 500,
            }},
        ]])
        self.assertEqual(resultado.status, 500)

    def test_cache_304_usa_status_final_do_documento(self):
        resultado = self.capturar([
            self.requisicao(), self.resposta(200),
            {"method": "Network.responseReceivedExtraInfo", "params": {
                "requestId": "documento", "statusCode": 304,
            }},
        ])
        self.assertEqual(resultado.status, 200)

    @patch("mmar_monitor.monitoramento.WebDriverWait", side_effect=lambda driver, tempo: WebDriverWait(driver, 0))
    def test_apenas_resposta_de_api_nao_confirma_navegacao(self, espera):
        with self.assertRaisesRegex(TimeoutException, "Sem resposta HTTP final"):
            self.capturar([self.resposta(200, "api", tipo="Fetch")])

    def test_falha_de_rede_nao_e_sucesso(self):
        with self.assertRaisesRegex(RuntimeError, "ERR_CONNECTION_RESET"):
            self.capturar([
                self.requisicao(),
                {"method": "Network.loadingFailed", "params": {
                    "requestId": "documento", "errorText": "net::ERR_CONNECTION_RESET",
                }},
            ])

    def test_post_nao_pode_ser_repetido(self):
        with self.assertRaisesRegex(RuntimeError, "nao foi GET"):
            self.capturar([self.requisicao(metodo="POST"), self.resposta(500)])

    def test_timeout_da_acao_ainda_consulta_status_capturado(self):
        resultado = self.capturar([
            self.requisicao(), self.resposta(200),
        ], acao=Mock(side_effect=TimeoutException()))
        self.assertEqual(resultado.status, 200)

    @patch("mmar_monitor.monitoramento.WebDriverWait")
    def test_timeout_identifica_espera_por_carregamento(self, espera):
        espera.return_value.until.side_effect = TimeoutException()
        with self.assertRaises(TimeoutException):
            aguardar_pagina(Mock())
        mensagem = espera.return_value.until.call_args.kwargs["message"]
        self.assertIn("document.readyState", mensagem)

    @patch("mmar_monitor.monitoramento.avisar")
    @patch("mmar_monitor.monitoramento.monitorar", side_effect=TimeoutException())
    def test_excecao_sem_mensagem_preserva_tipo_no_alerta_e_no_terminal(self, executar, avisar):
        with patch("builtins.print") as imprimir:
            with self.assertRaisesRegex(RuntimeError, "TimeoutException"):
                executar_monitoramento(Mock(), 60)
        self.assertIn("TimeoutException", avisar.call_args.args[1])
        self.assertIn("TimeoutException", imprimir.call_args.args[0])

    @patch("mmar_monitor.monitoramento.aguardar_resposta_http")
    def test_status_inicial_vem_do_registro_de_navegacao(self, capturar):
        driver = Mock(current_url="https://sistemas.anatel.gov.br/incluir")
        driver.execute_script.return_value = {"status": 500, "url": driver.current_url}
        self.assertEqual(resposta_inicial(driver).status, 500)
        capturar.assert_not_called()

    @patch("mmar_monitor.monitoramento.aguardar_resposta_http")
    def test_status_inicial_desconhecido_faz_get_sem_adicionar_historico(self, capturar):
        driver = Mock(current_url="https://sistemas.anatel.gov.br/incluir")
        for entrada in (None, {"status": 0, "url": driver.current_url},
                        {"status": 200, "url": "chrome-error://chromewebdata/"}):
            with self.subTest(entrada=entrada):
                driver.execute_script.return_value = entrada
                resposta_inicial(driver)
                capturar.call_args.args[1]()
                driver.execute_script.assert_called_with(
                    "window.location.replace(arguments[0]);", driver.current_url,
                )

    def test_normaliza_rotulo_com_acentos(self):
        self.assertEqual(normalizar_rotulo("+ Nova Solicita\u00e7\u00e3o"), "nova solicitacao")
        self.assertNotEqual(normalizar_rotulo("Enviar solicitacao"), "nova solicitacao")

    @patch("mmar_monitor.monitoramento.aguardar_pagina")
    @patch("mmar_monitor.monitoramento.avisar")
    @patch("mmar_monitor.monitoramento.resposta_inicial")
    def test_tela_diferente_apenas_alerta(self, ler, avisar, aguardar):
        driver = Mock(current_url="https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir")
        ler.return_value = RespostaHTTP(200, driver.current_url, "GET")
        monitorar(driver, 60)
        avisar.assert_called_once()
        driver.back.assert_not_called()
        driver.refresh.assert_not_called()

    @patch("mmar_monitor.monitoramento.aguardar_pagina")
    @patch("mmar_monitor.monitoramento.resposta_inicial")
    def test_sem_historico_nao_navega(self, ler, aguardar):
        driver = Mock(current_url="https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir")
        ler.return_value = RespostaHTTP(500, driver.current_url, "GET")
        driver.execute_cdp_cmd.side_effect = lambda comando, parametros: {"currentIndex": 0, "entries": []}
        with self.assertRaisesRegex(RuntimeError, "Sem pagina anterior"):
            monitorar(driver, 60)
        driver.back.assert_not_called()

    @patch("mmar_monitor.monitoramento.aguardar_pagina")
    @patch("mmar_monitor.monitoramento.resposta_inicial")
    def test_historico_fora_do_mmar_nao_navega(self, ler, aguardar):
        driver = Mock(current_url="https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir")
        ler.return_value = RespostaHTTP(500, driver.current_url, "GET")
        for url in (
            "https://outro.example/se/modulos/radioamador/solicitacoes",
            "https://sistemas.anatel.gov.br/login",
            driver.current_url,
        ):
            with self.subTest(url=url):
                driver.execute_cdp_cmd.return_value = {
                    "currentIndex": 1, "entries": [{"url": url}],
                }
                with self.assertRaisesRegex(RuntimeError, "Pagina anterior inesperada"):
                    monitorar(driver, 60)
                driver.back.assert_not_called()

    def test_botao_ausente_ou_ambiguo_nao_clica(self):
        driver = Mock()
        botao = Mock(text="+ Nova Solicita\u00e7\u00e3o")
        for elementos in ([], [botao, botao]):
            with self.subTest(quantidade=len(elementos)):
                driver.find_elements.return_value = elementos
                with self.assertRaisesRegex(RuntimeError, "sem clicar"):
                    localizar_botao(driver)
                botao.click.assert_not_called()

    @patch("mmar_monitor.monitoramento.time.sleep")
    @patch("mmar_monitor.monitoramento.aguardar_pagina")
    @patch("mmar_monitor.monitoramento.avisar")
    @patch("mmar_monitor.monitoramento.resposta_inicial")
    def test_mudanca_durante_espera_interrompe(self, ler, avisar, aguardar, dormir):
        driver = Mock(current_url="https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir")
        historico = {
            "currentIndex": 1,
            "entries": [{"url": "https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes"}],
        }
        driver.execute_cdp_cmd.side_effect = [None, historico,
            {"frameTree": {"frame": {"loaderId": "antes"}}},
            {"frameTree": {"frame": {"loaderId": "depois"}}}]
        ler.return_value = RespostaHTTP(500, driver.current_url, "GET")
        monitorar(driver, 60)
        avisar.assert_called_once()
        driver.back.assert_not_called()

    @patch("mmar_monitor.monitoramento.time.sleep")
    @patch("mmar_monitor.monitoramento.aguardar_pagina")
    @patch("mmar_monitor.monitoramento.localizar_botao")
    @patch("mmar_monitor.monitoramento.avisar")
    @patch("mmar_monitor.monitoramento.resposta_inicial")
    @patch("mmar_monitor.monitoramento.aguardar_resposta_http")
    def test_ciclo_volta_atualiza_clica_e_para(self, capturar, ler, avisar, localizar, aguardar, dormir):
        driver = Mock(current_url="https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir")
        historico = {
            "currentIndex": 1,
            "entries": [{"url": "https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes"}],
        }
        driver.execute_cdp_cmd.side_effect = lambda comando, parametros: (
            historico if comando == "Page.getNavigationHistory"
            else {"frameTree": {"frame": {"loaderId": "documento"}}}
        )
        ler.return_value = RespostaHTTP(500, driver.current_url, "GET")
        capturar.side_effect = lambda navegador, acao: (acao(), RespostaHTTP(200, driver.current_url, "GET"))[1]
        monitorar(driver, 60)
        dormir.assert_called_once_with(60)
        driver.back.assert_called_once()
        driver.refresh.assert_called_once()
        localizar.return_value.click.assert_called_once()
        avisar.assert_called_once()
        self.assertIn("HTTP 200", avisar.call_args.args[1])
        self.assertLess(driver.mock_calls.index(unittest.mock.call.back()), driver.mock_calls.index(unittest.mock.call.refresh()))

    @patch("mmar_monitor.monitoramento.time.sleep")
    @patch("mmar_monitor.monitoramento.aguardar_pagina")
    @patch("mmar_monitor.monitoramento.localizar_botao")
    @patch("mmar_monitor.monitoramento.avisar")
    @patch("mmar_monitor.monitoramento.resposta_inicial")
    @patch("mmar_monitor.monitoramento.aguardar_resposta_http")
    def test_repete_enquanto_500_e_para_em_outro_erro(self, capturar, ler, avisar, localizar, aguardar, dormir):
        driver = Mock(current_url="https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir")
        historico = {
            "currentIndex": 1,
            "entries": [{"url": "https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes"}],
        }
        driver.execute_cdp_cmd.side_effect = lambda comando, parametros: (
            historico if comando == "Page.getNavigationHistory"
            else {"frameTree": {"frame": {"loaderId": "documento"}}}
        )
        ler.return_value = RespostaHTTP(500, driver.current_url, "GET")
        respostas = iter([RespostaHTTP(500, driver.current_url, "GET"), RespostaHTTP(503, driver.current_url, "GET")])
        capturar.side_effect = lambda navegador, acao: (acao(), next(respostas))[1]
        monitorar(driver, 60)
        self.assertEqual(driver.back.call_count, 2)
        self.assertEqual(driver.refresh.call_count, 2)
        self.assertEqual(localizar.return_value.click.call_count, 2)
        avisar.assert_called_once()
        self.assertIn("HTTP 503", avisar.call_args.args[1])


if __name__ == "__main__":
    unittest.main()