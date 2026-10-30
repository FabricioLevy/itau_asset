# -*- coding: utf-8 -*-
"""
Automação da tela "Consulta Status de validação de Cotas"
(/oc3svc/ConsultaStatusValidacao.aspx) do portal intracorp9.itau.

Fluxo (dentro do iframe "iframeConteudo" do portal):
  1. Abre a tela navegando o iframe direto pra URL (evita depender do menu
     hover, que é frágil de automatizar).
  2. Seleciona o "Sistema" (LZ/XZ) no dropdown ddlSistema.
  3. Se um (ou mais) dia específico foi pedido (--dias/--data-posicao),
     seleciona o dia no calendário do campo "Dt Posição"
     (`selecionar_data_posicao`) — repetindo os passos 4 e 5 uma vez por
     dia útil pedido, já que o campo só aceita um dia por vez.
  4. Clica "Listar" (popula o grid dtgCarteiras via UpdatePanel/async
     postback) — já filtrado pelo servidor pela "Dt Posição" selecionada.
  5. Clica "Gerar Excel" (postback completo fora de UpdatePanel — dispara
     download do arquivo) e espera o arquivo aparecer na pasta de download.

Sobre o filtro "Dt Posição" (`tbxDataPosicao`): o campo vem do servidor
com o atributo HTML `disabled`, e navegadores não enviam campos
desabilitados no postback — por isso, mesmo clicando no dia certo no
calendário (CalendarExtender), o valor selecionado nunca chegava no
servidor, que sempre devolvia os dados "de hoje" (confirmado comparando
os dados baixados com e sem interagir com o calendário: idênticos).
`selecionar_data_posicao` contorna isso removendo o atributo `disabled`
via JS depois de selecionar o dia — assim o valor passa a ser enviado
normalmente no próximo postback (Listar), e o servidor já devolve só os
fundos daquele dia (não é mais necessário filtrar o resultado localmente
por "DataProcessamento" depois do download).

Não mexe em "Efetuar Carga" (altera dados) nem em "Inverter seleção" —
"Gerar Excel" exporta o que estiver listado, independente de seleção.

A gravação no SQL Server (--salvar-sql) fica em carga_sql.py.
"""
from __future__ import annotations

import glob
import os
import time
from datetime import date, timedelta

import pandas as pd
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

BASE_URL = "https://intracorp9.itau"
REPORT_PATH = "/oc3svc/ConsultaStatusValidacao.aspx?IspbVeiculoLegal=60701190"
IFRAME_ID = "iframePaginas"

SISTEMAS = {"LZ": "1", "XZ": "2"}

# valor da coluna "Mesa Gestão" do relatório quando o fundo não está na VW_FUNDOS_COTAS_PL
MESA_NAO_ENCONTRADA = "Não encontrado"

WEEKDAYS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]  # date.weekday(): seg=0..dom=6
MONTHS_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _log(msg: str) -> None:
    print(msg, flush=True)


def dia_util_anterior(d: date) -> date:
    """Devolve o dia útil anterior a `d` (D-1), pulando sábado/domingo.
    Não conhece feriados — se cair em feriado, o calendário vai mesmo
    assim selecionar esse dia (ajuste manual com --data-posicao se precisar).
    """
    anterior = d - timedelta(days=1)
    while anterior.weekday() >= 5:  # 5=sábado, 6=domingo
        anterior -= timedelta(days=1)
    return anterior


def gerar_lista_dias_uteis(data_final: date, quantidade: int) -> list:
    """Devolve `quantidade` dias úteis terminando em `data_final` (incluído),
    em ordem crescente. Ex.: gerar_lista_dias_uteis(date(2026,9,15), 3) ->
    [13/09 (dom, se cair em fim de semana já pula), ..., 15/09]. Na prática:
    [D-2, D-1, D] onde D = data_final, pulando sábado/domingo.
    """
    dias = [data_final]
    atual = data_final
    for _ in range(max(quantidade, 1) - 1):
        atual = dia_util_anterior(atual)
        dias.append(atual)
    return sorted(dias)


