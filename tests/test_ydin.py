import os
import stat

import httpx
import pytest

from holvi import ydin

from conftest import AGENTTI_IP, POSTI_IP, SALAISUUDET, ctx_ip, lokirivit


def test_salaisuudet_ohittaa_kommentit_ja_tyhjat_ja_sailyttaa_yhtasuuruusmerkin(asetukset):
    (asetukset.kansio / "salaisuudet.env").write_text(
        "# kommentti\n\n  A = yksi  \nB=arvo=jossa=yhtasuuruus\nrikkinainen rivi\n", encoding="utf-8"
    )
    assert ydin.salaisuudet() == {"A": "yksi", "B": "arvo=jossa=yhtasuuruus"}


def test_salaisuudet_puuttuva_tiedosto_antaa_tyhjan(asetukset):
    (asetukset.kansio / "salaisuudet.env").unlink()
    assert ydin.salaisuudet() == {}


def test_kirjaa_kirjoittaa_json_rivin_ilman_salaisuuksia(asetukset):
    ydin.kirjaa("192.0.2.50", "agentti", "github_repot", {"x": 1}, "ok", "3 repoa")
    rivit = lokirivit(asetukset)
    assert rivit[0]["tyokalu"] == "github_repot"
    assert set(rivit[0]) == {"aika", "ip", "agentti", "tyokalu", "parametrit", "tulos", "lisatieto"}
    teksti = asetukset.loki.read_text(encoding="utf-8")
    assert not any(s in teksti for s in SALAISUUDET)


def test_loki_luodaan_oikeuksilla_ei_muille_luettavaksi(asetukset):
    ydin.kirjaa("ip", "n", "t", {}, "ok")
    tila = stat.S_IMODE(os.stat(asetukset.loki).st_mode)
    assert tila & 0o007 == 0  # ei oikeuksia "muille"


def test_tuntematon_ip_estetaan_kirjataan_ja_halytetaan(asetukset, halytykset):
    with pytest.raises(PermissionError):
        ydin.tarkista_saannoilla(ctx_ip("203.0.113.5"), "github_repot", {})
    r = lokirivit(asetukset)[0]
    assert r["tulos"] == "estetty" and r["agentti"] == "tuntematon"
    assert halytykset and "ESTETTY" in halytykset[0]


def test_tunnettu_ip_mutta_vaara_tyokalu_estetaan(asetukset, halytykset):
    # posti-agentilla on vain gmail-oikeudet: GitHub ei saa onnistua
    with pytest.raises(PermissionError):
        ydin.tarkista_saannoilla(ctx_ip(POSTI_IP), "github_repot", {})
    with pytest.raises(PermissionError):
        ydin.tarkista_saannoilla(ctx_ip(AGENTTI_IP), "gmail_haku", {})
    assert [r["tulos"] for r in lokirivit(asetukset)] == ["estetty", "estetty"]


def test_sallittu_pyynto_palauttaa_ip_ja_nimen(asetukset, halytykset):
    assert ydin.tarkista_saannoilla(ctx_ip(AGENTTI_IP), "github_repot", {}) == (AGENTTI_IP, "agentti")
    assert halytykset == []


def test_saannot_puuttuu_tai_rikki_ei_anna_oikeutta(asetukset, halytykset):
    (asetukset.kansio / "saannot.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PermissionError):
        ydin.tarkista_saannoilla(ctx_ip(AGENTTI_IP), "github_repot", {})
    (asetukset.kansio / "saannot.json").write_text("rikki", encoding="utf-8")
    with pytest.raises(ValueError):  # JSONDecodeError: fail closed, pyyntoa ei hyvaksyta
        ydin.tarkista_saannoilla(ctx_ip(AGENTTI_IP), "github_repot", {})


def test_pyyntorajoitus_estaa_31_pyynnon_ja_halyttaa_vain_kerran(asetukset, halytykset, monkeypatch):
    monkeypatch.setattr(ydin.time, "time", lambda: 6000.0)
    ctx = ctx_ip(AGENTTI_IP)
    for _ in range(ydin.MAX_PYYNTOJA_MINUUTISSA):
        ydin.tarkista_saannoilla(ctx, "github_repot", {})
    for _ in range(3):
        with pytest.raises(PermissionError, match="liikaa"):
            ydin.tarkista_saannoilla(ctx, "github_repot", {})
    assert len([h for h in halytykset if "liikaa" in h]) == 1


def test_pyyntorajoitus_nollautuu_seuraavana_minuuttina_ja_vanhat_avaimet_poistuvat(asetukset, halytykset, monkeypatch):
    aika = {"t": 6000.0}
    monkeypatch.setattr(ydin.time, "time", lambda: aika["t"])
    ctx = ctx_ip(AGENTTI_IP)
    for _ in range(ydin.MAX_PYYNTOJA_MINUUTISSA):
        ydin.tarkista_saannoilla(ctx, "github_repot", {})
    aika["t"] += 60
    ydin.tarkista_saannoilla(ctx, "github_repot", {})
    assert len(ydin._laskuri) == 1  # edellisen minuutin laskuri siivottu


def test_rajoitus_on_ip_kohtainen(asetukset, halytykset, monkeypatch):
    monkeypatch.setattr(ydin.time, "time", lambda: 6000.0)
    for _ in range(ydin.MAX_PYYNTOJA_MINUUTISSA):
        ydin.tarkista_saannoilla(ctx_ip(AGENTTI_IP), "github_repot", {})
    # toinen asiakas ei kuulu saman rajan alle
    ydin.tarkista_saannoilla(ctx_ip(POSTI_IP), "gmail_haku", {})


def test_kiintea_tarkistus_nimeaa_kutsujan_ja_rajoittaa(asetukset, halytykset, monkeypatch):
    monkeypatch.setattr(ydin.time, "time", lambda: 6000.0)
    tarkista = ydin.tarkista_kiintea("posti-agentti", "Holvi-posti")
    assert tarkista(ctx_ip("192.0.2.99"), "gmail_haku", {}) == ("192.0.2.99", "posti-agentti")
    for _ in range(ydin.MAX_PYYNTOJA_MINUUTISSA - 1):
        tarkista(ctx_ip("192.0.2.99"), "gmail_haku", {})
    with pytest.raises(PermissionError):
        tarkista(ctx_ip("192.0.2.99"), "gmail_haku", {})


def test_kutsujan_ip_ilman_pyyntoa_on_tuntematon():
    from types import SimpleNamespace

    assert ydin.kutsujan_ip(SimpleNamespace(request_context=SimpleNamespace(request=None))) == "tuntematon"
    pyynto = SimpleNamespace(client=None)
    assert ydin.kutsujan_ip(SimpleNamespace(request_context=SimpleNamespace(request=pyynto))) == "tuntematon"


def test_telegram_lahettaa_tokenilla_mutta_ei_vuoda_sita_virheeseen(asetukset, monkeypatch):
    kutsut = []

    def posti(url, json, timeout):
        kutsut.append((url, json))
        raise httpx.ConnectError("verkko poikki")

    monkeypatch.setattr(httpx, "post", posti)
    ydin.telegram("testi", "Holvi")  # ei saa nostaa virhetta
    assert kutsut[0][0].startswith("https://api.telegram.org/bot123456:")
    assert kutsut[0][1] == {"chat_id": "42", "text": "Holvi: testi"}


def test_telegram_ilman_asetuksia_ei_tee_mitaan(asetukset, monkeypatch):
    (asetukset.kansio / "salaisuudet.env").write_text("", encoding="utf-8")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("ei saa kutsua verkkoa"))
    ydin.telegram("testi")
