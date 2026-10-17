# holvi

[![CI](https://github.com/tonyweckstrom1987/holvi/actions/workflows/ci.yml/badge.svg)](https://github.com/tonyweckstrom1987/holvi/actions/workflows/ci.yml) ![Lisenssi: MIT](https://img.shields.io/badge/lisenssi-MIT-blue.svg)

Tunnusvälittäjä tekoälyagenteille. Agentti ei koskaan näe avaimia: se pyytää holvia tekemään rajatun haun, holvi tarkistaa säännöt, tekee haun itse ja palauttaa vain tuloksen. Jokainen pyyntö kirjataan lokiin, ja estetyistä pyynnöistä tulee hälytys.

**English summary:** A small MCP server that sits between AI agents and your accounts. Agents get narrow, read-only tools (GitHub repos/commits/files, Gmail search/read) and never see the API tokens. Per-client tool permissions by source IP, firewall-level port isolation, input validation, size and rate limits, an audit log without secrets or fetched data, and Telegram alerts for blocked requests. About 640 lines of Python, 101 tests (mock network only), pinned to `mcp<2`.

**Teknologiat:** Python 3.10+, MCP (FastMCP, streamable HTTP), httpx, pytest.

> **Tila:** Versio 0.1.0. Koodi on johdettu kotipalvelimella käytössä olleesta holvista ja siivottu julkaisua varten (ks. [CHANGELOG](CHANGELOG.md)). Testit käyttävät vain valeverkkoa: oikeaa GitHubia tai Googlea vasten testattu on käytössä ollut edeltäjä, ei tätä julkaisuversiota sellaisenaan.

## Miksi

Jos agentille antaa suoraan GitHub-tokenin tai sähköpostin tunnukset, yksi onnistunut prompt-injektio (esim. haitallinen sähköposti, jonka agentti lukee) voi vuotaa ne. Holvi pitää tunnukset toisessa prosessissa ja toisella käyttäjällä. Agentti saa käyttöönsä vain ne työkalut, jotka sille on erikseen sallittu, ja jokaisella työkalulla on kova katto.

```text
 agentti A (192.0.2.10) --\                       +--> GitHub (token vain holvilla)
                           >-- MCP/HTTP --> holvi +
 agentti B (192.0.2.11) --/   (palomuuri +        +--> Gmail (vain luku, Googlen puolella rajattu)
                              IP-säännöt)
                                  |
                                  +--> audit-loki (ei avaimia, ei haettua dataa)
                                  +--> Telegram-hälytys estetyistä pyynnöistä
```

Kaksi prosessia: `holvi` (portti 8700, oikeudet `saannot.json`:sta) ja `holvi-posti` (portti 8701, vain Gmail). Erillinen posti-prosessi on tahallinen: sähköpostia lukeva agentti on suurimmassa prompt-injektion riskissä, eikä sen koskaan pidä nähdä GitHub-työkaluja.

## Työkalut

| Työkalu | Mitä tekee | Rajat |
| --- | --- | --- |
| `github_repot` | Listaa omat repot | Enintään 100, vain valitut kentät |
| `github_commitit` | Repon viimeisimmät commitit | Enintään 30, viestistä vain otsikkorivi |
| `github_tiedosto` | Lukee tiedoston tai listaa hakemiston | Tekstiä enintään 20 000 merkkiä, hakemisto 200 riviä, binäärit ohitetaan, arkaluonteiset tiedostonimet estetty |
| `gmail_haku` | Hakee viestejä Gmailin hakusyntaksilla | Enintään 20 viestiä, haku enintään 200 merkkiä |
| `gmail_viesti` | Lukee yhden viestin tekstin | Enintään 8 000 merkkiä, liitteistä vain nimet |

Kaikki tekevät vain lukupyyntöjä. Palautettu sisältö on merkitty ulkopuoliseksi dataksi (`varoitus`-kenttä).

## Turvamalli

Suojaus on kerroksittain, jotta yhden kerroksen virhe ei riitä:

1. **Palomuuri.** Kukin asiakas pääsee vain omaan porttiinsa ([esimerkki](esimerkit/nftables.example.conf)). Tämä on oikea raja.
2. **Oikeudet IP:n mukaan.** `saannot.json` kertoo, mitä työkaluja kukin lähde-IP saa käyttää. Tuntematon IP tai kielletty työkalu: pyyntö estetään, kirjataan ja siitä lähtee hälytys. Jos säännöt puuttuvat tai ovat rikki, mitään ei sallita.
3. **Vain luku.** Gmail-oikeus on Googlen puolella rajattu `gmail.readonly`-scopeen, joten viestin lähetys tai poisto ei onnistu vaikka koodissa olisi virhe. GitHubiin käytetään vain GET-pyyntöjä; suosittelen hienojakoista (fine-grained) tokenia, jolla on vain lukuoikeus tarvittaviin repoihin.
4. **Syötteen tarkistus.** Repon nimi, tiedostopolku ja viestin tunniste tarkistetaan tiukalla sallittujen merkkien listalla ennen kuin mitään kutsutaan ulos. Polussa ei sallita `..`-osia.
5. **Arkaluonteiset tiedostonimet.** `.env`, avaimet (`id_rsa`, `*.pem`, `*.key`, ...), `.npmrc`, `credentials*`, `secrets.*` ym. eivät ole luettavissa GitHubin kautta.
6. **Ulkopuolinen data.** Tiedostojen ja viestien sisältö palautetaan varoituksen kanssa, ettei sen ohjeita noudateta.
7. **Kovat katot.** Pyyntörajoitus (30 / min / IP), koko- ja määrärajat edellä.
8. **Loki ilman salaisuuksia.** Lokiin kirjataan kuka, mitä työkalua, millä parametreilla ja kuinka kävi, mutta ei avaimia eikä haettua sisältöä. Virheistä kirjataan vain poikkeuksen tyyppi. Lokitiedosto luodaan oikeuksilla 640.
9. **Hälytys.** Estetyt pyynnöt, vanhentunut GitHub-token ja peruttu Gmail-lupa lähettävät Telegram-viestin.

## Rajoitukset

Tämä on kotilabran ja pienen tiimin työkalu, ei yrityskäyttöön tarkoitettu varasto. Tiedä nämä ennen käyttöä:

- **IP-osoite ei ole vahva tunnistautuminen.** Jos joku voi väärentää lähde-IP:n tai ajaa koodia agentin kontissa, hän perii agentin oikeudet. Palomuuri ja erilliset kontit (yksi palvelu per kontti) ovat välttämättömiä.
- **Ei TLS:ää.** Palvelin puhuu pelkkää HTTP:tä. Käytä sitä vain luotetussa sisäverkossa tai VPN:n (esim. Tailscale) sisällä, tai aseta eteen TLS-päättävä välityspalvelin.
- **Prompt-injektiota ei voi estää kokonaan.** `varoitus`-kenttä on vain ohje mallille, ei takuu. Siksi agentille annetaan vain vähimmäisoikeudet ja arkaluonteisin tieto pidetään pois.
- **Tiedostoesto perustuu nimiin.** Se ei skannaa sisältöä: jos salaisuus on `README.md`:ssä, se on luettavissa.
- **Yksi tili.** GitHub-puolella oletetaan, että token kuuluu yhdelle omistajalle (repot haetaan tokenin omistajan alta).
- **MCP-kirjasto kiinnitetty versioon 1.x** (`mcp<2`). Versio 2 nimesi `FastMCP`:n uudelleen, eikä holvi ole vielä siirretty siihen.
- **Gmail-kirjautumisen kulkua (`holvi-kirjaudu`) ei testata automaattisesti.** Sen tallennus- ja oikeuslogiikka on testattu, itse selainkierros ei.

## Asennus

Tarvitset Python 3.10+:n ja järjestelmän, jossa on `systemd` ja `nftables` (esimerkit olettavat Linuxin).

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin holvi
sudo mkdir -p /opt/holvi /etc/holvi /var/log/holvi
sudo python3 -m venv /opt/holvi/venv
sudo /opt/holvi/venv/bin/pip install git+https://github.com/tonyweckstrom1987/holvi.git
sudo chown holvi:holvi /var/log/holvi
sudo chown root:holvi /etc/holvi && sudo chmod 750 /etc/holvi
```

**Säännöt ja salaisuudet.** Kopioi [saannot.example.json](esimerkit/saannot.example.json) nimellä `/etc/holvi/saannot.json` ja vaihda asiakkaiden IP-osoitteet. Kopioi [salaisuudet.example.env](esimerkit/salaisuudet.example.env) nimellä `/etc/holvi/salaisuudet.env` (omistaja `root:holvi`, oikeudet 640) ja täytä `GITHUB_TOKEN` itse. **Älä liitä avaimia keskusteluun tai agentille**; kirjoita ne tiedostoon itse.

**Gmail.** Luo Google Cloud -projektiin OAuth-asiakas (Desktop) ja ota Gmail API käyttöön. Aja sitten palvelimella `sudo HOLVI_DIR=/etc/holvi /opt/holvi/venv/bin/holvi-kirjaudu`; se kysyy asiakastunnisteen ja salaisuuden, tulostaa kirjautumislinkin ja tallentaa refresh-tokenin suoraan `salaisuudet.env`-tiedostoon (oikeudet 600). Selain avataan omalla koneella SSH-tunnelilla: `ssh -L 8765:localhost:8765 kayttaja@palvelin`. Pyydetty oikeus on vain `gmail.readonly`.

**Palomuuri ja palvelut.** Sovella [nftables-esimerkki](esimerkit/nftables.example.conf) ja asenna [systemd-unitit](esimerkit/systemd/) (vaihda `HOLVI_HOST` palvelimen omaksi osoitteeksi; oletus on `127.0.0.1`). Sitten:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now holvi.service holvi-posti.service
```

Valvonta: [holvi-sydan.sh](esimerkit/systemd/holvi-sydan.sh) lähettää minuutin välein sydänmerkin Uptime Kuman push-osoitteeseen, kun molemmat palvelut ovat käynnissä.

**Agentin puolella** MCP-asiakas osoittaa palvelimen `/mcp`-polkuun, esim. `http://192.0.2.2:8700/mcp` (streamable HTTP, tilaton).

## Vaihtoehtoja ja miksi tämä

Samaa ongelmaa ratkovia projekteja on useita, enkä ole kokeillut niitä kaikkia. Esimerkiksi Infisicalin [Agent Vault](https://github.com/Infisical/agent-vault) on avoimen lähdekoodin tunnusvälittäjä ja -holvi agenteille; muita ovat mm. Vultrino, Janee ja Pincer. Yleiset salaisuuksien hallintajärjestelmät (HashiCorp Vault, Bitwarden Secrets Manager, Infisical) säilyttävät tunnukset hyvin, mutta eivät rajaa sitä, *mitä agentti niillä tekee*.

Holvi on tarkoituksella pieni ja kapea:

- **Työkalu, ei yleinen välityspalvelin.** Agentti saa nimetyn, rajatun työkalun (esim. "lue tämän repon tiedosto") eikä yleistä pääsyä palveluun, jolloin hyökkäyspinta on pieni ja jokaisella työkalulla on omat kovat rajat.
- **Sääntöpohjainen, ei LLM.** Oikeuspäätökset tekee koodi, ei malli.
- **Luettavissa kerralla.** Noin 640 riviä Pythonia ja kaksi prosessia. Voit lukea koko turvallisuuslogiikan illassa.
- **Rajoitus kääntäen:** jos tarvitset monta palvelua, lyhytikäisiä tunnuksia, tiimikäyttöä tai vahvaa tunnistautumista, jokin yllä mainituista sopii paremmin.

## Testit

```bash
pip install -e ".[dev]"
python -m pytest -q
```

101 testiä, ei verkkoa eikä oikeita tunnuksia (valeverkko `httpx`:n tilalla). Testit kattavat mm. oikeudet ja pyyntörajoituksen, polku- ja nimitarkistukset, arkaluonteiset tiedostonimet, koko- ja määrärajat, sen että lokiin ei pääse salaisuuksia eikä haettua dataa, sen että Gmailiin tehdään vain lukupyyntöjä, sen että postipalvelin ei tarjoa GitHub-työkaluja, yhden kokonaistestin, jossa oikea palvelinprosessi ja oikea MCP-asiakas keskustelevat HTTP:n yli, sekä repon oman tarkistuksen (ei oikeita IP-osoitteita, tailnet-nimiä tai salaisuuden näköisiä merkkijonoja). Koodin kriittiset rivit on varmistettu mutaatiotestauksella: tahallinen rikkominen (esim. oikeustarkistuksen tai pituusrajan poisto) kaataa testit.

## Lisenssi

MIT. Katso [LICENSE](LICENSE).
