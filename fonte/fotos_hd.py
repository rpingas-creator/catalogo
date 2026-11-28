#!/usr/bin/env python3
"""Procura fotografias de maior qualidade nos sites oficiais dos fornecedores
(TopTex, Roly/Stamina via Gorfactory, Tejo Brinde) para cada artigo do catálogo.

Só aceita uma fotografia se for a MESMA imagem que o catálogo já mostra
(comparação com a miniatura atual), para nunca trocar por um artigo errado.
Não descarrega as fotografias grandes: guarda apenas o endereço oficial em
fonte/fotos_hd.json, que o catálogo usa na página do artigo (com a foto atual
como alternativa se o fornecedor não responder)."""
import base64, gzip, hashlib, io, json, os, re, sys, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
LIMIAR = float(os.environ.get("LIMIAR", "14"))  # diferença média máxima (0-255) para considerar a mesma foto

def get(url, timeout=25):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            if r.status != 200:
                return None
            ct = r.headers.get("Content-Type", "")
            b = r.read()
            if "image" not in ct and not (b[:3] == b"\xff\xd8\xff" or b[:4] == b"\x89PNG"):
                return None
            return b
    except Exception:
        return None

TW, TH = 24, 36

def norm_img(im):
    if im.mode in ("RGBA", "LA", "P"):
        fundo = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        fundo.paste(im, mask=im.split()[-1])
        im = fundo
    return im.convert("RGB")

def ref_vec(im):
    im = norm_img(im)
    return np.asarray(im.resize((TW, int(round(TW * im.size[1] / im.size[0]))) if im.size[0] else (TW, TH), Image.BILINEAR), dtype=np.float32)

def melhor_recorte(cand, ref):
    """Menor diferença entre a miniatura atual e um recorte (zoom 100% a 45%) da foto do fornecedor."""
    rh, rw = ref.shape[0], ref.shape[1]
    cw, ch = cand.size
    big = np.asarray(cand, dtype=np.float32)
    best = 999.0
    for esc in (1.0, 0.92, 0.85, 0.78, 0.72, 0.66, 0.6, 0.55, 0.5, 0.45):
        w = cw * esc
        h = w * rh / rw
        if h > ch:
            h = ch * esc
            w = h * rw / rh
            if w > cw:
                continue
        passo = max(2.0, min(cw, ch) * 0.04)
        xs = np.arange(0, max(0.0, cw - w) + 0.01, passo) if cw - w > 0.5 else [0.0]
        ys = np.arange(0, max(0.0, ch - h) + 0.01, passo) if ch - h > 0.5 else [0.0]
        for y in ys:
            for x in xs:
                c = cand.crop((int(x), int(y), int(x + w), int(y + h))).resize((rw, rh), Image.BILINEAR)
                d = float(np.abs(np.asarray(c, dtype=np.float32) - ref).mean())
                if d < best:
                    best = d
        if best <= LIMIAR * 0.6:
            break
    return best

def abrir(b):
    try:
        im = Image.open(io.BytesIO(b))
        im.load()
        return norm_img(im)
    except Exception:
        return None

def get_txt(url, timeout=25):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore"), r.geturl()
    except Exception:
        return "", ""

def toptex_pagina(R):
    """Lê a página oficial do artigo em toptex.pt e devolve as fotografias que lá aparecem."""
    h, _ = get_txt("https://www.toptex.pt/catalogsearch/result/?q=" + urllib.request.quote(R))
    m = re.search(r'href="(https://www\.toptex\.pt/%s-[^"?#]+\.html)"' % re.escape(R.lower()), h)
    if not m:
        return []
    pg, _ = get_txt(m.group(1))
    vis, out = set(), []
    for u in re.findall(r"https://cdn\.toptex\.com/(?:pictures/%s(?:-\d+)?(?:_\d{4})?\.jpg|packshots/PS_%s_[A-Z0-9]+\.png)" % (re.escape(R), re.escape(R)), pg, re.I):
        if u not in vis:
            vis.add(u); out.append(u)
    out.sort(key=lambda u: (0 if re.search(r"/%s(_\d{4})?\.jpg" % re.escape(R), u, re.I) else 1))
    return out[:8]

PLACE = {}
def toptex_placeholder(suf):
    if suf not in PLACE:
        b = get("https://cdn.toptex.com/pictures/ZZZNAOEXISTE999%s.jpg?w=240" % suf)
        PLACE[suf] = hashlib.md5(b).hexdigest() if b else ""
    return PLACE[suf]

ANOS = ["_2026", "_2025", "_2024", "_2023", "_2022", "_2021", "_2020", "_2019", ""]

