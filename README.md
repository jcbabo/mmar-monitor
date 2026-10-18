# Monitor MMAR - Anatel

Projeto independente para acompanhar a inclusao de solicitacoes de licenciamento
de radioamador no MMAR.

## Estado atual

CLI com conexao a uma aba existente do Chrome autenticado. Por padrao, apenas
confere a conexao. Com `--monitorar`, repete a abertura de "Nova Solicitacao"
enquanto confirmar status HTTP 500 na navegacao principal. Nao decide pelo texto
da pagina, nao preenche nem envia formularios.

Fluxo informado pelo usuario:

- URL: https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir
- O erro ocorre ao clicar em "Nova Solicitacao", antes de preencher ou enviar.
- Firefox e Chrome exibem uma tela generica de erro 500.

Uma resposta HTTP final diferente de 500 interrompe o monitor e gera um
`window.alert()` com o status, inclusive 200, 403 ou 503. Um 200 pode ser login,
captcha ou formulario: isso indica mudanca, nao sucesso confirmado.
Erro 500 depois de um envio nao garante que a
solicitacao falhou; nunca use este ciclo para repetir envio de formularios.

## Instalacao

Requer Python 3.10+ e Chrome com depuracao remota habilitada.

```bash
cd ~/jbabo/projects/mmar-monitor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Abrir o Chrome com depuracao remota

Se o Chrome do monitor do SEC ja estiver com depuracao na porta 9222, use a mesma
janela e abra uma aba para o MMAR. Nao inicie outro Chrome na mesma porta.

Caso contrario, execute um dos comandos abaixo. O diretorio de perfil separado
e necessario nas versoes recentes do Chrome; nao use o perfil padrao do navegador.
Esse perfil preserva os logins entre execucoes, mas exige login proprio na primeira
vez. O Chrome habitual pode continuar aberto.

### Chrome no Windows

Execute no PowerShell do Windows, nao no terminal Bash do WSL:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:LOCALAPPDATA\Chrome-Monitor"
```

Se o executavel nao estiver nesse caminho, localize o `chrome.exe` nas propriedades
do atalho do Chrome e substitua somente o caminho do executavel no comando.

### Chrome no Linux

Execute no terminal da sessao grafica do Linux:

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="$HOME/.local/share/chrome-monitor"
```

### Conferir a depuracao e abrir o MMAR

Na janela iniciada, abra `http://localhost:9222/json/version`. Deve aparecer um
JSON com campos como `Browser` e `webSocketDebuggerUrl`. Se nao abrir, confira se
o perfil separado ja estava em uso por um Chrome sem depuracao; nesse caso,
feche apenas as janelas desse perfil e execute o comando novamente.

Depois, entre no portal da Anatel nessa mesma janela, faca login e resolva o
captcha manualmente. Clique em "Nova Solicitacao" e mantenha uma unica aba na URL:

```text
https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir
```

Deixe a aba na tela de erro 500, preservando a pagina anterior no historico.
O primeiro clique em "Nova Solicitacao" e sempre manual.

A porta de depuracao permite controlar o navegador autenticado. Mantenha-a local;
nao a publique na rede nem abra regras de firewall para acesso externo.

### Monitor no WSL e Chrome no Windows

O teste no navegador confirma a porta no Windows, mas nao garante acesso pelo
WSL. No terminal WSL, verifique:

```bash
curl --max-time 5 http://localhost:9222/json/version
```

Se retornar o JSON, use o monitor com o host padrao (`localhost`). Isso depende da
configuracao de rede do WSL, como o modo espelhado. Em modo NAT, o IP do Windows
pode nao funcionar, pois o Chrome normalmente escuta apenas no loopback.
Se o teste falhar, confirme a configuracao de rede antes de prosseguir; nao
exponha a porta na rede para contornar o problema.

## Uso inicial

Exibir as opcoes, sem conectar ao navegador:

```bash
python monitor.py --help
```

Conferir a conexao e selecionar uma unica aba existente, sem refresh ou envio:

```bash
python monitor.py
```

Por padrao, procura a URL de inclusao informada acima. Abra essa aba manualmente
no Chrome antes de executar. Para selecionar outra URL, use `--url 'FRAGMENTO'`.

Se houver outro host ja acessivel de forma segura, informe-o explicitamente:

```bash
python monitor.py --host IP_DO_WINDOWS --porta 9222
```

O script encerra apos a verificacao e mantem o navegador aberto. Se varias abas
corresponderem ao fragmento, recusa a selecao; refine a URL ou feche as duplicadas.

## Monitorar novas tentativas

Depois do primeiro clique manual e do erro 500, execute com o ambiente virtual
ativo:

```bash
python monitor.py --monitorar
```

1. Consulta o status HTTP da navegacao atual no registro do Chrome, quando disponivel.
  Se nao houver status valido, faz um GET de conferencia na mesma URL usando
  `window.location.replace`, preservando a pagina anterior no historico.
2. Aguarda 60 segundos, sem fazer requisicoes ao portal durante essa espera.
3. Volta uma pagina pelo historico e verifica o botao "Nova Solicitacao".
4. Atualiza essa pagina, localiza novamente o botao e clica uma vez.
5. Captura a resposta HTTP do GET do documento principal, ignorando APIs, imagens
  e iframes. Em redirecionamentos, considera a resposta final, nao o 302 intermediario.
6. Repete somente em HTTP 500 na URL esperada. Em outro status final, para e abre
  um `window.alert()` com o codigo para conferencia manual, inclusive na verificacao inicial.

O monitor habilita os eventos de rede do Chrome via CDP e os le pelos logs de
performance do ChromeDriver. Nao usa `requests`, nao copia cookies e nao faz
requisicoes separadas fora da sessao do navegador. O GET inicial de conferencia,
quando necessario, substitui a pagina atual e pode retornar uma tela diferente.

O botao deve ser unico, visivel e habilitado, com o texto "Nova Solicitacao"
(acentos e o sinal `+` sao aceitos). Historico inesperado, botao ausente ou
ambiguo e falhas de navegacao interrompem o ciclo com aviso, sem tentar outros
botoes. A pagina anterior precisa estar na mesma origem e na area de radioamador.
Uma resposta principal que nao seja GET interrompe o ciclo sem repetir a acao.
Falha de rede ou ausencia de status confirmado em 30 segundos interrompem o
monitor como situacao indeterminada, nunca como sucesso. Se o clique atingir o
timeout de navegacao, o monitor ainda consulta os eventos capturados por ate 30
segundos. O carregamento da listagem tambem tem limite de 30 segundos.

Para alterar o intervalo (minimo de 30 segundos):

```bash
python monitor.py --monitorar --intervalo 120
```

Use `Ctrl+C` no terminal para parar. O Chrome permanece aberto. Nao navegue
manualmente na aba enquanto o monitor estiver rodando; pare-o antes. Ao receber
um alerta, a automacao ja esta parando: fechar o alerta nao reinicia o ciclo.
O alerta nao garante foco da janela nem notificacao do sistema operacional.

O fluxo foi testado com navegador simulado; o seletor do botao e o historico
ainda precisam ser conferidos no portal real. Nao ha tentativas de login ou
resolucao automatica de captcha.

## Estrutura

```text
mmar-monitor/
  .gitignore
  README.md
  requirements.txt
  monitor.py
  mmar_monitor/
    __init__.py
    navegador.py
    monitoramento.py
  tests/
    test_monitoramento.py
```

Testes locais, sem acessar a Anatel:

```bash
python -m unittest discover -s tests -v
```

O projeto nao depende do monitor do SEC.