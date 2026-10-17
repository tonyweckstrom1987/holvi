"""Kertakayttoinen Gmail-kirjautuminen holville (vain luku -oikeus).

Aja holvin asennuskoneella (palvelimella, jolla salaisuudet.env on). Selain
avataan omalla koneella SSH-tunnelin kautta:
  ssh -L 8765:localhost:8765 kayttaja@palvelin
Skripti kysyy client ID:n ja secretin, tulostaa kirjautumislinkin, odottaa
Googlen paluuta ja tallentaa refresh-tokenin suoraan salaisuudet.env-tiedostoon
(oikeudet 600). Tokenia ei tulosteta koskaan.
"""
import base64
import getpass
import hashlib
import os
import secrets
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import httpx
TIEDOSTO = Path(os.environ.get("HOLVI_DIR", "/etc/holvi")) / "salaisuudet.env"
PORTTI = int(os.environ.get("KIRJAUTUMIS_PORTTI", "8765"))
ISANTA = os.environ.get("HOLVI_KIRJAUTUMIS_ISANTA", "127.0.0.1")
PALUU = f"http://localhost:{PORTTI}/"
AUTH_URL = os.environ.get("HOLVI_GOOGLE_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth")
TOKEN_URL = os.environ.get("HOLVI_GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token")
OIKEUS = "https://www.googleapis.com/auth/gmail.readonly"
def tallenna(uudet):
    """Korvaa tai lisaa avaimet sailyttaen muut rivit ja tiedoston oikeudet."""
    rivit = TIEDOSTO.read_text().splitlines() if TIEDOSTO.exists() else []
    pidetaan = [r for r in rivit if r.split("=", 1)[0].strip() not in uudet]
    pidetaan += [f"{k}={v}" for k, v in uudet.items()]
    # Uusi tiedosto luodaan heti oikeuksilla 600, ei ensin muille luettavana.
    fd = os.open(TIEDOSTO, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as tiedosto:
        tiedosto.write("\n".join(pidetaan) + "\n")
def main():
    client_id = input("Client ID: ").strip()
    client_secret = getpass.getpass("Client secret (ei nay kirjoittaessa): ").strip()
    if not client_id or not client_secret:
        sys.exit("Client ID tai secret puuttuu.")
    tila = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    linkki = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": PALUU,
        "response_type": "code",
        "scope": OIKEUS,
        "access_type": "offline",
        "prompt": "consent",
        "state": tila,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    tulos = {}
    class Kasittelija(BaseHTTPRequestHandler):
        def do_GET(self):
            kysely = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" not in kysely and "error" not in kysely:
                self.send_response(404)
                self.end_headers()
                return
            tulos.update({k: v[0] for k, v in kysely.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Valmis. Voit sulkea taman valilehden.".encode())
        def log_message(self, *args):
            pass
    print("\nAvaa tama linkki selaimessa (kopioi koko rivi):\n")
    print(linkki)
    print("\nOdotan Googlen vastausta...")
    palvelin = HTTPServer((ISANTA, PORTTI), Kasittelija)
    while not tulos:
        palvelin.handle_request()
    palvelin.server_close()
    if "error" in tulos:
        sys.exit("Google palautti virheen: " + tulos["error"])
    if tulos.get("state") != tila:
        sys.exit("Turvatarkistus epaonnistui (state ei tasmaa). Mitaan ei tallennettu.")
    vastaus = httpx.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": tulos["code"],
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": PALUU,
    }, timeout=20)
    if vastaus.status_code != 200:
        sys.exit(f"Tokenin haku epaonnistui (HTTP {vastaus.status_code}). Mitaan ei tallennettu.")
    data = vastaus.json()
    if OIKEUS not in data.get("scope", "").split():
        sys.exit("Google ei antanut Gmail-lukuoikeutta. Mitaan ei tallennettu.")
    if "refresh_token" not in data:
        sys.exit("Google ei antanut refresh-tokenia. Mitaan ei tallennettu.")
    tallenna({
        "GMAIL_CLIENT_ID": client_id,
        "GMAIL_CLIENT_SECRET": client_secret,
        "GMAIL_REFRESH_TOKEN": data["refresh_token"],
    })
    print("VALMIS: Gmail-lupa tallennettu holviin.")
if __name__ == "__main__":
    main()