def _titulo_dia(d: date) -> str:
    return f"{WEEKDAYS_PT[d.weekday()]}, {d.day} de {MONTHS_PT[d.month - 1]} de {d.year}"


def abrir_tela(driver, timeout: int = 30) -> None:
    """Navega o iframe de conteúdo do portal direto para a tela de Consulta
    Status Validação (equivalente a clicar OC3 > SVC > Consulta Status
    Validação no menu, mas sem depender do menu hover-dinâmico).

    Ao final, o `driver` já está com o foco (switch_to.frame) dentro do
    iframe, pronto pra interagir com os campos da tela.
    """
    driver.switch_to.default_content()
    url = BASE_URL + REPORT_PATH
    driver.execute_script(
        "document.getElementById(arguments[0]).src = arguments[1];", IFRAME_ID, url
    )

    def _iframe_carregado(d):
        try:
            return d.execute_script(
                "var f = document.getElementById(arguments[0]);"
                "return !!(f && f.contentWindow && f.contentWindow.document "
                "&& f.contentWindow.document.readyState === 'complete' "
                "&& f.contentWindow.document.getElementById('btnListar'));",
                IFRAME_ID,
            )
        except Exception:
            return False

    WebDriverWait(driver, timeout).until(_iframe_carregado)
    frame = driver.find_element(By.ID, IFRAME_ID)
    driver.switch_to.frame(frame)


def selecionar_data_posicao(driver, data_alvo: date, timeout: int = 15) -> None:
    """Abre o calendário (CalendarExtender), clica no dia `data_alvo` e
    força o campo `tbxDataPosicao` a ser enviado no próximo postback.

    O campo vem sempre com o atributo HTML `disabled` do servidor — mesmo
    depois de clicar no dia certo, o navegador não envia campos
    desabilitados no postback, então o servidor ignorava a seleção e
    sempre devolvia os dados "de hoje". Por isso, depois de confirmar que
    o clique no calendário preencheu o campo com a data certa, removemos
    o `disabled` via JS: assim o valor passa a ser enviado normalmente no
    próximo "Listar".
    """
    driver.find_element(By.ID, "imgCalendarioDataPosicao").click()
    WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.ID, "CalendarExtender1_popupDiv"))
    )

    titulo_esperado = f"{MONTHS_PT[data_alvo.month - 1]}, {data_alvo.year}"
    for _ in range(4):
        titulo_atual = driver.find_element(By.ID, "CalendarExtender1_title").text.strip()
        if titulo_atual.lower() == titulo_esperado.lower():
            break
        # decide pra que lado navegar comparando mês/ano exibido com o alvo
        driver.find_element(By.ID, "CalendarExtender1_prevArrow").click()
        time.sleep(0.3)
    else:
        raise RuntimeError(
            f"Não consegui navegar o calendário até {titulo_esperado!r} "
            f"(ficou em {titulo_atual!r})"
        )

    titulo_dia = _titulo_dia(data_alvo)
    dia_el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(
            (By.XPATH, f'//div[@class="ajax__calendar_day" and @title="{titulo_dia}"]')
        )
    )
    dia_el.click()
    # o CalendarExtender fecha o popup sozinho ao selecionar; garante que sumiu
    WebDriverWait(driver, timeout).until(
        EC.invisibility_of_element_located((By.ID, "CalendarExtender1_popupDiv"))
    )
    valor_campo = driver.find_element(By.ID, "tbxDataPosicao").get_attribute("value")
    _log(f"[status_validacao] tbxDataPosicao após seleção: {valor_campo!r}")
    valor_esperado = data_alvo.strftime("%d/%m/%Y")
    if valor_campo != valor_esperado:
        raise RuntimeError(
            f"campo Dt Posição não refletiu a data clicada "
            f"(esperado {valor_esperado!r}, veio {valor_campo!r}) — o filtro "
            f"não pode ser aplicado com confiança"
        )

    # o campo vem `disabled` do servidor; navegador não envia campo
    # desabilitado no postback, então removemos o atributo pra a data
    # selecionada ser realmente enviada no próximo "Listar"
    ainda_desabilitado = driver.execute_script(
        "var el = document.getElementById('tbxDataPosicao');"
        "if (el) { el.removeAttribute('disabled'); }"
        "return el ? el.disabled : null;"
    )
    if ainda_desabilitado:
        raise RuntimeError(
            "não consegui remover o atributo disabled do campo Dt Posição "
            "— o filtro não vai ser enviado no postback"
        )
    _log("[status_validacao] disabled removido de tbxDataPosicao — "
         f"Dt Posição {valor_campo} será enviada no próximo Listar")


