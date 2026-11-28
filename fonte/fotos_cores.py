#!/usr/bin/env python3
"""Fotografia de cada cor de cada artigo, a partir dos sites oficiais dos fornecedores.
Guarda as fotos em img/cores/<marca>/ (máx. LADO px) e liga-as às cores em dados.json.gz
(campo "ph" de cada cor), que o catálogo usa quando se escolhe uma cor."""
import gzip, hashlib, html, io, json, os, re, unicodedata, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
LADO = int(os.environ.get("LADO") or 500)
QUAL = int(os.environ.get("QUALIDADE") or 80)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def get(url, timeout=30):
    for _ in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                if r.status == 200:
                    return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                return None
        except Exception:
            pass
    return None

def sem_ac(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)

def pasta(m):
    return re.sub(r"[^a-z0-9]", "", str(m).lower())

def seguro(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(s))

PH = {}
def assin(b):
    try:
        im = Image.open(io.BytesIO(b)); im.load()
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA"); f = Image.new("RGB", im.size, (255, 255, 255)); f.paste(im, mask=im.split()[-1]); im = f
        return list(im.convert("L").resize((16, 24)).getdata())
    except Exception:
        return None

def toptex_ph():
    if "tt" not in PH:
        b = get("https://cdn.toptex.com/packshots/PS_ZZZ999_ZZZZZ.png?w=%d" % LADO)
        PH["tt"] = assin(b) if b else None
    return PH["tt"]

def e_generica(b):
    a, p = assin(b), toptex_ph()
    if not a or not p:
        return False
    return sum(abs(x - y) for x, y in zip(a, p)) / len(a) < 4

def toptex_codigos(R):
    """Códigos das fotos por cor (PS_<REF>_<CÓDIGO>.png) na página oficial do artigo."""
    h = (get("https://www.toptex.pt/catalogsearch/result/?q=" + urllib.parse.quote(R)) or b"").decode("utf-8", "ignore")
    m = re.search(r'href="(https://www\.toptex\.pt/%s-[^"?#]+\.html)"' % re.escape(R.lower()), h)
    if not m:
        return []
    pg = (get(m.group(1)) or b"").decode("utf-8", "ignore")
    return list(dict.fromkeys(re.findall(r"cdn\.toptex\.com/packshots/PS_%s_([A-Z0-9]+)\.png" % re.escape(R), pg, re.I)))

