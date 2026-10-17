import json
from types import SimpleNamespace

import pytest

from holvi import gmail, ydin

AGENTTI_IP = "192.0.2.10"
POSTI_IP = "192.0.2.11"


class Vastaus:
    def __init__(self, data=None, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("virhe", request=None, response=None)


def ctx_ip(ip):
    """Teeskentelee MCP:n kontekstia: pyynnon tehnyt IP-osoite."""
    pyynto = SimpleNamespace(client=SimpleNamespace(host=ip))
    return SimpleNamespace(request_context=SimpleNamespace(request=pyynto))


@pytest.fixture
def asetukset(tmp_path, monkeypatch):
    """Eristetty asetuskansio ja loki. Testit eivat koske oikeisiin tiedostoihin."""
    kansio = tmp_path / "etc"
    kansio.mkdir()
    (kansio / "saannot.json").write_text(
        json.dumps({
            "agentit": {
                AGENTTI_IP: {"nimi": "agentti", "tyokalut": ["github_repot", "github_commitit", "github_tiedosto"]},
                POSTI_IP: {"nimi": "posti", "tyokalut": ["gmail_haku", "gmail_viesti"]},
            }
        }),
        encoding="utf-8",
    )
    (kansio / "salaisuudet.env").write_text(
        "# kommentti\n"
        "GITHUB_TOKEN=ghp_TESTITOKEN_EI_OIKEA\n"
        "GMAIL_CLIENT_ID=testi-id\n"
        "GMAIL_CLIENT_SECRET=testi-secret-EI-OIKEA\n"
        "GMAIL_REFRESH_TOKEN=testi-refresh-EI-OIKEA\n"
        "TELEGRAM_BOT_TOKEN=123456:TESTI-EI-OIKEA\n"
        "TELEGRAM_CHAT_ID=42\n",
        encoding="utf-8",
    )
    loki = tmp_path / "loki" / "audit.log"
    monkeypatch.setattr(ydin, "ASETUKSET", kansio)
    monkeypatch.setattr(ydin, "LOKI", loki)
    ydin._laskuri.clear()
    gmail._gmail_token.update({"arvo": None, "vanhenee": 0.0})
    return SimpleNamespace(kansio=kansio, loki=loki)


@pytest.fixture
def halytykset(monkeypatch):
    """Tallentaa Telegram-halytykset ilman verkkoa."""
    lista = []
    monkeypatch.setattr(ydin, "telegram", lambda viesti, etuliite="Holvi": lista.append(viesti))
    return lista


def lokirivit(asetukset):
    if not asetukset.loki.exists():
        return []
    return [json.loads(r) for r in asetukset.loki.read_text(encoding="utf-8").splitlines()]


SALAISUUDET = [
    "ghp_TESTITOKEN_EI_OIKEA",
    "testi-secret-EI-OIKEA",
    "testi-refresh-EI-OIKEA",
    "123456:TESTI-EI-OIKEA",
]