def candidatos(x):
    mar, ref = x.get("mar"), str(x.get("ref") or "").strip()
    if not ref:
        return []
    out = []
    if mar == "TopTex":
        R = ref.upper()
        for u in toptex_pagina(R):
            out.append(("tt", "", u + "?w=240", u + "?w=1400"))
        cores = []
        for c in x.get("cols") or []:
            k = re.sub(r"[^A-Z0-9]", "", str(c.get("c") or "").upper())
            if k and k not in cores:
                cores.append(k)
        for k in cores[:6]:
            u = "https://cdn.toptex.com/packshots/PS_%s_%s.png" % (R, k)
            out.append(("tt", "", u + "?w=240", u + "?w=1400"))
        for s in ANOS:
            out.append(("tt", s, "https://cdn.toptex.com/pictures/%s%s.jpg?w=240" % (R, s), "https://cdn.toptex.com/pictures/%s%s.jpg?w=1400" % (R, s)))
    elif mar in ("Roly", "Stamina"):
        m = re.match(r"^[A-Za-z]*(\d+)", ref)
        if not m:
            return []
        n = m.group(1)
        cores = []
        for c in x.get("cols") or []:
            cc = str(c.get("c") or "").strip()
            if re.fullmatch(r"\d{1,4}", cc) and cc not in cores:
                cores.append(cc)
        cores = cores[:8]
        B = "https://static.gorfactory.es/images/models/%s/" % n
        pad = []
        for c in cores:
            mod = [("model/%s/%s_%s_1_1.jpg" % ("{t}", n, c)), ("model/%s/%s_%s_1_2.jpg" % ("{t}", n, c))]
            vis = [("views/%s/p_%s_%s_1_1.jpg" % ("{t}", n, c))]
            pad += (mod + vis) if mar == "Roly" else (vis + mod)
        for p in pad:
            out.append(("gf", "", B + p.format(t="large"), B + p.format(t="hd")))
    elif mar == "TejoBrinde":
        B = "https://www.tejobrinde.pt/resources/IMAGENS_500X500/"
        out.append(("tb", "", B + ref + ".JPG", B + ref + ".JPG"))
    return out

def procura(x):
    chave = "%s|%s" % (x.get("mar"), x.get("ref"))
    try:
        bp = os.path.join(os.path.dirname(AQUI), str(x.get("big") or ""))
        if x.get("big") and not str(x.get("big")).startswith("http") and os.path.isfile(bp):
            base = Image.open(bp)  # a foto que o catálogo mostra na página do artigo
        else:
            base = Image.open(io.BytesIO(base64.b64decode(x.get("img") or "")))
        base.load()
        ref_ass = ref_vec(base)
    except Exception:
        ref_ass = None
    melhor = None
    vistos = 0
    for tipo, suf, peq, grande in candidatos(x):
        b = get(peq)
        if not b:
            continue
        if tipo == "tt" and hashlib.md5(b).hexdigest() in set(PLACE.values()):
            continue
        vistos += 1
        cand = abrir(b)
        if cand is None:
            continue
        if cand.size[0] < 200:
            cand = cand.resize((200, int(200 * cand.size[1] / cand.size[0])), Image.BILINEAR)
        elif cand.size[0] > 240:
            cand = cand.resize((240, int(240 * cand.size[1] / cand.size[0])), Image.BILINEAR)
        d = melhor_recorte(cand, ref_ass) if ref_ass is not None else 999
        if melhor is None or d < melhor[0]:
            melhor = (d, grande)
        if d <= 1.5 or vistos >= 18:
            break
    if melhor and melhor[0] <= LIMIAR:
        if os.environ.get("DEBUG"):
            print("DBG OK", chave, round(melhor[0], 1), melhor[1], flush=True)
        return chave, melhor[1], melhor[0], vistos
    if os.environ.get("DEBUG"):
        print("DBG", chave, "cands", len(candidatos(x)), "vistos", vistos, "melhor", melhor, flush=True)
    return chave, None, (melhor[0] if melhor else None), vistos

def main():
    dados = json.load(gzip.open(os.path.join(AQUI, "dados.json.gz"), "rt", encoding="utf-8"))
    marcas = set((os.environ.get("MARCAS") or "TopTex,Roly,Stamina,TejoBrinde").split(","))
    itens = [x for x in dados if x.get("mar") in marcas]
    lim = int(os.environ.get("LIMITE") or 0)
    if lim:
        itens = itens[:lim]
    for s in ANOS:
        toptex_placeholder(s)
    res, est = {}, {}
    with ThreadPoolExecutor(int(os.environ.get("FIOS") or 24)) as ex:
        for i, (chave, url, d, vistos) in enumerate(ex.map(procura, itens)):
            m = chave.split("|")[0]
            e = est.setdefault(m, {"total": 0, "com_hd": 0, "foto_diferente": 0, "sem_foto": 0})
            e["total"] += 1
            if url:
                res[chave] = url
                e["com_hd"] += 1
            elif vistos:
                e["foto_diferente"] += 1
            else:
                e["sem_foto"] += 1
            if i % 500 == 0:
                print(i, "de", len(itens), flush=True)
    destino = os.path.join(AQUI, "fotos_hd.json")
    antigo = {}
    if os.path.exists(destino) and not lim:
        antigo = {}
    if os.environ.get("DEBUG"):
        return
    if os.environ.get("MARCAS") and os.path.exists(destino):
        velho = json.load(open(destino, encoding="utf-8"))
        velho = {k: v for k, v in velho.items() if k.split("|")[0] not in marcas}
        velho.update(res)
        res = velho
    json.dump(res, open(destino, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    rel = ["Fotografias de maior qualidade (só quando é a mesma foto que o catálogo já tinha)"]
    fr = os.path.join(AQUI, "fotos_hd_relatorio.txt")
    if os.environ.get("MARCAS") and os.path.exists(fr):
        for l in open(fr, encoding="utf-8").read().splitlines()[1:]:
            if l.split() and l.split()[0] not in marcas and l.split()[0] not in est:
                est[l.split()[0]] = l
    for m, e in sorted(est.items()):
        if isinstance(e, str):
            rel.append(e); continue
        rel.append("  %-11s total %5d · com foto maior %5d · fornecedor tem outra foto %4d · sem foto no fornecedor %4d" % (m, e["total"], e["com_hd"], e["foto_diferente"], e["sem_foto"]))
    open(os.path.join(AQUI, "fotos_hd_relatorio.txt"), "w", encoding="utf-8").write("\n".join(rel) + "\n")
    print("\n".join(rel))

main()
