"""
DA LANCIARE UNA SOLA VOLTA, IN LOCALE, per ciascun brand/account TikTok.
Apre il browser per fare login con l'account TikTok del brand e genera un
refresh token da salvare nel tuo .env.

Prerequisiti (li devi fare tu, non posso farli al posto tuo):
1. Vai su https://developers.tiktok.com/ e crea un account developer + un'app
   (puoi riusare la stessa app developer per piu' brand, basta rifare il
   login con l'account TikTok giusto quando lanci questo script)
2. Nella tua app aggiungi il prodotto "Content Posting API" (richiede Login Kit)
3. Richiedi gli scope: user.info.basic, video.publish
4. Registra come Redirect URI un dominio HTTPS reale che controlli
   (TikTok non accetta localhost). Se hai gia' una pagina di callback per
   altri progetti, riusala.
5. Copia Client Key e Client Secret e impostali come variabili d'ambiente
   prima di lanciare questo script:
       TIKTOK_CLIENT_KEY=...
       TIKTOK_CLIENT_SECRET=...
       TIKTOK_REDIRECT_URI=...

Uso:
    python get_tiktok_token.py PET      (o TECH, o il nome brand che vuoi)

NB: finche' l'app non ha superato l'audit "Direct Post" di TikTok (scope
video.publish, 4-10 settimane), i video pubblicati finiranno comunque in
stato privato/bozza (SELF_ONLY) indipendentemente da cosa chiediamo qui.
"""
import os
import secrets
import sys
import urllib.parse
import webbrowser

import requests

CLIENT_KEY = os.environ["TIKTOK_CLIENT_KEY"]
CLIENT_SECRET = os.environ["TIKTOK_CLIENT_SECRET"]
REDIRECT_URI = os.environ["TIKTOK_REDIRECT_URI"]
SCOPES = "user.info.basic,video.publish"


def main():
    if len(sys.argv) < 2:
        print("Uso: python get_tiktok_token.py NOME_BRAND   (es. PET oppure TECH)")
        return
    brand = sys.argv[1].upper()

    state = secrets.token_urlsafe(16)
    auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
    })

    print(f"Apro il browser per il login TikTok del brand '{brand}'...")
    print("IMPORTANTE: fai login con l'account TikTok di QUESTO brand specifico.")
    webbrowser.open(auth_url)
    print(f"\nDopo il login, la pagina di callback ti mostrera' il valore di 'code'.")
    code = input("Incolla qui il 'code': ").strip()

    if not code:
        raise RuntimeError("Nessun code inserito. Riprova.")

    token_resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
    )
    token_resp.raise_for_status()
    data = token_resp.json()

    if "refresh_token" not in data:
        print("\n[ERRORE] TikTok non ha restituito un refresh_token. Risposta completa:")
        print(data)
        return

    print(f"\n=== SALVA QUESTI VALORI NEL TUO .env (brand: {brand}) ===")
    print(f"TIKTOK_{brand}_CLIENT_KEY={CLIENT_KEY}")
    print(f"TIKTOK_{brand}_CLIENT_SECRET={CLIENT_SECRET}")
    print(f"TIKTOK_{brand}_REFRESH_TOKEN={data['refresh_token']}")


if __name__ == "__main__":
    main()
