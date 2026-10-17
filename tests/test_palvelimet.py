import asyncio
import importlib

import pytest

from holvi import palvelin, posti


def nimet(mcp):
    return {t.name for t in asyncio.run(mcp.list_tools())}


def test_paapalvelin_tarjoaa_tasmalleen_odotetut_tyokalut():
    assert nimet(palvelin.mcp) == {"github_repot", "github_commitit", "github_tiedosto", "gmail_haku", "gmail_viesti"}


def test_postipalvelin_tarjoaa_vain_gmail_lukutyokalut_ei_githubia():
    assert nimet(posti.mcp) == {"gmail_haku", "gmail_viesti"}


@pytest.mark.parametrize("mcp", [palvelin.mcp, posti.mcp])
def test_kaikki_tyokalut_ovat_lukutyokaluja(mcp):
    kielletyt = ("send", "delete", "remove", "modify", "write", "create", "post", "push", "lahet", "poista", "kirjoita", "luo")
    for nimi in nimet(mcp):
        assert not any(k in nimi for k in kielletyt), nimi


@pytest.mark.parametrize("mcp", [palvelin.mcp, posti.mcp])
def test_konteksti_ei_nay_agentille_tyokalun_parametrina(mcp):
    for tyokalu in asyncio.run(mcp.list_tools()):
        assert "ctx" not in tyokalu.inputSchema.get("properties", {}), tyokalu.name


def test_palvelimet_kuuntelevat_oletuksena_vain_paikallisesti():
    assert palvelin.mcp.settings.host == "127.0.0.1" and posti.mcp.settings.host == "127.0.0.1"
    assert palvelin.mcp.settings.port == 8700 and posti.mcp.settings.port == 8701


def test_osoite_ja_portti_voi_asettaa_ymparistomuuttujilla(monkeypatch):
    monkeypatch.setenv("HOLVI_HOST", "192.0.2.5")
    monkeypatch.setenv("HOLVI_PORT", "9000")
    try:
        uusi = importlib.reload(palvelin)
        assert uusi.mcp.settings.host == "192.0.2.5" and uusi.mcp.settings.port == 9000
    finally:
        monkeypatch.undo()
        importlib.reload(palvelin)
