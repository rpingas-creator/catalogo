#!/usr/bin/env python3
"""Reconstrói index.html só com os artigos que existem na calculadora.
Lê (fornecedor, referência, nome) da função pública catalogo_lista() do Supabase
(não expõe custos). Se algo falhar, não altera nada."""
import gzip, json, os, re, sys, urllib.request

URL = "https://mocvrclxtuvdlowaihgd.supabase.co"
KEY = "sb_publishable_v8lxMKraPxlZtyYRlPqxlQ_Lq4q6jsI"
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
RAIZ = os.path.dirname(AQUI)

def chave(sup, ref):
    return re.sub(r"\s+", "", str(sup or "")).lower() + "|" + str(ref or "").strip().lower()

def nucleo(sup, ref):
    """Referência normalizada: a calculadora e o catálogo escrevem algumas referências de forma diferente."""
    import unicodedata
    s = "".join(c for c in unicodedata.normalize("NFD", str(ref or "").strip().upper()) if unicodedata.category(c) != "Mn")
    f = re.sub(r"\s+", "", str(sup or "")).lower()
    if f == "thclothes":
        return re.sub(r"^THC-", "", s).replace("-", " ")
    if f in ("roly", "stamina", "tejobrinde"):
        s = re.sub(r"^[A-Z]{1,3}(?=\d)", "", s)
        s = s.lstrip("0") or "0"
    return s

def sem_acentos(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower().strip()) if unicodedata.category(c) != "Mn")

def lista_calculadora(rpc="catalogo_lista2"):
    teste = os.environ.get("LISTA_TESTE")
    if teste:
        return json.load(open(teste, encoding="utf-8"))
    out, desde, passo = [], 0, 1000
    while True:
        req = urllib.request.Request(
            URL + "/rest/v1/rpc/" + rpc,
            data=json.dumps({"de": desde, "n": passo}).encode(),
            headers={"apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            lote = json.load(r)
        out += lote
        if len(lote) < passo:
            return out
        desde += passo

def main():
    try:
        lista = lista_calculadora()  # inclui cores e tamanhos (sem custos)
    except Exception as ex:
        print("catalogo_lista2 indisponível (%s); a usar catalogo_lista (sem tamanhos)." % ex)
        lista = lista_calculadora("catalogo_lista")
    if len(lista) < 100:
        sys.exit("Lista da calculadora demasiado pequena (%d). Nada foi alterado." % len(lista))
    calc = {chave(p["sup"], p["ref"]): p for p in lista}
    calc_src, nuc_src = {}, {}
    nuc = {}
    for p in lista:
        nuc.setdefault(re.sub(r"\s+", "", str(p["sup"])).lower() + "|" + nucleo(p["sup"], p["ref"]), p)
        base = nucleo(p["sup"], p["ref"]).split("-")[0]
        nuc.setdefault(re.sub(r"\s+", "", str(p["sup"])).lower() + "|" + base, p)
    dados = json.load(gzip.open(os.path.join(AQUI, "dados.json.gz"), "rt", encoding="utf-8"))
    for x in dados:
        k = re.sub(r"\s+", "", str(x.get("mar"))).lower()
        calc_src[chave(x.get("mar"), x.get("ref"))] = x
        nuc_src.setdefault(k + "|" + nucleo(x.get("mar"), x.get("ref")), x)
    ficam, nomes, clones, sem, tamanhos, cores = [], 0, 0, 0, 0, 0
    usados = set()
    fotos = {}
    mar_de = {}
    for x in dados:
        mar_de.setdefault(re.sub(r"\s+", "", str(x.get("mar"))).lower(), x.get("mar"))
    for p in lista:
        k = re.sub(r"\s+", "", str(p["sup"])).lower()
        x = calc_src.get(chave(p["sup"], p["ref"])) or nuc_src.get(k + "|" + nucleo(p["sup"], p["ref"])) or nuc_src.get(k + "|" + nucleo(p["sup"], p["ref"]).split("-")[0])
        if x is not None:
            e = dict(x)
            if id(x) in usados:
                e["ref"] = str(p["ref"]); clones += 1
            usados.add(id(x))
        else:
            e = {"ref": str(p["ref"]), "nome": p.get("name") or str(p["ref"]), "cat": "Sem categoria", "desc": "", "gsm": "", "comp": "", "pers": "", "sz": "", "cols": [], "img": "", "mar": mar_de.get(k, p["sup"])}
            sem += 1
        if p.get("name") and p["name"] != e.get("nome"):
            e["nome"] = p["name"]; nomes += 1
        tam = [t.strip() for t in re.split(r"[,;]", str(p.get("sizes") or "")) if t.strip()]
        if tam and x is not None and k in ("roly", "jhk"):  # fornecedores com tamanhos refeitos a partir do site
            e["sz"] = "; ".join(tam); tamanhos += 1
        cal = {sem_acentos(c) for c in re.split(r"[,;]", str(p.get("colors") or "")) if c.strip()}
        if cal and x is not None and e.get("cols") and k in ("roly", "jhk"):
            fil = [c for c in e["cols"] if sem_acentos(c.get("n")) in cal]
            if fil and len(fil) < len(e["cols"]) and len({sem_acentos(c.get("n")) for c in fil}) >= 0.9 * len(cal):  # só se os nomes coincidirem
                e["cols"] = fil; cores += 1
        if (e.get("cat") or "Sem categoria") == "Sem categoria":
            try:
                from categorias import classify
                e["cat"] = classify(e)
            except Exception:
                pass
        ficam.append(e)
        big = str(e.get("big") or "")
        if big and not big.startswith("http"):
            fc = {str(c.get("n")): c["ph"] for c in (e.get("cols") or []) if c.get("ph")}
            fotos[chave(p["sup"], p["ref"])] = [big, fc] if fc else [big]
    if sem > 0.5 * len(lista):
        sys.exit("Só %d de %d artigos da calculadora têm dados no catálogo. Nada foi alterado." % (len(lista) - sem, len(lista)))
    # fotografias para a calculadora (ecrã de produtos com fotos): fornecedor|referência -> [foto, {cor: foto}]
    fj = json.dumps(fotos, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    fp = os.path.join(RAIZ, "fotos.json")
    if not os.path.exists(fp) or open(fp, encoding="utf-8").read() != fj:
        open(fp, "w", encoding="utf-8").write(fj)
        print("fotos.json: %d artigos com fotografia." % len(fotos))
    tpl = open(os.path.join(AQUI, "template.html"), encoding="utf-8").read()
    html = tpl.replace("__DATA__", json.dumps(ficam, ensure_ascii=False, separators=(",", ":")))
    destino = os.path.join(RAIZ, "index.html")
    antigo = open(destino, encoding="utf-8").read() if os.path.exists(destino) else ""
    if html == antigo:
        print("Sem alterações."); return
    open(destino, "w", encoding="utf-8").write(html)
    print("Catálogo reconstruído: %d artigos (%d da calculadora; %d sem ficha na fonte; %d duplicados; %d nomes, %d tamanhos e %d listas de cores atualizados)." % (len(ficam), len(lista), sem, clones, nomes, tamanhos, cores))

main()
