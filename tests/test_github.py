import base64

import httpx
import pytest
from mcp.server.fastmcp import FastMCP

from holvi import github, ydin

from conftest import SALAISUUDET, Vastaus, lokirivit


def tarkista_ok(ctx, tyokalu, parametrit):
    return "192.0.2.10", "testi"


@pytest.fixture
def tyokalut():
    return github.rekisteroi(FastMCP("testi"), tarkista_ok)


def koodaa(teksti):
    raaka = teksti if isinstance(teksti, bytes) else teksti.encode()
    return base64.b64encode(raaka).decode()


@pytest.mark.parametrize("polku", ["", "README.md", "src/app/main.py", "docs/a b.md", "a/b/c.txt"])
def test_polku_kelpaa(polku):
    assert github.polku_kelpaa(polku)


@pytest.mark.parametrize(
    "polku",
    ["/etc/passwd", "../x", "a/../b", "a/./b", "a//b", "a/b/", "x" * 301, "a;b", "a?b=1", "a%2e%2e/b", "a\\b", "a\nb", "README.md\n"],
)
def test_polku_ei_kelpaa(polku):
    assert not github.polku_kelpaa(polku)


@pytest.mark.parametrize(
    "polku",
    [".env", "config/.env.local", "id_rsa", "home/id_ed25519.pub", "x/server.pem", "a/b/private.key",
     "keys/cert.p12", "cert.pfx", "vault.kdbx", ".npmrc", ".pypirc", ".netrc", "credentials.json",
     "aws/credentials", "secrets.yml", "secret.json", "SECRETS.YML", "dir/.ENV"],
)
def test_arkaluonteiset_tiedostonimet_estetaan(polku):
    assert github.ARKAT_TIEDOSTOT.search(polku)


@pytest.mark.parametrize("polku", ["README.md", "src/environment.py", "docs/secrets-management.md", "keyboard.py", "env.md"])
def test_tavalliset_tiedostot_eivat_osu_estoon(polku):
    assert not github.ARKAT_TIEDOSTOT.search(polku)


def test_github_haku_ilman_tokenia_ei_kutsu_verkkoa(asetukset, monkeypatch):
    (asetukset.kansio / "salaisuudet.env").write_text("", encoding="utf-8")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("ei saa kutsua verkkoa"))
    with pytest.raises(RuntimeError, match="ei ole viela asetettu"):
        github.github_haku("/user")


def test_github_haku_laheta_tokenin_vain_otsikossa(asetukset, monkeypatch):
    nahty = {}

    def get(url, params, headers, timeout):
        nahty.update(url=url, params=params, headers=headers)
        return Vastaus({"ok": 1})

    monkeypatch.setattr(httpx, "get", get)
    assert github.github_haku("/user", {"a": 1}) == {"ok": 1}
    assert nahty["url"] == "https://api.github.com/user"
    assert nahty["headers"]["Authorization"] == "Bearer ghp_TESTITOKEN_EI_OIKEA"
    assert "ghp_TESTITOKEN_EI_OIKEA" not in nahty["url"]


def test_github_401_halyttaa_ja_nostaa_virheen_ilman_tokenia_viestissa(asetukset, halytykset, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: Vastaus({}, 401))
    with pytest.raises(RuntimeError) as virhe:
        github.github_haku("/user")
    assert "ghp_" not in str(virhe.value)
    assert any("vanhentunut" in h for h in halytykset)


def test_github_repot_palauttaa_vain_valitut_kentat(asetukset, tyokalut, monkeypatch):
    monkeypatch.setattr(github, "github_haku", lambda polku, p=None: [
        {"name": "a", "description": None, "language": None, "private": True, "pushed_at": "t", "html_url": "u", "turha": "x"}
    ])
    tulos = tyokalut["github_repot"](None)
    assert tulos == [{"nimi": "a", "kuvaus": "", "kieli": "", "yksityinen": True, "paivitetty": "t", "url": "u"}]
    assert lokirivit(asetukset)[0]["tulos"] == "ok"


def test_commitit_virheellinen_repon_nimi_estetaan_ennen_verkkoa(asetukset, tyokalut, monkeypatch):
    monkeypatch.setattr(github, "github_haku", lambda *a, **k: pytest.fail("ei saa kutsua GitHubia"))
    for nimi in ["..", ".", "a/b", "x y", "", "a" * 101, "../..", "repo;rm", "repo\n"]:
        with pytest.raises(ValueError):
            tyokalut["github_commitit"](None, nimi)
    assert {r["tulos"] for r in lokirivit(asetukset)} == {"estetty"}


def test_commitit_rajaa_maaran_ja_lyhentaa_viestin(asetukset, tyokalut, monkeypatch):
    haut = []

    def haku(polku, parametrit=None):
        haut.append((polku, parametrit))
        if polku == "/user":
            return {"login": "omistaja"}
        return [{"sha": "abcdef123456", "commit": {"message": "otsikko\n\nrunko", "author": {"date": "pvm"}}}]

    monkeypatch.setattr(github, "github_haku", haku)
    for pyydetty, odotettu in [(999, 30), (0, 1), (-5, 1), (7, 7)]:
        tulos = tyokalut["github_commitit"](None, "repo", pyydetty)
        assert haut[-1] == ("/repos/omistaja/repo/commits", {"per_page": odotettu})
    assert tulos == [{"sha": "abcdef1", "viesti": "otsikko", "pvm": "pvm"}]


