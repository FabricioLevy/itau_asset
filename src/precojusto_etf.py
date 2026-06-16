
import sys
import os
import pathlib
folder = pathlib.Path().resolve().parent.name


if (folder == 'bases-fundos-iam'):
    sys.path.append("../")
else:
    filePath = os.environ.get('BASES_FUNDOS_IAM_FILE_PATH')
    sys.path.append(filePath)


from Funcoes.LakeConn import Conn
import pandas as pd
from datetime import date, datetime, timedelta
from qs_utils.qsdate import QsDate
from xbbg import blp
from Preco_PnL.assets.ntnb import  cash_flow as calc_cupom_ntnb, unit_price_deprecated as pu_careca_ntnb
from Preco_PnL.assets.ntnf import  cash_flow as calc_cupom_ntnf, unit_price as pu_careca_ntnf
from Preco_PnL.assets.ltn import  cash_flow as calc_cupom_ltn, unit_price_deprecated as pu_careca_ltn



# -----------------------------------------------------------------------------
# Salvamento das cotacoes mais recentes das NTN-Bs
# -----------------------------------------------------------------------------
ARQUIVO_COTACOES_BS = r"\\fswcorp\WMSASSET\ASSET_COMUM\ETFs\cotacoes_bs.csv"



def _salvar_cotacoes_bs(df, arquivo_destino=ARQUIVO_COTACOES_BS):
    #
    # Salva o historico de cotacoes das NTN-Bs (ISIN, tipo, data, preco, taxa e
    # data/hora da atualizacao) em arquivo CSV de rede e remove registros com
    # mais de n_dias de idade.
    #
    # Toda a logica esta envolta em try/except (incluindo blocos internos para
    # cada etapa que pode falhar isoladamente) para que falhas de rede, BBG sem
    # cotacao ou problemas de I/O nao impactem o fluxo de calculo do preco
    # justo dos ETFs.
    #
    try:
        agora = datetime.now()
        data_cotacao = agora.date().strftime("%Y-%m-%d")
        str_atualizacao = agora.strftime("%Y-%m-%d %H:%M:%S")


        #
        # Monta o DataFrame com apenas as NTN-Bs e descarta linhas sem preco
        # (cotacao ausente na BBG nao deve gerar registro).
        #
        try:
            mask_ntnb = df["tipo_ativo"] == "NTN-B"
            colunas_necessarias = ["isin", "tipo_ativo", "preco_online", "taxa_online"]
            df_ntnb = df.loc[mask_ntnb, colunas_necessarias].copy()
            df_ntnb = df_ntnb.drop_duplicates(subset=["isin"])
            df_ntnb = df_ntnb.dropna(subset=["preco_online"])
        except Exception:
            df_ntnb = pd.DataFrame()


        if df_ntnb.empty:
            return


        df_novo = pd.DataFrame({
            "isin"                  : df_ntnb["isin"].values,
            "tipo_ativo"            : df_ntnb["tipo_ativo"].values,
            "data"                  : data_cotacao,
            "valor_cotacao"         : df_ntnb["preco_online"].values,
            "taxa"                  : df_ntnb["taxa_online"].values,
            "data_hora_atualizacao" : str_atualizacao,
        })


        #
        # Le o historico existente. Se o arquivo nao existir, falhar na leitura
        # ou estiver corrompido, segue so com os registros novos.
        #
        try:
            df_novo.to_csv(
                arquivo_destino,
                sep=";",
                decimal=",",
                index=False,
            )
        except Exception:
            pass


    except Exception:
        #
        # Garantia final: nenhuma excecao daqui sobe para o calculo do preco
        # justo dos ETFs.
        #
        pass
# -----------------------------------------------------------------------------



