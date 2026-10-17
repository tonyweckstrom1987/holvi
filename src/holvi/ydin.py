"""Holvin yhteinen ydin: asetukset, salaisuudet, loki, halytys ja pyyntojen tarkistus.

Periaate: agentti ei koskaan nae avaimia. Tama moduuli lukee salaisuudet
tiedostosta, kirjaa jokaisen pyynnon (ilman avaimia ja ilman haettua dataa)
ja paattaa, saako kutsuja kayttaa pyydettya tyokalua.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# httpx kirjaa muuten URL:t lokiin, ja Telegram-URL sisaltaa tokenin
logging.getLogger("httpx").setLevel(logging.WARNING)

ASETUKSET = Path(os.environ.get("HOLVI_DIR", "/etc/holvi"))
LOKI = Path(os.environ.get("HOLVI_LOKI", "/var/log/holvi/audit.log"))
MAX_PYYNTOJA_MINUUTISSA = 30

# (ip, minuutti) -> pyyntojen maara
_laskuri = {}


def salaisuudet():
    """Luetaan joka kerta, jotta avaimen vaihto ei vaadi uudelleenkaynnistysta."""
    tulos = {}
    polku = ASETUKSET / "salaisuudet.env"
    if polku.exists():
        for rivi in polku.read_text().splitlines():
            rivi = rivi.strip()
            if rivi and not rivi.startswith("#") and "=" in rivi:
                avain, arvo = rivi.split("=", 1)
                tulos[avain.strip()] = arvo.strip()
    return tulos


def saannot():
    return json.loads((ASETUKSET / "saannot.json").read_text(encoding="utf-8"))


def kirjaa(ip, nimi, tyokalu, parametrit, tulos, lisatieto=""):
    """Loki ei koskaan sisalla avaimia eika haettua dataa."""
    LOKI.parent.mkdir(parents=True, exist_ok=True)
    rivi = {
        "aika": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ip": ip,
        "agentti": nimi,
        "tyokalu": tyokalu,
        "parametrit": parametrit,
        "tulos": tulos,
        "lisatieto": lisatieto,
    }
    # Lokissa on hakulausekkeita ja viestien tunnisteita: ei muille luettavaksi.
    fd = os.open(LOKI, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o640)
    with os.fdopen(fd, "a", encoding="utf-8") as tiedosto:
        tiedosto.write(json.dumps(rivi, ensure_ascii=False) + "\n")


def telegram(viesti, etuliite="Holvi"):
    """Halytys Telegramiin. Ei koskaan nosta virhetta eika tulosta tokenia."""
    s = salaisuudet()
    token, chat = s.get("TELEGRAM_BOT_TOKEN"), s.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": f"{etuliite}: {viesti}"},
            timeout=10,
        )
    except httpx.HTTPError:
        pass


def kutsujan_ip(ctx):
    pyynto = ctx.request_context.request
    if pyynto is None or pyynto.client is None:
        return "tuntematon"
    return pyynto.client.host


def _rajoita(ip, nimi, tyokalu, parametrit, etuliite):
    """Pyyntorajoitus: enintaan MAX_PYYNTOJA_MINUUTISSA per IP ja minuutti."""
    minuutti = int(time.time() // 60)
    for vanha in [k for k in _laskuri if k[1] < minuutti]:
        del _laskuri[vanha]
    avain = (ip, minuutti)
    _laskuri[avain] = _laskuri.get(avain, 0) + 1
    if _laskuri[avain] > MAX_PYYNTOJA_MINUUTISSA:
        kirjaa(ip, nimi, tyokalu, parametrit, "estetty", "liikaa pyyntoja")
        if _laskuri[avain] == MAX_PYYNTOJA_MINUUTISSA + 1:
            telegram(f"ESTETTY: {nimi} ({ip}) teki liikaa pyyntoja minuutissa.", etuliite)
        raise PermissionError("Holvi: liikaa pyyntoja, odota hetki.")


def tarkista_saannoilla(ctx, tyokalu, parametrit):
    """Palauttaa (ip, agentin nimi) tai nostaa virheen, jos pyynto ei ole sallittu.

    Oikeudet tulevat saannot.json-tiedostosta: kutsujan IP -> sallitut tyokalut.
    """
    ip = kutsujan_ip(ctx)
    agentti = saannot().get("agentit", {}).get(ip)
    nimi = agentti["nimi"] if agentti else "tuntematon"
    if agentti is None or tyokalu not in agentti.get("tyokalut", []):
        kirjaa(ip, nimi, tyokalu, parametrit, "estetty", "ei oikeutta")
        telegram(f"ESTETTY: {nimi} ({ip}) yritti kayttaa tyokalua {tyokalu}.")
        raise PermissionError("Holvi: ei oikeutta tahan tyokaluun.")
    _rajoita(ip, nimi, tyokalu, parametrit, "Holvi")
    return ip, nimi


def tarkista_kiintea(nimi, etuliite):
    """Tarkistus palvelimelle, jolla on vain yksi asiakas (esim. posti-agentti).

    Oikea raja on palomuuri (ks. esimerkit/nftables.example.conf): tama vain
    nimeaa kutsujan lokiin ja rajoittaa pyyntojen maaran.
    """

    def tarkista(ctx, tyokalu, parametrit):
        ip = kutsujan_ip(ctx)
        _rajoita(ip, nimi, tyokalu, parametrit, etuliite)
        return ip, nimi

    return tarkista
