# Muutosloki

Muoto noudattaa [Keep a Changelog](https://keepachangelog.com/fi/1.1.0/) -tapaa ja versiointi [semveriä](https://semver.org/lang/fi/).

## [0.1.0] - 2026-10-17

Ensimmäinen julkinen versio. Pohjana kotipalvelimella käytössä ollut holvi, jota on siivottu ja jäsennelty julkaisua varten.

### Lisätty
- 101 testiä (valeverkko, ei oikeita tunnuksia) ja mutaatiotestaus kriittisille riveille.
- CI: testit Pythonilla 3.10–3.13 sekä pakettitesti (rakenna, asenna puhtaaseen ympäristöön, tarkista työkalulistat).
- Repon omat tarkistukset: ei oikeita IP-osoitteita, tailnet-nimiä tai salaisuuden näköisiä merkkijonoja.
- Esimerkit: säännöt, salaisuuspohja, nftables ja kovennetut systemd-unitit.
- Postipalvelimelle pyyntörajoitus (30 / min / IP), kuten pääpalvelimella.

### Muutettu
- Yhteinen ydin (`ydin`, `github`, `gmail`); aiempi Gmail-koodin kaksoiskappale poistettu.
- Palvelimet kuuntelevat oletuksena osoitetta `127.0.0.1` (aiemmin `0.0.0.0`). Aseta `HOLVI_HOST` / `HOLVI_POSTI_HOST` itse.
- Postipalvelin kirjaa kutsujan todellisen IP:n (aiemmin kiinteä arvo) ja käyttää samaa Gmail-tunnuslogiikkaa kuin pääpalvelin (peruutetusta luvasta hälytys).
- `holvi-kirjaudu` kuuntelee oletuksena osoitetta `127.0.0.1` ja luo `salaisuudet.env`-tiedoston oikeuksilla 600.
- Lokitiedosto luodaan oikeuksilla 640.
- MCP-kirjasto kiinnitetty versioon 1.x (`mcp>=1.9,<2`).

### Korjattu
- Repon nimen, tiedostopolun ja viestin tunnisteen tarkistus hyväksyi rivinvaihdon merkkijonon lopussa (`$`-ankkuri); nyt vaaditaan koko merkkijonon täsmäys.
- Pyyntörajoituksen laskuri kasvoi rajattomasti; vanhat minuutit siivotaan.