def tejo_cores(ref):
    """Lê a tabela de cores da página oficial do artigo: [(nome da cor, código)]."""
    b = get("https://www.tejobrinde.pt/pt-pt/detalhe-produto/" + urllib.parse.quote(ref))
    if not b:
        return []
    t = b.decode("utf-8", "ignore")
    i = t.find('id="color_table"')
    if i < 0:
        return []
    t = t[i:t.find("</table>", i)]
    out = []
    for tr in re.findall(r"<tr.*?</tr>", t, re.S):
        m = re.search(r"/%s_([A-Za-z0-9]+)_t\.JPG" % re.escape(ref), tr, re.I)
        if not m:
            continue
        tds = [html.unescape(re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        nomes = [re.sub(r"\s+", " ", x) for x in tds if x and not re.fullmatch(r"[A-Za-z0-9]{1,4}", x.strip())]
        out.append((nomes[0] if nomes else "", m.group(1)))
    return out

def candidatos(x, c, extra):
    mar, ref, cod = x.get("mar"), str(x.get("ref") or "").strip(), str(c.get("c") or "").strip()
    if mar == "TopTex" and cod:
        k = re.sub(r"[^A-Z0-9]", "", cod.upper())
        if extra:
            ks = [e for e in extra if e.upper() == k] or [e for e in extra if sem_ac(e) == sem_ac(c.get("n"))]
            if not ks:
                return []
            k = ks[0].upper()
        return [("tt", "https://cdn.toptex.com/packshots/PS_%s_%s.png?w=%d" % (ref.upper(), k, LADO))]
    if mar in ("Roly", "Stamina") and re.fullmatch(r"\d{1,4}", cod):
        m = re.match(r"^[A-Za-z]*(\d+)", ref)
        if not m:
            return []
        n = m.group(1); B = "https://static.gorfactory.es/images/models/%s/" % n
        return [("gf", B + "views/large/p_%s_%s_1_1.jpg" % (n, cod)), ("gf", B + "model/large/%s_%s_1_1.jpg" % (n, cod))]
    if mar == "JHK" and cod:
        return [("jk", "https://s3-eu-west-1.amazonaws.com/resources.jhktshirt.com/pictures/sku/jhktshirt_%s_%s.jpg" % (ref.lower(), cod.lower()))]
    if mar == "TejoBrinde":
        alvo = [sem_ac(c.get("c")), sem_ac(c.get("n"))]
        for nome, k in extra:
            s = sem_ac(nome)
            if s and any(a and (s == a or s.startswith(a) or a.startswith(s)) for a in alvo):
                return [("tb", "https://www.tejobrinde.pt/resources/Imagens_500x500/%s_%s.JPG" % (ref, k))]
    return []

def guardar_img(b, destino):
    im = Image.open(io.BytesIO(b)); im.load()
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); f = Image.new("RGB", im.size, (255, 255, 255)); f.paste(im, mask=im.split()[-1]); im = f
    im = im.convert("RGB"); im.thumbnail((LADO, LADO), Image.LANCZOS)
    out = io.BytesIO(); im.save(out, "JPEG", quality=QUAL, optimize=True, progressive=True)
    os.makedirs(os.path.dirname(os.path.join(RAIZ, destino)), exist_ok=True)
    open(os.path.join(RAIZ, destino), "wb").write(out.getvalue())
    return len(out.getvalue())

def artigo(x):
    """Devolve [(índice da cor, caminho)] e bytes gravados."""
    extra = tejo_cores(str(x.get("ref"))) if x.get("mar") == "TejoBrinde" else toptex_codigos(str(x.get("ref")).upper()) if x.get("mar") == "TopTex" else []
    res, tot, feitos = [], 0, {}
    for i, c in enumerate(x.get("cols") or []):
        for tipo, url in candidatos(x, c, extra):
            if url in feitos:
                res.append((i, feitos[url])); break
            b = get(url)
            if not b or len(b) < 800:
                continue
            if tipo == "tt" and e_generica(b):
                continue
            destino = "img/cores/%s/%s__%s.jpg" % (pasta(x["mar"]), seguro(x["ref"]), seguro(sem_ac(c.get("c") or c.get("n")) or i))
            try:
                tot += guardar_img(b, destino)
            except Exception:
                continue
            feitos[url] = destino
            res.append((i, destino)); break
    return res, tot

def main():
    caminho = os.path.join(AQUI, "dados.json.gz")
    dados = json.load(gzip.open(caminho, "rt", encoding="utf-8"))
    marcas = set((os.environ.get("MARCAS") or "TopTex,Roly,Stamina,TejoBrinde,JHK").split(","))
    itens = [x for x in dados if x.get("mar") in marcas and x.get("cols")]
    lim = int(os.environ.get("LIMITE") or 0)
    if lim:
        itens = itens[:lim]
    toptex_ph()
    est, total = {}, 0
    with ThreadPoolExecutor(int(os.environ.get("FIOS") or 16)) as ex:
        for j, (x, (res, tot)) in enumerate(zip(itens, ex.map(artigo, itens))):
            e = est.setdefault(x["mar"], [0, 0, 0])
            e[0] += len(x["cols"]); e[1] += len(res); total += tot
            if res:
                e[2] += 1
            for i, d in res:
                x["cols"][i]["ph"] = d
            if j % 500 == 0:
                print(j, "de", len(itens), flush=True)
    with gzip.open(caminho, "wt", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
    rel = ["Fotografias por cor (img/cores, máx. %d px) — %d MB" % (LADO, total // 1048576)]
    for m, (n, ok, art) in sorted(est.items()):
        rel.append("  %-11s cores %6d · com foto %6d (%d%%) · artigos com fotos por cor %5d" % (m, n, ok, ok * 100 // max(n, 1), art))
    open(os.path.join(AQUI, "fotos_cores_relatorio.txt"), "w", encoding="utf-8").write("\n".join(rel) + "\n")
    print("\n".join(rel))

main()
