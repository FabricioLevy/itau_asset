import files_sdk

files_sdk.set_api_key("SUA_CHAVE")
files_sdk.base_url = "https://tmxvettafi.files.com"

# Listar uma pasta (string vazia = pasta raiz)
for item in files_sdk.folder.list_for("").auto_paging_iter():
    print(item.type, item.path)

# Baixar um arquivo para o disco local
files_sdk.download_file("pasta/relatorio.csv", "relatorio.csv")

# Enviar um arquivo local
files_sdk.upload_file("/caminho/local/relatorio.csv", "pasta/relatorio.csv")

# Ler o conteúdo direto na memória
with files_sdk.open("pasta/relatorio.csv", "r") as f:
    conteudo = f.read()