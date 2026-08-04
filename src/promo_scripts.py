"""
Genera lo script vocale per un video promo a partire dal titolo prodotto,
senza bisogno di una chiave Claude (questa pipeline gira in locale via
Task Scheduler, senza .env con ANTHROPIC_API_KEY - vedi generate_promo_videos.py
per il precedente approccio a script scritti a mano uno per uno).

Stile: hook basato su un problema comune della nicchia (mai "compra questo
prodotto" diretto), poi il prodotto come soluzione, poi CTA. Stessa
struttura dei copioni scritti a mano che hanno gia' generato i primi 8
video (vedi src/jobs/generate_promo_videos.py), ma parametrizzata cosi'
copre tutti i 48 prodotti del catalogo senza doverli scrivere a mano uno
per uno.
"""
import random

PET_KEYWORDS = (
    "dog", "cat", "pet", "paw", "puppy", "leash", "collar", "grooming",
    "nail", "feeder", "treat", "kennel", "harness",
)
TECH_KEYWORDS = (
    "phone", "magsafe", "wireless", "charger", "car mount", "holder",
    "cable", "usb", "earbuds", "watch", "stand", "mount",
)
# Terzo brand (Beffante, 2026-08-03): tech "da casa/scrivania" - proiettori,
# webcam, speaker, smartwatch, power bank, videosorveglianza. Confina con
# Magdock, che invece resta sugli accessori PER TELEFONO: per questo va
# testato PRIMA di TECH in _detect_niche, altrimenti parole come "watch" o
# "speaker" lo dirotterebbero su Magdock (account e token sbagliati).
# Questa e' la lista canonica: src/jobs/daily_promo.py la importa da qui
# invece di tenerne una copia propria, cosi' le due non possono divergere.
HOME_KEYWORDS = (
    "projector", "webcam", "speaker", "smartwatch", "smart watch",
    "laptop", "power bank", "security", "computer camera", "web camera",
    "beauty camera", "wifi camera", "home camera", "fill light",
)

_CTA = "Shop the link in our bio 🛒"

# Aggiunte 2026-08-02: la ricerca 2026 (Hootsuite, TrueFuture Media,
# Eclincher) conferma che share/save sono il segnale di ranking piu' pesato
# su Instagram/TikTok (una DM share vale 3-10x un like) - prima OGNI caption
# chiudeva solo con "shop the link", zero richiesta esplicita di salvare o
# condividere, il che significa non attivare mai il segnale piu' forte che
# l'algoritmo guarda. Queste si aggiungono in rotazione, mantenendo comunque
# il link in bio.
# Bug trovato con un audit su 400 generazioni (2026-08-02): concatenando
# queste con _CTA il carrello finiva DUE volte nella stessa caption
# ("...forget 🛒 Shop the link in our bio 🛒") sul 51% dei video. Era
# visibile anche nel mio test a campione e mi era sfuggito - contare i
# difetti su tutto il pool lo ha reso ovvio. Ora la parte "shop" e' senza
# emoji e l'emoji compare una sola volta, in chiusura.
_SHOP_TEXT = "Shop the link in our bio"
_SHARE_CTAS = [
    f"Save this before you forget. {_SHOP_TEXT} 🛒",
    f"Tag someone who needs this. {_SHOP_TEXT} 🛒",
    f"Send this to a friend who'd actually use it. {_SHOP_TEXT} 🛒",
]

