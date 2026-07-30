"""
Job 8: sostituisce le descrizioni prodotto (spesso scritte male/tradotte
dal cinese quando importate da CJ) con copy pulito e persuasivo in inglese.

Uso:
    python -m src.jobs.rewrite_descriptions
"""
from src.clients.shopify_client import ShopifyClient

# id prodotto Shopify -> nuova descrizione (hook + benefici + CTA)
DESCRIPTIONS = {
    10940355412295: """
<p><strong>Grooming multiple dogs shouldn't feel like a workout.</strong></p>
<ul>
<li>Adjustable height so you're never hunched over</li>
<li>Non-slip, ribbed rubber surface keeps your pet steady and calm</li>
<li>Built-in leash arm frees up both your hands</li>
<li>Folds flat for easy storage between sessions</li>
</ul>
<p>One table, every dog, zero back pain.</p>
""",
    10940353315143: """
<p><strong>The grooming table that makes every trim easier.</strong></p>
<ul>
<li>Raises your pet to a comfortable working height</li>
<li>Non-slip surface keeps them calm and secure</li>
<li>Sturdy build, folds flat when you're done</li>
</ul>
<p>Bath time, trims, brushing - all without the back pain.</p>
""",
    10941557342535: """
<p><strong>A gentler way to remove loose fur.</strong></p>
<ul>
<li>Fine, soft needles - no pulling or tugging</li>
<li>Light mist function evenly distributes conditioning oil</li>
<li>UVC light helps sanitize as you groom</li>
</ul>
<p>Less shedding around the house, more comfort for your pet.</p>
""",
    10940432580935: """
<p><strong>A magnetic car mount that actually holds.</strong></p>
<ul>
<li>Fits phones from 50mm to 95mm wide - universal fit</li>
<li>One-touch mounting, no tools required</li>
<li>360-degree rotation for portrait or landscape view</li>
</ul>
<p>Glance at your GPS without ever taking your hands off the wheel.</p>
""",
    10940413378887: """
<p><strong>A slim wallet case that carries what you need.</strong></p>
<ul>
<li>Card slots built into the case - leave your wallet at home</li>
<li>Soft-touch finish, comfortable in hand</li>
<li>Full access to ports, camera, and buttons</li>
</ul>
<p>One less thing in your pocket, same phone protection.</p>
""",
    10940377465159: """
<p><strong>Keep your car charged and organized.</strong></p>
<ul>
<li>Fast charging for your phone on the go</li>
<li>Compact design that stays out of the way</li>
<li>Reliable connection, no dropped charge</li>
</ul>
<p>One less thing to worry about on every drive.</p>
""",
    10941557145927: """
<p><strong>Grooming your cat or dog, without the fight.</strong></p>
<ul>
<li>Gentle bristles that remove loose fur without pulling</li>
<li>Comfortable grip for longer grooming sessions</li>
<li>Works on both long and short-haired pets</li>
</ul>
<p>Less shedding, happier pet, calmer grooming sessions.</p>
""",
    10941558358343: """
<p><strong>MagSafe protection that snaps into place.</strong></p>
<ul>
<li>Strong magnetic alignment - no more fumbling with chargers</li>
<li>Slim profile, doesn't add bulk to your phone</li>
<li>Compatible with MagSafe accessories and wireless chargers</li>
</ul>
<p>Everyday protection that doesn't get in your way.</p>
""",
    10941558260039: """
<p><strong>Wear your phone, don't carry it.</strong></p>
<ul>
<li>Adjustable crossbody strap for hands-free days</li>
<li>Soft liquid silicone case protects against drops</li>
<li>Detachable strap for when you don't need it</li>
</ul>
<p>Perfect for festivals, travel days, or just not wanting to hold your phone.</p>
""",
    10941558096199: """
<p><strong>Beat the heat, keep your pet comfortable.</strong></p>
<ul>
<li>Self-cooling gel activates with your pet's body weight - no freezing or plugging in required</li>
<li>Waterproof, easy to wipe clean</li>
<li>Works indoors, outdoors, in the car, or in the crate</li>
</ul>
<p>A cooler spot for your pet, all summer long.</p>
""",
    10941557834055: """
<p><strong>An instant cool-down spot for hot days.</strong></p>
<ul>
<li>Pressure-activated cooling gel, no refrigeration needed</li>
<li>Durable, chew-resistant material</li>
<li>Rolls up flat for easy travel</li>
</ul>
<p>Give your dog somewhere cool to rest, wherever you are.</p>
""",
    10940353577287: """
<p><strong>Nail trims your dog won't dread.</strong></p>
<ul>
<li>Sharp, precise blade for a clean cut every time</li>
<li>Ergonomic grip for full control</li>
<li>Safe for dogs and cats of any size</li>
</ul>
<p>Quick, confident trims - no more anxious pets or accidental nicks.</p>
""",
    10941557670215: """
<p><strong>A cool, comfortable spot for hot days.</strong></p>
<ul>
<li>Self-cooling mat, no freezer or batteries needed</li>
<li>Waterproof and easy to clean</li>
<li>Soft enough for daily naps</li>
</ul>
<p>Because summer shouldn't mean an uncomfortable pet.</p>
""",
    10940404793671: """
<p><strong>Your phone and your cards, in one place.</strong></p>
<ul>
<li>Built-in card slots for essentials</li>
<li>Flip cover protects your screen</li>
<li>Slim enough to slide into a pocket</li>
</ul>
<p>Leave the wallet at home - everything you need is already on your phone.</p>
""",
    10940369666375: """
<p><strong>MagSafe-compatible, built to actually hold on.</strong></p>
<ul>
<li>Strong magnetic lock - stress-tested to stay put</li>
<li>Genuine leather card holder, fits 2-3 cards</li>
<li>Compatible with iPhone 12 through 14 Pro Max</li>
</ul>
<p>Carry your cards and your phone as one - no wallet needed.</p>
""",
    10941557047623: """
<p><strong>The deshedding tool that actually works.</strong></p>
<ul>
<li>Double-sided rake removes loose undercoat without cutting skin</li>
<li>Reduces shedding around the house significantly</li>
<li>Comfortable for daily use on dogs and cats</li>
</ul>
<p>Less fur on your couch, less fur everywhere.</p>
""",
    10941558063431: """
<p><strong>Never worry about dropping your phone again.</strong></p>
<ul>
<li>Adjustable crossbody strap, universal fit</li>
<li>Secure wrist strap option included</li>
<li>Lightweight, doesn't add bulk</li>
</ul>
<p>Hands-free convenience for busy days out.</p>
""",
    10940420194631: """
<p><strong>Wireless charging, hands-free driving.</strong></p>
<ul>
<li>15W fast wireless charging while you drive</li>
<li>Bendable magnetic arm adjusts to any angle</li>
<li>One-hand mount and release</li>
</ul>
<p>Your phone charged and visible, every single drive.</p>
""",
    10941558128967: """
<p><strong>A magnetic case built for crossbody wear.</strong></p>
<ul>
<li>Strong magnetic closure keeps your phone secure</li>
<li>Adjustable strap, comfortable for all-day wear</li>
<li>Slim profile, doesn't feel bulky</li>
</ul>
<p>Hands-free and stylish, wherever you're headed.</p>
""",
    10940429467975: """
<p><strong>A car mount that won't let you down.</strong></p>
<ul>
<li>Stainless steel magnetic mount - stress-tested to hold securely</li>
<li>Water-resistant, built to last</li>
<li>Smooth 360-degree rotation for any angle</li>
</ul>
<p>The difference between a good mount and a cheap one shows up when it's too late - don't find out the hard way.</p>
""",
    10941558325575: """
<p><strong>MagSafe protection with a card holder built in.</strong></p>
<ul>
<li>Flip-style leather case with strong magnetic alignment</li>
<li>Separates into a slim case + card holder when you need it</li>
<li>Full camera and port access</li>
</ul>
<p>Flexible protection for however your day goes.</p>
""",
    10941558456647: """
<p><strong>Wireless charging that keeps up with you.</strong></p>
<ul>
<li>MagSafe-compatible fast wireless charging</li>
<li>Compact enough to carry in a bag or pocket</li>
<li>Reliable magnetic alignment, no fumbling</li>
</ul>
<p>Top up your phone anywhere, without the cables.</p>
""",
    10940406923591: """
<p><strong>A phone case that carries everything.</strong></p>
<ul>
<li>Multiple card slots plus a zippered pocket for cash</li>
<li>Genuine leather, durable everyday protection</li>
<li>Fits comfortably in one hand</li>
</ul>
<p>Your phone, cards, and cash - all in one place.</p>
""",
    10940354068807: """
<p><strong>The trick to stress-free nail trims.</strong></p>
<ul>
<li>Precision blade for a clean, confident cut</li>
<li>Safety guard helps you avoid cutting too close</li>
<li>Comfortable grip for easy control</li>
</ul>
<p>Thirty seconds, done - no stress for you or your pet.</p>
""",
    10940356952391: """
<p><strong>Nail trims made simple.</strong></p>
<ul>
<li>Sharp stainless steel blade, clean cut every time</li>
<li>Ergonomic handle for a secure grip</li>
<li>Works for both cats and dogs</li>
</ul>
<p>Confident, quick trims your pet won't dread.</p>
""",
    10941558161735: """
<p><strong>An instant chill spot for your pet.</strong></p>
<ul>
<li>Cooling gel pad, no freezer required</li>
<li>Soft surface, comfortable for naps</li>
<li>Easy to wipe clean</li>
</ul>
<p>A cooler, calmer pet all summer long.</p>
""",
    10941558194503: """
<p><strong>A phone strap that adds a little sparkle.</strong></p>
<ul>
<li>Rhinestone-detail crossbody strap</li>
<li>Adjustable length for your preferred fit</li>
<li>Durable, secure attachment</li>
</ul>
<p>Hands-free convenience that still looks good.</p>
""",
    10941557276999: """
<p><strong>Professional-grade deshedding, at home.</strong></p>
<ul>
<li>Stainless steel double-sided comb removes loose fur and mats</li>
<li>Gentle on skin, effective on undercoat</li>
<li>Suitable for most coat types</li>
</ul>
<p>Noticeably less shedding after just a few uses.</p>
""",
    10940424225095: """
<p><strong>A simple, secure car mount.</strong></p>
<ul>
<li>Clip-style holder fits most phone sizes</li>
<li>Easy one-hand mount and release</li>
<li>Sturdy grip, stays put over bumps</li>
</ul>
<p>Keep your phone visible and secure on every drive.</p>
""",
}


def rewrite_all() -> None:
    shopify = ShopifyClient()
    for product_id, html in DESCRIPTIONS.items():
        shopify.update_product_description(product_id, html.strip())
        print(f"  + {product_id}: descrizione aggiornata")


if __name__ == "__main__":
    rewrite_all()
