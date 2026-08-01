"""
DA LANCIARE UNA SOLA VOLTA PER BRAND, IN LOCALE. Genera il refresh token
YouTube per Groomlyco o Magdock (canali/account Google separati).

Prerequisiti:
1. https://console.cloud.google.com/ - crea/riusa un progetto, abilita
   "YouTube Data API v3"
2. Crea credenziali OAuth 2.0 di tipo "App desktop"
3. Scarica il JSON e salvalo in questa cartella come
   client_secret_groomlyco.json o client_secret_magdock.json (a seconda
   del brand che stai configurando)

Uso:
    python get_youtube_token.py --brand groomlyco
    python get_youtube_token.py --brand magdock
"""
import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

parser = argparse.ArgumentParser()
parser.add_argument("--brand", required=True, choices=["groomlyco", "magdock"])
args = parser.parse_args()

client_secret_file = f"client_secret_{args.brand}.json"
flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
credentials = flow.run_local_server(port=0)

brand_upper = args.brand.upper()
print(f"\n=== SALVA QUESTI VALORI COME SECRET/VARIABILI D'AMBIENTE ({brand_upper}) ===")
print(f"YOUTUBE_{brand_upper}_CLIENT_ID={credentials.client_id}")
print(f"YOUTUBE_{brand_upper}_CLIENT_SECRET={credentials.client_secret}")
print(f"YOUTUBE_{brand_upper}_REFRESH_TOKEN={credentials.refresh_token}")
