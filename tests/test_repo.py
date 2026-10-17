"""Repon omat tarkistukset: ei salaisuuksia, ei oikeita osoitteita, ei vahingossa mukaan eksyneita tiedostoja."""
import re
import subprocess
from pathlib import Path

JUURI = Path(__file__).resolve().parent.parent
TARKISTA_PAATTEET = {".py", ".md", ".json", ".toml", ".yml", ".yaml", ".conf", ".service", ".timer", ".env", ".sh", ".txt", ".example", ""}


def seurattavat():
    try:
        ulos = subprocess.run(["git", "ls-files"], cwd=JUURI, capture_output=True, text=True, check=True).stdout.split()
        tiedostot = [JUURI / t for t in ulos]
    except (subprocess.CalledProcessError, FileNotFoundError):
        tiedostot = [p for p in JUURI.rglob("*") if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts]
    ohita = {"test_repo.py"}  # tama tiedosto sisaltaa hakumallit
    return [
        t for t in tiedostot
        if t.is_file() and t.name not in ohita and t.suffix in TARKISTA_PAATTEET
        and not any(osa in {".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist"} or osa.endswith(".egg-info") for osa in t.parts)
    ]


# 192.0.2.0/24, 198.51.100.0/24 ja 203.0.113.0/24 ovat dokumentointiin varattuja osoitteita
SALLITUT_IP = re.compile(r"^(192\.0\.2|198\.51\.100|203\.0\.113)\.\d+$|^(127\.0\.0\.1|0\.0\.0\.0)$")
IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SALAISUUS_MALLIT = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"\b[0-9]{8,10}:[A-Za-z0-9_-]{30,}\b"),  # Telegram-bottitokeni
    re.compile(r"GOCSPX-[A-Za-z0-9_-]{10,}"),
    re.compile(r"[0-9]{6,}-[a-z0-9]{20,}\.apps\.googleusercontent\.com"),
    re.compile(r"1//[0-9A-Za-z_-]{30,}"),  # Googlen refresh token
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def test_ei_oikeita_ip_osoitteita():
    for t in seurattavat():
        for osuma in IP.findall(t.read_text(encoding="utf-8", errors="ignore")):
            assert SALLITUT_IP.match(osuma), f"{t.relative_to(JUURI)}: {osuma}"


def test_ei_tailnet_nimia():
    for t in seurattavat():
        assert ".ts.net" not in t.read_text(encoding="utf-8", errors="ignore"), t.name


def test_ei_salaisuuden_nakoisia_merkkijonoja():
    for t in seurattavat():
        teksti = t.read_text(encoding="utf-8", errors="ignore")
        for malli in SALAISUUS_MALLIT:
            assert not malli.search(teksti), f"{t.relative_to(JUURI)}: {malli.pattern}"


def test_ei_oikeita_salaisuustiedostoja_mukana():
    for t in seurattavat():
        assert t.name not in {"salaisuudet.env", "kuma_push_token", "saannot.json"}, t.name


def test_esimerkkitiedostot_ovat_olemassa():
    for nimi in ["saannot.example.json", "salaisuudet.example.env", "nftables.example.conf"]:
        assert (JUURI / "esimerkit" / nimi).exists(), nimi


def test_lahdekoodi_on_ascii():
    for t in (JUURI / "src").rglob("*.py"):
        t.read_text(encoding="ascii")