def selecionar_sistema(driver, sistema: str) -> None:
    valor = SISTEMAS[sistema.upper()]
    Select(driver.find_element(By.ID, "ddlSistema")).select_by_value(valor)


def clicar_listar(driver, timeout: int = 60) -> int:
    """Clica em Listar e espera o grid (re)carregar. Devolve a quantidade
    de linhas retornadas (0 se a consulta não trouxe resultado)."""
    driver.find_element(By.ID, "btnListar").click()

    def _grid_pronto(d):
        # a busca terminou quando o popup "Processando..." não está visível
        try:
            popup = d.find_element(By.ID, "pnlPopup")
            return popup.value_of_css_property("display") == "none"
        except Exception:
            return True

    WebDriverWait(driver, timeout).until(_grid_pronto)
    time.sleep(0.5)  # pequena folga pro DOM assentar após o async postback
    linhas = driver.find_elements(By.CSS_SELECTOR, "input[id^='dtgCarteiras_checkBox_']")
    return len(linhas)


def _arquivos_em(pasta: str) -> set:
    return set(glob.glob(os.path.join(pasta, "*")))


def gerar_excel(driver, download_dir: str, timeout: int = 60) -> str:
    """Clica em 'Gerar Excel' e espera o arquivo aparecer em `download_dir`.
    Devolve o caminho do arquivo baixado."""
    antes = _arquivos_em(download_dir)
    driver.find_element(By.ID, "btnGerarExcel").click()

    inicio = time.time()
    novo_arquivo = None
    while time.time() - inicio < timeout:
        depois = _arquivos_em(download_dir)
        candidatos = [f for f in (depois - antes) if not f.endswith((".crdownload", ".tmp"))]
        if candidatos:
            novo_arquivo = max(candidatos, key=os.path.getmtime)
            # espera o tamanho parar de crescer (download realmente terminou)
            tamanho_anterior = -1
            while True:
                time.sleep(0.5)
                tamanho_atual = os.path.getsize(novo_arquivo)
                if tamanho_atual == tamanho_anterior:
                    break
                tamanho_anterior = tamanho_atual
            break
        time.sleep(0.5)

    if not novo_arquivo:
        raise TimeoutException(
            f"Nenhum arquivo novo apareceu em {download_dir!r} após clicar em Gerar Excel "
            f"(timeout de {timeout}s)"
        )
    return novo_arquivo


def _data_efetiva(datas_hora: "pd.Series", janela_madrugada_horas: int) -> "pd.Series":
    """Calcula a "data efetiva" de cada timestamp: se o horário for antes de
    `janela_madrugada_horas`, considera que é o fechamento do dia anterior
    (alguns sistemas, como o LZ, fecham o processamento de D já na madrugada
    de D+1, carimbado com a data de "hoje"). Devolve uma Series de `date`
    (ou `NaT`/None onde `datas_hora` for inválido).
    """
    eh_madrugada = datas_hora.dt.hour < janela_madrugada_horas
    dia = datas_hora.dt.date
    dia_anterior = (datas_hora - pd.to_timedelta(1, unit="D")).dt.date
    return dia.where(~eh_madrugada, dia_anterior)


