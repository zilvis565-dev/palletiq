## PalletIQ

Bazinis pakavimo algoritmo projektas, skirtas parinkti tinkamiausią dėžę arba paletę iš galimų katalogų.

### Kas yra projekte

- `packing_engine.py` — pagrindinis pakavimo algoritmas
- `boxes.csv` — galimų dėžių katalogas
- `pallets.csv` — galimų palečių katalogas
- `items_sample.csv` — pavyzdinės prekės testavimui

### Paleidimas

```bash
python packing_engine.py
```

### Kaip veikia

1. Nuskaito prekes iš `items_sample.csv`
2. Nuskaito dėžes iš `boxes.csv`
3. Nuskaito paletes iš `pallets.csv`
4. Išbando visus konteinerius
5. Parenka geriausią variantą

### CSV struktūra

#### items_sample.csv
- `sku`
- `length`
- `width`
- `height`
- `weight`
- `qty`
- `can_rotate`

#### boxes.csv ir pallets.csv
- `code`
- `type`
- `length`
- `width`
- `height`
- `max_weight`
- `tare_weight`
- `cost`
- `active`

### Tolimesni žingsniai

Galima toliau pridėti:
- kelių konteinerių logiką
- stabilumo tikrinimą
- svorio centro vertinimą
- Excel importą
- rezultatų eksportą
