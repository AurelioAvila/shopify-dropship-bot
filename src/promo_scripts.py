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


def _detect_niche(title: str) -> str:
    t = title.lower()
    if any(k in t for k in PET_KEYWORDS):
        return "PET"
    if any(k in t for k in TECH_KEYWORDS):
        return "TECH"
    return "PET" if random.random() < 0.5 else "TECH"


def build_script_for_product(title: str) -> tuple:
    """Returns (script_text, niche) - niche is 'PET' or 'TECH', used to pick
    the Shopify brand (Groomlyco vs Magdock) downstream."""
    niche = _detect_niche(title)
    hook = random.choice(PET_HOOKS if niche == "PET" else TECH_HOOKS)
    resolution = random.choice(PET_RESOLUTIONS if niche == "PET" else TECH_RESOLUTIONS)
    script = f"{hook} {resolution} Look at the result."
    return script, niche


def build_caption_for_product(title: str, niche: str) -> str:
    tag_pool = (
        ["#dogsoftiktok", "#doggrooming", "#petcare", "#dogtok", "#puppylove"]
        if niche == "PET"
        else ["#techtok", "#phoneaccessories", "#lifehack", "#deskaesthetic", "#fyp"]
    )
    tags = " ".join(random.sample(tag_pool, 3))
    return f"{title.split(',')[0][:60]} — {_CTA} {tags}"