def _ler_grid_baixado(caminho: str, janela_madrugada_horas: int = 6,
                      sistema_label: str = None, data_posicao: date = None) -> "pd.DataFrame":
    """Lê o .xls baixado (é uma tabela HTML, não um binário Excel de verdade)
    e devolve um DataFrame com uma coluna extra "DataEfetiva" calculada a
    partir de "DataProcessamento" — sem filtrar nenhuma linha (o filtro por
    data já é feito pelo próprio servidor via "Dt Posição", ver
    `selecionar_data_posicao`) — e outra "DtPosicao" com o dia filtrado no
    portal (`data_posicao`; vazia quando a busca foi sem filtro de data).

    Números no formato BR (ex.: "1,4199502") são convertidos corretamente
    (vírgula decimal, ponto como separador de milhar).

    Alguns sistemas (observado no LZ) rodam o processamento do fechamento de
    D já na madrugada de D+1 — o registro fica com timestamp de "amanhã"
    (ex.: 16/09 00:14), mas é, na prática, o fechamento de 15/09. Por isso a
    "data efetiva" de cada linha (ver `_data_efetiva`) já joga de volta pro
    dia anterior quando o horário é antes de `janela_madrugada_horas`
    (padrão: 6h).
    """
    with open(caminho, encoding="latin-1") as f:
        html = f.read()
    df = pd.read_html(html, header=0, thousands=".", decimal=",")[0]

    if "DataProcessamento" not in df.columns:
        raise ValueError(
            f"coluna 'DataProcessamento' não encontrada em {caminho!r} "
            f"(colunas: {list(df.columns)})"
        )

    datas_hora = pd.to_datetime(
        df["DataProcessamento"], format="%d/%m/%Y %H:%M:%S", errors="coerce"
    )
    df["DataEfetiva"] = _data_efetiva(datas_hora, janela_madrugada_horas)
    df["DtPosicao"] = pd.Timestamp(data_posicao) if data_posicao else pd.NaT
    if sistema_label and "Sistema" in df.columns:
        # a coluna "Sistema" vem com o código numérico (1=LZ, 2=XZ); troca
        # pelo rótulo que já sabemos (mais legível no relatório final)
        df["Sistema"] = sistema_label
    return df.reset_index(drop=True)


def _listar_e_baixar(driver, sistema: str, download_dir: str, bruto_dir: str,
                     rotulo_arquivo: str) -> str:
    """Clica "Listar" (grid já refletindo a Dt Posição/Sistema selecionados
    antes de chamar essa função) e "Gerar Excel", movendo o download bruto
    pra `bruto_dir` com um nome que inclui `rotulo_arquivo`. Devolve o
    caminho do arquivo bruto."""
    qtd = clicar_listar(driver)
    _log(f"[status_validacao] grid carregado com {qtd} linha(s) ({rotulo_arquivo})")
    if qtd == 0:
        _log("[status_validacao] aviso: nenhuma linha retornada — "
             "'Gerar Excel' provavelmente vai gerar um arquivo vazio")

    arquivo_bruto = gerar_excel(driver, download_dir)
    novo_caminho = os.path.join(bruto_dir, f"{sistema}_{rotulo_arquivo}_" + os.path.basename(arquivo_bruto))
    if os.path.exists(novo_caminho):
        os.remove(novo_caminho)
    os.replace(arquivo_bruto, novo_caminho)
    _log(f"[status_validacao] download bruto: {novo_caminho}")
    return novo_caminho


