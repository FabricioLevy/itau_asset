from __future__ import annotations

import os
import re
import base64
import glob
import pandas as pd
import QuantLib as ql
from datetime import date
import win32com.client as win32
from PIL import Image
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage


BASE_OUTPUT = "../output/rolagem"
INPUT_EXCEL = "../input/fundos_rolagem.xlsx"

GRUPOS_EXCLUIR = {
    "DI1",
}


# ================= ORDEM ABAS =================


def ordem_abas() -> list[str]:
    try:
        xls = pd.ExcelFile(INPUT_EXCEL)
        return xls.sheet_names
    except Exception:
        return []


# ================= LER PNGs =================


def ler_pngs(dt: str, output_dir: str) -> list:
    padrao  = os.path.join(output_dir, f"rolagem_*_{dt}.png")
    achados = {os.path.basename(p): p for p in glob.glob(padrao)}

    if not achados:
        print("Nenhum PNG encontrado.")
        return []

    abas = ordem_abas()

    nomes_ordenados = []

    # DOL_WDO sempre primeiro
    dol_nome = f"rolagem_DOL_WDO_{dt}.png"
    if dol_nome in achados:
        nomes_ordenados.append(dol_nome)

    # ordem Excel
    for aba in abas:
        nome = f"rolagem_{aba}_{dt}.png"
        if nome in achados and nome not in nomes_ordenados:
            nomes_ordenados.append(nome)

    # sobras
    for nome in sorted(achados):
        if nome not in nomes_ordenados:
            nomes_ordenados.append(nome)

    resultado = []

    for nome in nomes_ordenados:
        path = achados[nome]

        match = re.match(r"rolagem_(.+)_\d{4}-\d{2}-\d{2}\.png", nome)
        grupo = match.group(1) if match else nome

        if grupo in GRUPOS_EXCLUIR:
            print(f"[SKIP] {nome}")
            continue

        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        resultado.append({
            "grupo": grupo,
            "path": path,
            "b64": b64,
        })

        print(f"[OK] {nome}")

    print("\nOrdem final:")
    print([x["grupo"] for x in resultado])

    return resultado


# ================= PDF =================


def gerar_pdf(pngs: list, dt: str, outdir: str) -> str:
    path = os.path.join(outdir, f"rolagem_{dt}.pdf")

    imgs = [Image.open(p["path"]).convert("RGB") for p in pngs]

    if not imgs:
        return ""

    imgs[0].save(
        path,
        save_all=True,
        append_images=imgs[1:],
        resolution=150,
    )

    print(f"[OK] PDF: {path}")
    return path


# ================= EXCEL =================


def gerar_excel(pngs: list, dt: str, outdir: str) -> str:
    path = os.path.join(outdir, f"rolagem_{dt}.xlsx")

    wb = Workbook()
    ws0 = wb.active
    wb.remove(ws0)

    for item in pngs:
        nome_aba = item["grupo"][:31]
        ws = wb.create_sheet(title=nome_aba)

        img = XLImage(item["path"])
        img.width  *= 0.7
        img.height *= 0.7

        ws.add_image(img, "A1")

    wb.save(path)

    print(f"[OK] Excel: {path}")
    return path


# ================= HTML BLOCO =================


def gerar_bloco_html(item: dict, titulo: str = "") -> str:
    cabecalho = f"""
      <tr>
        <td style="font-family:Arial; font-size:16px; font-weight:bold; padding-bottom:8px;">
          {titulo}
        </td>
      </tr>""" if titulo else ""
    return f"""
    <table align="left" width="90%" style="margin-bottom:20px;">{cabecalho}
      <tr>
        <td>
          <img src="data:image/png;base64,{item['b64']}"
               width="100%" style="display:block;border:0;" />
        </td>
      </tr>
    </table>
    """


# ================= ASSINATURA =================


def obter_assinatura(nome="FL") -> str:
    base = os.environ.get("APPDATA", "")

    for ext in ("htm", "html"):
        f = os.path.join(base, "Microsoft", "Signatures", f"{nome}.{ext}")
        if os.path.exists(f):
            with open(f, encoding="utf-8", errors="ignore") as arq:
                return arq.read()

    return ""


# ================= HTML EMAIL =================


def gerar_html_email(blocos, dt, assinatura):
    dt_fmt = pd.to_datetime(dt).strftime("%d/%m/%Y")

    return f"""
    <html>
    <body style="font-family:Arial;">

      <p>Prezados, bom dia.</p>

      <p>
        Segue relatório de rolagens com data base em
        <b>{dt_fmt}</b>.
      </p>

      {"".join(blocos)}

      <br><br><br><br><br>

      {assinatura}

    </body>
    </html>
    """


# ================= ENVIO =================


def enviar_email(html, pdf, para, cc=None):
    app = win32.Dispatch("outlook.application")
    mail = app.CreateItem(0)

    mail.Subject = "Relatório de Rolagens"
    mail.HTMLBody = html
    mail.To = "; ".join(para)

    if cc:
        mail.CC = "; ".join(cc)

    if pdf:
        mail.Attachments.Add(os.path.abspath(pdf))

    # if xlsx:
    #     mail.Attachments.Add(os.path.abspath(xlsx))

    mail.Display()


# ================= MAIN =================


if __name__ == "__main__":
    dt = ql.Brazil().advance(
        ql.Date.from_date(date.today()),
        ql.Period('-1d')
    ).to_date().strftime("%Y-%m-%d")

    pasta = os.path.join(BASE_OUTPUT, pd.to_datetime(dt).strftime("%Y%m%d"))

    print("Data:", dt)
    print("Pasta:", pasta)

    pngs = ler_pngs(dt, pasta)

    if not pngs:
        print("Nenhuma imagem encontrada.")
    else:
        pdf = gerar_pdf(pngs, dt, pasta)
        # xlsx = gerar_excel(pngs, dt, pasta)

        blocos = [
            gerar_bloco_html(pngs[0], titulo="Relatório de Rolagens"),
            *[gerar_bloco_html(i) for i in pngs[1:]],
        ]

        assinatura = obter_assinatura("FL")

        html = gerar_html_email(blocos, dt, assinatura)

        enviar_email(
            html,
            pdf,
            ["fabricio.levy@itau-unibanco.com.br"],
            [],
        )

        print("\nConcluído com sucesso")
