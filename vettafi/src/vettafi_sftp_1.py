"""
Baixa os arquivos diarios dos indices VettaFi (Files.com) de dentro da rede Itau.

Restricoes da rede Itau e como o script lida com elas:
- sem saida direta para a internet: todo trafego passa pelo proxy corporativo
  (proxynew.itau:8080), autenticado com RACF/senha de rede;
- porta 22 bloqueada: o SFTP e tunelado pelo proxy (HTTP CONNECT). Se o proxy
  recusar o tunel, cai para a API REST da Files.com via HTTPS (porta 443);
- TLS interceptado com a CA propria do Itau: verificacao SSL desligada no HTTPS.

Variaveis de ambiente (depois de usar setx, reabra o VS Code):
  SQL_LOGIN, SENHA_WINDOWS     RACF e senha de rede (autenticacao no proxy)
  VETTAFI_USER, VETTAFI_SENHA  login da Files.com (a senha so e usada pela
                               API REST, quando nao ha API key em input/)
  VETTAFI_PROXY                opcional, substitui o proxy padrao
                               (ex.: http://127.0.0.1:3128 do px, para NTLM)
"""
import base64
import os
import socket
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import requests
import urllib3

try:
    import paramiko
except ImportError:  # sem paramiko, so resta a API REST
    paramiko = None


# ---- Raiz do projeto (independe do diretorio de execucao) ----
# __file__   = .../itau_asset/vettafi/src/vettafi_sftp_1.py
# parents[1] = .../itau_asset/vettafi   <- BASE_DIR
BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
CAMINHO_API_KEY = INPUT_DIR / "files_api_key.txt"
CAMINHO_CHAVE_SSH = INPUT_DIR / "id_api_key.txt"


# ---- Proxy corporativo Itau ----
PROXY_PADRAO = "proxynew.itau:8080"
TIMEOUT = 60


# ---- Files.com / VettaFi ----
HOST_FILES = "tmxvettafi.files.com"
PORTA_SFTP = 22
BASE_URL = "https://{}/api/rest/v1".format(HOST_FILES)
INDICES = ["RAFSBDRP", "RAFSBRAP"]
DATA_HOJE = date.today().strftime("%Y%m%d")

VETTAFI_USER = os.environ.get("VETTAFI_USER", "fabricio.levy@itau-unibanco.com.br")
VETTAFI_SENHA = os.environ.get("VETTAFI_SENHA")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



def url_proxy():
    """URL do proxy com RACF/senha codificados (senha com @, :, & etc. quebra a URL)."""
    if os.environ.get("VETTAFI_PROXY"):
        return os.environ["VETTAFI_PROXY"]

    racf = os.environ.get("SQL_LOGIN")
    senha = os.environ.get("SENHA_WINDOWS")
    if not racf or not senha:
        raise RuntimeError(
            "Defina SQL_LOGIN (RACF) e SENHA_WINDOWS (senha de rede) para "
            "autenticar no proxy do Itau e reabra o VS Code."
        )
    return "http://{}:{}@{}".format(
        quote(racf, safe=""), quote(senha, safe=""), PROXY_PADRAO)



def arquivos_do_dia():
    """{caminho remoto: destino local} do arquivo de hoje de cada indice."""
    arquivos = {}
    for indice in INDICES:
        nome = "{}_{}_ADJ.VFC.csv".format(DATA_HOJE, indice)
        remoto = "INDEX_DATA/{}/ADJ_CLOSE_CONSTITUENTS/{}".format(indice, nome)
        arquivos[remoto] = OUTPUT_DIR / nome
    return arquivos



# ---- Opcao 1: SFTP com a chave SSH, tunelado pelo proxy ----

