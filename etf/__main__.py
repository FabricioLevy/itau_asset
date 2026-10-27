import sys
import os
import pathlib
import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay
from datetime import date,datetime

folder = pathlib.Path().resolve().parent.name

if (folder == 'bases-fundos-iam'):
    sys.path.append("../")
    filePathRun = ''
else:
    filePath = os.environ.get('BASES_FUNDOS_IAM_FILE_PATH')
    sys.path.append(filePath)
    filePathRun = os.environ.get('BASES_FUNDOS_IAM_FILE_PATH') + '\\Views\\'

from Posicao.SSC_functions import getdf_lista_fundos
from Funcoes.LakeConn import Conn, db_insert_frame, delete_insert_with_transaction
from qs_utils.qsdate import QsDate
from CLog.log import log_iam, log_last_run, log_iam_flow_status
from Backup.Expurgo_tbl import check_expurgo
import argparse


def roda_vw_cotas_pl(*args, date_ref=None, lista_fundos=[], tipos = ['benchmark_global', 'meta_global'], id_iamflow=None, **kwargs):
    # Log IAM Flow
    if id_iamflow is not None:
        log_iam_flow_status(id=id_iamflow, dt_ref=date_ref, status_execucao='running')

    # Log
    dt_01 = datetime.now()

    if date_ref is None:
        dateQueryI = date.today() - BDay(12)

    else:
        dateQueryI = datetime.strptime(date_ref, '%Y-%m-%d').date() - BDay(12)

    if not lista_fundos:
        query_fundos1 = ""
        query_fundos2 = ""

    else:
        query_fundos1 = "AND codigo_IAM_fundo in " + "(" + ', '.join(f"'{fundo}'" for fundo in lista_fundos) + ")"
        query_fundos2 = "AND a.codigo_IAM_fundo in " + "(" + ', '.join(f"'{fundo}'" for fundo in lista_fundos) + ")"

    # Dates

    dateQueryF = date.today() - BDay(0) # Não alterar - é preciso rodar até d0 o script pois há contas cumulativas
    dateQueryDateCorte = dateQueryI + BDay(2)  # Data que efetivamente será atualizada no banco
    dateQueryAux1 = dateQueryI - BDay(4) # Não alterar - datas auxiliares para calcular o valor da meta
    dateQueryAux2 = dateQueryAux1 - BDay(10) # Não alterar - datas auxiliares para calcular o cota benchmark
    dateQueryAux3 = dateQueryAux2 - BDay(1) # Não alterar - datas auxiliares para calcular o valor do indice

    dateQueryAux1 = dateQueryAux1.strftime('%Y-%m-%d')
    dateQueryAux2 = dateQueryAux2.strftime('%Y-%m-%d')
    dateQueryAux3 = dateQueryAux3.strftime('%Y-%m-%d')
    dateQueryI = dateQueryI.strftime('%Y-%m-%d')
    dateQueryF = dateQueryF.strftime('%Y-%m-%d')

    # Ajuste para fundos mensais
    def GetCadastro(campo, tabela='FUNDOS_CADASTRO_ATIVOS', tipo='codigo_IAM_ativo', apelido=None, coluna='valor_str',
                    query_adicional=''):
        if apelido == None:
            apelido = campo
        conn = Conn()
        sql = f"""select {tipo}, {coluna} as {apelido} from {tabela} (nolock)
                            where campo = '{campo}' {query_adicional}
                            order by date_change"""
        df = pd.read_sql(sql, conn)
        df = df.groupby([tipo], as_index=False, sort=False).tail(1).reset_index(drop=True)
        return df

    alldates = pd.date_range(dateQueryAux2, dateQueryF, freq='b')

    dfFundos = getdf_lista_fundos(lista_fundos=lista_fundos)
    if len(dfFundos) > 0:
        dfFrequenciaNAV = GetCadastro('FrequenciaNAV', 'FUNDOS_CADASTRO_FUNDOS', 'codigo_iam_fundo', 'FrequenciaNAV',
                                      query_adicional=query_fundos1)
        dfCheck = pd.merge(dfFundos, dfFrequenciaNAV, how='left', on=['codigo_iam_fundo'])

        if len(dfCheck) > 0 and (dfCheck['FrequenciaNAV'] == 'Mensal').all():
            alldates = pd.date_range(dateQueryAux2, dateQueryF, freq='d')

    # Conn
    conn = Conn()
    table = 'VW_FUNDOS_COTAS_PL'

    try:
        sql = f"""
        select * from (
        select *,
        isnull(denominador_pl,LAG(patrimonio,1) OVER (PARTITION BY codigo_IAM_fundo, classe ORDER BY codigo_IAM_fundo, classe, date)) as last_patrimonio
        from (
        SELECT a.date, a.codigo_IAM_fundo, a.classe,
        tbCalculoCota.valor_str as calculo_cota, tbMesaGestao.valor_str as mesa_gestao,tbDataInicio.valor_date as data_inicio_fundo,
        a.qt_cotas, a.cota, a.cota_grossup,
        a.patrimonio,a.last_patrimonio as denominador_pl,b.valor_str as benchmark, --dividendo,
        CASE
         WHEN d.preco_limpo is not null THEN a.patrimonio * d.preco_limpo
         ELSE a.patrimonio
        END as patrimonio_brl,
        e.valor_str as meta,
        row_number() over(partition by a.date, a.codigo_IAM_fundo, a.classe order by (
        isnull(DATEDIFF(day, b.date_change, a.date),0) +
        isnull(DATEDIFF(day, c.date_change, a.date),0) +
        isnull(DATEDIFF(day, e.date_change, a.date),0) +
        isnull(DATEDIFF(day, tbCalculoCota.date_change, a.date),0) +
        isnull(DATEDIFF(day, tbMesaGestao.date_change, a.date),0) )) as rn
        FROM FUNDOS_COTAS_PL (nolock) as a
        LEFT JOIN FUNDOS_CADASTRO_FUNDOS (nolock) as b on a.codigo_IAM_fundo = b.codigo_IAM_fundo and b.campo = 'Benchmark' and a.date >= b.date_change
        LEFT JOIN FUNDOS_CADASTRO_FUNDOS (nolock) as e on a.codigo_IAM_fundo = e.codigo_IAM_fundo and e.campo = 'Meta' and a.date >= e.date_change
        LEFT JOIN FUNDOS_CADASTRO_FUNDOS (nolock) as c on a.codigo_IAM_fundo = c.codigo_IAM_fundo and c.campo = 'Moeda' and a.date >= c.date_change
        LEFT JOIN FUNDOS_CADASTRO_FUNDOS (nolock) as tbCalculoCota on a.codigo_IAM_fundo = tbCalculoCota.codigo_IAM_fundo and tbCalculoCota.campo = 'CalculoCota'
        LEFT JOIN FUNDOS_CADASTRO_FUNDOS (nolock) as tbMesaGestao on a.codigo_IAM_fundo = tbMesaGestao.codigo_IAM_fundo and tbMesaGestao.campo = 'MesaGestao'
        LEFT JOIN FUNDOS_CADASTRO_FUNDOS (nolock) as tbDataInicio on a.codigo_IAM_fundo = tbDataInicio.codigo_IAM_fundo and tbDataInicio.campo = 'datainicio'
        -- cotacao do dia ou, se faltar (feriado no Brasil, falha de carga), a ultima dos 7 dias anteriores
        OUTER APPLY (
            SELECT TOP 1 m.preco_limpo FROM FUNDOS_DADOS_MOEDAS (nolock) as m
            WHERE m.codigo_IAM_moeda_quote = c.valor_str and m.codigo_IAM_moeda_base = 'BRL_B3_2'
            and m.date <= a.date and m.date >= DATEADD(day, -7, a.date) and m.preco_limpo is not null
            ORDER BY m.date DESC
        ) as d

        where a.date >= '{dateQueryAux2}' and a.date <= '{dateQueryF}' {query_fundos2}

        )as cota_pl
        where rn=1) as b where date>='{dateQueryI}' and date<='{dateQueryF}'

        """
        df = pd.read_sql(sql, conn)
        df.drop(columns=['denominador_pl'],inplace=True)

        # Adicionando dividendos vindos da tabela de dividendos
        sql = f"""
            select distinct date as dt,data_ex as date, codigo_IAM_fundo, dividendo
            from FUNDOS_DIVIDENDOS_FUNDOS
            where data_ex >= '{dateQueryAux2}' and data_ex <= '{dateQueryF}' {query_fundos1}
        """
        df_dividendos = pd.read_sql(sql, conn)

        df_dividendos.sort_values(by=['dt'], inplace=True)
        df_dividendos.drop_duplicates(subset=['date', 'codigo_IAM_fundo'], keep='first', inplace=True)

        # Adicionando eventos para fundos, envento impactará a cota com dividendo
        sql = f"""
            select date_change as date, codigo_IAM_fundo, valor_num as razao_evento , campo
            from FUNDOS_CADASTRO_FUNDOS
            where campo in ('evento_grupamento','evento_desdobramento')
            and date_change >= '{dateQueryAux2}' and date_change <= '{dateQueryF}' {query_fundos1}
        """
        df_evento_agrup = pd.read_sql(sql, conn)
        mask = df_evento_agrup['campo']=='evento_desdobramento'
        if len(df_evento_agrup.loc[mask, 'razao_evento']) > 0:
            df_evento_agrup.loc[mask, 'razao_evento'] = 1 / df_evento_agrup.loc[mask, 'razao_evento']
        df_evento_agrup.drop(['campo'], axis=1, inplace=True)

        df = pd.merge(df, df_dividendos, how='left', on=['date', 'codigo_IAM_fundo'])
        df.dividendo.fillna(0, inplace=True)

        df = pd.merge(df, df_evento_agrup, how='left', on=['date', 'codigo_IAM_fundo'])
        df['razao_evento'].fillna(1, inplace=True)

        # ajustando last_date_cota pela lista de feriados do fundo
        sql = f""" select date_change as date,codigo_IAM_fundo, valor_str as COUNTRY from FUNDOS_CADASTRO_FUNDOS where  campo = 'CalendarioFeriados'"""
        dfFundHoliday = pd.read_sql(sql, conn)
        #pegar apenas o último registro para cada fundo
        dfFundHoliday.sort_values(by=['codigo_IAM_fundo', 'date'], inplace=True)
        dfFundHoliday = dfFundHoliday.groupby('codigo_IAM_fundo', as_index=False).tail(1)
        dfFundHoliday = dfFundHoliday[['codigo_IAM_fundo', 'COUNTRY']]
        df = pd.merge(df, dfFundHoliday, how='left', on=['codigo_IAM_fundo'])

        df["COUNTRY"].fillna(value='BR', inplace=True)
        df["COUNTRY"] = df["COUNTRY"].apply(lambda x: x.split(","))
        df["last_date_cota"] = df.apply(lambda x: QsDate((x["date"]), calendar=x['COUNTRY']).add_business_days(-1)._date_np,axis=1)

        try:
            if len(dfCheck) > 0 and (dfCheck['FrequenciaNAV'] == 'Mensal').all():
                df["last_date_cota"] = df['date'].apply(lambda date: (date.replace(day=1) - pd.Timedelta(days=1)))
        except:
            pass

        df["last_date_cota"] = pd.to_datetime(df["last_date_cota"]).dt.date
        df['last_date_cota'] = pd.to_datetime(df['last_date_cota'], format='%Y-%m-%d %H:%M')
        df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d %H:%M')
        df = df.drop(['rn','COUNTRY'], axis=1)

        # Verificando se eh o primeiro dia do fundo, se sim, replicaremos o last_patrimonio

        #mask_primeiro_dia = df["date"] == df["data_inicio_fundo"]
        #df.loc[mask_primeiro_dia, "last_patrimonio"] = df["last_patrimonio"].fillna(df["patrimonio"])
        #df = df.drop(['data_inicio_fundo'], axis=1)

        #### CALCULAR COTA BENCHMARK
        df1 = df[['codigo_IAM_fundo','classe']]
        df1 = df1.drop_duplicates()

        # Create df with last possible days
        df_auxiliar = pd.DataFrame(columns=['date', 'codigo_IAM_fundo', 'classe'])
        for index, row in df1.iterrows():
            dfTemp = pd.DataFrame(columns=['date'], data={'date': alldates})
            dfTemp['codigo_IAM_fundo'] = row['codigo_IAM_fundo']
            dfTemp['classe'] = row['classe']
            df_auxiliar = pd.concat([df_auxiliar, dfTemp])

        dfBench = df_auxiliar.copy()
        dfBench['last_date'] = dfBench.apply(lambda row: row['date'] - BDay(1), axis=1)

        # Get Benchs Compositition
        sql = f""" select date as last_date, codigo_IAM_fundo, tipo, codigo_IAM_indice,
        perc, perc_original, multiplicador_indice, soma_indice, meta_tipo from FUNDOS_BENCHMARKS
        WHERE date >= '{dateQueryAux3}' and date <= '{dateQueryF}' {query_fundos1} """
        dfBenchComposition = pd.read_sql(sql, conn)
        dfBenchComposition['last_date'] = pd.to_datetime(dfBenchComposition['last_date'], format='%Y-%m-%d %H:%M')

        # Em caso de troca de benchmark ou meta, substituiremos o valor do benchmark do dia
        # anterior ao valor  do dia da mudança, no dfBenchComposition
        sql = f""" select date_change, codigo_IAM_fundo, campo, valor_str from FUNDOS_CADASTRO_FUNDOS (nolock)
        WHERE campo in ('benchmark','meta') {query_fundos1} """

        dfCadastroBench = pd.read_sql(sql, conn)
        dfCadastroBench['campo'] = dfCadastroBench['campo'].str.lower()
        dfCadastroBench['campo'] = dfCadastroBench['campo'].replace(['benchmark'],'benchmark_global')
        dfCadastroBench['campo'] = dfCadastroBench['campo'].replace(['meta'],'meta_global')

        dfCadastroBench['date_change'] = dfCadastroBench['date_change'].astype('datetime64[ns]')

        # Trabalhando com merge para fazer a substituicao para todos os fundos da lista
        dfBenchComposition = pd.merge(dfBenchComposition, dfCadastroBench, how='left',
                                      left_on=['last_date', 'codigo_IAM_fundo', 'tipo'],
                                      right_on=['date_change', 'codigo_IAM_fundo','campo'])
        df_aux = dfBenchComposition[(dfBenchComposition['valor_str'].notna())]
        df_aux.drop(columns = ['date_change','campo','valor_str'], axis = 1, inplace = True)
        df_aux.loc[:, 'last_date'] = df_aux['last_date'] - BDay(1)

        dfBenchComposition.drop(columns = ['date_change','campo','valor_str'], axis = 1, inplace = True)
        dfBenchComposition = pd.merge(dfBenchComposition, df_aux, how='left', suffixes = ('','_aux'),
                                      left_on=['last_date', 'codigo_IAM_fundo', 'tipo'],
                                      right_on=['last_date', 'codigo_IAM_fundo','tipo'])

        dfBenchComposition = dfBenchComposition[dfBenchComposition['codigo_IAM_indice_aux'].isna()]
        dfBenchComposition.drop(dfBenchComposition.filter(regex='_aux').columns, axis=1, inplace=True)

        dfBenchComposition = pd.concat([df_aux, dfBenchComposition], sort=False).sort_index()
        dfBenchComposition.sort_values(by=['last_date','codigo_IAM_fundo','tipo','codigo_IAM_indice'],ignore_index=True, inplace=True)

        dfBench = pd.merge(dfBench, dfBenchComposition, how='outer', left_on=['last_date', 'codigo_IAM_fundo'],
                           right_on=['last_date', 'codigo_IAM_fundo']) # outer join para forcar pegar necessariamente o bench

        # Filtrando para ter somente data inicial maior igual data de inicio do fundo
        fundos = list(dfBench['codigo_IAM_fundo'].unique())
        fundos = [f"'{x}'" for x in fundos]
        fundos = ','.join(map(str, fundos))
        query_data_inicio_fundo = f"""
        SELECT codigo_IAM_fundo, data_inicio FROM (
            SELECT codigo_IAM_fundo, valor_date as data_inicio, ROW_NUMBER () over (partition by codigo_IAM_fundo order by date_change desc) as rn
            FROM FUNDOS_CADASTRO_FUNDOS (nolock) where codigo_IAM_fundo in ({fundos}) and campo = 'DataInicio'
            ) as a where rn = 1"""
        df_data_inicio = pd.read_sql(query_data_inicio_fundo, Conn("DBSX337"))
        df_data_inicio["data_inicio"] = pd.to_datetime(df_data_inicio["data_inicio"])

        dfBench = dfBench.merge(df_data_inicio, left_on=["codigo_IAM_fundo"], right_on=["codigo_IAM_fundo"], how="left")

        # Ajustando tipo e benchmark quando fundo nao tiver dados para tras. Pegamos o bench do ultimo dia mais atual disponivel. Por meio do outer join
        dfBench["tipo"] = dfBench.groupby(['codigo_IAM_fundo'], sort=False)['tipo'].transform(lambda x: x.ffill().bfill())
        dfBench["codigo_IAM_indice"] = dfBench.groupby(['codigo_IAM_fundo'], sort=False)['codigo_IAM_indice'].transform(lambda x: x.ffill().bfill())
        dfBench["perc"] = dfBench.groupby(['codigo_IAM_fundo'], sort=False)['perc'].transform(lambda x: x.ffill().bfill())
        dfBench["perc_original"] = dfBench.groupby(['codigo_IAM_fundo'], sort=False)['perc_original'].transform(lambda x: x.ffill().bfill())
        dfBench["multiplicador_indice"] = dfBench.groupby(['codigo_IAM_fundo'], sort=False)['multiplicador_indice'].transform(lambda x: x.ffill().bfill())
        dfBench["data_inicio"].fillna(pd.to_datetime("1900-01-01"), inplace = True)
        dfBench = dfBench[dfBench["date"]>=dfBench["data_inicio"]] # filtrando para pegar somente datas acima da data de inicio do fundo
        # Usando perc_original ao invés do perc quando há troca de mês ou de benchmark
        dfBench.loc[dfBench['date'].dt.month!=dfBench['last_date'].dt.month,'perc'] = dfBench['perc_original']
        dfBench = pd.merge(dfBench, df_aux, how='left', suffixes = ('','_aux'),
                                      left_on=['last_date', 'codigo_IAM_fundo', 'tipo','codigo_IAM_indice'],
                                      right_on=['last_date', 'codigo_IAM_fundo','tipo','codigo_IAM_indice'])
        dfBench.loc[dfBench['perc_original_aux'].notna(),'perc'] = dfBench['perc_original']
        dfBench.drop(dfBench.filter(regex='_aux').columns, axis=1, inplace=True)

        dfBench.drop(['perc_original'], axis=1, inplace=True)

        # Get data from indices. Add column is_string to verify in checknumber.
        sql = f"""
        SELECT date, codigo_IAM_indice, pnl_perc
        FROM FUNDOS_DADOS_INDICES (nolock)
        where date >= '{dateQueryAux2}' and date <= '{dateQueryF}'
        """
        dfIndices = pd.read_sql(sql, conn)

        dfIndices['date'] = pd.to_datetime(dfIndices['date'], format='%Y-%m-%d %H:%M')
        dfTemp = dfIndices[dfIndices['codigo_IAM_indice'] == 'CDI'].copy()
        dfTemp.loc[:,'codigo_IAM_indice'] = 'CDI_E'
        dfIndices = pd.concat([dfIndices,dfTemp])
        dfTemp = dfIndices[dfIndices['codigo_IAM_indice'] == 'CDI'].copy()
        dfTemp.loc[:,'codigo_IAM_indice'] = 'CDI_A'
        dfIndices = pd.concat([dfIndices,dfTemp])
        dfTemp = dfIndices[dfIndices['codigo_IAM_indice'] == 'IBOV'].copy()
        dfTemp.loc[:,'codigo_IAM_indice'] = 'IBOV_E'
        dfIndices = pd.concat([dfIndices,dfTemp])
        dfTemp = dfIndices[dfIndices['codigo_IAM_indice'] == 'IMA_S'].copy()
        dfTemp.loc[:,'codigo_IAM_indice'] = 'IMA_S_E'
        dfIndices = pd.concat([dfIndices,dfTemp])

        dfIndicesIsString = dfIndices[['codigo_IAM_indice']].drop_duplicates()
        dfIndicesIsString['is_string'] = 1

        # Calculate benchs
        try:
            dfBench = pd.merge(dfBench, dfIndices, how='left', left_on=['date', 'codigo_IAM_indice'],
                               right_on=['date', 'codigo_IAM_indice'])
            dfBench = pd.merge(dfBench, dfIndicesIsString, how='left', left_on=['codigo_IAM_indice'], right_on=['codigo_IAM_indice'])
        except:
            # Dando fillna no codigo_IAM_indice para merge funcionar em casos em que o fundo nao possui indice de bench
            dfBench["codigo_IAM_indice"].fillna("NA", inplace = True)
            dfBench = pd.merge(dfBench, dfIndices, how='left', left_on=['date', 'codigo_IAM_indice'],
                               right_on=['date', 'codigo_IAM_indice'])
            dfBench['is_string'] = np.NaN

        # Funcao usada para preencher pnl_perc de benchmarks que sejam taxas pré-fixadas ao ano
        def CheckNumber(x, pnl_perc, dt, is_string, tipo='benchmark_global'):
            valor = 252
            if tipo == 'meta_global':
                valor = QsDate(f"{dt.year}-01-01").business_days_diff(f"{int(dt.year)+1}-01-01")
            try:
                if not (is_string == 1):
                    pnl_perc = (1 + float(x)) ** (1 / valor) - 1
                return pnl_perc
            except:
                return pnl_perc

        # Se data inicio = 1, rentabilidade bench no dia sera em 0, entao cota_benchmark = 1
        mask_data_inicio = (dfBench["data_inicio"] == dfBench["date"])
        dfBench.loc[mask_data_inicio , 'pnl_perc'] = 0
        dfBench['pnl_perc'] = dfBench.apply(lambda row: CheckNumber(row['codigo_IAM_indice'], row['pnl_perc'], row['date'], row['is_string'], row['tipo']), axis=1)
        dfBench['soma_indice'].fillna(0, inplace=True)
        dfBench['soma_indice'] = dfBench.apply(lambda row: CheckNumber(row['soma_indice'], row['soma_indice'], row['date'], False, row['tipo']), axis=1)

        mask_feriado_indice = (pd.isna(dfBench['pnl_perc']))
        dfBench.loc[mask_feriado_indice , 'soma_indice'] = 0

        dfBench['pnl_perc'].fillna(0, inplace=True)
        dfBench.drop(columns=['is_string'], inplace = True)

        dfBench['pnl_perc'] = dfBench['pnl_perc'] * dfBench['multiplicador_indice']
        dfBench['pnl_perc'] = dfBench['pnl_perc'] + dfBench['soma_indice']
        dfBench = dfBench.drop(['multiplicador_indice','soma_indice'], axis = 1)
        dfBench.loc[dfBench['meta_tipo']=='multiplicacao','pnl_perc'] = 0
        dfBench['result_bench'] = dfBench['perc'] * dfBench['pnl_perc']
        lista_colunas = list(dfBench.columns)
        dfBench = dfBench.groupby(by=['date', 'codigo_IAM_fundo','tipo','classe'], as_index=False, sort=False).sum(numeric_only=True)

        if len(dfBench) == 0:
            dfBench = pd.DataFrame(columns=lista_colunas)

        try:
            dfBench = dfBench.drop(['perc', 'pnl_perc'], axis=1)
        except:
            pass

        dfBench = dfBench.rename(columns={'result_bench': 'pnl_perc'})

        # Get last data from VW Cotas PL
        sql = f"""
        select *
        FROM
        VW_FUNDOS_COTAS_PL where date >= '{dateQueryAux2}' and date<'{dateQueryI}' {query_fundos1}
        """

        df1 = pd.read_sql(sql, conn)
        df1 = df1.drop(['last_cota_com_dividendo'], axis=1)
        df1['date'] = pd.to_datetime(df1['date'], format='%Y-%m-%d %H:%M')

        df = pd.concat([df1,df])

        df = pd.merge(df_auxiliar, df, how='left', left_on=['date', 'codigo_IAM_fundo', 'classe'],
                      right_on=['date', 'codigo_IAM_fundo', 'classe'])

        for tipo in tipos:
            dfBenchTemp = dfBench[dfBench['tipo']==tipo]
            dfBenchTemp = dfBenchTemp.drop(['tipo'], axis=1)

            df = pd.merge(df, dfBenchTemp, how='left', on=['date', 'codigo_IAM_fundo','classe'])
            # Change columns and calculation
            df['pnl_perc'] = df['pnl_perc'].fillna(0)

            if tipo == 'meta_global':
                dfMeta = dfBenchComposition[dfBenchComposition['tipo']=='meta_global']
                dfMeta = dfMeta[['last_date','codigo_IAM_fundo','multiplicador_indice','meta_tipo']].groupby(by=['last_date','codigo_IAM_fundo'], as_index=False).head(1)
                dfMeta.rename({'last_date':'date','multiplicador_indice':'meta_multiplicador'}, axis=1, inplace=True)
                df.drop(['meta_tipo','meta_multiplicador'], axis=1, inplace=True)
                df = pd.merge(df, dfMeta, how='left', on=['date','codigo_IAM_fundo'])

            if tipo == 'meta_global':
                df.loc[(df['qt_cotas'].isnull()) & (df['meta_tipo'] == 'soma'),'pnl_perc'] = 0

            tipoCota = ''
            if tipo == 'benchmark_global':
                df['benchmark_pnl_perc'] = df['pnl_perc']
                tipoCota = 'cota_benchmark'
            if tipo == 'meta_global':
                tipoCota = 'cota_meta'

            df['pnl_perc'] = 1 + df['pnl_perc']

            # Get funds ultima cota bench/meta
            sql = f"""
            select date, codigo_IAM_fundo, classe, {tipoCota} as pnl_perc
            FROM VW_FUNDOS_COTAS_PL (nolock)
            where date >= '{dateQueryAux2}'
            and date < '{dateQueryAux1}'{query_fundos1}
            order by date, codigo_IAM_fundo, classe
            """
            dfCotaBench = pd.read_sql(sql, conn)
            # Descarta cotas zeradas/nulas do historico (indicam que ainda nao foram calculadas)
            dfCotaBench = dfCotaBench[dfCotaBench['pnl_perc'].fillna(0) != 0]
            dfCotaBench = dfCotaBench.groupby(['codigo_IAM_fundo','classe'], as_index=False, sort=False).tail(1).reset_index(drop=True)
            dfLastCotaBench = dfCotaBench.copy()
            dfCotaBench.drop('date', axis=1, inplace=True)

            try:
                # Lidando com colunas com mesmo nome
                df["classe_x"] = df["classe_x"].iloc[:, 1]
                df = df.loc[:, ~df.columns.duplicated()].copy()
            except:
                pass

            # Filtrando apenas dias depois da ultima cota bench/meta (caso nao haja dados na VW_FUNDOS_COTAS_PL, nao filtra nada)
            df = pd.merge(df, dfLastCotaBench, how = 'left', on = ['codigo_IAM_fundo', 'classe'], suffixes = ('','_y'), indicator = True)
            mask_depois_ultima_cotabench = (df['date'] > df['date_y']) | (df['_merge'] == 'left_only')
            df = df.loc[mask_depois_ultima_cotabench, :]
            df.drop(columns = ['date_y', 'pnl_perc_y', '_merge'], inplace = True)

            df = pd.concat([dfCotaBench,df], axis = 0 )
            df.reset_index(drop=True, inplace=True)

            # Calculate new cota_benchmark/meta
            try:
                df["classe"] = df["classe_x"]
            except:
                pass

            df['pnl_perc'] = df['pnl_perc'].fillna(0)
            df['pnl_perc'] = df.groupby(by=['codigo_IAM_fundo', 'classe'], as_index=False, sort=False)['pnl_perc'].cumprod()
            df.drop([tipoCota], axis=1, inplace=True)
            df.rename({'pnl_perc':tipoCota}, axis=1, inplace=True)

        df = df.dropna(subset=['qt_cotas'])
        df['razao_evento'].fillna(1, inplace=True)
        # Calculate cota com dividendo
        dfDiff = df.groupby(['codigo_IAM_fundo', 'classe'], sort=False)['cota'].shift(1).rename('diff')
        df = pd.concat([df, dfDiff], axis=1)
        df['diff'] = df['cota']/df['razao_evento'] - df['diff']
        df['diff'] = df['diff'] + df['dividendo']

        dfLastCota = df.groupby(['codigo_IAM_fundo', 'classe'], sort=False)['cota'].shift().rename('last_cota_com_dividendo')
        df = pd.concat([df, dfLastCota], axis=1)

        df['rent'] = df['diff'] / df['last_cota_com_dividendo']
        df['rent'] = 1 + df['rent']

        dfTemp = df.groupby(['codigo_IAM_fundo', 'classe'], as_index=False, sort=False).head(1)
        df.loc[list(dfTemp.index), 'rent'] = df.loc[list(dfTemp.index), 'cota_com_dividendo']

        df['rent'] = df['rent'].replace(np.inf, np.nan)
        df['rent'].fillna(1, inplace=True)

        dfTemp = df.groupby(by=['codigo_IAM_fundo', 'classe'], sort=False, dropna=False)['rent'].cumprod().to_frame()
        dfTemp = dfTemp.rename(columns={'rent': 'cota_com_dividendo'})

        df = df.drop(['cota_com_dividendo', 'diff', 'rent'], axis=1)
        df = pd.concat([df, dfTemp], axis=1)
        df['cota_com_dividendo'].fillna(1, inplace=True)
        df.drop(['last_cota_com_dividendo'], axis=1, inplace=True)

        # Calculate funds gain/loss
        dfReturn = df.groupby(['codigo_IAM_fundo', 'classe'], sort=False)['cota_com_dividendo'].pct_change().rename('fundo_pnl_perc_novo')
        df = pd.concat([df, dfReturn], axis=1)
        df['fundo_pnl_novo'] = df['fundo_pnl_perc_novo'] * df['last_patrimonio']
        df['fundo_pnl_perc'] = df['fundo_pnl_perc_novo']
        df['fundo_pnl'] = df['fundo_pnl_novo']

        dfReturn = df.groupby(['codigo_IAM_fundo', 'classe'], sort=False)['cota_benchmark'].pct_change().rename('benchmark_pnl_perc_novo')
        df = pd.concat([df, dfReturn], axis=1)
        df['benchmark_pnl_novo'] = df['benchmark_pnl_perc_novo'] * df['last_patrimonio']
        df['benchmark_pnl_perc'] = df['benchmark_pnl_perc_novo']
        df['benchmark_pnl'] = df['benchmark_pnl_novo']

        df.drop(['fundo_pnl_perc_novo', 'fundo_pnl_novo','benchmark_pnl_perc_novo', 'benchmark_pnl_novo','last_cota_benchmark'], axis=1, inplace=True)

        # tratando valores nulos
        df["cota_meta"].fillna(1, inplace = True)
        df["cota_benchmark"].fillna(1, inplace=True)

        #calculando last cota benchmark
        dfLastCotaBenchmark = df.groupby(['codigo_IAM_fundo', 'classe'], sort=False)['cota_benchmark'].shift().rename('last_cota_benchmark')
        df = pd.concat([df, dfLastCotaBenchmark], axis=1)

        #calculando last cota com dividendo
        dfLastCotaDividendo = df.groupby(['codigo_IAM_fundo', 'classe'], sort=False)['cota_com_dividendo'].shift().rename('last_cota_com_dividendo')
        df = pd.concat([df, dfLastCotaDividendo], axis=1)

        # Retirar valores infinitos
        df.replace([np.inf, -np.inf], 0, inplace = True)

        if lista_fundos:
            df = df[df['codigo_IAM_fundo'].isin(lista_fundos)]

        try:
            df.drop(['classe_x', 'meta_tipo_x', 'classe_y', 'last_date_x', 'codigo_IAM_indice_x','meta_tipo_y','last_date_y', 'codigo_IAM_indice_y', "data_inicio_x", "data_inicio_y"], axis=1, inplace=True)
        except:
            pass

        #filtrar data
        df = df[df["date"] <= dateQueryF]
        df = df[df['date'] >= dateQueryDateCorte]

        df = df.drop_duplicates(subset=['date', 'codigo_IAM_fundo', 'classe'])

        #Retirando fundos de fechamento para data de D0 e deixando somente os fundos de abertura em d0
        # mask_abertura = ((df["date"] == dateQueryF) & (df["calculo_cota"] == 'FECHAMENTO'))
        # df= df.loc[~mask_abertura]

        # Incluindo datetime processamento e racf de quem rodou
        df = log_last_run(df)

        # Adicionando coluna de tipo_dado
        df['tipo_dado'] = 'oficial'
        df.replace([np.inf, -np.inf], np.nan, inplace=True)

        # Deixando na mesma ordem que a vw_fundos_cotas_pl para facilitar comparacao
        df = df[['date','codigo_IAM_fundo','classe','qt_cotas','cota','patrimonio','benchmark','cota_benchmark','last_patrimonio','patrimonio_brl','dividendo','cota_com_dividendo','benchmark_pnl_perc','fundo_pnl_perc','fundo_pnl','benchmark_pnl','last_cota_com_dividendo','last_date_cota','mesa_gestao','calculo_cota','last_cota_benchmark','meta','cota_meta','meta_tipo','meta_multiplicador','tipo_dado','log_last_processamento','log_last_user','cota_grossup']].copy()
        if len(df) > 0:
            # deletando até d0 para abertura e até d-1 para fechamento
            sql = f"delete from {table} where ((date>= '{dateQueryDateCorte}' and date <= '{dateQueryF}' and calculo_cota='ABERTURA') or (date>= '{dateQueryDateCorte}' and date <= '{dateQueryF}' and (calculo_cota='FECHAMENTO' or calculo_cota is null))) {query_fundos1}"

            # conn.execute(sql)
            # conn.commit()

            # # Insert on database
            # db_insert_frame(table, df)

            #Alteração para evitar erro de PK na base #taincam
            delete_insert_with_transaction(sql, table, df)

            # Update cota benchmark na fundos posicao explodida down - se o range de datas contemplar o expurgo, realizar o update nas 2 tabelas
            tbl =  check_expurgo('FUNDOS_POSICAO_EXPLODIDA_DOWN',dateQueryDateCorte)
            if tbl=='FUNDOS_POSICAO_EXPLODIDA_DOWN_expurgo':
                sql = f"""
                UPDATE a
                SET a.cota_benchmark = b.cota_benchmark, a.last_cota_benchmark=b.last_cota_benchmark
                from {tbl} (nolock) as a
                LEFT JOIN VW_FUNDOS_COTAS_PL (nolock) as b
                on b.classe in ('A','Total') and a.date = b.date and a.codigo_IAM_fundo = b.codigo_IAM_fundo
                where a.date >= '{dateQueryDateCorte}' and a.date <= '{dateQueryF}' {query_fundos2} and b.cota_benchmark is not null
                """
                conn.execute(sql)
                conn.commit()

            sql = f"""
            UPDATE a
            SET a.cota_benchmark = b.cota_benchmark, a.last_cota_benchmark=b.last_cota_benchmark
            from FUNDOS_POSICAO_EXPLODIDA_DOWN (nolock) as a
            LEFT JOIN VW_FUNDOS_COTAS_PL (nolock) as b
            on b.classe in ('A','Total') and a.date = b.date and a.codigo_IAM_fundo = b.codigo_IAM_fundo
            where a.date >= '{dateQueryDateCorte}' and a.date <= '{dateQueryF}' {query_fundos2} and b.cota_benchmark is not null
            """

            conn.execute(sql)
            conn.commit()

        else:
            print('não há dados para inserir')
            pass

        # Log

        # Log IAM Flow
        if id_iamflow is not None:
            log_iam_flow_status(id=id_iamflow, dt_ref=date_ref, status_execucao='ok', status_final='ok', status_qualidade='ok')

        log_iam(data_ref_inicio=dateQueryDateCorte.strftime('%Y-%m-%d'), data_ref_final=dateQueryF, tabela=table,
                data_hora_inicio=dt_01,
                rows_inserted=len(df), script=os.path.basename(__file__),
                observacao=f'Fundos = {lista_fundos} , Data Ref = {date_ref}', id_iamflow=id_iamflow, data_ref=date_ref)

    except Exception as msg:
        import traceback
        print("ERRO em VW_FUNDOS_COTAS_PL_Update.py:")
        traceback.print_exc()

        # Log IAM Flow
        if id_iamflow is not None:
            log_iam_flow_status(id=id_iamflow, dt_ref=date_ref, status_execucao='erro', status_final='erro')

        log_iam(data_ref_inicio=dateQueryDateCorte.strftime('%Y-%m-%d'), data_ref_final=dateQueryF, tabela=table,
                data_hora_inicio=dt_01,
                script=os.path.basename(__file__), observacao=f'Fundos = {lista_fundos} , Data Ref = {date_ref}', id_iamflow=id_iamflow, data_ref=date_ref)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--date_ref", help="Date referência")
    parser.add_argument("-i", "--id_iamflow", help="Id do script no IAM Flow para controle de log")
    parser.add_argument("-l", "--lista_fundos", help="Lista de fundos em formato string, sem o []")
    args = parser.parse_args()

    lista_fundos = []
    if args.lista_fundos is not None:
        lista_fundos = args.lista_fundos.split(',')

    roda_vw_cotas_pl(date_ref=args.date_ref, id_iamflow=args.id_iamflow, lista_fundos=lista_fundos)
