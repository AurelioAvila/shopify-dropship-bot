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
import json
import os
import random

# --- Memoria degli hook gia' usati per sottocategoria (2026-08-05) -----------
#
# Trovato indagando Beffante: "I didn't expect a projector this size to
# actually be watchable." e' uscito su TRE proiettori DIVERSI (id/cj_pid
# distinti, l'anti-ripetizione prodotto del 2026-08-04 aveva gia' impedito
# che fossero lo stesso item) in meno di 27 ore, e "Anyone still watching
# movies on a laptop screen" due volte. hook = random.choice(hook_pool) non
# aveva memoria: con pool da 6 elementi e poche estrazioni il repeat non e'
# raro. Prodotto diverso ma hook identico si legge comunque come contenuto
# ripostato a chi vede piu' di un video del canale - stessa famiglia del
# fact_history.json costruito ieri per xn0time, qui applicata agli hook.
HOOK_HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "hook_history.json")
HOOK_HISTORY_DEPTH = 2  # sul pool piu' piccolo (6) lascia comunque 4 alternative


def _load_hook_history() -> dict:
    try:
        with open(HOOK_HISTORY_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_hook_history(history: dict) -> None:
    try:
        os.makedirs(os.path.dirname(HOOK_HISTORY_PATH), exist_ok=True)
        with open(HOOK_HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=1)
    except Exception as exc:
        print(f"Impossibile salvare hook_history.json: {exc}")


def _pick_hook(pool: list, key: str) -> str:
    """random.choice(pool) ma escludendo gli ultimi HOOK_HISTORY_DEPTH hook
    usati per questa chiave (sottocategoria, o niche_default quando la
    sottocategoria non e' riconosciuta)."""
    history = _load_hook_history()
    recent = history.get(key, [])[-HOOK_HISTORY_DEPTH:]
    options = [h for h in pool if h not in recent] or list(pool)
    hook = random.choice(options)
    history[key] = (history.get(key, []) + [hook])[-HOOK_HISTORY_DEPTH:]
    _save_hook_history(history)
    return hook


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
    # "paw"/"paw cleaner"/"paw wash" aggiunti dall'altra sessione il
    # 2026-08-05: prodotti descritti solo come "paw cleaner" senza le altre
    # parole di grooming restavano senza sottocategoria.
    "PET_GROOMING": ("brush", "comb", "nail", "clipper", "shampoo", "bath", "deshedding", "hair remover", "grooming", "trimmer", "paw", "paw cleaner", "paw wash"),
    # PET_FEEDING copriva sia le ciotole sia le borracce/dispenser d'acqua
    # (2026-08-04): due problemi diversi con risposte diverse, quindi la
    # scelta casuale dell'hook poteva mettere "Carrying an open cup of water
    # for him never once worked" su una ciotola slow-feeder, e - dopo
    # l'introduzione dei payoff - accoppiare un hook sull'acqua con una
    # spiegazione sul mangiare troppo in fretta. Separate: PET_FEEDING resta
    # sul cibo, PET_HYDRATION prende acqua/borracce/dispenser. Non
    # riunificarle: e' esattamente il difetto che questo split ha corretto.
    "PET_FEEDING": ("feeder", "bowl", "food", "treat", "puzzle", "slow", "leakage"),
    "PET_HYDRATION": ("water", "bottle", "dispenser", "drink", "hydration"),
    "PET_COMFORT": ("bed", "mat", "pad", "cooling", "pillow", "blanket", "sleeping", "cushion"),
    "PET_WALKING": ("leash", "collar", "harness", "poop", "walking"),
    "PET_TOYS": ("toy", "ball", "chew", "interactive", "rope"),
    # Aggiunta 2026-08-06 (ricerca trend settimanale). "collar" e' gia' una
    # keyword PET_WALKING, quindi senza questa voce un GPS tracker con
    # "collar" nel titolo (comune sui nomi CJ, es. "GPS Pet Tracker Collar
    # Anti-Lost Smart Locator") avrebbe preso un hook su tiraggio al
    # guinzaglio - lo stesso mismatch hook/prodotto gia' corretto per i paw
    # cleaner (PET_GROOMING, 2026-08-04) e le borracce (PET_HYDRATION,
    # 2026-08-05). Le keyword qui sotto (gps/tracker/locator/anti-lost/smart
    # tag/finder) pesano piu' di "collar" da sole, quindi _detect_subcategory
    # (punteggio a match piu' alto) sceglie questa e non PET_WALKING.
    # Fonte: Zendrop elenca i GPS pet tracker tra i prodotti pet dropshipping
    # di tendenza 2026 sia nella guida sia nella propria categoria "GPS
    # Tracking Devices" (https://www.zendrop.com/blog/dropshipping-pet-products/,
    # https://www.zendrop.com/tech-products/). Il prodotto e' anche
    # effettivamente reperibile dal fornitore che questo bot gia' usa via
    # src/clients/cj_client.py, non solo citato nelle guide:
    # https://cjdropshipping.com/product/gps-pet-tracker-p-2DD6409D-362E-44AA-9390-416C37A3D1B5.html
    "PET_TRACKING": ("gps", "tracker", "locator", "anti-lost", "smart tag", "finder"),
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
    # Ricerca trend 2026-08-04 (routine di manutenzione): stesso difetto di
    # coerenza gia' descritto sopra (PET_FEEDING/TECH_CASE), stavolta su una
    # sottocategoria intera senza NESSUN hook adatto. "paw" e' gia' una
    # keyword PET a livello di nicchia (PET_KEYWORDS, questo file) - un
    # prodotto come "Portable Dog Paw Cleaner Cup" veniva quindi instradato
    # correttamente su Groomlyco/PET, ma non c'era nessuna keyword "paw" nelle
    # sottocategorie: zero hit su tutte, quindi ricadeva sul pool generico
    # PET_HOOKS (shedding/comportamento) invece di uno sul vero motivo per
    # cui si compra un lavapiedi per cani. I paw cleaner sono segnalati come
    # prodotto vincente 2026, a basso rischio e facile da dimostrare in video
    # brevi, da BuckyDrop
    # (https://blog.buckydrop.com/trending-pet-products-dropshipping-2026/)
    # e Zendrop (https://www.zendrop.com/blog/dropshipping-pet-products/).
    # Aggiunta keyword "paw"/"paw cleaner"/"paw wash" a PET_GROOMING sopra e
    # hook dedicati qui, invece di forzarli nel pool generico.
    "PET_GROOMING": [
        "If your dog hates this every single time, you're probably doing it wrong.",
        "This is the mistake almost every dog owner makes while grooming.",
        "Grooming used to take two people and end in a wet bathroom floor.",
        "My dog used to hide the second he heard the clippers come out.",
        "Nobody tells you the groomer bill adds up to a holiday every year.",
        "The trick isn't holding him still, it's what you do before that.",
        "Ten minutes at home beats an hour of wrestling at the salon.",
        "Muddy paws on the couch again, and it's always right after a walk.",
        "Wiping four paws with a towel at the door never actually works.",
        "The walk isn't the problem, the ninety seconds after you get home is.",
        "If your dog tracks mud through the house after every single walk, this is why.",
    ],
    "PET_FEEDING": [
        "If your dog inhales dinner in nine seconds flat, that's a real problem.",
        "Nobody warns you that eating too fast is what makes dogs sick later.",
        "A bored dog and a full bowl is a worse combination than it sounds.",
        "My vet asked one question about mealtimes and it explained everything.",
        "Your dog isn't greedy, the bowl is just the wrong shape.",
        "The bloating scare cost me a night at the emergency vet.",
    ],
    # Spostati qui da PET_FEEDING il 2026-08-04: parlano di acqua, non di
    # cibo, e restando nello stesso pool finivano su prodotti-ciotola.
    # Pool ampliato da 3 a 6 (2026-08-05, ricerca settimanale): unico
    # sotto-pool ancora sotto la soglia di 5-6 hook applicata al resto del
    # file dal 2026-08-02. Fontane/borracce d'acqua per cani restano segnalate
    # come prodotto vincente 2026 (cjdropshipping.com, pbfulfill.com), quindi
    # 3 hook per un video ogni pochi giorni si sarebbero ripetuti in fretta -
    # nessuno storico anti-riuso protegge questo pool. Archetipi aggiunti
    # (POV / mito da smontare / momento specifico) diversi dai tre esistenti
    # (aneddoto / conseguenza / frustrazione), stessa regola di varieta' gia'
    # applicata alle altre sottocategorie.
    "PET_HYDRATION": [
        "He used to drink from puddles on every walk because I forgot water.",
        "A thirsty dog on a hot walk is how a good afternoon turns into a vet visit.",
        "Carrying an open cup of water for him never once worked.",
        "POV: your dog finally drinks on a walk instead of pulling toward every puddle.",
        "The mistake is packing a bottle he can't actually drink from.",
        "Halfway through every walk he stops, and it's never actually about being tired.",
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
    # Aggiunta 2026-08-06, stessa ricerca trend di SUBCATEGORY_KEYWORDS sopra:
    # prima di questa sottocategoria un tracker GPS sarebbe caduto su
    # PET_WALKING (via la keyword "collar") con hook su guinzaglio/tiraggio,
    # incoerenti col vero motivo per cui si compra un localizzatore.
    "PET_TRACKING": [
        "If your dog has ever bolted through an open gate, this one's for you.",
        "I checked my phone forty times the day he slipped his collar.",
        "POV: he's not in the yard, and you don't know which direction he went.",
        "A tag with your number on it only works if a stranger finds him first.",
        "The scariest ten minutes of my week started with a front door left open.",
        "Every escape happens on the one day you weren't watching the yard.",
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
    """Nicchia indovinata dal SOLO titolo. E' un ripiego: quando il vendor
    Shopify e' noto va passato a build_script_for_product(niche=...), perche'
    e' un dato curato e questa funzione no.

    Misurato 2026-08-04 su tutto il catalogo: 13 prodotti su 139 (9%)
    finivano nella nicchia sbagliata, e 8 erano accessori da auto mandati in
    PET - cioe' pubblicati sul canale Groomlyco con un voiceover sui cani
    sopra le foto di un tracker GPS o di una dash cam. La causa era il
    ripiego finale, che era un lancio di moneta:
        return "PET" if random.random() < 0.5 else "TECH"
    Un prodotto senza keyword note veniva assegnato a caso, quindi anche il
    brand su cui veniva pubblicato era casuale. Ora il ripiego e' TECH, che
    e' la nicchia piu' generica delle tre (un oggetto non riconosciuto e'
    quasi sempre un accessorio, non un articolo per animali), ed e'
    deterministico: lo stesso prodotto da' sempre lo stesso risultato, quindi
    un errore e' riproducibile e correggibile invece di apparire a caso.
    """
    t = title.lower()
    if any(k in t for k in PET_KEYWORDS):
        return "PET"
    # HOME prima di TECH: le due si sovrappongono ("watch" -> smartwatch,
    # "speaker", "camera") e il piu' specifico deve vincere, altrimenti i
    # prodotti Beffante finirebbero pubblicati sull'account Magdock.
    if any(k in t for k in HOME_KEYWORDS):
        return "HOME"
    return "TECH"


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


# PAYOFF: la risposta vera alla promessa fatta dall'hook (aggiunto 2026-08-04).
#
# Perche' esiste. Fino a oggi lo script era hook + resolution + closer, dove
# la resolution e' una frase vuota ("Here's what actually works.", "This
# changes everything."). Risultato: l'hook prometteva una spiegazione
# specifica ("There's a reason your dog abandons the bed and lies on the
# tiles") e il video non la dava MAI. Chi guarda resta in attesa del
# pagamento della promessa, non arriva, e se ne va: e' coerente col dato
# misurato il 2026-08-04, cioe' ZERO share e ZERO save su 64+ post di tutti
# i brand, con retention ferma al 28-39%. Un video senza informazione non e'
# condivisibile - non c'e' niente da mandare a un amico.
#
# Regole seguite scrivendoli:
#  - nessuna statistica inventata (regola permanente): sono spiegazioni di
#    meccanismo verificabili, non numeri;
#  - frasi corte (12-18 parole) per non gonfiare la durata: il payoff
#    sostituisce la resolution, non si aggiunge, cosi' il video passa da
#    ~9s a ~13s invece di raddoppiare;
#  - il payoff deve rispondere alla stessa domanda che pone l'hook della
#    sottocategoria, altrimenti si ricrea il mismatch hook/prodotto gia'
#    corretto una volta per SUBCATEGORY_HOOKS.
SUBCATEGORY_PAYOFFS = {
    "PET_GROOMING": [
        "Most dogs don't hate the brush, they hate being held still, so work in short passes and let him stand.",
        "Loose hair comes out easier before a bath, not after, because wet fur mats around the undercoat.",
    ],
    "PET_FEEDING": [
        "Eating fast means swallowing air, and that's what causes the bloating, so the fix is slowing the bowl down, not feeding less.",
        "A bowl that makes him work for it turns a ten second meal into a few minutes, which is the whole point.",
    ],
    "PET_HYDRATION": [
        "Dogs drink far less on walks than they need, and they'll take water from a bowl shape long before a narrow spout.",
        "Refusing water on a walk is usually about how it's offered, not thirst, which is why a fold-out bowl works when a bottle doesn't.",
    ],
    "PET_COMFORT": [
        "Dogs lose heat through their paws and belly, not by sweating, so a cool surface does more than a fan ever will.",
        "That's why he picks the tiles: he's looking for something that pulls heat away, and a padded bed traps it instead.",
    ],
    "PET_WALKING": [
        "Pulling is leverage, not disobedience, so moving the clip to the chest takes the leverage away without correcting him.",
        "A harness that sits on the shoulders lets him pull with his whole body, which is why your arm gives out first.",
    ],
    "PET_TOYS": [
        "Destructive chewing is almost always boredom, so the fix is a toy that takes work to solve, not a tougher toy.",
        "A toy that gives up its treat too easily gets abandoned in minutes, which is why difficulty matters more than durability.",
    ],
    "PET_TRACKING": [
        "A tag only helps once he's found; live GPS shows you where he is while you're still looking, not after.",
        "The cheap trackers update rarely, so by the time you check the app he's already moved somewhere else.",
    ],
    "TECH_CHARGING": [
        "Wireless charging loses most of its speed to misalignment, so a magnet that centres the coil matters more than the wattage.",
        "Heat is what kills a battery, and a pad that keeps the phone raised charges cooler than one lying flat against it.",
    ],
    "TECH_CAR": [
        "Vent mounts fail because the vent itself flexes, so the ones that hold clamp onto something rigid instead.",
        "Every brake and pothole is a small drop test, which is why grip strength matters more than how the mount looks.",
    ],
    "TECH_CASE": [
        "A wallet case isn't about protection, it's about not carrying a second thing, which is the part reviews never mention.",
        "Corners take the impact in almost every drop, so raised corners do more than a thicker back ever will.",
    ],
    "TECH_DESK": [
        "Cable mess isn't a tidiness problem, it's a length problem, so shortening the run fixes what clips never will.",
        "A stand that lifts the screen to eye level does more for your neck than any chair adjustment.",
    ],
    "HOME_STREAMING": [
        "Bad video is almost always bad light, not a bad camera, so lighting your face beats upgrading the lens.",
        "Front light removes the shadows that make a webcam look cheap, which is why the ring matters more than megapixels.",
    ],
    "HOME_SECURITY": [
        "Most home cameras miss what matters because of placement, not resolution, so height and angle beat specs.",
        "Recording locally means it still works when the internet drops, which is exactly when you'd want it most.",
    ],
    "HOME_ENTERTAINMENT": [
        "Projector brightness matters far less than controlling the light in the room, which is why daytime viewing disappoints.",
        "Throw distance decides your screen size, so measure the room before you pick the projector, not after.",
    ],
    "HOME_WEARABLE": [
        "Sleep tracking is the feature people actually keep using, and it only works if the strap is comfortable enough to wear at night.",
        "Battery life decides whether you keep wearing it, because a watch charging on the desk tracks nothing.",
    ],
    "HOME_WORKSPACE": [
        "Power banks are rated by cell capacity, not by what reaches your device, so expect noticeably less than the number on the box.",
        "Charging a laptop needs enough wattage, not just enough capacity, which is the spec that gets buried.",
    ],
}


# Quota di video che NON vendono nulla. 0.8 = 4 su 5 puro contenuto utile,
# 1 su 5 con spinta al negozio. Alzare/abbassare qui e' il modo di ritarare
# la strategia senza toccare altro; a 0 si torna al comportamento precedente.
VALUE_FIRST_PROBABILITY = 0.8

# Chiusure orientate a salvataggio e condivisione, mai al negozio: sono i due
# segnali che l'algoritmo pesa di piu' (una DM share vale 3-10x un like, un
# save ~5x) ed erano quelli che i nostri video non chiedevano mai davvero,
# perche' finivano tutti con "shop the link".
VALUE_CLOSERS = [
    "Save this so you have it when you need it.",
    "Send this to someone who keeps getting it wrong.",
    "Save this before your next one.",
    "Share this with whoever's about to buy the wrong thing.",
    "Worth saving if you've ever wondered why.",
]


def build_script_for_product(title: str, niche: str = None) -> tuple:
    """Returns (script_text, niche, hook) - niche is 'PET', 'TECH' or 'HOME',
    used to pick the Shopify brand (Groomlyco/Magdock/Beffante) downstream.
    The hook is returned separately so the caption can open with it too - see
    build_caption_for_product.

    `niche` esplicita (2026-08-04): il chiamante che conosce gia' il vendor
    Shopify del prodotto deve passarlo, invece di far reindovinare la nicchia
    dal titolo. Il vendor e' curato a mano, il titolo CJ no - vedi
    _detect_niche per i numeri sull'errore che questo evita.
    """
    niche = niche if niche in ("PET", "TECH", "HOME") else _detect_niche(title)
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
    hook_key = subcategory or f"{niche}_default"
    hook = _pick_hook(hook_pool, hook_key)
    # Il payoff SOSTITUISCE la resolution generica, non si aggiunge: e' la
    # risposta vera alla promessa dell'hook (vedi SUBCATEGORY_PAYOFFS).
    # Quando la sottocategoria non e' riconosciuta (_detect_subcategory puo'
    # tornare None su un prodotto fuori dalle keyword note) si ricade sulla
    # vecchia resolution invece di lasciare un buco nello script.
    payoff_pool = SUBCATEGORY_PAYOFFS.get(subcategory) or resolutions

    # VALUE-FIRST (2026-08-04): 4 video su 5 non vendono nulla.
    #
    # Motivo, misurato: watch time mediano 2.2-3.7s e ZERO share su 60+ post
    # di TUTTI gli account. Nel 2026 il segnale di ranking piu' pesante e' la
    # condivisione in DM, e nessuno manda a un amico una pubblicita'. Un
    # catalogo di video che finiscono tutti con "compra qui" non puo'
    # generare share per costruzione, a prescindere da quanto sia curato il
    # render - infatti la qualita' tecnica e' allineata su tutti e quattro i
    # generatori senza che le views si muovano.
    #
    # Cambia SOLO la chiusura: niente negozio, ma una CTA di salvataggio o
    # condivisione. Il prodotto resta visibile a schermo, quindi il brand
    # lavora comunque, ma il video ha un motivo di esistere anche per chi non
    # comprera' mai.
    #
    # Un primo tentativo usava ENTRAMBI i payoff per rendere il video piu'
    # ricco: misurato, portava lo script da 37 a 59 parole medie, cioe' da
    # ~11s a ~18s - una regressione diretta sul lavoro fatto per stare sotto
    # i 15s (la ricerca 2026 misura fino a 1.8x replay sotto quella soglia, e
    # i replay contano nel watch time). La sostanza della strategia e' NON
    # VENDERE, non allungare: un payoff solo, chiusura diversa.
    value_first = random.random() < VALUE_FIRST_PROBABILITY

    closer = random.choice(VALUE_CLOSERS) if value_first else random.choice(closers)
    script = f"{hook} {random.choice(payoff_pool)} {closer}"
    return script, niche, hook, value_first


def build_caption_for_product(title: str, niche: str, hook: str, value_first: bool = False) -> str:
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
    # #ai (2026-08-05): disclosure obbligatoria per voiceover sintetico sopra
    # footage reale, sia per la policy TikTok aggiornata il 2026-07-21 (AI
    # disclosure estesa dalle sole ads a tutti i contenuti, voci clonate/
    # sintetiche incluse) sia per l'AI Act UE (art. 50, transparency
    # obligations in vigore dal 2026-08-02). TikTok accetta la disclosure
    # anche solo in caption, non serve il toggle nativo (comunque non
    # esposto dall'endpoint bozze che usiamo). Sempre presente, non nel
    # campionamento casuale del tag_pool.
    tags = " ".join(random.sample(tag_pool, 3)) + " #ai"
    # value_first: la caption deve seguire il video. Se il voiceover non
    # vende, mettere "Shop the link in our bio" sotto lo rimetterebbe nella
    # casella "pubblicita'" agli occhi di chi legge e dell'algoritmo,
    # annullando il motivo per cui il video e' stato scritto cosi'.
    if value_first:
        return f"{hook} {random.choice(VALUE_CLOSERS)} {tags}"
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
# Sotto le 2 parole il nome prodotto non identifica piu' niente ("Pet",
# "Usb"): meglio nessun prodotto che un moncherino.
_PRODUCT_MIN_WORDS = 2

# Token di specifica che i nomi CJ mettono DAVANTI al tipo di prodotto
# ("1.5l Cat Dog Water Bowl", "4 In 1 Retractable Car Charger", "36 Inch
# Professional Pet Dog Grooming"). Tenendo le prime N parole si finiva per
# tenere solo la specifica e buttare il sostantivo cercabile - cioe' l'unica
# ragione per cui il prodotto sta nel titolo.
_SPEC_UNITS = (
    "in", "inch", "inches", "cm", "mm", "m", "ft", "l", "ml", "pcs", "pack",
    "set", "layers", "layer", "degrees", "degree", "w", "a", "v", "k", "p",
    "hz", "mah", "g", "kg", "oz", "x",
)


def _is_spec_token(word: str) -> bool:
    """True se la parola e' una specifica ("2pcs", "120w", "1080p", "4", "in",
    "layers") e non il nome di cio' che il prodotto e'.

    Regola volutamente semplice: contiene una cifra, oppure e' un'unita' di
    misura. "Type-c" non ha cifre e non e' un'unita', quindi resta.
    """
    w = word.strip().lower()
    return (not w) or w in _SPEC_UNITS or any(c.isdigit() for c in w)


def shorten_product_name(name: str, max_words: int = _PRODUCT_MAX_WORDS) -> str:
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

    # Via le specifiche IN TESTA (non quelle in mezzo: "Usb Type-c Cable 120w"
    # deve restare tale se ci sta). Se il nome fosse fatto di sole specifiche
    # si tiene tutto, meglio qualcosa che niente.
    head = 0
    while head < len(words) and _is_spec_token(words[head]):
        head += 1
    if head < len(words):
        words = words[head:]

    words = words[:max_words]
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
    budget = YOUTUBE_TITLE_MAX - len(_SHORTS_SUFFIX)

    # Correzione 2026-08-04 (secondo giro). La versione precedente dava
    # precedenza al prodotto e accorciava l'hook: misurato sull'INTERO
    # catalogo, 111 titoli su 132 (84%) uscivano con l'hook tagliato a meta'
    # frase, cioe' senza la parola che lo rende una frase. Reali, dai video
    # gia' pubblicati:
    #   "Nobody tells you this before you get | Motorcycle Electric Vehicle"
    #   "I've bought the same charger three times because I | Magnetic Cable"
    #   "I didn't expect a projector this size to actually be | Mini Led"
    # Il taglio cade su confine di parola, quindi il codice sembrava corretto,
    # ma un hook monco non e' un hook: e' la stessa cosa che si e' gia' pagata
    # a frame 0 col fragment "This is" al posto della frase intera.
    #
    # Ora la priorita' e' invertita e la regola e' netta: l'hook non si tocca,
    # il prodotto si accorcia finche' ci sta (e sparisce se proprio non ci
    # sta). L'hook e' cio' che fa fermare lo scroll; il prodotto e' un bonus
    # di ricercabilita', non vale il prezzo di rompere la frase.
    if len(hook) > budget:
        # Unico caso in cui l'hook viene tagliato: da solo non ci sta.
        # Si taglia sull'ultimo confine di proposizione disponibile, non
        # sull'ultima parola: "If your dog destroys everything when you leave
        # the house" si regge da solo, "...it's not bad behavior, it's" no.
        cut = hook[:budget]
        clause = max(cut.rfind(","), cut.rfind(";"), cut.rfind(" - "))
        if clause > budget // 2:
            cut = cut[:clause]
        else:
            cut = cut.rsplit(" ", 1)[0]
        return f"{cut.rstrip(' ,.;:-')}{_SHORTS_SUFFIX}"

    for words in range(_PRODUCT_MAX_WORDS, _PRODUCT_MIN_WORDS - 1, -1):
        product = shorten_product_name(product_name, words)
        if not product:
            break
        candidate = f"{hook} | {product}"
        if len(candidate) <= budget:
            return f"{candidate}{_SHORTS_SUFFIX}"

    return f"{hook}{_SHORTS_SUFFIX}"
