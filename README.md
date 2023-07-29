# Woob Bank Exporter

## Quick Start

```bash
DOCKER_BUILDKIT=1 docker build -t woob-bank-exporter .
docker run -dit --name woob-bank-exporter --env WOOB_BANK_NAME=xxx --env WOOB_BANK_MODULE=xxx --env WOOB_BANK_LOGIN=xxx --env WOOB_BANK_PASSWORD=xxx
```

## Metrics

```bash
# TYPE woob_bank_balance gauge
woob_bank_balance{currency="EUR",job="woob-bank-exporter",label="Compte courant M XXX",module="xxx",name="xxx",number="01234567",owner_type="PRIV",ownership="owner",type="1"} 19999.44
# HELP woob_bank_balance Balance on this bank account
# TYPE woob_bank_balance gauge
woob_bank_balance{currency="EUR",job="woob-bank-exporter",label="LDDS M XXX",module="xxx",name="xxx",number="01234567-D",owner_type="PRIV",ownership="owner",type="2"} 10000.06
...
```