def test_tiedosto_estaa_arkaluonteisen_tai_virheellisen_polun_ennen_verkkoa(asetukset, tyokalut, monkeypatch):
    monkeypatch.setattr(github, "github_haku", lambda *a, **k: pytest.fail("ei saa kutsua GitHubia"))
    for polku in [".env", "a/id_rsa", "../x", "/etc/passwd"]:
        with pytest.raises(ValueError):
            tyokalut["github_tiedosto"](None, "repo", polku)
    with pytest.raises(ValueError):
        tyokalut["github_tiedosto"](None, "..", "README.md")


def vastaa_tiedostolla(monkeypatch, data):
    def haku(polku, parametrit=None):
        return {"login": "o"} if polku == "/user" else data

    monkeypatch.setattr(github, "github_haku", haku)


def test_tiedosto_lukee_tekstin_ja_merkitsee_sen_ulkopuoliseksi_dataksi(asetukset, tyokalut, monkeypatch):
    vastaa_tiedostolla(monkeypatch, {"type": "file", "encoding": "base64", "size": 5, "content": koodaa("heiä")})
    tulos = tyokalut["github_tiedosto"](None, "repo", "README.md")
    assert tulos["teksti"] == "heiä"
    assert "ulkopuolista dataa" in tulos["varoitus"]


def test_tiedosto_lyhentaa_pitkan_tekstin(asetukset, tyokalut, monkeypatch):
    pitka = "x" * (github.TIEDOSTO_MAX_MERKKEJA + 50)
    vastaa_tiedostolla(monkeypatch, {"type": "file", "encoding": "base64", "size": len(pitka), "content": koodaa(pitka)})
    teksti = tyokalut["github_tiedosto"](None, "repo", "iso.txt")["teksti"]
    assert teksti.endswith("[...lyhennetty]")
    assert len(teksti) == github.TIEDOSTO_MAX_MERKKEJA + len("\n[...lyhennetty]")


def test_tiedosto_ohittaa_binaarin_ja_liian_suuren(asetukset, tyokalut, monkeypatch):
    vastaa_tiedostolla(monkeypatch, {"type": "file", "encoding": "base64", "size": 3, "content": koodaa(b"a\x00b")})
    assert tyokalut["github_tiedosto"](None, "repo", "x.bin")["ohitettu"] == "binaaritiedosto"
    vastaa_tiedostolla(monkeypatch, {"type": "file", "encoding": "base64", "size": github.TIEDOSTO_MAX_TAVUJA + 1, "content": ""})
    assert tyokalut["github_tiedosto"](None, "repo", "x.bin")["ohitettu"] == "liian suuri"
    vastaa_tiedostolla(monkeypatch, {"type": "file", "encoding": "base64", "size": 2, "content": koodaa(b"\xff\xfe")})
    assert tyokalut["github_tiedosto"](None, "repo", "x.txt")["ohitettu"] == "binaaritiedosto"


def test_tiedosto_listaa_hakemiston_rajatusti_ja_ohittaa_muut_tyypit(asetukset, tyokalut, monkeypatch):
    lista = [{"name": f"f{i}", "type": "file", "size": i, "download_url": "salainen-url"} for i in range(500)]
    vastaa_tiedostolla(monkeypatch, lista)
    tulos = tyokalut["github_tiedosto"](None, "repo", "")
    assert tulos["tyyppi"] == "hakemisto" and len(tulos["kohteet"]) == github.HAKEMISTO_MAX_RIVEJA
    assert set(tulos["kohteet"][0]) == {"nimi", "tyyppi", "koko"}
    vastaa_tiedostolla(monkeypatch, {"type": "symlink"})
    assert tyokalut["github_tiedosto"](None, "repo", "x")["teksti"] == ""


def test_loki_ei_sisalla_tiedoston_sisaltoa_eika_salaisuuksia(asetukset, tyokalut, monkeypatch):
    vastaa_tiedostolla(monkeypatch, {"type": "file", "encoding": "base64", "size": 12, "content": koodaa("SALAINEN-SISALTO")})
    tyokalut["github_tiedosto"](None, "repo", "README.md")
    teksti = asetukset.loki.read_text(encoding="utf-8")
    assert "SALAINEN-SISALTO" not in teksti
    assert not any(s in teksti for s in SALAISUUDET)


def test_virhe_kirjataan_vain_poikkeuksen_tyyppina(asetukset, tyokalut, monkeypatch):
    def haku(polku, parametrit=None):
        raise RuntimeError("viesti jossa ghp_TESTITOKEN_EI_OIKEA")

    monkeypatch.setattr(github, "github_haku", haku)
    with pytest.raises(RuntimeError):
        tyokalut["github_repot"](None)
    r = lokirivit(asetukset)[0]
    assert r["tulos"] == "virhe" and r["lisatieto"] == "RuntimeError"
    assert "ghp_" not in asetukset.loki.read_text(encoding="utf-8")