def baixar_status_validacao(driver, sistema: str, datas_posicao,
                            download_dir: str, destino: str = None,
                            janela_madrugada_horas: int = 6) -> str:
    """Executa o fluxo completo pra um sistema (LZ ou XZ).

    `datas_posicao` pode ser um único `date`, uma lista de `date`s (ex.:
    D-1, D-2, D-3) ou `None` pra trazer todos os fundos do grid sem
    filtrar por data (inclusive os "Pendente", sem DataProcessamento
    ainda).

    Como o campo "Dt Posição" da tela só aceita um dia por vez, quando
    `datas_posicao` tem mais de uma data o fluxo Listar -> Gerar Excel é
    repetido uma vez por data (forçando a Dt Posição antes de cada
    "Listar" — ver `selecionar_data_posicao`), e os resultados são
    concatenados no `.xlsx` final. Devolve o caminho desse `.xlsx`. Os
    downloads brutos (um por data) ficam em `download_dir/bruto/`.
    """
    if datas_posicao is not None:
        datas_posicao = sorted({datas_posicao} if isinstance(datas_posicao, date) else set(datas_posicao))
        datas_str = ", ".join(d.strftime("%d/%m/%Y") for d in datas_posicao)
    else:
        datas_str = "todas (sem filtro)"
    _log(f"[status_validacao] abrindo tela (sistema={sistema}, datas-alvo=[{datas_str}])")
    abrir_tela(driver)
    selecionar_sistema(driver, sistema)

    bruto_dir = os.path.join(download_dir, "bruto")
    os.makedirs(bruto_dir, exist_ok=True)

    if datas_posicao is None:
        arquivo_bruto = _listar_e_baixar(driver, sistema, download_dir, bruto_dir, "TODOS")
        df = _ler_grid_baixado(arquivo_bruto, janela_madrugada_horas, sistema_label=sistema)
        sufixo = "TODOS_" + date.today().strftime("%Y%m%d")
    else:
        partes = []
        for d in datas_posicao:
            selecionar_data_posicao(driver, d)
            arquivo_bruto = _listar_e_baixar(
                driver, sistema, download_dir, bruto_dir, d.strftime("%Y%m%d")
            )
            partes.append(_ler_grid_baixado(arquivo_bruto, janela_madrugada_horas,
                                            sistema_label=sistema, data_posicao=d))
        df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
        sufixo = (f"{datas_posicao[0].strftime('%Y%m%d')}_a_{datas_posicao[-1].strftime('%Y%m%d')}"
                  if len(datas_posicao) > 1 else datas_posicao[0].strftime("%Y%m%d"))

    destino = destino or os.path.join(download_dir, f"StatusValidacao_{sistema}_{sufixo}.xlsx")
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    df.to_excel(destino, index=False, engine="openpyxl")
    _log(f"[status_validacao] {len(df)} linha(s) (Dt Posição=[{datas_str}]) -> {destino}")
    return destino


def _norm(valor) -> str:
    """Normaliza um código de fundo pra comparação (sem espaços nas bordas,
    maiúsculas) — mesmo critério usado em batimento/src/verificar.py."""
    return " ".join(str(valor).split()).upper()


def traduzir_codigos_sac() -> pd.DataFrame:
    """O "Fundo" do portal (Consulta Status Validação) usa a antiga "Sigla
    SAC" (ex.: "173-ITAÚ INDEX", com espaço/acento), enquanto
    VW_FUNDOS_COTAS_PL.codigo_IAM_fundo usa o código IAM canônico (ex.:
    "173-ITAU_INDEX", underscore/sem acento) — por isso muitos fundos
    apareciam como "Não encontrado" ao comparar direto.

    SISTEMAS_DICIONARIO_FUNDOS (sistema='SAC', tipo='Carteira') faz essa
    ponte: `codigo_sistema` = sigla SAC (igual ao "Fundo" do portal),
    `codigo_IAM_fundo` = código canônico. Devolve um DataFrame com colunas
    `_key` (sigla SAC normalizada) e `codigo_IAM_fundo`.
    """
    import sql_connection as sc

    query = """
        SELECT [codigo_sistema], [codigo_IAM_fundo]
          FROM [DBSX337].[dbo].[SISTEMAS_DICIONARIO_FUNDOS] WITH (NOLOCK)
         WHERE sistema = 'SAC' AND tipo = 'Carteira'
    """
    df = sc.query(query)
    if df.empty:
        return pd.DataFrame(columns=["_key", "codigo_IAM_fundo"])
    df["_key"] = df["codigo_sistema"].map(_norm)
    df = df.drop_duplicates(subset="_key", keep="first")
    return df[["_key", "codigo_IAM_fundo"]].reset_index(drop=True)