def gerar_preco_justo_etfRF(controle):
        
    # Conn
    conn = Conn()


    d0 = date.today()
    d1 = str(QsDate(d0).add_business_days(-1))
        
    lista_fundos = list(controle.keys())
    dict_ticker_etf = {fundo: controle[fundo]['ticker'] for fundo in lista_fundos}
    dict_bench_etf = {fundo: controle[fundo]['bench'] for fundo in lista_fundos}
    dict_indice_format = {fundo: controle[fundo]['indice_formatado'] for fundo in lista_fundos}


    #dicionario mes vencimento para codigo
    dict_vencimento = {
    '1'  : 'F',
    '2'  : 'G',
    '3'  : 'H',
    '4'  : 'J',
    '5'  : 'K',
    '6'  : 'M',
    '7'  : 'N',
    '8'  : 'Q',
    '9'  : 'U',
    '10' : 'V',
    '11' : 'X',
    '12' : 'Z'
    }


    ###############################
    #QUERIES NECESSARIAS DO DBSX337
    ###############################


    string_fundos = ", ".join([f"'{fundo}'" for fundo in lista_fundos])


    #POSICAO RF
    sql = f"""
    SELECT 
        dt,
        clcli_cd,
        Trim(rftp_cd) AS tipo_ativo,
        dt_vencimento,
        Concat(rftp_cd, ' ', dt_vencimento) AS ticker,
        isin,
        Sum(qt_total) AS quantidade,
        sum(vl_liq_pos) as valor_posicao
    FROM 
        dbsx337.dbo.VCRAPRF
    WHERE 1=1
        and dt = '{d1}' 
        and clcli_cd IN ({string_fundos})
    GROUP BY 
        dt,clcli_cd,rftp_cd,dt_vencimento,isin
    ORDER BY 
        dt,clcli_cd,rftp_cd,dt_vencimento
    """
    df_pos = pd.read_sql(sql, conn)


    #COTA/PL
    sql = f"""
    SELECT 
        dt,
        clcli_cd,
        QT_COTAS1 as qt_cotas
    FROM 
        DBSX337.DBO.VCRAPLSI
    WHERE 1=1
        and clcli_cd IN ({string_fundos})
        and dt = '{d1}'
    """
    df_cota = pd.read_sql(sql, conn)


    #VNA
    sql = f"""
    SELECT 
        data_referencia,
        titulos_tipo_titulo,
        titulos_vna
    FROM 
        dbsx337.dbo.tbhh3042_anbima_titulo_publico_vna
    WHERE  1=1
        and titulos_tipo_titulo = 'NTN-B'
        AND data_referencia = '{d0}'
    """
    df_vna = pd.read_sql(sql, conn)


    #PL DESCONSIDERANDO B'S
    sql = f"""
    SELECT 
        a.dt,
        a.clcli_cd,
        (vl_patrliqtot1 - vl_brutopos_bs) AS PLexBs
    FROM 
        dbsx337.dbo.vcraplsi AS A
        JOIN (
            SELECT 
                dt,
                clcli_cd,
                SUM(vl_brutopos) AS VL_BRUTOPOS_Bs
            FROM 
                dbsx337.dbo.vcraprf
            WHERE 1=1
                and dt = '{d1}'
                AND rftp_cd IN ('NTN-B', 'LTN', 'NTN-F')
                AND clcli_cd IN ({string_fundos})
            GROUP BY 
                dt,
                clcli_cd
        ) AS B
        ON A.dt = B.dt
        AND A.clcli_cd = B.clcli_cd
    WHERE 1=1
        and a.dt = '{d1}'
        AND a.clcli_cd IN ({string_fundos})
    """
    df_plexbs = pd.read_sql(sql, conn)


    #DURATION INDICE
    # sql = f"""
    # SELECT DISTINCT 
    #     data_referencia,
    #     indice,
    #     duration
    # FROM 
    #     dbsx337..tbhh3031_anbima_indices_mais_ima_resultados_componentes WITH (NOLOCK)
    # WHERE 1=1
    #     and data_referencia = '{d1}'"""
    sql = \
    f"""
    select distinct 
        data_referencia,
        indice,
        duration
    from 
        dbsx337..tbhh3031_anbima_indices_mais_ima_resultados_componentes with (nolock)
    where 1=1
        and data_referencia = '{d1}'
    union
        select date as data_referencia,'NTNB 2060' AS indice, macaulay_duration as duration from FUNDOS_DADOS_ATIVOS where date='{d1}' and codigo_IAM_ativo='BRSTNCNTB690'
    union
        select date as data_referencia,'NTNB 2050' AS indice, macaulay_duration as duration from FUNDOS_DADOS_ATIVOS where date='{d1}' and codigo_IAM_ativo='BRSTNCNTB3D4'
    union
        select date as data_referencia,'NTNB 2035' AS indice, macaulay_duration as duration from FUNDOS_DADOS_ATIVOS where date='{d1}' and codigo_IAM_ativo='BRSTNCNTB0O7'
    union
        select date, codigo_IAM_indice, SUM(macaulay_duration*perc) as duration from FUNDOS_COMPOSICAO_INDICES where codigo_IAM_indice = 'ITBR_5_PRE' and date = '{d1}' group by date, codigo_IAM_indice
    """
    df_indexduration = pd.read_sql(sql, conn)


    #-----------------------------------------------------------------------------------------------------------------------


    ####################
    #FUNCOES NECESSARIAS
    ####################


    def papel_vencendo(df):
            
        #CALCULA VALOR DO PAPEL VENCENDO PARA COMPOR O CAIXA
        df['valor_vencimento'] = 0
        mask = (df['dt_vencimento']==d0) & (df['tipo_ativo']=='NTN-B')
        df.loc[mask, 'valor_vencimento'] = df.loc[mask, 'valor_posicao']


        df = df.groupby(by=['clcli_cd']).agg({'valor_vencimento':'sum'}).reset_index()


        return df


    def pagamento_cupom(df, bbg_vna):


        mask = (df['tipo_ativo']=='NTN-B')
        df.loc[mask, 'cupom'] = df.apply(lambda x: calc_cupom_ntnb(date_ref=d0, date_maturity=x["dt_vencimento"], vna=bbg_vna), axis=1)


        mask = (df['tipo_ativo']=='NTN-F')
        df.loc[mask, 'cupom'] = df.apply(lambda x: calc_cupom_ntnf(date_ref=d0, date_maturity=x["dt_vencimento"]), axis=1)


        mask = (df['tipo_ativo']=='LTN')
        df.loc[mask, 'cupom'] = df.apply(lambda x: calc_cupom_ltn(date_ref=d0, date_maturity=x["dt_vencimento"]), axis=1)


        df['cupom'] = df['cupom'].fillna(0)
        df['valor_cupom'] = df['cupom'] * df['quantidade'] 
        df = df.groupby(by=['clcli_cd','tipo_ativo','dt_vencimento']).agg({'valor_cupom':'sum'}).reset_index()
        df_consolidado = df.groupby(by=['clcli_cd']).agg({'valor_cupom':'sum'}).reset_index()


        return df_consolidado, df


    def patrimonio_online(df):
        #PATRIMONIO ONLINE
        df['pl_online'] = df['quantidade'] * df['preco_online']
        df =  df.groupby('clcli_cd').agg({'pl_online':'sum'})


        return df


    def taxa_ponderada(df):
        
        #CALCULA TAXA PONDERADA
        df['total'] = df['preco_online'] * df['quantidade']
        df['composicao_perc'] = df['total']/df.groupby('clcli_cd')['total'].transform('sum')


        df['taxa_ponderada'] = df['composicao_perc'] * df['taxa_online']
        df = df.groupby('clcli_cd').agg({'taxa_ponderada':'sum'}).reset_index()
        df['taxa_ponderada'] = df['taxa_ponderada']/100


        return df


    def requisicoes_preco_bbg(df):


        #PREPARAR TICKER PARA REQUISICAO NA BBG
        mask = (df['tipo_ativo']=='NTN-B')


        #LISTA COM TICKERS PARA REQUISICAO BBG
        lista_ntnb = df.loc[mask, 'TickerBBG'].unique().tolist()
        lista_ex_ntnb = df.loc[~mask, 'TickerBBG'].unique().tolist()


        bbg_ntnb_preco = blp.bdp(tickers=lista_ntnb, flds=["px_last"]).reset_index().rename(columns={'index':'TickerBBG','px_last':'preco_online'})
        bbg_ex_ntnb_preco = blp.bdp(tickers=lista_ex_ntnb, flds=["yas_bond_px"]).reset_index().rename(columns={'index':'TickerBBG','yas_bond_px':'preco_online'})


        preco_bbg = pd.concat([bbg_ntnb_preco[['TickerBBG','preco_online']],bbg_ex_ntnb_preco[['TickerBBG','preco_online']]])
        preco_bbg.drop_duplicates(inplace=True)
        #df = df.merge(preco_bbg, how='inner', on ='TickerBBG').reset_index()


        return preco_bbg


    def requisicoes_taxa_bbg(df):
        
        mask = (df['tipo_ativo']=='NTN-B')


        lista_taxa_pre = df.loc[~mask, 'TickerBBG'].unique().tolist()
        lista_ntnb = df.loc[mask, 'TickerBBG'].unique().tolist()


        bbg_pre_tx = blp.bdp(tickers=lista_taxa_pre, flds=["last_trade"]).reset_index().rename(columns={'index':'TickerBBG','last_trade':'taxa_online'})
        bbg_ntnb_tx = blp.bdp(tickers=lista_ntnb, flds=["last_yld"]).reset_index().rename(columns={'index':'TickerBBG','last_yld':'taxa_online'})


        taxa_bbg = pd.concat([bbg_ntnb_tx[['TickerBBG','taxa_online']], bbg_pre_tx[['TickerBBG','taxa_online']]])
        taxa_bbg.drop_duplicates(inplace=True)
        #df = df.merge(taxa_bbg, left_on='TickerBBG', right_on='TickerBBG', how='left')


        return taxa_bbg 


    def preco_etf(df):
        
        df.drop_duplicates(inplace=True)
        df['ticker_etf_bbg'] = df['ticker_etf'] + " Equity"


        lista_ticker_etf = df['ticker_etf_bbg'].unique().tolist()
        px_compra_venda_etf = blp.bdp(tickers=lista_ticker_etf, flds=["px_bid","px_ask","last_trade"]).reset_index().rename(columns={'index':'ticker_etf_bbg','px_bid':'compra','px_ask':'venda','last_trade':'ultimo_negocio'})
        df = df.merge(px_compra_venda_etf, how='inner', on='ticker_etf_bbg')
        return df


    #-----------------------------------------------------------------------------------------------------------------------


    ########################
    #TRATAMENTOS NECESSARIOS
    ########################


    #CRIAR DATAFRAME COM TODA A POSICAO DE TPF MENOS LFT
    df = df_pos[df_pos['tipo_ativo']!='LFT'].copy()
    df = df.groupby(['dt','clcli_cd','tipo_ativo','ticker', 'isin', 'dt_vencimento']).agg({'quantidade': 'sum', 'valor_posicao':'sum'}).reset_index()


    df['dt_vencimento'] = pd.to_datetime(df['dt_vencimento'], format = '%Y-%m-%d')
    df['mes_vencimento'] = df['dt_vencimento'].dt.month.astype(str)
    df['codigo_vencimento'] = df['mes_vencimento'].map(dict_vencimento)
    df['ticker_etf'] = df['clcli_cd'].map(dict_ticker_etf)


    #PREPARAR TICKER PARA REQUISICAO NA BBG DOS PRECOS ONLINE
    mask = (df['tipo_ativo']=='NTN-B')
    df.loc[mask, 'TickerBBG'] = df['isin'] + " @ITAM Corp"
    df.loc[~mask, 'TickerBBG'] = df['isin'] + " Corp"


    #CAPTURAR PRECOS ONLINE DA BBG
    precos_bbg = requisicoes_preco_bbg(df[['tipo_ativo','TickerBBG']].drop_duplicates())
    df = df.merge(precos_bbg, how='left', on='TickerBBG').reset_index()
    df.drop(columns=['TickerBBG'], inplace=True)


    #PREPARAR TICKER PARA REQUISICAO NA BBG DAS TAXAS ONLINE
    mask = (df['tipo_ativo']=='NTN-B')
    df.loc[mask, 'TickerBBG'] = df['isin'] + " @ITAM Corp"
    df.loc[~mask, 'TickerBBG'] = "OD" + df['codigo_vencimento'] + df['dt_vencimento'].dt.year.astype(str).str[-2:] + " Comdty"


    #CAPTURAR TAXAS ONLINE DA BBG
    taxas_bbg = requisicoes_taxa_bbg(df[['tipo_ativo','TickerBBG']].drop_duplicates())
    df = df.merge(taxas_bbg, how='left', on=['TickerBBG']).reset_index()
    df.drop(columns=['TickerBBG'], inplace=True)


    #
    # SALVAR HISTORICO DAS COTACOES DAS NTN-Bs (nao impacta o fluxo principal).
    # Esta chamada e envolta em try/except aqui tambem como camada extra de
    # seguranca, embora a funcao ja trate suas proprias excecoes internamente.
    #
    try:
        _salvar_cotacoes_bs(df)
    except Exception:
        pass


    #CALCULAR VALOR DOS PAPEIS VENCENDO HOJE
    df_vencimento = papel_vencendo(df[['dt_vencimento','clcli_cd','tipo_ativo','valor_posicao']])


    #CAPTURAR VNA DA BBG
    bbg_vna = blp.bdp(tickers=["EF323775@ANDE Corp"], flds=["idx_ratio"], settle_dt=d0).reset_index() * 1000
    bbg_vna = bbg_vna['idx_ratio'][0]


    #CAPTURAR VALOR DOS CUPONS PAGOS HOJE
    df_cupom, df_cupom_aberto = pagamento_cupom(df[['dt_vencimento','clcli_cd','tipo_ativo','quantidade','mes_vencimento']], bbg_vna)


    #CAPTURAR PRECO DE COMPRA E VENDA DOS ETFS ONLINE
    df_etf = preco_etf(df[['ticker_etf']])


    #REALIZAR MARCACAO NOS PAPEIS QUE PAGAM CUPOM HOJE
    df = df.merge(df_cupom_aberto, how='left', on =['dt_vencimento','tipo_ativo','clcli_cd'])
    df['paga_cupom_hoje'] = df['valor_cupom'].apply(lambda x: 1 if x > 0 else 0)


    #CALCULAR PU CARECADO SE A NTNB PAGAR CUPOM HOJE
    mask = (df['paga_cupom_hoje'] == 1) & (df['tipo_ativo']=='NTN-B')
    df.loc[mask, 'preco_online'] = df.loc[mask, 'preco_online'].apply(lambda x: pu_careca_ntnb(date_ref=d0 , date_maturity=df.loc[mask, 'dt_vencimento'], rate_ref=df.loc[mask, 'taxa_online'], vna = bbg_vna))   


    #CALCULAR PU CARECADO SE A NTNF PAGAR CUPOM HOJE
    #mask = (df['paga_cupom_hoje'] == 1) & (df['tipo_ativo']=='NTN-F')
    df['dt_vencimento'] = pd.to_datetime(df['dt_vencimento'])
    mask = df['tipo_ativo']=='NTN-F'
    #df.loc[mask, 'preco_online'] = df.loc[mask, 'preco_online'].apply(lambda x: pu_careca_ntnf(date_ref=pd.to_datetime(d0) , date_maturity=df.loc[mask, 'dt_vencimento'], rate_ref=df.loc[mask, 'taxa_online']))   
    df.loc[mask, "preco_online"] = df.apply(lambda x: pu_careca_ntnf(date_ref = QsDate(d0), date_maturity = x["dt_vencimento"], rate_ref = x["taxa_online"]), axis = 1)


    #CALCULAR PU CARECADO SE A LTN PAGAR CUPOM HOJE
    #mask = (df['paga_cupom_hoje'] == 1) & (df['tipo_ativo']=='LTN')
    mask = df['tipo_ativo']=='LTN'
    #df.loc[mask, 'preco_online'] = df.loc[mask, 'preco_online'].apply(lambda x: pu_careca_ltn(date_ref=d0 , date_maturity=df.loc[mask, 'dt_vencimento'], rate_ref=df.loc[mask, 'taxa_online']))   
    df.loc[mask, "preco_online"] = df.apply(lambda x: pu_careca_ltn(date_ref = QsDate(d0), date_maturity = x["dt_vencimento"], rate_ref = x["taxa_online"]), axis = 1)


    #CALCULAR O PL ONLINE
    df_pl_online =  patrimonio_online(df[['clcli_cd','quantidade','preco_online']])


    #CALCULAR A TAXA PONDERADA
    df_tx_ponderada = taxa_ponderada(df[['clcli_cd','taxa_online','preco_online','quantidade']])



    #AGREGAÇÃO DAS METRICAS EM UM UNICO DATAFRAME
    df_consolidado = df_cota.merge(df_plexbs, how='left', on=['dt','clcli_cd'])
    df_consolidado = df_consolidado.merge(df_vencimento, how='left', on='clcli_cd')
    df_consolidado = df_consolidado.merge(df_cupom, how='left', on='clcli_cd').reset_index()


    df_consolidado['indice_fundo'] = df_consolidado['clcli_cd'].map(dict_bench_etf)
    df_consolidado = df_consolidado.merge(df_indexduration, how='left', left_on=['dt','indice_fundo'], right_on=['data_referencia','indice'])


    df_consolidado['ticker_etf'] = df_consolidado['clcli_cd'].map(dict_ticker_etf)
    df_consolidado = df_consolidado.merge(df_etf, on='ticker_etf', how='left')


    df_consolidado = df_consolidado.merge(df_pl_online, on='clcli_cd', how='left')
    df_consolidado = df_consolidado.merge(df_tx_ponderada, on='clcli_cd', how='left')
    
    df_consolidado['indice'] = df_consolidado['clcli_cd'].map(dict_indice_format)


    #CALCULOS DAS METRICAS FINAIS
    df_consolidado['caixa'] = df_consolidado['PLexBs'] + df_consolidado['valor_cupom'] + df_consolidado['valor_vencimento']
    df_consolidado['valor_justo_cota'] = (df_consolidado['caixa'] + df_consolidado['pl_online']) / df_consolidado['qt_cotas']
    df_consolidado['yld_eq_compra'] = df_consolidado['taxa_ponderada'] - (((df_consolidado['compra'] - df_consolidado['valor_justo_cota'])/(df_consolidado['duration']/252))/100)
    df_consolidado['yld_eq_venda'] = df_consolidado['taxa_ponderada'] - (((df_consolidado['venda'] - df_consolidado['valor_justo_cota'])/(df_consolidado['duration']/252))/100)
    df_consolidado['yld_ult_negocio'] = df_consolidado['taxa_ponderada'] - (((df_consolidado['ultimo_negocio'] - df_consolidado['valor_justo_cota']) / (df_consolidado['duration'] / 252)) / 100)
    df_consolidado['spread'] = df_consolidado['yld_eq_compra'] - df_consolidado['yld_eq_venda']
    df_consolidado['duration'] = df_consolidado['duration']/252


    dfFinal = df_consolidado.copy()
    dfFinal['data_hora_atualizacao'] = datetime.now()


    dfFinal = dfFinal[['data_hora_atualizacao','ticker_etf','indice','taxa_ponderada','yld_ult_negocio','spread','duration','valor_justo_cota']]
    dfFinal.rename(columns={'ticker_etf':'etf','taxa_ponderada':'yield_estimado','yld_ult_negocio':'yield_ultimo_negocio','valor_justo_cota':'valor_estimado_cota'}, inplace=True)
    
    
    return dfFinal


