# 🏠 De Huissleutel Woningaanbod Monitor

Automatische monitoring van nieuw woningaanbod op [dehuissleutel.nl/nl/aanbod](https://www.dehuissleutel.nl/nl/aanbod) met directe WhatsApp-notificaties via CallMeBot en GitHub Actions.

---

## 📋 Functionaliteiten

- **Webscraping:** Haalt automatisch de actuele aanbodpagina op met realistische browserheaders om blokkades te voorkomen.
- **Deduplicatie:** Houdt reeds geziene woningen bij in `seen_listings.json`.
- **WhatsApp Notificaties:** Verstuurt direct een geformatteerd WhatsApp-bericht met titel, huurprijs, details en directe link zodra er een nieuw pand online staat.
- **GitHub Actions Automation:** Draait automatisch elke 10 minuten in de cloud, inclusief geautomatiseerde commit & push van de bijgewerkte `seen_listings.json`.
- **Veilig:** Gevoelige gegevens zoals telefoonnummer en API-keys worden beheerd via omgevingsvariabelen / GitHub Secrets.

---

## 📲 1. CallMeBot API-key aanvragen

De notificaties worden gratis verstuurd via de **CallMeBot WhatsApp API**:

1. Voeg het telefoonnummer van CallMeBot toe aan je WhatsApp-contacten:
   - Telefoonnummer: **`+34 644 59 71 67`** (of zie [callmebot.com](https://www.callmebot.com/blog/free-api-whatsapp-messages/))
2. Stuur via WhatsApp het volgende bericht naar dit nummer:
   ```text
   I allow callmebot to send me messages
   ```
3. Binnen enkele seconden ontvang je een bericht terug met je persoonlijke **API-key** (bijv. `123456`).
4. Noteer:
   - **`WHATSAPP_PHONE`**: Jouw eigen telefoonnummer inclusief landcode zonder `+` of spaties (bijv. `31612345678` voor Nederland).
   - **`CALLMEBOT_API_KEY`**: De verkregen API-key.

---

## 💻 2. Lokale installatie en testuitvoering

### Stap 1: Repository klonen & virtual environment opzetten
```bash
git clone <jouw-repo-url>
cd huissleutel-monitor

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
WHATSAPP_PHONE=31612345678
CALLMEBOT_API_KEY=jouw_api_key_hier
```

### Stap 3: Monitor uitvoeren
Voer het script uit:
```bash
python monitor.py
```
*(Of: `python main.py`)*

Het script zal:
- `seen_listings.json` controleren (of leeg aanmaken als het nog niet bestaat).
- De huidige woningen ophalen en vergelijken.
- Bij nieuwe woningen een WhatsApp-notificatie versturen.
- De nieuwe slugs toevoegen aan `seen_listings.json`.

---

## ⚙️ 3. GitHub Actions instellen (24/7 Monitoring)

Deze repository bevat een kant-en-klare workflow in [`.github/workflows/check_listings.yml`](.github/workflows/check_listings.yml) die elke 10 minuten automatisch draait.

### Secrets configureren in GitHub:
1. Ga in je GitHub repository naar **Settings** > **Secrets and variables** > **Actions**.
2. Klik op **New repository secret**.
3. Voeg de volgende twee secrets toe:
   - `WHATSAPP_PHONE`: Jouw telefoonnummer (bijv. `31612345678`).
   - `CALLMEBOT_API_KEY`: Jouw CallMeBot API-key (bijv. `123456`).

### Workflow Permissies instellen:
Om de bijgewerkte `seen_listings.json` terug te kunnen pushen naar de repository:
1. Ga naar **Settings** > **Actions** > **General**.
2. Scroll naar **Workflow permissions**.
3. Selecteer **Read and write permissions** en klik op **Save**.

### Handmatig testen op GitHub:
Ga naar het tabblad **Actions** in GitHub, selecteer **Check Listings** en klik op **Run workflow**.

---

## 📁 Bestandsstructuur

```text
huissleutel-monitor/
├── .github/
│   └── workflows/
│       └── check_listings.yml   # GitHub Actions cron workflow (elke 10 min)
├── .env.example                 # Voorbeeldconfiguratie voor omgevingsvariabelen
├── .gitignore                   # Negeert .env, venvs, cache (behoudt seen_listings.json)
├── main.py                      # Handig startpunt / entrypoint
├── monitor.py                   # Hoofdlogica: scraper, matcher & WhatsApp sender
├── requirements.txt             # Python dependencies (requests, beautifulsoup4)
├── seen_listings.json           # JSON database met reeds geziene woning-IDs
└── README.md                    # Handleiding en documentatie
```
