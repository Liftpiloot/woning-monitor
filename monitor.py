#!/usr/bin/env python3
"""
Huissleutel Monitor
Automatische monitoring van nieuw woningaanbod op https://www.dehuissleutel.nl/nl/aanbod
met WhatsApp-notificaties via CallMeBot (ondersteuning voor meerdere telefoonnummers).
"""

import json
import logging
import os
import re
import sys
import urllib.parse
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Logging configuratie
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("huissleutel-monitor")

BASE_URL = "https://www.dehuissleutel.nl"
AANBOD_URL = "https://www.dehuissleutel.nl/nl/aanbod"
SEEN_LISTINGS_FILE = os.getenv("SEEN_LISTINGS_FILE", "seen_listings.json")

# Browser headers om weigeringen of blokkades te voorkomen
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.dehuissleutel.nl/",
    "Connection": "keep-alive",
}


def load_env_file(filepath: str = ".env") -> None:
    """
    Laadt environment variables in uit een lokaal .env bestand als deze aanwezig is.
    Overschrijft reeds gezette variabelen niet.
    """
    if not os.path.exists(filepath):
        return

    logger.debug(f".env bestand gevonden op '{filepath}', variabelen inladen...")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)
    except Exception as e:
        logger.warning(f"Fout bij lezen van {filepath}: {e}")


def get_whatsapp_recipients() -> List[Dict[str, str]]:
    """
    Haalt alle geconfigureerde WhatsApp-ontvangers op uit omgevingsvariabelen.
    Ondersteunt:
    - WHATSAPP_PHONE & CALLMEBOT_API_KEY (hoofdnummer)
    - WHATSAPP_PHONE_2 & CALLMEBOT_API_KEY_2 (tweede nummer)
    - Genummerde variabelen: WHATSAPP_PHONE_N & CALLMEBOT_API_KEY_N (bijv. 3, 4, ...)
    - Komma-gescheiden telefoonnummers en API-keys in WHATSAPP_PHONE en CALLMEBOT_API_KEY
    """
    recipients: List[Dict[str, str]] = []
    seen_phones = set()

    def add_recipient(phone: str, api_key: str, label: str) -> None:
        p = phone.strip()
        k = api_key.strip()
        if p and k and p not in seen_phones:
            seen_phones.add(p)
            recipients.append({"phone": p, "api_key": k, "label": label})

    # 1. Hoofdnummer (standaard of _1)
    phone_1 = os.getenv("WHATSAPP_PHONE", "").strip() or os.getenv("WHATSAPP_PHONE_1", "").strip()
    key_1 = os.getenv("CALLMEBOT_API_KEY", "").strip() or os.getenv("CALLMEBOT_API_KEY_1", "").strip()

    # Ondersteun eventuele komma-gescheiden invoer in WHATSAPP_PHONE
    if "," in phone_1:
        phones = [p.strip() for p in phone_1.split(",") if p.strip()]
        keys = [k.strip() for k in key_1.split(",") if k.strip()]
        for idx, p in enumerate(phones):
            k = keys[idx] if idx < len(keys) else (keys[0] if keys else "")
            add_recipient(p, k, f"Ontvanger {idx + 1}")
    else:
        add_recipient(phone_1, key_1, "Ontvanger 1")

    # 2. Tweede en volgende nummers via WHATSAPP_PHONE_2, WHATSAPP_PHONE_3, etc.
    idx = 2
    while True:
        phone_n = os.getenv(f"WHATSAPP_PHONE_{idx}", "").strip()
        key_n = os.getenv(f"CALLMEBOT_API_KEY_{idx}", "").strip() or key_1

        if not phone_n:
            if idx > 10:
                break
            # Kijk of er eventueel hogere indexen zijn ingesteld
            any_higher = any(os.getenv(f"WHATSAPP_PHONE_{i}") for i in range(idx + 1, idx + 5))
            if not any_higher:
                break
            idx += 1
            continue

        add_recipient(phone_n, key_n, f"Ontvanger {idx}")
        idx += 1

    return recipients