def gerar_preco_justo_etfGOAT11(controle):


    # Conn
    conn = Conn()


    d0 = date.today()
    d1 = str(QsDate(d0).add_business_days(-1))


    lista_fundos = list(controle.keys())
    dict_ticker_etf = {fundo: controle[fundo]['ticker'] for fundo in lista_fundos}
    dict_bench_etf = {fundo: controle[fundo]['bench'] for fundo in lista_fundos}
    dict_indice_format = {fundo: controle[fundo]['indice_formatado'] for fundo in lista_fundos}


    #---------------------------------------------------------------------------------------------------------------------------


    ###############################
    #QUERIES NECESSARIAS DO DBSX337
    ###############################


    string_fundos = ", ".join([f"'{fundo}'" for fundo in lista_fundos])


    #COTA/PL
    sql = f"""
    SELECT 
        dt,
        clcli_cd,
        QT_COTAS1 as qt_cotas
    FROM 
        DBSX337.DBO.VCRAPLSI
    WHERE 1=1
        and clcli_cd IN ({string_fundos})
        and dt = '{d1}'
    """
    df_cota = pd.read_sql(sql, conn)


    #POSICAO RV
    sql = f"""
    SELECT 
        dt,
        clcli_cd,
        acao,
        qt_total,
        vl_preco_mercmedio,
        vl_mercadoliquido
    FROM 
        dbsx337.dbo.vcraprv
    WHERE 1=1
        and dt = '{d1}'
        AND clcli_cd IN ({string_fundos})
    """
    df_rv = pd.read_sql(sql, conn)


    #DURATION INDICE
    sql = f"""
    SELECT DISTINCT 
        data_referencia,
        indice,
        duration
    FROM 
        dbsx337..tbhh3031_anbima_indices_mais_ima_resultados_componentes WITH (NOLOCK)
    WHERE 1=1
        and data_referencia = '{d1}'"""
    df_indexduration = pd.read_sql(sql, conn)


    #BTC
    sql = f"""
    SELECT 
        dt,
        clcli_cd,
        codpap as acao,
        quantidade as qt_total,
        valor_total,
        remun_perc,
        ic_tipo_movimento
    FROM 
        dbsx337.dbo.vcrabtc WITH (NOLOCK)
    WHERE 1=1
        and clcli_cd IN ({string_fundos})
        AND dt = '{d1}'
    ORDER BY 
        dt,
        clcli_cd ASC
    """
    df_btc = pd.read_sql(sql, conn)


    #CASH PARADO
    sql = f"""
    SELECT 
        dt,
        clcli_cd,
        ds,
        vl
    FROM 
        dbsx337.dbo.vcraprdp
    WHERE 
        clcli_cd IN ({string_fundos})
        AND mttp_cd = 251
        AND dt = '{d1}'
    """
    df_cash = pd.read_sql(sql, conn)


    #-----------------------------------------------------------------------------------------------------------------------


    def preco_etf_composicao(df):
        
        df.drop_duplicates(inplace=True)


        df['ticker_etf_bbg'] = df['acao'] + " BZ Equity"


        lista_ticker_etf = df['ticker_etf_bbg'].unique().tolist()
        px_online_etf = blp.bdp(tickers=lista_ticker_etf, flds=["LAST_TRADE"]).reset_index()
        px_online_etf.rename(columns={'index':'ticker_etf_bbg','last_trade':'preco_online'}, inplace=True)


        df = df.merge(px_online_etf, how='inner', on='ticker_etf_bbg')
        df = df[['acao','preco_online']]


        return df


    df = pd.concat([df_rv[['clcli_cd','acao','qt_total']] , df_btc[['clcli_cd','acao','qt_total']]])
    df = df.groupby(by=['clcli_cd','acao']).sum().reset_index()


    df['indice_fundo'] = df['clcli_cd'].map(dict_bench_etf)
    df['ticker_etf'] = df['clcli_cd'].map(dict_ticker_etf)


    #calcular o PL online puxando o preço dos etfs que compoe o fundo
    dfPrecos = preco_etf_composicao(df[['acao']])
    df = df.merge(dfPrecos, how='left', on='acao').reset_index()
    df['total_online'] = df['preco_online'] * df['qt_total']


    dfPatrimonioOnline = df[['clcli_cd','total_online']].groupby(by='clcli_cd').sum().reset_index()
    dfPatrimonioOnline.rename(columns={'total_online':'patrimonio_online'}, inplace=True)


    #puxar saldo parado do fundo
    df_cash = df_cash.groupby(by=['dt','clcli_cd']).sum().reset_index()
    dfCaixa = df_cash[['clcli_cd','vl']]
    dfCaixa.rename(columns={'vl':'caixa'}, inplace=True)


    #calcular qtd cotas do fundo
    dfQtdCota = df_cota[['clcli_cd','qt_cotas']]


    df_consolidado = dfPatrimonioOnline.merge(dfCaixa, how='left', on='clcli_cd')
    df_consolidado = df_consolidado.merge(dfQtdCota, how='left', on='clcli_cd')


    df_consolidado['valor_estimado_cota'] = (df_consolidado['caixa'] + df_consolidado['patrimonio_online'])/df_consolidado['qt_cotas']
    df_consolidado['indice'] = df['clcli_cd'].map(dict_indice_format)
    df_consolidado['etf'] = df['clcli_cd'].map(dict_ticker_etf)


    dfFinal = df_consolidado.copy()
    
    dfFinal['data_hora_atualizacao'] = datetime.now()
    dfFinal['yield_estimado'] = '-'
    dfFinal['yield_ultimo_negocio'] = '-'
    dfFinal['yield_ultimo_negocio'] = '-'
    dfFinal['spread'] = '-'
    dfFinal['duration'] = '-'


    dfFinal = dfFinal[['data_hora_atualizacao','etf','indice','yield_estimado','yield_ultimo_negocio','spread','duration','valor_estimado_cota']]


    return dfFinal