# Nota sui pattern di hook (aggiornato 2026-08-03): i test 2026 su 30 hook
# virali danno solo 4 famiglie sopra quota 70 - Identity Call, Contrarian
# Strike, Open Loop, Confession - con Identity Call primo assoluto (85 di
# media) perche' nomina in faccia il pubblico a cui parla. Mancava del tutto
# in entrambe le nicchie, aggiunto ora.
PET_HOOKS = [
    "If you have a dog that sheds all year, this one's for you.",
    "Golden retriever owners already know where this is going.",
    "If your dog hates this every single time, you're probably doing it wrong.",
    "Nobody tells you this before you get a dog, until it's too late.",
    "This is the mistake almost every dog owner makes without realizing it.",
    "If your dog destroys everything when you leave the house, it's not bad behavior, it's boredom.",
    "Multiple dogs, one afternoon, and it used to be complete chaos.",
    "The difference between a stressed dog and a calm one is smaller than you think.",
]
PET_RESOLUTIONS = [
    "Here's what actually works.",
    "This changes everything.",
    "Here's the fix nobody talks about.",
    "This solved it in one try.",
]

TECH_HOOKS = [
    "If you drive with your phone on the dashboard, watch this.",
    "iPhone users with a MagSafe case: this is the part nobody mentions.",
    "The difference between cheap and good only shows up when it's already too late.",
    "I stress-tested this so you don't have to.",
    "Your phone keeps sliding every time you brake, and there's a reason for that.",
    "One clean setup instead of a tangled mess of cables every night.",
    "POV: your phone never falls again.",
    "Most people find out this breaks the hard way.",
]
TECH_RESOLUTIONS = [
    "This one actually holds.",
    "Five second install, never taking it off.",
    "Worth the extra couple of euros over the cheap version.",
    "Smooth, solid, no more excuses.",
]


# Hook specifici per SOTTOCATEGORIA di prodotto (aggiunti 2026-08-02).
# Prima l'hook veniva pescato a caso dal pool generico della nicchia, quindi
# capitava (verificato su un render reale) un video con hook "Multiple dogs,
# one afternoon, and it used to be complete chaos" - che parla di toelettatura
# - montato su un distributore di crocchette. Chi resta per l'hook e poi vede
# un prodotto che non c'entra si sente ingannato e scrolla a meta' video:
# retention distrutta proprio dove l'algoritmo la misura (checkpoint 3/10/20s).
SUBCATEGORY_KEYWORDS = {
    "PET_GROOMING": ("brush", "comb", "nail", "clipper", "shampoo", "bath", "deshedding", "hair remover", "grooming", "trimmer"),
    "PET_FEEDING": ("feeder", "bowl", "food", "treat", "puzzle", "slow", "water", "bottle", "dispenser", "leakage"),
    "PET_COMFORT": ("bed", "mat", "pad", "cooling", "pillow", "blanket", "sleeping", "cushion"),
    "PET_WALKING": ("leash", "collar", "harness", "poop", "walking"),
    "PET_TOYS": ("toy", "ball", "chew", "interactive", "rope"),
    "TECH_CHARGING": ("charger", "charging", "wireless", "magsafe", "power", "cable", "usb", "adapter"),
    "TECH_CAR": ("car", "mount", "dashboard", "vent", "navigation", "bracket"),
    "TECH_CASE": ("case", "cover", "protective", "wallet", "card holder", "lanyard", "crossbody"),
    "TECH_DESK": ("organizer", "stand", "desk", "storage", "bag", "holder"),
    # Beffante (2026-08-04): stesse quattro famiglie di prodotto che compongono
    # HOME_KEYWORDS, ma separate per non ripetere lo stesso hook generico su
    # una webcam, un proiettore e uno smartwatch - esattamente il difetto gia'
    # risolto una volta per Groomlyco/Magdock.
    "HOME_STREAMING": ("webcam", "computer camera", "web camera", "beauty camera", "fill light", "ring light"),
    "HOME_SECURITY": ("security", "wifi camera", "home camera", "surveillance", "doorbell"),
    "HOME_ENTERTAINMENT": ("projector", "speaker"),
    "HOME_WEARABLE": ("smartwatch", "smart watch", "fitness tracker"),
    "HOME_WORKSPACE": ("laptop", "power bank"),
}

