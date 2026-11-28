#!/usr/bin/env python3
"""Descarrega as fotografias de maior qualidade (lista em fonte/fotos_hd.json, só fotos
confirmadas como iguais às do catálogo) e guarda-as no próprio repositório, em img/,
com no máximo LADO px no lado maior. Atualiza dados.json.gz para os artigos que ainda
não tinham foto grande."""
import gzip, io, json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
LADO = int(os.environ.get("LADO") or 800)
QUAL = int(os.environ.get("QUALIDADE") or 82)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def get(url):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read()
        except Exception:
            pass
    return None

def pasta(mar):
    return re.sub(r"[^a-z0-9]", "", str(mar).lower())

def guardar(item):
    chave, url, destino = item
    if "cdn.toptex.com" in url:
        url = re.sub(r"\?w=\d+", "?w=%d" % max(LADO, 900), url)
    b = get(url)
    if not b:
        return chave, None, 0
    try:
        im = Image.open(io.BytesIO(b)); im.load()
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA"); f = Image.new("RGB", im.size, (255, 255, 255)); f.paste(im, mask=im.split()[-1]); im = f
        im = im.convert("RGB")
        im.thumbnail((LADO, LADO), Image.LANCZOS)
        out = io.BytesIO(); im.save(out, "JPEG", quality=QUAL, optimize=True, progressive=True)
        os.makedirs(os.path.dirname(os.path.join(RAIZ, destino)), exist_ok=True)
        open(os.path.join(RAIZ, destino), "wb").write(out.getvalue())
        return chave, destino, len(out.getvalue())
    except Exception:
        return chave, None, 0

def main():
    hd = json.load(open(os.path.join(AQUI, "fotos_hd.json"), encoding="utf-8"))
    caminho = os.path.join(AQUI, "dados.json.gz")
    dados = json.load(gzip.open(caminho, "rt", encoding="utf-8"))
    por = {"%s|%s" % (x.get("mar"), x.get("ref")): x for x in dados}
    trabalho = []
    for chave, url in hd.items():
        x = por.get(chave)
        if not x:
            continue
        big = str(x.get("big") or "")
        if not big or big.startswith("http"):
            big = "img/%s/%s.jpg" % (pasta(x["mar"]), re.sub(r"[^A-Za-z0-9._-]", "_", str(x["ref"])))
        trabalho.append((chave, url, big))
    lim = int(os.environ.get("LIMITE") or 0)
    if lim:
        trabalho = trabalho[:lim]
    ok = falhou = tot = 0
    with ThreadPoolExecutor(16) as ex:
        for i, (chave, destino, n) in enumerate(ex.map(guardar, trabalho)):
            if destino:
                ok += 1; tot += n
                x = por[chave]
                if x.get("big") != destino or not x.get("gbig"):
                    x["big"] = destino; x["gbig"] = 1
            else:
                falhou += 1
            if i % 500 == 0:
                print(i, "de", len(trabalho), flush=True)
    with gzip.open(caminho, "wt", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
    print("Guardadas %d fotografias (%d MB, média %d KB); %d falharam." % (ok, tot // 1048576, tot // max(ok, 1) // 1024, falhou))

main()