# -----------------------------------------------------------------------------
def fut_ticker_atual(
  data_referencia : datetime
, str_prefixo     : str = "TY"
, str_sufixo      : str = "COMB Comdty"
) -> str :
  #
  # Usa a data de referência para determinar qual é a letra a ser usada para o
  # vencimento do ticker que deve estar sendo negociado.
  #
  dict_codigos = \
  {  3 : "H" # Março
  ,  6 : "M" # Junho
  ,  9 : "U" # Setembro
  , 12 : "Z" # Dezembro
  }
  ano = data_referencia.year
  mes = data_referencia.month
  #
  # Encontrar o próximo mês de vencimento trimestral >= mês atual
  #
  meses_validos   = sorted(dict_codigos.keys())
  n_proximo_mes   = None
  for m in meses_validos :
    if m >= mes :
      n_proximo_mes = m
      break
  #
  # Se não encontrou nenhum no ano atual, pega o primeiro do próximo ano
  #
  if n_proximo_mes is None :
    n_proximo_mes = meses_validos[0]
    ano += 1
  #
  # Monta o ticker
  #
  str_codigo_mes = dict_codigos[n_proximo_mes]
  str_ano_2d     = str(ano)[- 2 :]
  str_ticker     = f"{str_prefixo}{str_codigo_mes}{str_ano_2d} {str_sufixo}"
  return str_ticker