def consultar_mesa_gestao(fundos, data_referencia: date = None, dias_historico: int = 120) -> pd.DataFrame:
    """Descobre a mesa de gestão de cada fundo (identificado pela sigla SAC,
    igual à coluna "Fundo" do portal). Primeiro traduz a sigla SAC pro
    código IAM canônico via `traduzir_codigos_sac` (com fallback pra usar a
    própria sigla, caso não haja tradução no dicionário) e então consulta a
    view VW_FUNDOS_COTAS_PL (banco DBSX337, via sql_connection) por esse
    código canônico.

    A mesa de gestão de um fundo praticamente não muda de um dia pro outro,
    então não exigimos igualdade exata de data: pegamos o registro **mais
    recente disponível** de cada fundo dentro dos últimos `dias_historico`
    dias a partir de `data_referencia` (padrão: hoje) — assim fundos
    "Pendente"/sem DataProcessamento hoje ainda aparecem com a mesa certa.

    Devolve um DataFrame com colunas `mesa_gestao`, `codigo_IAM_fundo`
    (vazio quando o fundo não foi achado na view) e `_key` (sigla SAC
    normalizada, usada pra cruzar com o "Fundo" do relatório) — uma linha
    por fundo pedido.
    """
    import sql_connection as sc

    data_referencia = data_referencia or date.today()
    data_inicio = data_referencia - timedelta(days=dias_historico)
    fundos_norm = sorted({_norm(f) for f in fundos if str(f).strip()})
    colunas = ["mesa_gestao", "codigo_IAM_fundo", "_key"]
    if not fundos_norm:
        return pd.DataFrame(columns=colunas)

    # sigla SAC -> código IAM canônico (fallback: a própria sigla)
    entrada = pd.DataFrame({"_key": fundos_norm})
    dic = traduzir_codigos_sac()
    entrada = entrada.merge(dic, on="_key", how="left")
    entrada["codigo_IAM_fundo"] = entrada["codigo_IAM_fundo"].fillna(entrada["_key"])

    codigos = sorted(set(entrada["codigo_IAM_fundo"]))
    lista_fundos = ", ".join("'" + c.replace("'", "''") + "'" for c in codigos)
    query = f"""
        SELECT [date], [codigo_IAM_fundo], [mesa_gestao]
          FROM [DBSX337].[dbo].[VW_FUNDOS_COTAS_PL] WITH (NOLOCK)
         WHERE date BETWEEN '{data_inicio.strftime('%Y-%m-%d')}' AND '{data_referencia.strftime('%Y-%m-%d')}'
           AND codigo_IAM_fundo IN ({lista_fundos})
    """
    df = sc.query(query)
    if df.empty:
        return pd.DataFrame(columns=colunas)
    df["date"] = pd.to_datetime(df["date"])
    # mantém só o registro mais recente de cada código canônico
    df = df.sort_values("date", ascending=False).drop_duplicates(subset="codigo_IAM_fundo", keep="first")

    # volta pra sigla SAC original (_key) pra poder cruzar com o relatório
    resultado = entrada.merge(df[["codigo_IAM_fundo", "mesa_gestao"]], on="codigo_IAM_fundo", how="left")
    # código que não existe na view (fallback sem tradução) não é um código IAM confiável
    resultado["codigo_IAM_fundo"] = resultado["codigo_IAM_fundo"].where(
        resultado["codigo_IAM_fundo"].isin(df["codigo_IAM_fundo"]))
    return resultado[colunas]