SUBCATEGORY_HOOKS = {
    # Pool ampliati da 3 a 6-7 hook ciascuno (2026-08-02): un audit su 400
    # generazioni ha mostrato solo 29 hook/titoli distinti in totale, cioe'
    # a 2-4 video al giorno ci si ripeteva ogni ~10 giorni. Gli archetipi
    # sono volutamente diversi tra loro (prima persona / conseguenza / POV /
    # momento specifico / mito da smontare) invece di variazioni della stessa
    # formula, che sarebbero varieta' solo apparente.
    #
    # Ricerca trend 2026-08-03 (routine di manutenzione, non audit): due
    # sottocategorie hanno le KEYWORD piu' larghe dei loro HOOK, cioe'
    # esattamente il difetto di coerenza che questo file dice di voler
    # evitare (vedi commento sopra SUBCATEGORY_KEYWORDS).
    #  - PET_FEEDING include "water"/"bottle"/"dispenser" tra le keyword, ma
    #    tutti gli hook parlavano solo di velocita' nel mangiare/ciotole. Le
    #    borracce/dispenser d'acqua portatili per cani sono indicate come
    #    prodotto vincente 2026 da piu' fonti indipendenti: Zendrop
    #    (https://www.zendrop.com/blog/dropshipping-pet-products/),
    #    CJdropshipping (https://cjdropshipping.com/blogs/dropshipping-niches/Best-Dropshipping-Pet-Products),
    #    PB Fulfill (https://pbfulfill.com/blogs/marketing-strategy/tiktok-viral-pet-products-to-dropship).
    #    Se un prodotto del genere entra in catalogo, prima avrebbe ricevuto
    #    un hook su "mangia troppo in fretta" incoerente col prodotto reale.
    #  - TECH_CASE include "wallet"/"card holder"/"crossbody" tra le keyword,
    #    e infatti 3 dei 6 prodotti Magdock gia' promossi in
    #    data/promo_content_log.json sono case a portafoglio ("Flip Phone
    #    Case Cover Card Wallet", "...Card Wallet Leather Case", "Card Fold
    #    Skin Feeling Wallet Mobile Phone Case") - ma tutti gli hook
    #    esistenti parlano solo di resistenza agli urti/cadute, non del vero
    #    motivo per cui si compra una wallet case (smettere di portare un
    #    portafoglio separato). Mismatch gia' capitato su video reali, non
    #    ipotetico.
    "PET_GROOMING": [
        "If your dog hates this every single time, you're probably doing it wrong.",
        "This is the mistake almost every dog owner makes while grooming.",
        "Grooming used to take two people and end in a wet bathroom floor.",
        "My dog used to hide the second he heard the clippers come out.",
        "Nobody tells you the groomer bill adds up to a holiday every year.",
        "The trick isn't holding him still, it's what you do before that.",
        "Ten minutes at home beats an hour of wrestling at the salon.",
    ],
    "PET_FEEDING": [
        "If your dog inhales dinner in nine seconds flat, that's a real problem.",
        "Nobody warns you that eating too fast is what makes dogs sick later.",
        "A bored dog and a full bowl is a worse combination than it sounds.",
        "My vet asked one question about mealtimes and it explained everything.",
        "Your dog isn't greedy, the bowl is just the wrong shape.",
        "The bloating scare cost me a night at the emergency vet.",
        "He used to drink from puddles on every walk because I forgot water.",
        "A thirsty dog on a hot walk is how a good afternoon turns into a vet visit.",
        "Carrying an open cup of water for him never once worked.",
    ],
    "PET_COMFORT": [
        "If your dog can't settle in summer, it's not restlessness, it's the heat.",
        "Most dog beds stop working exactly when your dog needs them most.",
        "There's a reason your dog abandons the bed and lies on the tiles.",
        "I kept turning the AC up for a dog who just needed a cold surface.",
        "Panting through the night isn't normal, it's a signal.",
        "The floor is winning against a bed you paid good money for.",
    ],
    "PET_WALKING": [
        "If your dog pulls the whole walk, the leash is half the problem.",
        "The mistake almost everyone makes on walks shows up months later.",
        "One bad harness is how a normal walk turns into a fight.",
        "My shoulder gave out before my dog's enthusiasm ever did.",
        "Pulling isn't disobedience, it's leverage, and you're losing it.",
        "The walk got easier the day I stopped blaming the dog.",
    ],
    "PET_TOYS": [
        "If your dog destroys everything when you leave, it's not bad behavior, it's boredom.",
        "Most dog toys are dead in a day, and that's the actual problem.",
        "A dog that never gets bored behaves completely differently.",
        "I came home to a shredded sofa and finally understood the pattern.",
        "The chewing stops when the brain has something else to do.",
        "You're not buying a toy, you're buying twenty quiet minutes.",
    ],
    "TECH_CHARGING": [
        "One clean setup instead of a tangled mess of cables every night.",
        "Cheap chargers fail in the one moment you actually needed them.",
        "If your phone charges slower than it used to, it might not be the battery.",
        "I found out mine was faulty at four percent in an airport.",
        "Three cables on the nightstand and none of them the right one.",
        "The cable isn't broken, it's just never been fast in the first place.",
    ],
    "TECH_CAR": [
        "Your phone keeps sliding every time you brake, and there's a reason for that.",
        "POV: your phone never falls off the dashboard again.",
        "The difference between a cheap mount and a good one shows up at the first pothole.",
        "Mine let go on a roundabout and I fished it out of the footwell.",
        "Looking down for two seconds is the whole reason this exists.",
        "Every cheap mount holds fine until the road stops being smooth.",
    ],
    "TECH_CASE": [
        "I stress-tested this case so you don't have to.",
        "Most people find out their case is useless the hard way.",
        "The drop that kills your phone is never the one you expect.",
        "Waist height onto tile is what actually breaks screens, not big falls.",
        "A repair quote costs more than every case I've ever bought combined.",
        "Thin and protective used to be a trade-off. It isn't anymore.",
        "I stopped carrying a separate wallet the day I got one of these.",
        "Losing my actual wallet twice in a year is what finally got me to switch.",
        "Cards, cash, ID, one thing in my pocket instead of two.",
    ],
    "TECH_DESK": [
        "One bag instead of digging through a drawer of tangled cables.",
        "If your desk eats every cable you own, this is why.",
        "Packing tech used to mean forgetting exactly one essential thing.",
        "I've bought the same charger three times because I couldn't find it.",
        "The drawer isn't messy, it just has no system at all.",
        "Five minutes of packing turns into twenty when nothing has a place.",
    ],
    "HOME_STREAMING": [
        "If your laptop webcam makes you look like you're in a hostage video, this is for you.",
        "Nobody tells you the built-in camera is the reason you look tired on every call.",
        "This is the setup that made my streams look like a different channel.",
        "The lighting was never the problem, the camera was.",
        "I upgraded this and people asked what changed about my whole setup.",
        "Every video call looked worse than it needed to, for one cheap reason.",
    ],
    "HOME_SECURITY": [
        "I checked my home security footage and immediately ordered a second one.",
        "POV: you finally see who rang the doorbell before opening the door.",
        "Nobody mentions this until after a package goes missing once.",
        "The peace of mind is worth more than the price tag.",
        "I used to guess who was at the door. Now I just check my phone.",
        "This caught something I never would have believed without the footage.",
    ],
    "HOME_ENTERTAINMENT": [
        "The projector made movie night better than the actual cinema.",
        "Anyone still watching movies on a laptop screen: this is for you.",
        "One speaker changed how every party at my place feels.",
        "I didn't expect a projector this size to actually be watchable.",
        "This turned a blank wall into the best screen in the house.",
        "The sound alone made the TV speakers feel pointless.",
    ],
    "HOME_WEARABLE": [
        "Most smartwatches die by day three, this is the one that didn't.",
        "I stopped checking my phone every five minutes once I got this.",
        "Nobody tells you battery life is the only spec that actually matters.",
        "This tracked something about my sleep I never would have noticed.",
        "The one feature I thought was gimmicky turned out to be the best part.",
        "I replaced my old one for a battery that didn't die by lunch.",
    ],
    "HOME_WORKSPACE": [
        "If you work from home, this is the upgrade nobody suggests.",
        "Anyone with a desk setup: this is the piece you're missing.",
        "My laptop stopped dying mid-call once I fixed this one thing.",
        "The cheap version breaks exactly when you need it most.",
        "I tested this for a week before I believed it.",
        "This costs less than what you're replacing every year.",
    ],
}