def tunel_proxy(host, porta):
    """Socket TCP ate host:porta passando pelo proxy (HTTP CONNECT)."""
    proxy = urlsplit(url_proxy())
    sock = socket.create_connection(
        (proxy.hostname, proxy.port or 8080), timeout=TIMEOUT)

    pedido = "CONNECT {0}:{1} HTTP/1.1\r\nHost: {0}:{1}\r\n".format(host, porta)
    if proxy.username:
        credencial = "{}:{}".format(
            unquote(proxy.username), unquote(proxy.password or ""))
        pedido += "Proxy-Authorization: Basic {}\r\n".format(
            base64.b64encode(credencial.encode("utf-8")).decode("ascii"))
    sock.sendall((pedido + "\r\n").encode("utf-8"))

    # le byte a byte: o que vier depois do cabecalho ja e o banner do SSH
    resposta = b""
    while not resposta.endswith(b"\r\n\r\n"):
        byte = sock.recv(1)
        if not byte:
            break
        resposta += byte

    status = resposta.split(b"\r\n", 1)[0].decode("latin-1")
    partes = status.split()
    if len(partes) < 2 or partes[1] != "200":
        sock.close()
        raise ConnectionError("proxy recusou o tunel para {}:{} ({})".format(
            host, porta, status or "sem resposta"))
    return sock



def baixar_via_sftp(arquivos):
    """Baixa os arquivos por SFTP. Devolve a lista dos que foram baixados."""
    if paramiko is None:
        raise RuntimeError("paramiko nao instalado")
    chave = paramiko.RSAKey.from_private_key_file(str(CAMINHO_CHAVE_SSH))

    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cliente.connect(
        HOST_FILES,
        port=PORTA_SFTP,
        username=VETTAFI_USER,
        pkey=chave,
        sock=tunel_proxy(HOST_FILES, PORTA_SFTP),
        allow_agent=False,
        look_for_keys=False,
        banner_timeout=TIMEOUT,
    )
    print("[sftp] conectado via proxy")

    baixados = []
    try:
        sftp = cliente.open_sftp()
        for remoto, destino in arquivos.items():
            try:
                sftp.stat(remoto)
            except FileNotFoundError:
                print("[aviso] arquivo do dia ainda nao publicado: {}".format(
                    destino.name))
                continue
            sftp.get(remoto, str(destino))
            print("[download] {}".format(destino.name))
            baixados.append(destino)
    finally:
        cliente.close()
    return baixados



# ---- Opcao 2: API REST da Files.com via HTTPS ----

def criar_sessao_http():
    """Sessao requests que sai pelo proxy e aceita a CA de interceptacao TLS."""
    sessao = requests.Session()
    # sem isso, HTTP(S)_PROXY / REQUESTS_CA_BUNDLE do Windows sobrepoem o que
    # esta configurado abaixo
    sessao.trust_env = False
    proxy = url_proxy()
    sessao.proxies = {"http": proxy, "https": proxy}
    sessao.verify = False
    return sessao



def parece_api_key(texto):
    """API key da Files.com: string unica, sem quebras de linha nem BEGIN/END."""
    if not texto:
        return False
    if "BEGIN" in texto or "\n" in texto or "\r" in texto:
        return False
    return 20 <= len(texto) <= 200



def ler_api_key():
    """Procura uma API key valida em input/. Retorna None se nao encontrar."""
    candidatos = []

    if CAMINHO_API_KEY.exists():
        candidatos.append(CAMINHO_API_KEY)

    if INPUT_DIR.exists():
        for arq in sorted(INPUT_DIR.glob("*.txt")):
            if arq not in candidatos:
                candidatos.append(arq)

    for arq in candidatos:
        try:
            bruto = arq.read_text(errors="replace").strip()
        except OSError:
            continue

        if parece_api_key(bruto):
            print("[auth] API key encontrada em {}".format(arq.name))
            return bruto

    return None