def gerar_relatorio_mesa_gestao(arquivos: dict, destino: str,
                                data_referencia: date = None) -> str:
    """Junta os .xlsx filtrados/baixados de cada sistema (`arquivos`:
    {sistema: caminho}, cada um já com as colunas "DataEfetiva" e
    "DtPosicao"), busca a mesa de gestão de cada fundo via SQL (registro
    mais recente disponível — ver `consultar_mesa_gestao`) e salva um único
    Excel em `destino`.

    Traz **todos** os fundos presentes nos arquivos de entrada — inclusive
    "Pendente"/sem DataProcessamento — cada um com sua própria data (coluna
    "Data" fica em branco quando não há DataProcessamento ainda; "Dt
    Posição" fica em branco quando a busca foi sem filtro de data).

    Colunas do relatório final: todas as trazidas pelo portal (menos "SAC",
    que na tela é só um link "Detalhe", sem dado nenhum) mais a Mesa Gestão
    e o Código IAM:

        Data, Dt Posição, Fundo, Código IAM, Sistema, Tipo, Passivo, Valor,
        Status, Status Banda, Carga Cockpit, Mesa Gestão, Id Cota,
        Id Carteira, Data Processamento
    """
    colunas_brutas = ["Fundo", "Sistema", "Tipo", "CodigoPassivo", "Valor",
                      "StatusCota", "StatusBanda", "NotificadaViaCockpit",
                      "IdCota", "IdCarteira", "DataProcessamento", "DataEfetiva",
                      "DtPosicao"]

    partes = []
    for caminho in arquivos.values():
        if os.path.exists(caminho):
            partes.append(pd.read_excel(caminho))
    combinado = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=colunas_brutas)

    if not combinado.empty:
        combinado["_key"] = combinado["Fundo"].map(_norm)
        combinado["DataEfetiva"] = pd.to_datetime(combinado["DataEfetiva"], errors="coerce")
        combinado["DtPosicao"] = pd.to_datetime(combinado["DtPosicao"], errors="coerce")
        mapa = consultar_mesa_gestao(combinado["Fundo"], data_referencia=data_referencia)
        combinado = combinado.merge(mapa[["_key", "mesa_gestao", "codigo_IAM_fundo"]],
                                    on="_key", how="left")
        sem_mesa = combinado["mesa_gestao"].isna().sum()
        if sem_mesa:
            _log(f"[status_validacao] aviso: {sem_mesa} linha(s) sem mesa de "
                 f"gestão encontrada na VW_FUNDOS_COTAS_PL")

    def _fmt_data(d):
        return d.strftime("%d/%m/%Y") if pd.notna(d) else ""

    final = pd.DataFrame({
        "_DataOrdenacao": combinado["DataEfetiva"] if not combinado.empty else [],
        "Data": combinado["DataEfetiva"].apply(_fmt_data) if not combinado.empty else [],
        "Dt Posição": combinado["DtPosicao"].apply(_fmt_data) if not combinado.empty else [],
        "Fundo": combinado["Fundo"].astype(str).str.strip() if not combinado.empty else [],
        "Código IAM": combinado["codigo_IAM_fundo"] if not combinado.empty else [],
        "Sistema": combinado["Sistema"] if not combinado.empty else [],
        "Tipo": combinado["Tipo"] if not combinado.empty else [],
        "Passivo": combinado["CodigoPassivo"] if not combinado.empty else [],
        "Valor": combinado["Valor"] if not combinado.empty else [],
        "Status": combinado["StatusCota"] if not combinado.empty else [],
        "Status Banda": combinado["StatusBanda"] if not combinado.empty else [],
        "Carga Cockpit": combinado["NotificadaViaCockpit"] if not combinado.empty else [],
        "Mesa Gestão": combinado["mesa_gestao"].fillna(MESA_NAO_ENCONTRADA) if not combinado.empty else [],
        "Id Cota": combinado["IdCota"] if not combinado.empty else [],
        "Id Carteira": combinado["IdCarteira"] if not combinado.empty else [],
        "Data Processamento": combinado["DataProcessamento"] if not combinado.empty else [],
    })
    if not final.empty:
        final = final.sort_values(["_DataOrdenacao", "Fundo"], na_position="last").reset_index(drop=True)
    final = final.drop(columns=["_DataOrdenacao"])

    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    final.to_excel(destino, index=False, engine="openpyxl")
    _log(f"[status_validacao] relatório consolidado ({', '.join(final.columns)}) "
         f"-> {destino} ({len(final)} linha(s))")
    return destino