_SUBCATEGORY_PREFIX = {"PET": "PET_", "TECH": "TECH_", "HOME": "HOME_"}


def _detect_subcategory(title: str, niche: str) -> str:
    """Bug trovato 2026-08-04: prima del terzo brand (Beffante/HOME) questa
    funzione usava 'prefix = PET_ if niche == PET else TECH_' - qualunque
    niche diversa da PET cadeva su TECH_, quindi un prodotto HOME (es. una
    webcam) veniva confrontato con le sottocategorie TECH_* e "usb"
    (TECH_CHARGING) gli assegnava un hook su caricabatterie che si scaricano,
    lo stesso tipo di incoerenza hook/prodotto gia' corretta una volta per
    Groomlyco/Magdock. Ora ogni niche cerca solo nelle proprie sottocategorie."""
    t = title.lower()
    prefix = _SUBCATEGORY_PREFIX.get(niche, "TECH_")
    best, best_hits = None, 0
    for sub, keywords in SUBCATEGORY_KEYWORDS.items():
        if not sub.startswith(prefix):
            continue
        hits = sum(1 for k in keywords if k in t)
        if hits > best_hits:
            best, best_hits = sub, hits
    return best


def _detect_niche(title: str) -> str:
    t = title.lower()
    if any(k in t for k in PET_KEYWORDS):
        return "PET"
    # HOME prima di TECH: le due si sovrappongono ("watch" -> smartwatch,
    # "speaker", "camera") e il piu' specifico deve vincere, altrimenti i
    # prodotti Beffante finirebbero pubblicati sull'account Magdock.
    if any(k in t for k in HOME_KEYWORDS):
        return "HOME"
    if any(k in t for k in TECH_KEYWORDS):
        return "TECH"
    return "PET" if random.random() < 0.5 else "TECH"


