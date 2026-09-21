
# ═══════════════════════════════════════════════════════════════════════════════
# Painel de Execução de Scripts Python
# ═══════════════════════════════════════════════════════════════════════════════
#
#   python painel.py          → sobe o painel em http://127.0.0.1:8765 e abre o navegador
#   python painel.py 8800     → usa outra porta
#
# Os scripts exibidos vêm de ../input/scripts.txt, uma linha por script:
#   Nome | caminho/do/script.py | argumentos (opcional)
#
# Cada script roda com o mesmo Python que abriu o painel e com a pasta do próprio
# script como diretório atual, então os caminhos relativos (../input, ../output)
# continuam valendo. O painel só escuta em 127.0.0.1 e só executa scripts que
# estão listados no arquivo.

from __future__ import annotations
from typing import Dict, List, Optional

import os
import sys
import json
import time
import shlex
import base64
import hashlib
import secrets
import threading
import subprocess
import webbrowser
from datetime import datetime
from html import escape as _esc
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
INPUT_SCRIPTS = os.path.normpath(os.path.join(BASE_DIR, "..", "input", "scripts.txt"))
LOGO_PATH     = os.path.normpath(os.path.join(BASE_DIR, "..", "input", "logo.png"))

HOST         = "127.0.0.1"
PORTA_PADRAO = 8765

ITAU_DARK   = "#000D3C"
ITAU_ORANGE = "#EC7000"
ITAU_WHITE  = "#ffffff"
ITAU_GRAY   = "#e0e0e0"
ITAU_GRAY2  = "#aaaaaa"
ITAU_RED    = "#c0392b"
ITAU_GREEN  = "#1e7e34"
ROW_PAR     = "#eaf0fb"

# exigido em todo POST — impede que outra página aberta no navegador dispare scripts
_TOKEN = secrets.token_urlsafe(24)

_JOBS: Dict[str, dict] = {}     # id do script → última execução
_LOCK = threading.Lock()
_EXEC_SEQ = 0


def _fmt_dur(seg: float) -> str:
    seg = int(round(seg))
    h, m, s = seg // 3600, seg % 3600 // 60, seg % 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s" if m else f"{s}s"

# ─────────────────────────────────────────────────────────────────────────────
# LEITURA DA LISTA DE SCRIPTS — ../input/scripts.txt
# ─────────────────────────────────────────────────────────────────────────────

def _ler_texto(path: str) -> str:
    # o Bloco de Notas pode salvar em UTF-8 ou ANSI
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ""


def ler_scripts() -> List[Dict]:
    if not os.path.exists(INPUT_SCRIPTS):
        return []

    scripts: List[Dict] = []
    vistos: set = set()
    for linha in _ler_texto(INPUT_SCRIPTS).splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue

        partes = [p.strip() for p in linha.split("|")]
        if len(partes) == 1:
            nome, caminho, args = "", partes[0], ""
        else:
            nome, caminho = partes[0], partes[1]
            args = partes[2] if len(partes) > 2 else ""

        caminho = caminho.strip('"').strip("'")
        if not caminho:
            continue
        # relativo → a partir da pasta do painel (src/); absoluto fica como está
        caminho = os.path.normpath(os.path.join(BASE_DIR, os.path.expandvars(caminho)))
        nome = nome or os.path.splitext(os.path.basename(caminho))[0]

        # id estável entre recargas do arquivo (não depende da ordem das linhas)
        sid = hashlib.sha1(f"{nome}|{caminho}".lower().encode("utf-8")).hexdigest()[:10]
        while sid in vistos:
            sid = hashlib.sha1(sid.encode()).hexdigest()[:10]
        vistos.add(sid)

        scripts.append({
            "id"     : sid,
            "nome"   : nome,
            "caminho": caminho,
            "args"   : args,
            "existe" : os.path.isfile(caminho),
        })
    return scripts


def _split_args(args: str) -> List[str]:
    # posix=False preserva as barras invertidas dos caminhos do Windows
    try:
        partes = shlex.split(args, posix=False)
    except ValueError:
        raise ValueError("Argumentos inválidos: aspas sem fechamento.")
    return [a[1:-1] if len(a) >= 2 and a[0] == a[-1] and a[0] in "\"'" else a
            for a in partes]

# ─────────────────────────────────────────────────────────────────────────────
# EXECUÇÃO
# ─────────────────────────────────────────────────────────────────────────────

