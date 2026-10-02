# Woningaanbod Monitor (Rental Alerts)

Automatische monitoring van nieuw woningaanbod met directe WhatsApp-notificaties via CallMeBot en GitHub Actions.

---

## Functionaliteiten

- **Webscraping:** Haalt periodiek de actuele woningpagina op met standaard browserheaders.
- **Deduplicatie:** Houdt reeds geziene woningen bij in `seen_listings.json`.
- **Meerdere Telefoonnummers:** Ondersteunt één of meerdere WhatsApp-nummers (bijv. voor partners of huisgenoten).
- **WhatsApp Notificaties:** Verstuurt direct een gestructureerd WhatsApp-bericht met titel, huurprijs, details en directe link zodra er een nieuw pand online staat.
- **GitHub Actions Automation:** Draait automatisch in de cloud, inclusief geautomatiseerde commit & push van de bijgewerkte `seen_listings.json`.
- **Veilig & Privacyvriendelijk:** Gevoelige gegevens zoals telefoonnummers, API-keys en portaal-URL's worden beheerd via omgevingsvariabelen / GitHub Secrets.

---

## 1. CallMeBot API-key aanvragen

De notificaties worden gratis verstuurd via de **CallMeBot WhatsApp API**. Ieder telefoonnummer heeft zijn eigen API-key nodig:

1. Voeg het telefoonnummer van CallMeBot toe aan WhatsApp op de telefoon die notificaties moet ontvangen:
   - Telefoonnummer: **`+34 644 59 71 67`** (of zie [callmebot.com](https://www.callmebot.com/blog/free-api-whatsapp-messages/))
2. Stuur via WhatsApp het volgende bericht vanaf dat toestel:
   ```text
   I allow callmebot to send me messages
   ```
3. Binnen enkele seconden ontvang je een bericht terug met je persoonlijke **API-key** (bijv. `123456`).
4. Noteer:
   - **`WHATSAPP_PHONE`**: Het telefoonnummer inclusief landcode zonder `+` of spaties (bijv. `31612345678` voor Nederland).
   - **`CALLMEBOT_API_KEY`**: De verkregen API-key.
5. *(Optioneel)* Herhaal stap 1 t/m 3 voor een tweede nummer voor `WHATSAPP_PHONE_2` en `CALLMEBOT_API_KEY_2`.

---

## 2. Lokale installatie en configuratie

### Stap 1: Repository klonen & virtual environment opzetten
```bash
git clone <jouw-repo-url>
cd <repo-naam>

# Maak een virtuele omgeving aan en activeer deze
python -m venv .venv
# Op Windows:
.venv\Scripts\activate
# Op macOS/Linux:
source .venv/bin/activate

# Installeer afhankelijkheden
pip install -r requirements.txt
```

### Stap 2: Omgevingsvariabelen instellen
Kopieer `.env.example` naar `.env`:
```bash
cp .env.example .env
```
Open `.env` en vul je gegevens in:
```env
# Eerste ontvanger
WHATSAPP_PHONE=31612345678
CALLMEBOT_API_KEY=jouw_eerste_api_key

# Tweede ontvanger (optioneel)
WHATSAPP_PHONE_2=31687654321
CALLMEBOT_API_KEY_2=jouw_tweede_api_key

# Optionele portaalconfiguratie (standaard voorgeprogrammeerd)
# PORTAL_NAME=Woningaanbod
# PORTAL_URL=https://...
# PORTAL_BASE_URL=https://...
```

### Stap 3: Monitor uitvoeren
Voer het script uit:
```bash
python monitor.py
```
*(Of: `python main.py`)*

Het script zal:
- Alle geconfigureerde ontvangers detecteren.
- `seen_listings.json` controleren (of leeg aanmaken als het nog niet bestaat).
- De actuele woningen ophalen en vergelijken.
- Bij nieuwe woningen naar alle ontvangers een WhatsApp-notificatie versturen.
- De nieuwe IDs toevoegen aan `seen_listings.json`.

---

## 3. GitHub Actions instellen (24/7 Monitoring)

Deze repository bevat een workflow in [`.github/workflows/check_listings.yml`](.github/workflows/check_listings.yml).

### Secrets configureren in GitHub:
1. Ga in je GitHub repository naar **Settings** > **Secrets and variables** > **Actions**.
2. Klik op **New repository secret**.
3. Voeg de vereiste secrets toe:
   - `WHATSAPP_PHONE`: Telefoonnummer 1 (bijv. `31612345678`).
   - `CALLMEBOT_API_KEY`: API-key voor telefoonnummer 1.
4. *(Optioneel)* Voeg secrets toe voor het tweede nummer of eigen portaal:
   - `WHATSAPP_PHONE_2`: Telefoonnummer 2 (bijv. `31687654321`).
   - `CALLMEBOT_API_KEY_2`: API-key voor telefoonnummer 2.
   - `PORTAL_NAME`: Naam van het portaal in het WhatsApp-bericht.

### Workflow Permissies instellen:
Om de bijgewerkte `seen_listings.json` terug te kunnen pushen naar de repository:
1. Ga naar **Settings** > **Actions** > **General**.
2. Scroll naar **Workflow permissions**.
3. Selecteer **Read and write permissions** en klik op **Save**.

### Betrouwbare 10-minuten trigger via cron-job.org
De ingebouwde cron van GitHub Actions (`schedule`) is "best-effort" en loopt tijdens piekdrukte op GitHub vaak vertraging op. Omdat de workflow [`workflow_dispatch`](.github/workflows/check_listings.yml) ondersteunt, kun je hem via een gratis externe cron-dienst stipt elke 10 minuten activeren:

1. **Maak een GitHub Personal Access Token (PAT) aan:**
   - Ga naar GitHub **Settings** > **Developer Settings** > **Personal access tokens** (Tokens classic).
   - Geef de token permissies voor Actions (`workflow` of vink `repo` aan).
   - Kopieer de gegenereerde token.

2. **Stel de taak in op [cron-job.org](https://cron-job.org) (gratis):**
   - Maak een account aan en klik op **Create cronjob**.
   - **Title:** `Listing Monitor Trigger`
   - **URL:** `https://api.github.com/repos/<jouw-gebruikersnaam>/<jouw-repo>/actions/workflows/check_listings.yml/dispatches`
   - **Execution schedule:** Every `10` minutes.
   - **Request Method:** `POST`
   - **Headers:**
     - `Authorization`: `Bearer <JOUW_GITHUB_PAT>`
     - `Accept`: `application/vnd.github+json`
     - `User-Agent`: `cron-job-agent`
   - **Request Body:**
     ```json
     {"ref": "main"}
     ```
   - Klik op **Save**. Je workflow start nu stipt elke 10 minuten.

---

## Bestandsstructuur

```text
├── .github/
│   └── workflows/
│       └── check_listings.yml   # GitHub Actions workflow
├── .env.example                 # Voorbeeldconfiguratie
├── .gitignore                   # Negeert .env, venvs, cache
├── main.py                      # Startpunt
├── monitor.py                   # Scraper, multi-recipient matching & WhatsApp sender
├── requirements.txt             # Python dependencies (requests, beautifulsoup4)
├── seen_listings.json           # JSON database met geziene IDs
└── README.md                    # Handleiding en documentatie
```