# Chiusura del voiceover. Prima era la stringa fissa "Look at the result."
# su OGNI video di entrambi i brand: la frase finale, cioe' quella che resta
# in testa e su cui si decide se salvare/condividere, era identica ovunque -
# uno dei segnali piu' riconoscibili di contenuto generato in serie.
#
# Alcune varianti spingono save/share invece del solo "guarda": la ricerca
# 2026 gia' applicata alle caption dice che condivisioni e salvataggi pesano
# 3-10x piu' dei like nella distribuzione.
# NB: le chiusure si scelgono per NICCHIA (pet/tech), non per sottocategoria,
# quindi devono restare valide per qualunque prodotto della nicchia. Un primo
# tentativo includeva "Save this before your next grooming day", che finiva
# anche su una ciotola anti-ingozzamento - incoerente col resto dello script.
PET_CLOSERS = [
    "Look at the difference.",
    "Watch what happens.",
    "Save this before you forget.",
    "Send this to someone with a dog.",
    "The change is immediate.",
    "Try it once and you'll see.",
]
TECH_CLOSERS = [
    "Look at the difference.",
    "Watch what happens.",
    "Save this for later.",
    "Send this to someone who needs it.",
    "One setup and it's done.",
    "Try it once and you'll see.",
]
HOME_CLOSERS = [
    "Look at the difference.",
    "Watch what happens.",
    "Save this for the next setup.",
    "Send this to someone building a desk setup.",
    "Plug it in once and forget about it.",
    "Try it once and you'll see.",
]