# -----------------------------------------------------------------------------
def gerar_preco_justo_etfT10R11(controle):
    # Conn
    conn = Conn()


    d0 = date.today()
    d1 = str(QsDate(d0).add_business_days(-1))


    lista_fundos = list(controle.keys())
    #---------------------------------------------------------------------------------------------------------------------------
    ###############################
    #QUERIES NECESSARIAS DO DBSX337
    ###############################
    str_fed_fund = "FEDL01 Index"
    str_cdi      = "BZSTSETA Index"
    df_fed       = blp.bdh(tickers = str_fed_fund, flds = ["PX_LAST"], start_date = d1, end_date = d1).reset_index().rename(columns = {"index" : "data", "fedl01_index" : "fed_fund"})


    if df_fed.shape[0] == 0 :
        d_fed = 0.0
    else :
        d_fed = df_fed[str_fed_fund].values[0][0]
    df_cdi       = blp.bdh(tickers = str_cdi     , flds = ["PX_LAST"], start_date = d1, end_date = d1).reset_index().rename(columns = {"index" : "data", "bzstseta_index" : "cdi"})
    if df_cdi.shape[0] == 0 :
        d_cdi = 0.0
    else :
        d_cdi = df_cdi[str_cdi].values[0][0]


    try :
        d0         = datetime.now()
        str_ticker = fut_ticker_atual(d0)
    except Exception as e :
        str_ticker = "TYH6 COMB Comdty"
    dfFinal = blp.bdp(tickers=[str_ticker], flds=["CTD_FORWARD_YTM_LAST","dur_adj_mid"]).reset_index()
    if dfFinal.shape[0] == 0 :
        #
        # Obtém a data de 10 dias adiante para garantir que o ticker futuro já tenha
        # mudado para o próximo vencimento.
        #
        d_mais10   = datetime.now() + timedelta(days = 10)
        str_ticker = fut_ticker_atual(d_mais10)
        dfFinal    = blp.bdp(tickers = [str_ticker], flds = ["CTD_FORWARD_YTM_LAST", "dur_adj_mid"]).reset_index()
    dfFinal.rename(columns={'index':'ticker_etf_bbg','ctd_forward_ytm_last':'yield_estimado','dur_adj_mid':'duration'}, inplace=True)
    dfFinal.drop(columns=['ticker_etf_bbg'], inplace=True)


    dfFinal['indice'] = "T10 + Diferencial de Juros BR vs EUA"
    dfFinal['etf'] = 'T10R11'
    dfFinal['valor_estimado_cota'] = '-'
    dfFinal['data_hora_atualizacao'] = datetime.now()
    dfFinal['yield_ultimo_negocio'] = '-'
    #dfFinal['yield_ultimo_negocio'] = '-' # Repetido
    dfFinal['spread'] = '-'
    #
    # Ajusta o valor do yield estimado com o diferencial de juros.
    #
    dfFinal["yield_estimado"] = dfFinal["yield_estimado"] + d_cdi - d_fed


    dfFinal = dfFinal[['data_hora_atualizacao','etf','indice','yield_estimado','yield_ultimo_negocio','spread','duration','valor_estimado_cota']]
    return dfFinal


