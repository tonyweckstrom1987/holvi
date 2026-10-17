import os
import stat

from holvi import kirjaudu


def test_tallenna_luo_tiedoston_oikeuksilla_600(tmp_path, monkeypatch):
    polku = tmp_path / "salaisuudet.env"
    monkeypatch.setattr(kirjaudu, "TIEDOSTO", polku)
    kirjaudu.tallenna({"GMAIL_CLIENT_ID": "a", "GMAIL_REFRESH_TOKEN": "b"})
    assert stat.S_IMODE(os.stat(polku).st_mode) == 0o600
    assert polku.read_text() == "GMAIL_CLIENT_ID=a\nGMAIL_REFRESH_TOKEN=b\n"


def test_tallenna_korvaa_vain_omat_avaimet_ja_sailyttaa_muut_rivit(tmp_path, monkeypatch):
    polku = tmp_path / "salaisuudet.env"
    polku.write_text("GITHUB_TOKEN=pysyy\nGMAIL_CLIENT_ID=vanha\n# kommentti\n")
    polku.chmod(0o640)
    monkeypatch.setattr(kirjaudu, "TIEDOSTO", polku)
    kirjaudu.tallenna({"GMAIL_CLIENT_ID": "uusi"})
    rivit = polku.read_text().splitlines()
    assert "GITHUB_TOKEN=pysyy" in rivit and "# kommentti" in rivit
    assert "GMAIL_CLIENT_ID=uusi" in rivit and "GMAIL_CLIENT_ID=vanha" not in rivit
    assert stat.S_IMODE(os.stat(polku).st_mode) == 0o640  # olemassa olevia oikeuksia ei muuteta


def test_kirjautuminen_pyytaa_vain_lukuoikeuden_ja_kuuntelee_oletuksena_paikallisesti():
    assert kirjaudu.OIKEUS == "https://www.googleapis.com/auth/gmail.readonly"
    assert kirjaudu.ISANTA == "127.0.0.1"