# Beffante: tech da casa/scrivania. Stessi 4 pattern di hook che reggono nel
# 2026 (Identity Call in testa, poi Contrarian/Open Loop/Confession), gia'
# applicati a Groomlyco e Magdock.
HOME_HOOKS = [
    "If you work from home, this is the upgrade nobody suggests.",
    "Anyone with a desk setup: this is the piece you're missing.",
    "The cheap version breaks exactly when you need it most.",
    "I tested this for a week before I believed it.",
    "Nobody mentions this until after you've already bought the wrong one.",
    "This costs less than what you're replacing every year.",
]
HOME_RESOLUTIONS = [
    "Here's what actually works.",
    "This changes the whole setup.",
    "Here's the part nobody explains.",
    "It solved it on the first try.",
]


def build_script_for_product(title: str) -> tuple:
    """Returns (script_text, niche, hook) - niche is 'PET' or 'TECH', used to
    pick the Shopify brand (Groomlyco vs Magdock) downstream. The hook is
    returned separately so the caption can open with it too - see
    build_caption_for_product."""
    niche = _detect_niche(title)
    # Hook coerente col prodotto quando riconosciamo la sottocategoria,
    # altrimenti si ricade sul pool generico della nicchia.
    subcategory = _detect_subcategory(title, niche)
    _pools = {
        "PET": (PET_HOOKS, PET_RESOLUTIONS, PET_CLOSERS),
        "TECH": (TECH_HOOKS, TECH_RESOLUTIONS, TECH_CLOSERS),
        "HOME": (HOME_HOOKS, HOME_RESOLUTIONS, HOME_CLOSERS),
    }
    default_hooks, resolutions, closers = _pools[niche]
    hook_pool = SUBCATEGORY_HOOKS.get(subcategory) or default_hooks
    hook = random.choice(hook_pool)
    resolution = random.choice(resolutions)
    closer = random.choice(closers)
    script = f"{hook} {resolution} {closer}"
    return script, niche, hook


def build_caption_for_product(title: str, niche: str, hook: str) -> str:
    # Prima la caption era solo il nome nudo del prodotto ("Flip Phone Case
    # Cover Card Wallet - Shop the link...") mentre il voiceover aveva gia'
    # un hook narrativo - i dati (cross_account_growth_analysis.py, 2026-08-02)
    # confermano che i post con hook in caption fanno 7-37% di engagement
    # contro 0-2.7% di quelli col solo nome prodotto. Ora la caption apre
    # con lo STESSO hook usato nel video invece di ignorarlo.
    tag_pool = {
        "PET": ["#dogsoftiktok", "#doggrooming", "#petcare", "#dogtok", "#puppylove"],
        "TECH": ["#techtok", "#phoneaccessories", "#lifehack", "#deskaesthetic", "#fyp"],
        # Beffante: tag di community reali sul tech da casa/scrivania. Niente
        # #fyp qui - TikTok ha dichiarato che non incide sulla distribuzione,
        # e su un account nuovo un tag da miliardi di view non emerge mai.
        "HOME": ["#desksetup", "#homeoffice", "#techfinds", "#gadgets", "#workfromhome"],
    }[niche]
    tags = " ".join(random.sample(tag_pool, 3))
    # ~50% delle volte usa una CTA orientata a save/share invece del solo
    # link - varieta' e allineamento al segnale di ranking piu' pesante,
    # senza perdere del tutto la spinta diretta al negozio.
    cta = random.choice(_SHARE_CTAS) if random.random() < 0.5 else _CTA
    return f"{hook} {cta} {tags}"


# Limite reale dei titoli YouTube. Superarlo NON fa fallire l'upload: YouTube
# tronca silenziosamente a 100 caratteri, e siccome "#shorts" stava in coda
# era proprio lui a sparire.
YOUTUBE_TITLE_MAX = 100
_SHORTS_SUFFIX = " #shorts"


