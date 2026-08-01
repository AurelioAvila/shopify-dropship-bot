"""
Job 6: pubblica i video generati (generate_promo_videos.py) su TikTok e
Instagram, sul brand giusto in base alla nicchia del video.

Uso:
    python -m src.jobs.publish_promo_videos
    python -m src.jobs.publish_promo_videos --only-tiktok
    python -m src.jobs.publish_promo_videos --video 1_nail_clipper_satisfying
"""
import argparse
import os

from src.clients.shopify_client import ShopifyClient
from src.social.instagram_upload import upload_reel
from src.social.tiktok_upload import upload_video_to_inbox
from src.social.youtube_upload import upload_video as upload_youtube_video
from src.social.x_upload import post_tweet

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "promo_videos")

# Ogni video generato viene mappato al brand giusto (nicchia pet vs tech) e
# alla caption/hashtag da usare in pubblicazione.
PET_BRAND = "GROOMLYCO"
TECH_BRAND = "MAGDOCK"

# Reels non supportano link cliccabili nel testo, quindi ogni caption chiude
# con un richiamo esplicito al link in bio (che punta allo store Shopify).
_CTA = "Shop the link in our bio 🛒"

VIDEOS = {
    "1_nail_clipper_satisfying": {
        "brand": PET_BRAND,
        "caption": f"My dog used to hate nail trims, until I found this 🐾 {_CTA} "
                    "#dogsoftiktok #petcare #satisfying",
    },
    "2_nail_trimmer_mythbust": {
        "brand": PET_BRAND,
        "caption": f"The mistake almost everyone makes when trimming their dog's nails 🐶 {_CTA} "
                    "#doggrooming #pettips #dogtok",
    },
    "3_grooming_table": {
        "brand": PET_BRAND,
        "caption": f"Grooming multiple dogs doesn't have to be chaos 🐕 {_CTA} "
                    "#doggrooming #multidog #petcare",
    },
    "4_magsafe_wallet_stresstest": {
        "brand": TECH_BRAND,
        "caption": f"I stress-tested this MagSafe case so you don't have to 📱 {_CTA} "
                    "#magsafe #phoneaccessories #techtok",
    },
    "5_car_mount_comparison": {
        "brand": TECH_BRAND,
        "caption": f"The difference only shows up when it's too late 🚗 {_CTA} "
                    "#carmount #phonemount #techtok",
    },
    "6_car_mount_pov": {
        "brand": TECH_BRAND,
        "caption": f"POV: your phone never drops in the car again 📱🚗 {_CTA} "
                    "#caraccessories #lifehack #fyp",
    },
    "7_puzzle_feeder_boredom": {
        "brand": PET_BRAND,
        "caption": f"It's not bad behavior, it's boredom 🐾 {_CTA} "
                    "#dogenrichment #puppytraining #dogtok",
    },
    "8_wireless_charger_stand": {
        "brand": TECH_BRAND,
        "caption": f"One clean charging setup instead of a cable mess 📱⌚ {_CTA} "
                    "#deskaesthetic #techtok #wirelesscharging",
    },
}


def publish_all(only: str | None = None, skip_tiktok: bool = False, skip_instagram: bool = False, skip_youtube: bool = False, skip_x: bool = False) -> None:
    shopify = ShopifyClient()

    items = {only: VIDEOS[only]} if only else VIDEOS
    for video_id, info in items.items():
        video_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp4")
        if not os.path.exists(video_path):
            print(f"  ! {video_id}: file non trovato ({video_path}), salto")
            continue

        brand = info["brand"]
        caption = info["caption"]
        print(f"Pubblico {video_id} (brand {brand})...")

        if not skip_tiktok:
            try:
                # In attesa dell'audit "Direct Post" di TikTok mandiamo il
                # video nelle bozze ("Upload to TikTok") invece di pubblicarlo
                # direttamente - funziona gia' oggi, senza restrizioni di
                # privacy_level, ma quell'endpoint non accetta una caption via
                # API: la salviamo in un .txt accanto al video e la mandiamo
                # anche su Telegram, cosi' il brand la trova sul telefono
                # proprio mentre pubblica la bozza dall'app.
                upload_video_to_inbox(brand, video_path, caption=caption)
                caption_path = os.path.join(OUTPUT_DIR, f"{video_id}_tiktok_caption.txt")
                with open(caption_path, "w", encoding="utf-8") as f:
                    f.write(caption)
                print(f"  > caption pronta da incollare: {caption_path}")
            except Exception as exc:
                print(f"  ! {video_id}: errore pubblicazione TikTok: {exc}")

        if not skip_instagram:
            try:
                public_url = shopify.upload_video_get_public_url(video_path, alt=video_id)
                upload_reel(brand, public_url, caption)
            except Exception as exc:
                print(f"  ! {video_id}: errore pubblicazione Instagram: {exc}")

        if not skip_youtube:
            try:
                yt_title = f"{caption.split('—')[0].strip()} #shorts"
                upload_youtube_video(brand, video_path, yt_title, caption)
            except Exception as exc:
                print(f"  ! {video_id}: errore pubblicazione YouTube: {exc}")

        if not skip_x:
            try:
                # Solo testo (free tier X API, niente media) - vedi
                # src/social/x_upload.py per il perche'. Salta da solo se
                # le credenziali X_{brand}_API_* non sono impostate.
                post_tweet(brand, caption)
            except Exception as exc:
                print(f"  ! {video_id}: errore pubblicazione X: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default=None, help="Pubblica solo questo video (id senza .mp4)")
    parser.add_argument("--only-tiktok", action="store_true")
    parser.add_argument("--only-instagram", action="store_true")
    parser.add_argument("--skip-youtube", action="store_true")
    parser.add_argument("--skip-x", action="store_true")
    args = parser.parse_args()
    publish_all(
        only=args.video,
        skip_tiktok=args.only_instagram,
        skip_instagram=args.only_tiktok,
        skip_youtube=args.only_tiktok or args.skip_youtube,
        skip_x=args.only_tiktok or args.skip_x,
    )
