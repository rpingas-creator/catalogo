"""Atribui uma categoria a artigos sem categoria, a partir do nome e do início da descrição.
Usado por construir.py para artigos novos."""
import re,json,gzip,unicodedata,collections,sys
def norm(s): return unicodedata.normalize("NFD",str(s or "").lower()).encode("ascii","ignore").decode()
R=["TopTex","Roly","JHK","THClothes","Valento"]
ROUPA=[
 ("Alta visibilidade",r"alta visib|refletor|high vis|hi-vis|\bhv\b"),
 ("Bebé",r"\bbebe|\bbaby|babete|body de|doudou|fralda|manta para bebe"),
 ("Calçado",r"sapat|botas?\b|tenis|sapatilh|chinel|sandalia|tamanco|calcado|socas?\b"),
 ("Meias Desportivas",r"\bmeias?\b|\bsocks?\b"),
 ("Luvas",r"\bluvas?\b|mitene"),
 ("Peluches",r"peluche|squidgy"),
 ("Equipamento de proteção",r"capacete|oculos|protector|protetor|auricular|viseira de prote|mascara|joelheira"),
 ("Profissional",r"fato-macaco|fato macaco|macacao|jardineira"),
 ("Gorros & Cachecóis",r"\bgorro|cachecol|bandana|balaclava|passa-montanhas|banda de cabeca|banda de pescoco|bandolete|headband|fita de cabeca|echarpe|lenco|gola polar|tubular de pescoco"),
 ("Bonés",r"\bbone|\bcap\b|viseira|trucker"),
 ("Chapéus",r"boina|chapeu|\bbucket|panama"),
 ("Aventais & Batas",r"avental|aventais|\bbata\b|jaleca|tunica|farda|cozinheir|jaleco|casaca de cozinha"),
 ("Roupa interior",r"cueca|boxer|soutien|pijama|roupa interior|camisola interior"),
 ("Vestidos & Saias",r"vestido|\bsaia"),
 ("Leggings",r"legging|collant"),
 ("Calções Desportivos",r"calcoes? (de )?(desporto|running|futebol|basket|padel|tenis)|short(s)? desport"),
 ("Calções",r"calcao|calcoes|bermuda|\bshorts?\b"),
 ("Fatos de treino",r"fato de treino|fato desportivo|conjunto de treino|tracksuit"),
 ("Calças",r"\bcalca|jogger|pantalona|jardineira|macacao|\bjeans?\b|chino"),
 ("Coletes",r"\bcolete|gilet|\bvest\b|bodywarmer"),
 ("Polares",r"polar\b|\bpolares|fleece|sherpa"),
 ("Casacos & Parkas",r"sobretudo|conjunto de chuva|casaco|parka|blusao|jaqueta|anorak|corta-vento|corta vento|impermeavel|softshell|kispo|blazer|gabardina|bomber|chubasquero|jacket"),
 ("Sweatshirts",r"sweat|hoodie|capuz|moletom"),
 ("Pullovers",r"pullover|camisola|cardigan|malha|tricot|jersey"),
 ("Camisas",r"\bcamisa\b|camisas|blusa"),
 ("Polos Desportivos",r"polo (tecnico|desportiv|sport)"),
 ("Polos Manga Comprida",r"polo.*manga comprida|manga comprida.*polo"),
 ("Polos",r"\bpolos?\b"),
 ("T-shirts Desportivas",r"t-shirt (tecnica|desportiv|sport|running)|camisola tecnica|t-shirt de desporto"),
 ("T-shirt Manga Cava",r"cai-cai|manga cava|alcas|regata|\btop\b|tank|camisola de alcas"),
 ("T-shirt Manga Comprida",r"t-shirt.*manga comprida|manga comprida"),
 ("T-shirt",r"t-shirt|tshirt|\btee\b|camiseta"),
 ("Mochilas & Malas",r"mochila|\bmalas?\b|trolley|backpack"),
 ("Sacos & Bolsas",r"\bsaco|bolsa|tote|necessaire|estojo|porta-computador|pochete|bolsinha|cesto|\bshopper"),
 ("Gravatas & Cintos",r"gravata|cinto|suspensorio|lacinho|papillon"),
 ("Toalhas & Roupões",r"toalha|roupao|\brobe\b|fouta|pareo|manta|cobertor|poncho"),
 ("Acessórios",r"."),
]
BRINDES=[
 ("Crachás & Lanyards",r"cracha|lanyard|fita porta|porta-cartoes de pescoco|identificador|porta-crachas|yoyo|yo-yo|porta-identificac|enrolador"),
 ("Porta-chaves",r"porta-chaves|porta chaves|chaveiro|\bkeyring"),
 ("Escrita",r"esferografic|caneta|\blapis|lapiseira|roller|marcador|marca-texto|sublinhador|conjunto (de )?escrita|apara-lapis|borracha|stylus|giz|aguarela|pinceis|lapis de cor|lapis de cera"),
 ("Cadernos & Blocos",r"caderno|bloco|agenda|notas|post-it|notebook|diario|moleskine|calendari|planner|memo"),
 ("Garrafas & Termos",r"garrafa|termo\b|termica|termico|cantil|squeeze|bidon"),
 ("Canecas & Copos",r"caneca|\bcopo|chavena|taca|\bmug|copos|shot|palhinha"),
 ("Geleiras & Lancheiras",r"geleira|lancheira|marmita|almoco|lunch|caixa (de|para) (almoco|refeic)|termica para|porta-alimentos|recipiente"),
 ("Guarda-chuvas",r"guarda-chuva|chapeu de chuva|guarda chuva|umbrella|sombrinha"),
 ("Tecnologia",r"carregador|suporte movel|acessorios de computador|power ?bank|bateria|cabo|auricular|fone|headphone|coluna|altifalante|speaker|smartwatch|relogio|\busb|pen drive|pendrive|\bpen\b|rato|\bhub\b|webcam|suporte (para|de) (telem|smartph|tablet|portatil)|telemovel|smartphone|bluetooth|wireless|sem fios|adaptador|ring light|tracker|localizador|lampada|candeeiro|led\b|selfie|tripe|cartao de memoria|leitor|teclado|tapete de rato"),
 ("Ferramentas & Lanternas",r"lanterna|x-ato|ferrament|canivete|multiferramenta|chave de fendas|fita metrica|nivel|alicate|martelo|x-acto|cortador|faca|raspador|kit de ferramentas|isqueiro|fosforo"),
 ("Viagem",r"viagem|balanca|bagagem|passaporte|almofada (de|para) pescoco|etiqueta de mala|cadeado|balanca de bagagem|porta-documentos|travel"),
 ("Saúde & Cuidado pessoal",r"escova|espelho|manicure|pedicure|higien|gel|sabonete|creme|protetor|desinfet|mascara|pastilheiro|pastilhas|comprimidos|caixa de comprimidos|primeiros socorros|lima de unhas|pente|escova de dentes|cosmetic|maquilhagem|termometro|massajador|toalhitas|batom|labios"),
 ("Casa & Cozinha",r"cozinha|natal|enfeite|sapateira|abridor|tabua|abre-garrafa|abre garrafa|saca-rolhas|vinho|cocktail|base para copos|bases para copos|individual|avental|pega|luva de forno|utensil|talher|prato|tigela|taça|bandeja|vela|difusor|aroma|decorac|moldura|porta-retratos|vaso|planta|semente|jardim|casa|saleiro|pimenteiro|especiaria|chaleira|cafeteira|cafe|cha\b|mel\b|chocolate|doces|rebucados|caixa de oferta|pano|esponja|organizador de cozinha|frigorifico|iman|ima\b|relogio de parede|almofada|tapete|cobertor|manta|caixa de arrumac|cesto|lanterna solar|churrasco|grelh"),
 ("Escritório",r"escritorio|regua|agrafador|clip|clipe|porta-cartoes|porta cartoes|cartao de visita|calculadora|organizador|pasta|capa|dossier|arquivador|porta-documentos|porta-canetas|porta-lapis|tesoura|fita-cola|carimbo|mousepad|suporte de secretaria|marcador de livros|pisa-papeis|bloco de secretaria|lupa|envelope"),
 ("Lazer & Desporto",r"bola|frisbee|jogo|puzzle|cartas|domino|xadrez|praia|chinelo|toalha|esteira|cadeira|guarda-sol|desporto|fitness|yoga|corda|garrafa desport|apito|braçadeira|bracadeira|bicicleta|ciclismo|campismo|tenda|hamac|piquenique|kite|papagaio|leque|abanico|paipai|pareo|bastoes|oculos de sol|oculos|binoculo|pesca|golfe|padel|raquete|bastao|antistress|anti-stress|cubo|spinner|insuflavel|balao|baloes|apito|futebol|claque|mao de espuma|sombreiro|chapeu de palha"),
 ("Crianças & Peluches",r"peluche|crianca|infantil|brinquedo|boneco|colorir|pintar|lapis de cor|mealheiro|baby|bebe|jogo infantil"),
 ("Medalhas & Troféus",r"medalha|trofeu|taca\b|pin\b|pins\b|emblema|botao|button|iman|souvenir|resina"),
 ("Pulseiras",r"pulseira"),
 ("Sacos & Bolsas",r"\bsaco|bolsa|tote|necessaire|estojo|shopper|pochete|porta-moedas|carteira|bolsinha|cesto|sacola|\bbag\b"),
 ("Mochilas & Malas",r"mochila|\bmalas?\b|trolley|maleta|backpack"),
 ("Bonés & Chapéus",r"\bbone|chapeu|viseira|gorro|cachecol|bandana"),
 ("Roupa & Têxtil",r"t-shirt|camisola|colete|casaco|polo|sweat|meias|luvas|avental|impermeavel|poncho"),
 ("Outros brindes",r"."),
]
def classify(x):
    t=norm(x["nome"]); d=norm(re.sub(r"^\s*duo concept \S+\s*","",norm(x.get("desc"))))
    d=" ".join(d.split()[:7])
    rules=ROUPA if x["mar"] in R else BRINDES
    for src in (t, t+" "+d):
        for cat,rx in rules:
            if rx=="." : continue
            if re.search(rx,src): return cat
    if x["mar"] in ("Roly","JHK","THClothes"):
        return "Sem categoria"
    return rules[-1][0]
