# Shopify Dropship Bot

Automazione gratuita (a parte i costi Shopify/CJ stessi) che replica le funzioni
principali di AutoDS: import prodotti, sync prezzo/stock, evasione ordini automatica.

## Setup

1. `python -m venv .venv && .venv\Scripts\activate` (Windows)
2. `pip install -r requirements.txt`
3. Copia `.env.example` in `.env` e compila:
   - `SHOPIFY_STORE_DOMAIN` / `SHOPIFY_ADMIN_API_TOKEN`: da Shopify Admin ->
     Impostazioni -> App e canali di vendita -> Sviluppa app -> Crea un'app.
     Scope necessari: `read_products, write_products, read_orders, write_orders,
     read_inventory, write_inventory`.
   - `CJ_EMAIL` / `CJ_API_KEY`: da CJdropshipping -> My CJ -> API.

## Uso

```bash
# 1. Importa prodotti in una nicchia
python -m src.jobs.import_products --keyword "led lamp" --limit 10

# 2. Sincronizza prezzo/stock (schedulare ogni 6h)
python -m src.jobs.sync_stock_price

# 3. Evadi automaticamente i nuovi ordini (schedulare ogni 30-60 min)
python -m src.jobs.fulfill_orders

# 4. Aggiorna il tracking quando CJ spedisce (schedulare ogni 2-3h)
python -m src.jobs.update_tracking
```

## Scheduling persistente

Questi job vanno fatti girare periodicamente. Su Windows, il modo più affidabile
è **Utilità di pianificazione (Task Scheduler)**, non un cron lato Claude (che vive
solo dentro una sessione di chat e sparisce quando la sessione finisce).

Esempio con Task Scheduler: crea un'attività che esegue
`C:\...\shopify-dropship-bot\.venv\Scripts\python.exe -m src.jobs.fulfill_orders`
con "Start in" impostato sulla cartella del progetto, ogni 30 minuti.

## Limiti rispetto ad AutoDS (onesti)

- **Ricerca "winning products"**: qui ci si affida al ranking di rilevanza di CJ
  per la keyword cercata. AutoDS ha algoritmi proprietari su milioni di store
  per stimare quali prodotti convertono meglio — questo bot non lo replica.
- **Nessuna UI**: tutto da riga di comando. AutoDS ha una dashboard.
- **Gestione errori minimale**: se CJ o Shopify cambiano risposta API o vai in
  rate limit, i job stampano l'errore ma non hanno retry automatici sofisticati.
- **Un solo fornitore** (CJdropshipping). AutoDS aggrega Amazon, AliExpress,
  Walmart e altri.

## Prima di lasciarlo girare su ordini reali

Testa il flusso completo con **un ordine di prova a basso valore** prima di fidarti
al 100%: crea un prodotto, ordinalo tu stesso, verifica che `fulfill_orders.py`
crei correttamente l'ordine su CJ e che `update_tracking.py` chiuda la fulfillment
su Shopify con il tracking giusto.