def load_seen_listings(filepath: str = SEEN_LISTINGS_FILE) -> List[str]:
    """
    Laadt de lijst met eerder geziene woning-IDs uit het JSON-bestand.
    Als het bestand nog niet bestaat, wordt een leeg JSON-bestand aangemaakt.
    """
    if not os.path.exists(filepath):
        logger.info(f"'{filepath}' bestaat nog niet; initialiseren als lege JSON-lijst [].")
        save_seen_listings([], filepath=filepath)
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                logger.info(f"{len(data)} reeds geziene listings geladen uit '{filepath}'.")
                return data
            logger.warning(f"Inhoud van '{filepath}' is geen JSON-lijst. Fallback naar lege lijst.")
            return []
    except Exception as e:
        logger.error(f"Fout bij openen van '{filepath}': {e}. Start met lege lijst.")
        return []


def save_seen_listings(seen_listings: List[str], filepath: str = SEEN_LISTINGS_FILE) -> None:
    """
    Slaat de lijst met geziene woning-IDs netjes geformatteerd op in JSON.
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(seen_listings, f, indent=2, ensure_ascii=False)
        logger.info(f"'{filepath}' succesvol bijgewerkt (totaal {len(seen_listings)} listings).")
    except Exception as e:
        logger.error(f"Fout bij opslaan van '{filepath}': {e}")


def get_listing_identifier(href: str) -> str:
    """
    Extraheert een stabiele slug/ID uit de woning-URL.
    Bijvoorbeeld:
      'nl/woning/3881/kerkstraat-17' -> '3881/kerkstraat-17'
      '/nl/aanbod/123-appartement'   -> '123-appartement'
    """
    cleaned = href.strip().split("?")[0].split("#")[0]
    match = re.search(r"(?:woning|aanbod)/(.+)", cleaned)
    if match:
        return match.group(1).strip("/")
    return cleaned.strip("/")


def fetch_listings() -> List[Dict[str, str]]:
    """
    Haalt de aanbodpagina op en parseert alle actuele woningen.
    """
    logger.info(f"Woningaanbod ophalen van {AANBOD_URL}...")
    try:
        response = requests.get(AANBOD_URL, headers=BROWSER_HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Netwerkfout bij ophalen van aanbodpagina: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    listings: List[Dict[str, str]] = []
    seen_ids = set()

    # 1. Doorzoek de woningcards voor gestructureerde data
    cards = soup.find_all("div", class_="card")
    for card in cards:
        woning_a = None
        for a in card.find_all("a", href=True):
            href = a["href"].strip()
            # Herken woning- of aanbodlinks (exclusief overzichtspagina)
            if any(key in href for key in ("nl/woning/", "/woning/", "nl/aanbod/", "/aanbod/")):
                if href.rstrip("/") not in ("nl/aanbod", "/nl/aanbod", "aanbod", "/aanbod"):
                    woning_a = a
                    break

        if not woning_a:
            continue

        raw_href = woning_a["href"].strip()
        listing_id = get_listing_identifier(raw_href)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)

        full_url = urllib.parse.urljoin(BASE_URL, raw_href)

        # Titel / Adres ophalen
        title_el = card.find("h5", class_="pb-0") or card.find("h5")
        title = title_el.get_text(" ", strip=True) if title_el else "Nieuwe Woning"

        # Huurprijs ophalen
        price_el = card.find("h5", class_="u-text-gold") or card.find(class_=lambda c: c and "gold" in c)
        price = price_el.get_text(" ", strip=True) if price_el else ""

        # Extra woningdetails ophalen (type woning, m2, etc.)
        detail_lines = []
        for mt_div in card.find_all("div", class_=lambda c: c and ("mt-1" in c or "mt-2" in c)):
            text = mt_div.get_text(" ", strip=True)
            if text and text not in detail_lines:
                detail_lines.append(text)
        details = " | ".join(detail_lines) if detail_lines else ""

        listings.append({
            "id": listing_id,
            "url": full_url,
            "title": title,
            "price": price,
            "details": details,
        })

    # 2. Fallback: vind eventuele <a> tags die buiten cards staan
    for a in soup.find_all("a", href=True):
        raw_href = a["href"].strip()
        if any(key in raw_href for key in ("nl/woning/", "/woning/", "nl/aanbod/", "/aanbod/")):
            if raw_href.rstrip("/") in ("nl/aanbod", "/nl/aanbod", "aanbod", "/aanbod"):
                continue
            listing_id = get_listing_identifier(raw_href)
            if listing_id not in seen_ids:
                seen_ids.add(listing_id)
                full_url = urllib.parse.urljoin(BASE_URL, raw_href)
                text = a.get_text(" ", strip=True) or "Woninglink"
                listings.append({
                    "id": listing_id,
                    "url": full_url,
                    "title": text,
                    "price": "",
                    "details": "",
                })

    logger.info(f"{len(listings)} actieve woning(en) gevonden op de website.")
    return listings


def send_whatsapp_notification(phone: str, api_key: str, message: str, label: str = "") -> bool:
    """
    Verstuurt een WhatsApp-notificatie via de CallMeBot API naar één ontvanger.
    URL formaat: https://api.callmebot.com/whatsapp.php?phone={phone}&text={text}&apikey={apikey}
    """
    if not phone or not api_key:
        logger.error(f"Kan WhatsApp-bericht niet versturen naar {label or phone}: telefoonnummer of API-key ontbreekt.")
        return False

    encoded_text = urllib.parse.quote_plus(message)
    endpoint = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_text}&apikey={api_key}"

    target_display = f"{label} ({phone})" if label else phone
    try:
        logger.info(f"WhatsApp-notificatie verzenden naar {target_display}...")
        response = requests.get(endpoint, timeout=15)
        if response.status_code == 200:
            logger.info(f"WhatsApp-notificatie succesvol verzonden naar {target_display}.")
            return True
        else:
            logger.error(f"CallMeBot API-fout voor {target_display} (Status {response.status_code}): {response.text.strip()}")
            return False
    except requests.RequestException as e:
        logger.error(f"Fout tijdens CallMeBot API-verzoek naar {target_display}: {e}")
        return False


def format_whatsapp_message(listing: Dict[str, str]) -> str:
    """
    Formatteert de WhatsApp-notificatie voor een nieuw woningaanbod.
    """
    lines = [
        "*De Huissleutel - Nieuw woningaanbod*",
        "",
        f"*Adres:* {listing['title']}",
    ]
    if listing.get("price"):
        lines.append(f"*Prijs:* {listing['price']}")
    if listing.get("details"):
        lines.append(f"*Details:* {listing['details']}")
    lines.append(f"*Link:* {listing['url']}")

    return "\n".join(lines)


def run_monitor() -> None:
    """
    Voert de monitoring cyclus uit:
    1. Laad omgevingsvariabelen (.env en environment)
    2. Zoek alle geconfigureerde WhatsApp-ontvangers
    3. Laad reeds geziene listings
    4. Haal actueel aanbod op
    5. Detecteer nieuwe woningen
    6. Stuur WhatsApp notificaties naar alle ontvangers
    7. Werk seen_listings.json bij
    """
    load_env_file()

    recipients = get_whatsapp_recipients()
    if not recipients:
        logger.warning(
            "Configuratiewaarschuwing: Geen geldige WhatsApp-ontvangers gevonden. "
            "Stel WHATSAPP_PHONE en CALLMEBOT_API_KEY in (.env of omgevingsvariabelen). "
            "Voor een extra nummer kun je ook WHATSAPP_PHONE_2 en CALLMEBOT_API_KEY_2 instellen."
        )
    else:
        logger.info(f"{len(recipients)} WhatsApp-ontvanger(s) geconfigureerd: " +
                    ", ".join(f"{r['label']} ({r['phone']})" for r in recipients))

    seen_ids = set(load_seen_listings(SEEN_LISTINGS_FILE))
    current_listings = fetch_listings()

    new_listings = [item for item in current_listings if item["id"] and item["id"] not in seen_ids]

    if not new_listings:
        logger.info("Geen nieuwe woningen aangetroffen. Alles is up-to-date.")
        return

    logger.info(f"{len(new_listings)} nieuwe woning(en) gevonden.")

    updated_seen_ids = list(seen_ids)

    for listing in new_listings:
        logger.info(f"Nieuw aanbod: '{listing['title']}' ({listing['url']})")
        message = format_whatsapp_message(listing)

        if recipients:
            for recipient in recipients:
                send_whatsapp_notification(
                    phone=recipient["phone"],
                    api_key=recipient["api_key"],
                    message=message,
                    label=recipient["label"],
                )
        else:
            logger.info("WhatsApp-verzending overgeslagen wegens ontbrekende inloggegevens.")
            logger.debug(f"Concept-bericht:\n{message}")

        updated_seen_ids.append(listing["id"])

    save_seen_listings(updated_seen_ids, SEEN_LISTINGS_FILE)
    logger.info("Monitoringcyclus afgerond.")


def main() -> None:
    try:
        run_monitor()
    except KeyboardInterrupt:
        logger.info("Monitor gestopt door gebruiker.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Onverwachte fout opgetreden: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