def _anexar(job: dict, texto: str) -> None:
    # chamar com _LOCK
    job["log"].append(texto)
    job["tam"] += len(texto)


def _matar(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        # /T derruba também os processos filhos que o script abriu
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.terminate()


def _acompanhar(job: dict, proc: subprocess.Popen) -> None:
    for linha in iter(proc.stdout.readline, b""):
        texto = linha.decode("utf-8", errors="replace").replace("\r\n", "\n")
        with _LOCK:
            _anexar(job, texto)

    rc  = proc.wait()
    fim = time.time()
    with _LOCK:
        job["fim"], job["codigo"] = fim, rc
        dur = _fmt_dur(fim - job["inicio"])
        if job["status"] == "parando":
            job["status"] = "interrompido"
            _anexar(job, f"\n■ Interrompido pelo usuário após {dur}\n")
        else:
            job["status"] = "ok" if rc == 0 else "erro"
            _anexar(job, f"\n■ Finalizado em {dur} — código de saída {rc}\n")
    print(f"  [{job['status'].upper()}] {job['nome']} ({dur})")


def iniciar(script: Dict, args: str) -> dict:
    global _EXEC_SEQ
    caminho = script["caminho"]
    pasta   = os.path.dirname(caminho)
    cmd     = [sys.executable, "-u", caminho] + _split_args(args)
    cab     = (f"▶ python {os.path.basename(caminho)} {args}".rstrip()
               + f"\n▶ pasta: {pasta}\n\n")

    with _LOCK:
        atual = _JOBS.get(script["id"])
        if atual and atual["status"] in ("rodando", "parando"):
            raise RuntimeError(f"{script['nome']} já está rodando.")
        _EXEC_SEQ += 1
        job = {
            "exec"  : _EXEC_SEQ,
            "nome"  : script["nome"],
            "status": "rodando",
            "inicio": time.time(),
            "fim"   : None,
            "codigo": None,
            "log"   : [cab],
            "tam"   : len(cab),
            "proc"  : None,
        }
        _JOBS[script["id"]] = job

    # UTF-8 para os acentos chegarem certos; -u para a saída aparecer em tempo real
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    try:
        proc = subprocess.Popen(cmd, cwd=pasta, env=env,
                                stdin=subprocess.DEVNULL,   # input() falha em vez de travar
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    except OSError as e:
        with _LOCK:
            _anexar(job, f"■ Falha ao iniciar: {e}\n")
            job["status"], job["fim"] = "erro", time.time()
        return job

    job["proc"] = proc
    print(f"  [RODANDO] {script['nome']}")
    threading.Thread(target=_acompanhar, args=(job, proc), daemon=True).start()
    return job


def parar(sid: str) -> bool:
    with _LOCK:
        job = _JOBS.get(sid)
        if not job or job["status"] != "rodando" or job["proc"] is None:
            return False
        job["status"] = "parando"
        proc = job["proc"]
    _matar(proc)
    return True


def parar_todos() -> None:
    with _LOCK:
        ativos = [j for j in _JOBS.values() if j["status"] == "rodando" and j["proc"]]
        for j in ativos:
            j["status"] = "parando"
    if ativos:
        print(f"  Interrompendo {len(ativos)} script(s) em execução...")
    for j in ativos:
        _matar(j["proc"])


def status_jobs() -> Dict[str, dict]:
    agora = time.time()
    with _LOCK:
        return {
            sid: {
                "exec"   : j["exec"],
                "status" : j["status"],
                "codigo" : j["codigo"],
                "inicio" : datetime.fromtimestamp(j["inicio"]).strftime("%d/%m %H:%M:%S"),
                "duracao": (j["fim"] or agora) - j["inicio"],
            }
            for sid, j in _JOBS.items()
        }


def ler_log(sid: str, exec_cli: Optional[int], desde: int) -> dict:
    with _LOCK:
        job = _JOBS.get(sid)
        if not job:
            return {"exec": None, "texto": "", "total": 0}
        if exec_cli != job["exec"]:     # execução nova → manda o log inteiro
            desde = 0
        if len(job["log"]) > 1:
            job["log"] = ["".join(job["log"])]
        return {"exec": job["exec"], "texto": job["log"][0][desde:], "total": job["tam"]}

# ─────────────────────────────────────────────────────────────────────────────
# PÁGINA HTML — mesmo layout do exposicao_html.py
# ─────────────────────────────────────────────────────────────────────────────

def gerar_html() -> str:
    logo_tag = ""
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as _f:
            _b64 = base64.b64encode(_f.read()).decode()
        _ext  = os.path.splitext(LOGO_PATH)[1].lstrip(".").lower()
        _mime = "image/png" if _ext == "png" else f"image/{_ext}"
        logo_tag = f'<img src="data:{_mime};base64,{_b64}" class="logo-img" alt="Itaú">'

    css = f"""
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f3fa; color: #1a1a2e; }}

    .hdr {{ background: {ITAU_DARK}; padding: 24px 40px 0; }}
    .hdr::after {{ content: ''; display: block; height: 4px; background: {ITAU_ORANGE}; margin-top: 20px; }}
    .hdr-inner {{ display: flex; align-items: center; justify-content: space-between; gap: 20px; }}
    .hdr h1 {{ color: #fff; font-size: 1.7rem; font-weight: 700; letter-spacing: .06em; }}
    .hdr .sub {{ color: {ITAU_GRAY2}; font-size: .88rem; margin-top: 5px; word-break: break-all; }}
    .hdr .sub strong {{ color: #fff; }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand span {{ color: {ITAU_GRAY2}; font-size: 2.1rem; font-weight: 700; letter-spacing: .04em;
                   white-space: nowrap; }}
    .logo-img {{ height: 52px; width: auto; object-fit: contain; }}

    .nav-wrapper {{ position: sticky; top: 0; z-index: 100;
                    box-shadow: 0 3px 10px rgba(0,0,0,.09); }}
    .nav-main {{ background: {ITAU_DARK}; padding: 0 40px;
                 display: flex; align-items: center; gap: 0; }}
    .main-btn {{ padding: 13px 28px; background: none; border: none;
                 border-bottom: 3px solid transparent;
                 color: {ITAU_GRAY2}; font-weight: 700; font-size: .88rem;
                 letter-spacing: .06em; cursor: default; white-space: nowrap; }}
    .main-btn.active {{ color: #fff; border-bottom-color: {ITAU_ORANGE}; }}
    .nav-info {{ margin-left: auto; display: flex; align-items: center; gap: 22px;
                 font-size: .76rem; font-weight: 700; letter-spacing: .06em; }}
    .nav-info .rodando {{ color: {ITAU_ORANGE}; }}
    .conn.on  {{ color: #7ee2a0; }}
    .conn.off {{ color: #ff8a80; }}

    .content {{ padding: 28px 40px 50px; }}

    .toolbar {{ display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 14px; }}
    .aba-title {{ font-size: 1rem; font-weight: 700; color: {ITAU_ORANGE};
                  text-transform: uppercase; letter-spacing: .08em; }}
    .qtd {{ background: {ITAU_ORANGE}18; color: {ITAU_ORANGE}; border-radius: 10px;
            font-size: .78rem; padding: 2px 10px; margin-left: 6px; }}
    .search-box {{ margin-left: auto; padding: 8px 16px; border: 1.5px solid {ITAU_GRAY}; border-radius: 8px;
                   font-size: .85rem; width: 300px; max-width: 100%; outline: none; transition: border .2s; }}
    .search-box:focus {{ border-color: {ITAU_ORANGE}; box-shadow: 0 0 0 3px {ITAU_ORANGE}22; }}
    .nav-btn {{ padding: 7px 18px; border: 2px solid {ITAU_ORANGE}; border-radius: 20px;
                background: #fff; color: {ITAU_ORANGE}; font-weight: 600; font-size: .82rem;
                cursor: pointer; transition: all .17s; white-space: nowrap; }}
    .nav-btn:hover {{ background: {ITAU_ORANGE}18; }}

    .tbl-wrap {{ overflow-x: auto; border-radius: 10px;
                 box-shadow: 0 2px 16px rgba(0,0,0,.10); }}
    .exp-table {{ border-collapse: collapse; width: 100%; font-size: .83rem;
                  background: #fff; min-width: 900px; }}
    .exp-table thead tr {{ background: {ITAU_DARK}; }}
    .exp-table th {{ color: #fff; font-weight: 600; padding: 11px 14px; white-space: nowrap;
                     text-align: center; border-right: 1px solid #ffffff1a; }}
    .exp-table td {{ padding: 9px 14px; text-align: center; border-bottom: 1px solid {ITAU_GRAY};
                     border-right: 1px solid {ITAU_GRAY}; white-space: nowrap; }}
    .exp-table td:first-child {{ text-align: left; font-weight: 600; }}
    .exp-table td:last-child, .exp-table th:last-child {{ border-right: none; }}
    .exp-table tbody tr {{ cursor: pointer; }}
    .exp-table tbody tr:nth-child(even) {{ background: {ROW_PAR}; }}
    .exp-table tbody tr:hover {{ background: #d6e4ff !important; transition: background .12s; }}
    .exp-table tbody tr.sel {{ background: {ITAU_ORANGE}14 !important; }}
    .exp-table tbody tr.sel td:first-child {{ box-shadow: inset 4px 0 0 {ITAU_ORANGE}; }}
    .exp-table td.c-path {{ text-align: left; white-space: normal; word-break: break-all;
                            font-family: Consolas, 'Cascadia Mono', monospace; font-size: .76rem;
                            color: #555; min-width: 240px; max-width: 460px; }}

    .arg-input {{ width: 100%; min-width: 150px; padding: 6px 10px; border: 1.5px solid {ITAU_GRAY};
                  border-radius: 6px; font-family: Consolas, 'Cascadia Mono', monospace; font-size: .8rem;
                  outline: none; background: #fff; transition: border .2s; }}
    .arg-input:focus {{ border-color: {ITAU_ORANGE}; box-shadow: 0 0 0 3px {ITAU_ORANGE}22; }}

    .st {{ display: inline-flex; align-items: center; gap: 6px; padding: 3px 12px; border-radius: 12px;
           font-size: .74rem; font-weight: 700; letter-spacing: .05em; white-space: nowrap; }}
    .st-pronto       {{ background: {ITAU_GRAY}; color: #555; }}
    .st-rodando,
    .st-parando      {{ background: {ITAU_ORANGE}22; color: {ITAU_ORANGE}; }}
    .st-rodando::before {{ content: ''; width: 8px; height: 8px; border-radius: 50%;
                           background: {ITAU_ORANGE}; animation: pulse 1s infinite; }}
    .st-ok           {{ background: {ITAU_GREEN}22; color: {ITAU_GREEN}; }}
    .st-erro         {{ background: {ITAU_RED}22; color: {ITAU_RED}; }}
    .st-interrompido {{ background: {ITAU_GRAY}; color: {ITAU_RED}; }}
    .st-ausente      {{ background: #fff; color: {ITAU_RED}; border: 1.5px dashed {ITAU_RED}; }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .25; }} }}

    .run-btn {{ padding: 6px 18px; border: 2px solid {ITAU_ORANGE}; border-radius: 20px;
                background: {ITAU_ORANGE}; color: #fff; font-weight: 700; font-size: .78rem;
                letter-spacing: .04em; cursor: pointer; transition: all .17s; white-space: nowrap; }}
    .run-btn:hover {{ box-shadow: 0 2px 8px {ITAU_ORANGE}55; }}
    .run-btn.stop {{ background: #fff; border-color: {ITAU_RED}; color: {ITAU_RED}; }}
    .run-btn.stop:hover {{ background: {ITAU_RED}; color: #fff; box-shadow: 0 2px 8px {ITAU_RED}55; }}
    .run-btn:disabled {{ opacity: .4; cursor: not-allowed; box-shadow: none; }}

    .vazio {{ background: #fff; border: 2px dashed {ITAU_GRAY}; border-radius: 10px; padding: 26px 30px;
              color: {ITAU_DARK}; line-height: 1.9; font-size: .9rem; }}
    .vazio code {{ background: {ROW_PAR}; padding: 2px 8px; border-radius: 4px;
                   font-family: Consolas, 'Cascadia Mono', monospace; font-size: .82rem; }}

    .console {{ margin-top: 28px; border-radius: 10px; overflow: hidden;
                box-shadow: 0 2px 16px rgba(0,0,0,.10); }}
    .console-hdr {{ background: {ITAU_DARK}; color: #fff; padding: 10px 16px; display: flex;
                    align-items: center; gap: 12px; border-bottom: 3px solid {ITAU_ORANGE}; }}
    .console-hdr .ttl {{ font-weight: 700; letter-spacing: .08em; font-size: .85rem; }}
    .console-hdr .nome {{ color: {ITAU_ORANGE}; font-weight: 700; font-size: .85rem; }}
    .console-hdr .acoes {{ margin-left: auto; }}
    .console-hdr .st-ok   {{ background: #7ee2a022; color: #7ee2a0; }}
    .console-hdr .st-erro {{ background: #ff8a8022; color: #ff8a80; }}
    .console-hdr .st-interrompido {{ background: #ffffff18; color: #ff8a80; }}
    .btn-ghost {{ padding: 5px 14px; border: 1.5px solid rgba(255,255,255,.35); border-radius: 14px;
                  background: none; color: #fff; font-size: .76rem; font-weight: 600; cursor: pointer;
                  transition: all .15s; }}
    .btn-ghost:hover {{ border-color: {ITAU_ORANGE}; color: {ITAU_ORANGE}; }}
    .console pre {{ background: #0a1230; color: #dfe6f5; font-family: Consolas, 'Cascadia Mono', monospace;
                    font-size: .8rem; line-height: 1.55; padding: 16px 18px; height: 440px; overflow: auto;
                    white-space: pre-wrap; word-break: break-word; }}
    .ln-meta {{ color: {ITAU_GRAY2}; }}
    .ln-err  {{ color: #ff8a80; }}
    .ln-warn {{ color: #ffb566; }}
    .ln-ok   {{ color: #7ee2a0; }}

    .footer {{ background: #fff; border-top: 3px solid {ITAU_DARK}; padding: 16px 40px;
               font-size: .78rem; color: {ITAU_GRAY2}; font-style: italic; text-align: center;
               word-break: break-all; }}
    .footer code {{ font-style: normal; font-family: Consolas, 'Cascadia Mono', monospace; color: {ITAU_DARK}; }}

    .toast {{ position: fixed; right: 24px; bottom: 24px; max-width: 460px; background: {ITAU_DARK};
              color: #fff; padding: 12px 20px; border-radius: 8px; border-left: 4px solid {ITAU_ORANGE};
              font-size: .85rem; box-shadow: 0 4px 20px rgba(0,0,0,.25); opacity: 0;
              transform: translateY(8px); transition: all .2s; pointer-events: none; z-index: 200; }}
    .toast.show {{ opacity: 1; transform: none; }}
    .toast.erro {{ border-left-color: {ITAU_RED}; }}

    @media (max-width: 720px) {{
      .hdr, .nav-main, .content, .footer {{ padding-left: 16px; padding-right: 16px; }}
      .brand span {{ display: none; }}
      .search-box {{ margin-left: 0; }}
    }}
    """

    js = r"""
    const $ = s => document.querySelector(s);
    const STATUS_TXT = { pronto: 'PRONTO', rodando: 'RODANDO', parando: 'PARANDO', ok: 'OK',
                         erro: 'ERRO', interrompido: 'INTERROMPIDO', ausente: 'NÃO ENCONTRADO' };
    const ATIVO = st => st === 'rodando' || st === 'parando';

    let SCRIPTS  = [];
    let JOBS     = {};
    let SEL      = null;                     // script cujo log aparece no console
    let LOG      = { exec: null, desde: 0 };
    let ocupado  = false, pendente = false;

    function esc(s) {
      return String(s ?? '').replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function fmtDur(s) {
      if (s == null) return '';
      s = Math.round(s);
      const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), r = s % 60;
      if (h) return `${h}h ${String(m).padStart(2, '0')}m`;
      return m ? `${m}m ${String(r).padStart(2, '0')}s` : `${r}s`;
    }

    function toast(msg, erro) {
      const t = $('#toast');
      t.textContent = msg;
      t.className = 'toast show' + (erro ? ' erro' : '');
      clearTimeout(toast._t);
      toast._t = setTimeout(() => { t.className = 'toast'; }, 3500);
    }

    async function api(url, body) {
      const opt = body === undefined ? {} : {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Token': TOKEN },
        body: JSON.stringify(body),
      };
      const r = await fetch(url, opt);
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.erro || 'HTTP ' + r.status);
      return d;
    }

    async function carregar() {
      let d;
      try { d = await api('/api/scripts'); }
      catch (e) { toast('Não foi possível ler a lista: ' + e.message, true); return; }
      SCRIPTS = d.scripts;
      $('#tbody').innerHTML = SCRIPTS.map(s => `
        <tr id="row-${s.id}" onclick="selecionar('${s.id}')">
          <td>${esc(s.nome)}</td>
          <td class="c-path" title="${esc(s.caminho)}">${esc(s.caminho)}</td>
          <td><input class="arg-input" id="args-${s.id}" value="${esc(s.args)}" placeholder="sem argumentos"
                     onclick="event.stopPropagation()"
                     onkeydown="if (event.key === 'Enter') rodar('${s.id}')"></td>
          <td class="c-status"></td>
          <td class="c-inicio"></td>
          <td class="c-dur"></td>
          <td class="c-acao"></td>
        </tr>`).join('');
      $('#qtd').textContent = SCRIPTS.length;
      $('#vazio').style.display = SCRIPTS.length ? 'none' : '';
      $('#tbl').style.display   = SCRIPTS.length ? '' : 'none';
      filtrar($('#busca').value);
      renderStatus();
      selecionar(SCRIPTS.some(s => s.id === SEL) ? SEL : (SCRIPTS[0]?.id ?? null));
    }

    function filtrar(q) {
      q = q.toLowerCase();
      document.querySelectorAll('#tbody tr').forEach(r => {
        r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    }

    function selecionar(id) {
      if (id !== SEL) {
        SEL = id;
        LOG = { exec: null, desde: 0 };
        $('#log').textContent = '';
      }
      document.querySelectorAll('#tbody tr').forEach(r => r.classList.toggle('sel', r.id === 'row-' + id));
      const s = SCRIPTS.find(x => x.id === id);
      $('#console-nome').textContent = s ? s.nome : '—';
      renderStatus();
      refresh();
    }

    function renderStatus() {
      for (const s of SCRIPTS) {
        const row = document.getElementById('row-' + s.id);
        if (!row) continue;
        const j  = JOBS[s.id];
        const st = j && ATIVO(j.status) ? j.status : (!s.existe ? 'ausente' : (j ? j.status : 'pronto'));
        const tip = j && j.codigo != null ? ` title="Código de saída ${j.codigo}"` : '';
        row.querySelector('.c-status').innerHTML = `<span class="st st-${st}"${tip}>${STATUS_TXT[st]}</span>`;
        row.querySelector('.c-inicio').textContent = j ? j.inicio : '';
        row.querySelector('.c-dur').textContent    = j ? fmtDur(j.duracao) : '';

        // só recria o botão quando o estado muda (evita piscar a cada atualização)
        const acao   = row.querySelector('.c-acao');
        const estado = ATIVO(st) ? st : (s.existe ? 'rodar' : 'off');
        if (acao.dataset.estado !== estado) {
          acao.dataset.estado = estado;
          acao.innerHTML = ATIVO(st)
            ? `<button class="run-btn stop" ${st === 'parando' ? 'disabled' : ''}
                       onclick="event.stopPropagation(); parar('${s.id}')">■ PARAR</button>`
            : `<button class="run-btn" ${s.existe ? '' : 'disabled'}
                       onclick="event.stopPropagation(); rodar('${s.id}')">▶ RODAR</button>`;
        }
      }

      const j = SEL && JOBS[SEL];
      $('#console-status').innerHTML = j ? `<span class="st st-${j.status}">${STATUS_TXT[j.status]}</span>` : '';
      const n = Object.values(JOBS).filter(x => ATIVO(x.status)).length;
      $('#rodando').textContent = n ? `● ${n} EM EXECUÇÃO` : '';
      document.title = (n ? `(${n}) ` : '') + 'Painel de Execução';
    }

    function classeLinha(l) {
      if (/^[▶■]/.test(l)) return 'ln-meta';
      if (/traceback|error\b|\berro\b|exception|falha/i.test(l)) return 'ln-err';
      if (/\baviso\b|warning/i.test(l)) return 'ln-warn';
      if (/\[ok\]|sucesso|conclu[ií]d/i.test(l)) return 'ln-ok';
      return '';
    }

    function anexarLog(texto) {
      const pre   = $('#log');
      const noFim = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 40;
      const frag  = document.createDocumentFragment();
      for (const l of texto.split(/(?<=\n)/)) {
        const c = classeLinha(l);
        if (c) {
          const sp = document.createElement('span');
          sp.className = c;
          sp.textContent = l;
          frag.appendChild(sp);
        } else {
          frag.appendChild(document.createTextNode(l));
        }
      }
      pre.appendChild(frag);
      if (noFim) pre.scrollTop = pre.scrollHeight;
    }

    function logVazio(msg) {
      $('#log').innerHTML = `<span class="ln-meta">${esc(msg)}</span>`;
      LOG = { exec: null, desde: 0 };
    }

    async function atualizarLog() {
      const id = SEL;
      if (!id) { logVazio('Selecione um script na tabela.'); return; }
      const d = await api(`/api/log?id=${id}&exec=${LOG.exec ?? ''}&desde=${LOG.desde}`);
      if (id !== SEL) return;                // trocou de script enquanto esperava
      if (d.exec === null) { logVazio('Nenhuma execução deste script nesta sessão. Clique em ▶ RODAR.'); return; }
      if (d.exec !== LOG.exec) { $('#log').textContent = ''; LOG.exec = d.exec; }
      if (d.texto) anexarLog(d.texto);
      LOG.desde = d.total;
    }

    function conexao(ok) {
      const c = $('#conn');
      c.className   = 'conn ' + (ok ? 'on' : 'off');
      c.textContent = ok ? '● CONECTADO' : '● PAINEL DESLIGADO — rode python painel.py';
    }

    async function refresh() {
      if (ocupado) { pendente = true; return; }
      ocupado = true;
      try {
        JOBS = (await api('/api/status')).jobs;
        renderStatus();
        await atualizarLog();
        conexao(true);
      } catch (e) {
        conexao(false);
      } finally {
        ocupado = false;
      }
      if (pendente) { pendente = false; refresh(); }
    }

    async function loop() {
      await refresh();
      setTimeout(loop, Object.values(JOBS).some(j => ATIVO(j.status)) ? 600 : 1500);
    }

    async function rodar(id) {
      const args = $('#args-' + id)?.value ?? '';
      try { await api('/api/rodar', { id, args }); }
      catch (e) { toast(e.message, true); return; }
      selecionar(id);
    }

    async function parar(id) {
      try { await api('/api/parar', { id }); }
      catch (e) { toast(e.message, true); }
      refresh();
    }

    function copiarLog() {
      navigator.clipboard.writeText($('#log').textContent)
        .then(() => toast('Saída copiada.'), () => toast('Não foi possível copiar.', true));
    }

    carregar().then(loop);
    """

    arq = _esc(INPUT_SCRIPTS)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Painel de Execução</title>
  <style>{css}</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-inner">
    <div>
      <h1>PAINEL DE EXECUÇÃO</h1>
      <p class="sub">Lista de scripts: &nbsp;<strong>{arq}</strong></p>
    </div>
    <div class="brand"><span>Itaú Asset Management</span>{logo_tag}</div>
  </div>
</div>

<div class="nav-wrapper">
  <nav class="nav-main">
    <button class="main-btn active">SCRIPTS PYTHON</button>
    <span class="nav-info">
      <span id="rodando" class="rodando"></span>
      <span id="conn" class="conn on">● CONECTADO</span>
    </span>
  </nav>
</div>

<div class="content">
  <div class="toolbar">
    <div class="aba-title">Scripts<span class="qtd" id="qtd">0</span></div>
    <input id="busca" class="search-box" placeholder="Filtrar por nome ou caminho..." oninput="filtrar(this.value)">
    <button class="nav-btn" onclick="carregar()" title="Lê o scripts.txt de novo">&#8635; Recarregar lista</button>
  </div>

  <div id="vazio" class="vazio" style="display:none">
    Nenhum script encontrado em <code>{arq}</code>.<br>
    Crie o arquivo com uma linha por script, no formato
    <code>Nome | C:\\caminho\\do\\script.py | argumentos</code>, e clique em <strong>Recarregar lista</strong>.
  </div>

  <div class="tbl-wrap" id="tbl">
    <table class="exp-table">
      <thead><tr>
        <th>SCRIPT</th><th>CAMINHO</th><th>ARGUMENTOS</th><th>STATUS</th>
        <th>INÍCIO</th><th>DURAÇÃO</th><th></th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>

  <div class="console">
    <div class="console-hdr">
      <span class="ttl">SAÍDA</span>
      <span class="nome" id="console-nome">—</span>
      <span id="console-status"></span>
      <div class="acoes"><button class="btn-ghost" onclick="copiarLog()">Copiar</button></div>
    </div>
    <pre id="log"></pre>
  </div>
</div>

<div class="footer">
  Formato do scripts.txt: &nbsp;<code>Nome | caminho do script.py | argumentos</code> &nbsp;|&nbsp;
  Cada script roda na própria pasta &nbsp;|&nbsp; Python: {_esc(sys.executable)}
</div>

<div id="toast" class="toast"></div>

<script>const TOKEN = {json.dumps(_TOKEN)};</script>
<script>{js}</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
# SERVIDOR HTTP (só 127.0.0.1)
# ─────────────────────────────────────────────────────────────────────────────

def _int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class _Handler(BaseHTTPRequestHandler):

    def log_message(self, *args) -> None:
        pass    # sem uma linha no console para cada atualização da página

    def _responder(self, corpo: bytes, tipo: str, codigo: int = 200) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, obj, codigo: int = 200) -> None:
        self._responder(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8", codigo)

    def _host_ok(self) -> bool:
        # só aceita requisições endereçadas ao próprio painel (bloqueia DNS rebinding)
        return (self.headers.get("Host") or "").lower() in self.server.hosts_ok

    def do_GET(self) -> None:
        if not self._host_ok():
            return self._json({"erro": "Host não permitido."}, 403)
        url = urlparse(self.path)
        q   = {k: v[0] for k, v in parse_qs(url.query).items()}

        if url.path in ("/", "/index.html"):
            self._responder(gerar_html().encode("utf-8"), "text/html; charset=utf-8")
        elif url.path == "/api/scripts":
            self._json({"scripts": ler_scripts(), "arquivo": INPUT_SCRIPTS})
        elif url.path == "/api/status":
            self._json({"jobs": status_jobs()})
        elif url.path == "/api/log":
            self._json(ler_log(q.get("id", ""), _int(q.get("exec")), max(_int(q.get("desde")) or 0, 0)))
        else:
            self._json({"erro": "Não encontrado."}, 404)

    def do_POST(self) -> None:
        if not self._host_ok():
            return self._json({"erro": "Host não permitido."}, 403)
        if not secrets.compare_digest(self.headers.get("X-Token", ""), _TOKEN):
            return self._json({"erro": "Sessão expirada — recarregue a página (F5)."}, 403)
        try:
            n     = int(self.headers.get("Content-Length") or 0)
            corpo = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            corpo = None
        if not isinstance(corpo, dict):
            return self._json({"erro": "Requisição inválida."}, 400)

        path = urlparse(self.path).path
        sid  = str(corpo.get("id", ""))

        if path == "/api/rodar":
            # só roda o que está no scripts.txt — o navegador manda o id, nunca o caminho
            script = next((s for s in ler_scripts() if s["id"] == sid), None)
            if script is None:
                return self._json({"erro": "Script não está mais na lista — clique em Recarregar lista."}, 404)
            if not script["existe"]:
                return self._json({"erro": f"Arquivo não encontrado: {script['caminho']}"}, 400)
            try:
                job = iniciar(script, str(corpo.get("args", "")))
            except (RuntimeError, ValueError) as e:
                return self._json({"erro": str(e)}, 409)
            return self._json({"ok": True, "exec": job["exec"]})

        if path == "/api/parar":
            return self._json({"ok": parar(sid)})

        self._json({"erro": "Não encontrado."}, 404)


class _Servidor(ThreadingHTTPServer):
    # no Windows, SO_REUSEADDR deixaria dois painéis abrirem na mesma porta
    allow_reuse_address = os.name != "nt"
    hosts_ok: set = set()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else PORTA_PADRAO
    # console do Windows (cp850/cp1252) não derruba o painel por causa de um caractere
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    httpd: Optional[_Servidor] = None
    for p in range(porta, porta + 20):
        try:
            httpd = _Servidor((HOST, p), _Handler)
            break
        except OSError:
            continue
    if httpd is None:
        print(f"ERRO: nenhuma porta livre entre {porta} e {porta + 19}.")
        return

    porta = httpd.server_address[1]
    httpd.hosts_ok = {f"127.0.0.1:{porta}", f"localhost:{porta}"}
    url = f"http://{HOST}:{porta}/"

    print(f"\n{'='*62}")
    print(f"  PAINEL DE EXECUÇÃO")
    print(f"  Endereço  : {url}")
    print(f"  Scripts   : {INPUT_SCRIPTS}")
    print(f"  Python    : {sys.executable}")
    print(f"  Ctrl+C para encerrar")
    print(f"{'='*62}\n")
    if not os.path.exists(INPUT_SCRIPTS):
        print(f"  [AVISO] {INPUT_SCRIPTS} não encontrado — o painel abre vazio.\n")

    threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando o painel...")
    finally:
        parar_todos()
        httpd.server_close()


if __name__ == "__main__":
    main()
