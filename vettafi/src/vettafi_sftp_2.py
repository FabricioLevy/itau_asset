import os
import stat
from datetime import date

import paramiko

HOST = "tmxvettafi.files.com"
PORT = 22
USERNAME = "fabricio.levy@itau-unibanco.com.br"  # usuário SFTP da conta Files.com (Configurações > Usuários > Nome de usuário)
KEY_PATH = "../input/id_api_key.txt"
PASSPHRASE = ''  # senha da chave privada, se houver
OUTPUT_DIR = "../output"
DATA_HOJE = date.today().strftime("%Y%m%d")


def conectar() -> paramiko.SSHClient:
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # confia na chave do host no 1º acesso
    cliente.connect(HOST, port=PORT, username=USERNAME, pkey=key)
    return cliente


def arquivo_mais_recente(sftp: paramiko.SFTPClient, pasta: str, indice: str) -> str:
    # Só há arquivos em dias úteis: pega o mais recente até hoje (cobre fim de semana/feriado)
    sufixo = f"_{indice}_ADJ.VFC.csv"
    candidatos = [
        nome for nome in sftp.listdir(pasta)
        if nome.endswith(sufixo) and nome[:8] <= DATA_HOJE
    ]
    if not candidatos:
        raise FileNotFoundError(f"Nenhum arquivo *{sufixo} encontrado em {pasta}")
    return max(candidatos)  # nome começa com AAAAMMDD, então a ordem alfabética é cronológica


cliente = conectar()
sftp = cliente.open_sftp()

# Listar uma pasta (ponto = pasta raiz)
for item in sftp.listdir_attr("."):
    tipo = "dir" if stat.S_ISDIR(item.st_mode) else "file"
    print(tipo, item.filename)

# Baixar os arquivos diários dos índices para o disco local
INDICES = ["RAFSBDRP", "RAFSBRAP"]

os.makedirs(OUTPUT_DIR, exist_ok=True)
conteudos = {}
for indice in INDICES:
    pasta_remota = f"INDEX_DATA/{indice}/ADJ_CLOSE_CONSTITUENTS"
    nome_arquivo = arquivo_mais_recente(sftp, pasta_remota, indice)
    caminho_remoto = f"{pasta_remota}/{nome_arquivo}"
    print("baixando", caminho_remoto)

    sftp.get(caminho_remoto, os.path.join(OUTPUT_DIR, nome_arquivo))

    # Ler o conteúdo direto na memória
    with sftp.open(caminho_remoto, "r") as f:
        conteudos[indice] = f.read()

# Enviar um arquivo local (ajuste o caminho remoto conforme a pasta de destino)
# sftp.put("/caminho/local/relatorio.csv", "pasta/relatorio.csv")

sftp.close()
cliente.close()