# Rumore tipico dei nomi prodotto CJdropshipping: sigle, compatibilita',
# ripetizioni. Va tolto prima di mettere il prodotto in un titolo YouTube.
_PRODUCT_NOISE = (
    "compatible with apple", "compatible with", "for apple", "multi-function",
    "multifunctional", "high quality", "new arrival", "hot sale", "dropship",
    "free shipping", "wholesale", "2026", "2025",
)
_PRODUCT_MAX_WORDS = 6


def shorten_product_name(name: str) -> str:
    """Riduce il nome prodotto a qualcosa di leggibile in un titolo.

    I nomi CJ sono lunghissimi e ripetitivi ("Compatible with Apple,
    Compatible with Apple , Mobile Phone MagSafe Magnetic Push Cover
    Protective Case" - caso reale dai log): messo intero saturerebbe il
    titolo senza aggiungere nulla di cercabile.
    """
    if not name:
        return ""
    low = name.lower()
    for noise in _PRODUCT_NOISE:
        low = low.replace(noise, " ")

    # Si tiene il primo segmento NON VUOTO, non semplicemente il primo.
    # Con "Compatible with Apple, Compatible with Apple , Mobile Phone
    # MagSafe..." la rimozione del rumore lascia il nome che inizia con una
    # virgola: prendendo split(",")[0] il risultato era la stringa vuota e
    # il prodotto spariva del tutto dal titolo (trovato testando proprio
    # questo nome, preso dai log reali).
    for sep in (",", " - ", "|", "/"):
        if sep in low:
            parts = [p for p in low.split(sep) if p.strip()]
            if parts:
                low = parts[0]

    words = [w for w in low.split() if any(c.isalnum() for c in w)]
    words = words[:_PRODUCT_MAX_WORDS]
    return " ".join(w.capitalize() for w in words).strip()


def build_youtube_title(hook: str, product_name: str = "") -> str:
    """Titolo YouTube a partire dall'hook, con "#shorts" SEMPRE presente.

    Bug reale (2026-08-02, video _JQ5J6ktUDs): il titolo era costruito dalla
    caption intera, che include CTA e hashtag di Instagram, arrivando a
    130-187 caratteri. YouTube troncava a 100 e "#shorts", essendo in fondo,
    veniva mangiato - il video perdeva la classificazione come Short.
    Verificato sul video pubblicato: titolo di esattamente 100 caratteri,
    nessun "#shorts".

    Due correzioni insieme:
      - si parte dall'HOOK, non dalla caption: "Shop the link in our bio" e
        gli hashtag sono testo da Instagram, in un titolo YouTube non ci
        vanno;
      - il troncamento avviene su confine di parola e riserva lo spazio per
        il suffisso, che quindi non puo' piu' essere tagliato.

    Aggiunta 2026-08-04: quando il nome prodotto e' disponibile finisce nel
    titolo. Col solo hook uscivano titoli come "Look at the difference.
    #shorts" o "Try it once and you'll see. #shorts" - frasi senza un solo
    sostantivo cercabile. Su Instagram/TikTok va bene (la caption e'
    secondaria al video), ma su YouTube il titolo E' la superficie di
    ricerca, e i dati misurati sugli altri canali dicono che i titoli senza
    soggetto concreto restano a 0 views.
    """
    hook = (hook or "").strip().rstrip(" .")
    product = shorten_product_name(product_name)

    budget = YOUTUBE_TITLE_MAX - len(_SHORTS_SUFFIX)
    if product:
        candidate = f"{hook} | {product}"
        if len(candidate) <= budget:
            hook = candidate
        else:
            # Se non ci sta tutto, ha precedenza il PRODOTTO (e' la parte
            # cercabile): si accorcia l'hook, non lo si butta.
            room = budget - len(product) - 3
            if room > 15:
                hook = f"{hook[:room].rsplit(' ', 1)[0].rstrip(' ,.;:-')} | {product}"
            else:
                hook = product

    if len(hook) > budget:
        hook = hook[:budget].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return f"{hook}{_SHORTS_SUFFIX}"