# -----------------------------------------------------------------------------
# 20260616  CDIB11 (Teva Selic Target 800) e LFTI11 (Teva Tesouro Selic)
#           Nova função para ETFs atrelados à Selic (posição em LFT).
#           Estrutura análoga à gerar_preco_justo_etfRF, porém:
#           - Filtra rftp_cd = 'LFT' (a etfRF exclui LFTs explicitamente)
#           - PLexLFTs substitui PLexBs como proxy de caixa
#           - Duration via índice IMA-S
#           - BBG: px_last / last_yld com ticker {isin} @ITAM Corp
# -----------------------------------------------------------------------------
def gerar_preco_justo_etfSelic(controle):

    conn = Conn()

    d0 = date.today()
    d1 = str(QsDate(d0).add_business_days(-1))

    lista_fundos       = list(controle.keys())
    dict_ticker_etf    = {fundo: controle[fundo]['ticker']           for fundo in lista_fundos}
    dict_bench_etf     = {fundo: controle[fundo]['bench']            for fundo in lista_fundos}
    dict_indice_format = {fundo: controle[fundo]['indice_formatado'] for fundo in lista_fundos}

    string_fundos = ", ".join([f"'{fundo}'" for fundo in lista_fundos])

    # POSICAO LFT
    sql = f"""
    SELECT
        dt,
        clcli_cd,
        Trim(rftp_cd) AS tipo_ativo,
        dt_vencimento,
        isin,
        Sum(qt_total)   AS quantidade,
        sum(vl_liq_pos) AS valor_posicao
    FROM
        dbsx337.dbo.VCRAPRF
    WHERE 1=1
        and dt = '{d1}'
        and clcli_cd IN ({string_fundos})
        and rftp_cd = 'LFT'
    GROUP BY
        dt, clcli_cd, rftp_cd, dt_vencimento, isin
    ORDER BY
        dt, clcli_cd, dt_vencimento
    """
    df_pos = pd.read_sql(sql, conn)

    # COTA/PL
    sql = f"""
    SELECT
        dt,
        clcli_cd,
        QT_COTAS1 as qt_cotas
    FROM
        DBSX337.DBO.VCRAPLSI
    WHERE 1=1
        and clcli_cd IN ({string_fundos})
        and dt = '{d1}'
    """
    df_cota = pd.read_sql(sql, conn)

    # PL DESCONSIDERANDO LFTs (equivalente ao PLexBs para os ETFs de renda fixa)
    sql = f"""
    SELECT
        a.dt,
        a.clcli_cd,
        (vl_patrliqtot1 - vl_brutopos_lft) AS PLexLFTs
    FROM
        dbsx337.dbo.vcraplsi AS A
        JOIN (
            SELECT
                dt,
                clcli_cd,
                SUM(vl_brutopos) AS VL_BRUTOPOS_LFT
            FROM
                dbsx337.dbo.vcraprf
            WHERE 1=1
                and dt = '{d1}'
                AND rftp_cd = 'LFT'
                AND clcli_cd IN ({string_fundos})
            GROUP BY
                dt, clcli_cd
        ) AS B
        ON A.dt = B.dt AND A.clcli_cd = B.clcli_cd
    WHERE 1=1
        and a.dt = '{d1}'
        AND a.clcli_cd IN ({string_fundos})
    """
    df_plexlft = pd.read_sql(sql, conn)

    # DURATION IMA-S
    sql = f"""
    SELECT DISTINCT
        data_referencia,
        indice,
        duration
    FROM
        dbsx337..tbhh3031_anbima_indices_mais_ima_resultados_componentes WITH (NOLOCK)
    WHERE 1=1
        and data_referencia = '{d1}'
        and indice = 'IMA-S'
    """
    df_indexduration = pd.read_sql(sql, conn)

    # BBG - precos e taxas das LFTs (mesmo formato que NTN-B: isin + " @ITAM Corp")
    df_pos['TickerBBG'] = df_pos['isin'] + " @ITAM Corp"
    lista_tickers = df_pos['TickerBBG'].unique().tolist()

    bbg_preco = blp.bdp(tickers=lista_tickers, flds=["px_last"]).reset_index().rename(
        columns={'index': 'TickerBBG', 'px_last': 'preco_online'}
    )
    bbg_taxa = blp.bdp(tickers=lista_tickers, flds=["last_yld"]).reset_index().rename(
        columns={'index': 'TickerBBG', 'last_yld': 'taxa_online'}
    )

    df_pos = df_pos.merge(bbg_preco, how='left', on='TickerBBG')
    df_pos = df_pos.merge(bbg_taxa,  how='left', on='TickerBBG')
    df_pos.drop(columns=['TickerBBG'], inplace=True)

    # PL ONLINE
    df_pos['pl_lft'] = df_pos['quantidade'] * df_pos['preco_online']
    df_pl_online = df_pos.groupby('clcli_cd').agg({'pl_lft': 'sum'}).reset_index()
    df_pl_online.rename(columns={'pl_lft': 'pl_online'}, inplace=True)

    # TAXA PONDERADA
    df_pos['total']           = df_pos['preco_online'] * df_pos['quantidade']
    df_pos['composicao_perc'] = df_pos['total'] / df_pos.groupby('clcli_cd')['total'].transform('sum')
    df_pos['taxa_ponderada']  = df_pos['composicao_perc'] * df_pos['taxa_online']
    df_tx_ponderada = df_pos.groupby('clcli_cd').agg({'taxa_ponderada': 'sum'}).reset_index()
    df_tx_ponderada['taxa_ponderada'] = df_tx_ponderada['taxa_ponderada'] / 100

    # PRECOS DO ETF NA BBG
    df_etf_tickers = pd.DataFrame({'ticker_etf': list(dict_ticker_etf.values())}).drop_duplicates()
    df_etf_tickers['ticker_etf_bbg'] = df_etf_tickers['ticker_etf'] + " Equity"
    lista_etf = df_etf_tickers['ticker_etf_bbg'].unique().tolist()
    px_etf = blp.bdp(tickers=lista_etf, flds=["px_bid", "px_ask", "last_trade"]).reset_index().rename(
        columns={'index': 'ticker_etf_bbg', 'px_bid': 'compra', 'px_ask': 'venda', 'last_trade': 'ultimo_negocio'}
    )
    df_etf_tickers = df_etf_tickers.merge(px_etf, how='inner', on='ticker_etf_bbg')

    # CONSOLIDACAO
    df_consolidado = df_cota.merge(df_plexlft,     how='left', on=['dt', 'clcli_cd'])
    df_consolidado['ticker_etf']   = df_consolidado['clcli_cd'].map(dict_ticker_etf)
    df_consolidado['indice_fundo'] = df_consolidado['clcli_cd'].map(dict_bench_etf)
    df_consolidado = df_consolidado.merge(df_etf_tickers,  on='ticker_etf',  how='left')
    df_consolidado = df_consolidado.merge(df_pl_online,    on='clcli_cd',    how='left')
    df_consolidado = df_consolidado.merge(df_tx_ponderada, on='clcli_cd',    how='left')
    df_consolidado = df_consolidado.merge(
        df_indexduration, how='left',
        left_on=['dt', 'indice_fundo'], right_on=['data_referencia', 'indice']
    )
    df_consolidado['indice'] = df_consolidado['clcli_cd'].map(dict_indice_format)

    # CALCULOS FINAIS
    df_consolidado['caixa']            = df_consolidado['PLexLFTs']
    df_consolidado['valor_justo_cota'] = (df_consolidado['caixa'] + df_consolidado['pl_online']) / df_consolidado['qt_cotas']
    df_consolidado['yld_eq_compra']    = df_consolidado['taxa_ponderada'] - (((df_consolidado['compra']         - df_consolidado['valor_justo_cota']) / (df_consolidado['duration'] / 252)) / 100)
    df_consolidado['yld_eq_venda']     = df_consolidado['taxa_ponderada'] - (((df_consolidado['venda']          - df_consolidado['valor_justo_cota']) / (df_consolidado['duration'] / 252)) / 100)
    df_consolidado['yld_ult_negocio']  = df_consolidado['taxa_ponderada'] - (((df_consolidado['ultimo_negocio'] - df_consolidado['valor_justo_cota']) / (df_consolidado['duration'] / 252)) / 100)
    df_consolidado['spread']           = df_consolidado['yld_eq_compra'] - df_consolidado['yld_eq_venda']
    df_consolidado['duration']         = df_consolidado['duration'] / 252

    dfFinal = df_consolidado.copy()
    dfFinal['data_hora_atualizacao'] = datetime.now()
    dfFinal = dfFinal[['data_hora_atualizacao', 'ticker_etf', 'indice', 'taxa_ponderada', 'yld_ult_negocio', 'spread', 'duration', 'valor_justo_cota']]
    dfFinal.rename(columns={
        'ticker_etf'      : 'etf',
        'taxa_ponderada'  : 'yield_estimado',
        'yld_ult_negocio' : 'yield_ultimo_negocio',
        'valor_justo_cota': 'valor_estimado_cota'
    }, inplace=True)

    return dfFinal