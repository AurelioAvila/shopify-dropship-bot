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

_CTA = "Shop the link in our bio 🛒"

# Aggiunte 2026-08-02: la ricerca 2026 (Hootsuite, TrueFuture Media,
# Eclincher) conferma che share/save sono il segnale di ranking piu' pesato
# su Instagram/TikTok (una DM share vale 3-10x un like) - prima OGNI caption
# chiudeva solo con "shop the link", zero richiesta esplicita di salvare o
# condividere, il che significa non attivare mai il segnale piu' forte che
# l'algoritmo guarda. Queste si aggiungono in rotazione, mantenendo comunque
# il link in bio.
_SHARE_CTAS = [
    "Save this before you forget 🛒 " + _CTA,
    "Tag someone who needs this 🛒 " + _CTA,
    "Send this to a friend who'd actually use it 🛒 " + _CTA,
]

PET_HOOKS = [
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
}

SUBCATEGORY_HOOKS = {
    "PET_GROOMING": [
        "If your dog hates this every single time, you're probably doing it wrong.",
        "This is the mistake almost every dog owner makes while grooming.",
        "Grooming used to take two people and end in a wet bathroom floor.",
    ],
    "PET_FEEDING": [
        "If your dog inhales dinner in nine seconds flat, that's a real problem.",
        "Nobody warns you that eating too fast is what makes dogs sick later.",
        "A bored dog and a full bowl is a worse combination than it sounds.",
    ],
    "PET_COMFORT": [
        "If your dog can't settle in summer, it's not restlessness, it's the heat.",
        "Most dog beds stop working exactly when your dog needs them most.",
        "There's a reason your dog abandons the bed and lies on the tiles.",
    ],
    "PET_WALKING": [
        "If your dog pulls the whole walk, the leash is half the problem.",
        "The mistake almost everyone makes on walks shows up months later.",
        "One bad harness is how a normal walk turns into a fight.",
    ],
    "PET_TOYS": [
        "If your dog destroys everything when you leave, it's not bad behavior, it's boredom.",
        "Most dog toys are dead in a day, and that's the actual problem.",
        "A dog that never gets bored behaves completely differently.",
    ],
    "TECH_CHARGING": [
        "One clean setup instead of a tangled mess of cables every night.",
        "Cheap chargers fail in the one moment you actually needed them.",
        "If your phone charges slower than it used to, it might not be the battery.",
    ],
    "TECH_CAR": [
        "Your phone keeps sliding every time you brake, and there's a reason for that.",
        "POV: your phone never falls off the dashboard again.",
        "The difference between a cheap mount and a good one shows up at the first pothole.",
    ],
    "TECH_CASE": [
        "I stress-tested this case so you don't have to.",
        "Most people find out their case is useless the hard way.",
        "The drop that kills your phone is never the one you expect.",
    ],
    "TECH_DESK": [
        "One bag instead of digging through a drawer of tangled cables.",
        "If your desk eats every cable you own, this is why.",
        "Packing tech used to mean forgetting exactly one essential thing.",
    ],
}


def _detect_subcategory(title: str, niche: str) -> str:
    t = title.lower()
    prefix = "PET_" if niche == "PET" else "TECH_"
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


def build_script_for_product(title: str) -> tuple:
    """Returns (script_text, niche, hook) - niche is 'PET' or 'TECH', used to
    pick the Shopify brand (Groomlyco vs Magdock) downstream. The hook is
    returned separately so the caption can open with it too - see
    build_caption_for_product."""
    niche = _detect_niche(title)
    # Hook coerente col prodotto quando riconosciamo la sottocategoria,
    # altrimenti si ricade sul pool generico della nicchia.
    subcategory = _detect_subcategory(title, niche)
    hook_pool = SUBCATEGORY_HOOKS.get(subcategory) or (PET_HOOKS if niche == "PET" else TECH_HOOKS)
    hook = random.choice(hook_pool)
    resolution = random.choice(PET_RESOLUTIONS if niche == "PET" else TECH_RESOLUTIONS)
    closer = random.choice(PET_CLOSERS if niche == "PET" else TECH_CLOSERS)
    script = f"{hook} {resolution} {closer}"
    return script, niche, hook


def build_caption_for_product(title: str, niche: str, hook: str) -> str:
    # Prima la caption era solo il nome nudo del prodotto ("Flip Phone Case
    # Cover Card Wallet - Shop the link...") mentre il voiceover aveva gia'
    # un hook narrativo - i dati (cross_account_growth_analysis.py, 2026-08-02)
    # confermano che i post con hook in caption fanno 7-37% di engagement
    # contro 0-2.7% di quelli col solo nome prodotto. Ora la caption apre
    # con lo STESSO hook usato nel video invece di ignorarlo.
    tag_pool = (
        ["#dogsoftiktok", "#doggrooming", "#petcare", "#dogtok", "#puppylove"]
        if niche == "PET"
        else ["#techtok", "#phoneaccessories", "#lifehack", "#deskaesthetic", "#fyp"]
    )
    tags = " ".join(random.sample(tag_pool, 3))
    # ~50% delle volte usa una CTA orientata a save/share invece del solo
    # link - varieta' e allineamento al segnale di ranking piu' pesante,
    # senza perdere del tutto la spinta diretta al negozio.
    cta = random.choice(_SHARE_CTAS) if random.random() < 0.5 else _CTA
    return f"{hook} {cta} {tags}"
