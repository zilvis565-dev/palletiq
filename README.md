## PalletIQ

Bazinis pakavimo algoritmo projektas, skirtas parinkti tinkamiausią dėžę arba paletę iš galimų katalogų.

### Kas yra projekte

- `packing_engine.py` — pagrindinis pakavimo algoritmas
- `boxes.csv` — galimų dėžių katalogas
- `pallets.csv` — galimų palečių katalogas
- `items_sample.csv` — pavyzdinės prekės testavimui
- `results.csv` — vieno konteinerio rezultato eksportas po paleidimo
- `results_multi.csv` — kelių konteinerių rezultato eksportas po paleidimo

### Paleidimas

```bash
python packing_engine.py
```

### Kaip veikia

1. Nuskaito prekes iš `items_sample.csv`
2. Nuskaito dėžes iš `boxes.csv`
3. Nuskaito paletes iš `pallets.csv`
4. Pirmiausia bando rasti vieną tinkamą dėžę, o jei nepavyksta — vieną tinkamą paletę
5. Tada papildomai bando išdėlioti prekes per kelis konteinerius
6. Išsaugo rezultatus į `results.csv` ir `results_multi.csv`

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

### Rezultatų failai

#### `results.csv`
Vieno geriausio konteinerio rezultatas su kiekvienos prekės koordinatėmis.

#### `results_multi.csv`
Kelių konteinerių rezultatas su atskiromis siuntomis.

### Tolimesni žingsniai

Galima toliau pridėti:
- stabilesnį fizinį krovimo modelį
- fragility ir stacking taisykles
- Excel importą
- vizualizaciją
- ERP integraciją
