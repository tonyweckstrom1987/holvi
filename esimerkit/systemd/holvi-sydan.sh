#!/bin/sh
# Lahettaa sydanmerkin Uptime Kuman push-osoitteeseen vain, jos molemmat palvelut ovat kaynnissa.
# Osoite on tiedostossa /etc/holvi/kuma_push_url (omistaja holvi, oikeudet 600), ei tassa skriptissa.
set -eu
systemctl is-active --quiet holvi.service || exit 0
systemctl is-active --quiet holvi-posti.service || exit 0
curl -fsS -m 10 "$(cat /etc/holvi/kuma_push_url)" > /dev/null
