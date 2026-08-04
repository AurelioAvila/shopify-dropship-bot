"""
DA LANCIARE UNA SOLA VOLTA PER BRAND, IN LOCALE. Genera il refresh token
YouTube per Groomlyco, Magdock o Beffante (canali/account Google separati).

Prerequisiti:
1. https://console.cloud.google.com/ - crea/riusa un progetto, abilita
   "YouTube Data API v3" E "YouTube Analytics API" (2026-08-04: la seconda
   serve per lo scope yt-analytics.readonly sotto - va abilitata a parte,
   altrimenti le chiamate falliscono con "API not enabled" anche col token
   giusto).
2. Crea credenziali OAuth 2.0 di tipo "App desktop"
3. Scarica il JSON e salvalo in questa cartella come
   client_secret_<brand>.json (es. client_secret_beffante.json)

GOTCHA GIA' INCONTRATA DUE VOLTE (una per brand, Groomlyco e Magdock): una
schermata di consenso OAuth appena creata e' in modalita' "Testing" e blocca
anche l'account PROPRIETARIO dell'app con "Access blocked: has not completed
verification" (403 access_denied), finche' quell'esatto account non viene
aggiunto in Google Auth Platform -> Pubblico -> Utenti di test. Aggiungilo
PRIMA di lanciare questo script, non dopo aver visto l'errore.

Uso:
    python get_youtube_token.py --brand beffante

I valori NON vengono stampati a schermo (2026-08-04): venivano scritti in
chiaro nel terminale e finivano nella cronologia/nei log. Ora vanno diretti
nelle variabili d'ambiente utente di Windows, che e' esattamente dove questo
progetto le legge (non sono GitHub secrets: gira su Scheduled Task locale).
Serve una nuova sessione PowerShell/Explorer perche' i processi gia' aperti
le vedano.
"""
import argparse
import subprocess

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",  # per leggere le statistiche nel dashboard
    # Aggiunto 2026-08-04: Groomlyco/Magdock avevano un token con SOLO
    # scope upload (niente readonly, niente analytics) - rilanciando con
    # questa lista si chiudono entrambi i gap in un colpo solo. Retention/
    # watch-time per video, non solo il conteggio finale delle views - vedi
    # project_growth_algorithm_research_2026_08_04 in memoria.
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

parser = argparse.ArgumentParser()
parser.add_argument("--brand", required=True, choices=["groomlyco", "magdock", "beffante"])
parser.add_argument("--print-values", action="store_true",
                    help="stampa i valori invece di salvarli (sconsigliato: finiscono in chiaro nel terminale)")
args = parser.parse_args()

client_secret_file = f"client_secret_{args.brand}.json"
flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
credentials = flow.run_local_server(port=0)

brand_upper = args.brand.upper()
values = {
    f"YOUTUBE_{brand_upper}_CLIENT_ID": credentials.client_id,
    f"YOUTUBE_{brand_upper}_CLIENT_SECRET": credentials.client_secret,
    f"YOUTUBE_{brand_upper}_REFRESH_TOKEN": credentials.refresh_token,
}

if args.print_values:
    print(f"\n=== VALORI ({brand_upper}) ===")
    for k, v in values.items():
        print(f"{k}={v}")
else:
    for k, v in values.items():
        subprocess.run(["setx", k, v], check=True, capture_output=True)
    print(f"\n[OK] Salvate {len(values)} variabili d'ambiente utente per {brand_upper}:")
    for k in values:
        print(f"  - {k}")
    print("\nApri una NUOVA finestra PowerShell perche' vengano lette.")