def autenticar(sessao):
    """Usa a API key se existir; senao abre sessao com usuario/senha."""
    chave = ler_api_key()
    if chave:
        sessao.headers["X-FilesAPI-Key"] = chave
        return

    if not VETTAFI_SENHA:
        raise RuntimeError(
            "Nenhuma credencial para a API REST.\n"
            "Obs.: id_api_key.txt contem uma chave SSH privada, que so serve "
            "para o SFTP.\n\n"
            "Opcao 1: gere uma API key em Files.com > My Settings > API Keys "
            "e salve em {}\n"
            "Opcao 2: defina VETTAFI_SENHA como variavel de ambiente e reabra "
            "o VS Code.".format(CAMINHO_API_KEY)
        )

    resp = sessao.post(
        "{}/sessions".format(BASE_URL),
        json={"username": VETTAFI_USER, "password": VETTAFI_SENHA},
        timeout=TIMEOUT,
    )
    if resp.status_code == 401:
        raise RuntimeError(
            "Files.com recusou usuario/senha (401). A conta pode estar "
            "configurada apenas para acesso por chave SSH, sem login por senha. "
            "Nesse caso e necessario gerar uma API key no painel."
        )
    resp.raise_for_status()
    # sessao aberta com usuario/senha usa X-FilesAPI-Auth, nao X-FilesAPI-Key
    sessao.headers["X-FilesAPI-Auth"] = resp.json()["id"]
    print("[auth] sessao aberta com usuario/senha")



def listar(sessao, caminho_remoto):
    """Lista o conteudo de uma pasta remota."""
    resp = sessao.get(
        "{}/folders/{}".format(BASE_URL, caminho_remoto.strip("/")),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()



def baixar(sessao, caminho_remoto, destino_local):
    """Baixa um arquivo da Files.com para o disco local."""
    meta = sessao.get(
        "{}/files/{}".format(BASE_URL, caminho_remoto),
        timeout=TIMEOUT,
    )
    meta.raise_for_status()

    # link pre-assinado, possivelmente em outro dominio: nao reenviar credenciais
    resp = sessao.get(
        meta.json()["download_uri"],
        headers={"X-FilesAPI-Key": None, "X-FilesAPI-Auth": None},
        timeout=300,
    )
    resp.raise_for_status()
    destino_local.write_bytes(resp.content)



def baixar_via_api(arquivos):
    """Baixa os arquivos pela API REST. Devolve a lista dos que foram baixados."""
    sessao = criar_sessao_http()
    autenticar(sessao)

    try:
        for item in listar(sessao, "/"):
            print(item.get("type"), item.get("display_name"))
    except requests.HTTPError as e:
        print("[aviso] nao foi possivel listar a raiz: HTTP {}".format(
            e.response.status_code))

    baixados = []
    for remoto, destino in arquivos.items():
        try:
            baixar(sessao, remoto, destino)
        except requests.HTTPError as e:
            status = e.response.status_code
            if status == 404:
                print("[aviso] arquivo do dia ainda nao publicado: {}".format(
                    destino.name))
            elif status in (401, 403):
                print("[erro] credencial sem permissao para {}".format(remoto))
            else:
                print("[erro] {}: HTTP {}".format(destino.name, status))
            continue
        print("[download] {}".format(destino.name))
        baixados.append(destino)
    return baixados



def main():
    print("[base] raiz do projeto: {}".format(BASE_DIR))
    print("[base] input : {}".format(INPUT_DIR))
    print("[base] output: {}".format(OUTPUT_DIR))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    arquivos = arquivos_do_dia()

    try:
        baixados = baixar_via_sftp(arquivos)
    except Exception as e:
        print("[sftp] indisponivel ({}); tentando a API REST via HTTPS".format(e))
        try:
            baixados = baixar_via_api(arquivos)
        except requests.exceptions.ProxyError as e:
            raise SystemExit(
                "[erro] o proxy recusou a conexao: {}\n"
                "- 407: RACF/senha (SQL_LOGIN/SENHA_WINDOWS) incorretos, ou o "
                "proxy exige NTLM/Kerberos. Nesse caso rode o px "
                "(pip install px-proxy; px) e defina "
                "VETTAFI_PROXY=http://127.0.0.1:3128\n"
                "- 403: {} bloqueado pela politica de acesso do Itau; pedir "
                "liberacao do dominio.".format(e, HOST_FILES)
            )

    print("[fim] {} arquivo(s) em {}".format(len(baixados), OUTPUT_DIR))



if __name__ == "__main__":
    main()
