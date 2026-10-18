# Monitor MMAR - Anatel

Projeto independente para acompanhar a inclusao de solicitacoes de licenciamento
de radioamador no MMAR.

## Estado atual

Estrutura inicial, com CLI e conexao a uma aba existente do Chrome autenticado.
Ainda nao detecta mudancas, nao atualiza paginas, nao clica em botoes e nao envia
formularios.

Fluxo informado pelo usuario:

- URL: https://sistemas.anatel.gov.br/se/modulos/radioamador/solicitacoes/incluir
- O erro ocorre ao clicar em "Nova Solicitacao", antes de preencher ou enviar.
- Firefox e Chrome exibem uma tela generica de erro 500.

A tela esperada quando o acesso funcionar ainda precisa ser confirmada para
definir a deteccao de sucesso. O erro relatado nao ocorre no envio; ainda assim,
o monitor nao deve enviar formularios automaticamente. Erro 500 depois de um
envio nao garante que a solicitacao falhou; repetir o envio pode gerar duplicatas.

## Instalacao

Requer Python 3.10+ e Chrome com depuracao remota habilitada.

```bash
cd ~/jbabo/projects/mmar-monitor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Use o Chrome ja preparado para o monitor do SEC, com porta 9222. Login e captcha
continuam sendo feitos manualmente no navegador. Nao exponha a porta de
depuracao a redes nao confiaveis.

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

Se precisar acessar o Chrome do Windows a partir do WSL, informe o host:

```bash
python monitor.py --host IP_DO_WINDOWS --porta 9222
```

O script encerra apos a verificacao e mantem o navegador aberto. Se varias abas
corresponderem ao fragmento, recusa a selecao; refine a URL ou feche as duplicadas.

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
```

Deteccao, alertas e politica de novas tentativas serao adicionados depois de
confirmarmos a tela de sucesso do MMAR. O projeto nao depende do monitor do SEC.