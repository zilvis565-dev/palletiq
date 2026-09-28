## PalletIQ

Bazinis pakavimo algoritmo projektas, skirtas parinkti tinkamiausią dėžę arba paletę iš galimų katalogų.

### Kas yra projekte

- `packing_engine.py` — pagrindinis pakavimo algoritmas
- `app.py` — web aplikacija testavimui per naršyklę
- `templates/index.html` — testavimo forma
- `boxes.csv` — galimų dėžių katalogas
- `pallets.csv` — galimų palečių katalogas
- `items_sample.csv` — pavyzdinės prekės testavimui
- `requirements.txt` — Python paketai Render paleidimui
- `render.yaml` — Render konfigūracija
- `results.csv` — vieno konteinerio rezultato eksportas po paleidimo
- `results_multi.csv` — kelių konteinerių rezultato eksportas po paleidimo

### Paleidimas lokaliai

```bash
pip install -r requirements.txt
python app.py
```

Tada atsidaryk naršyklėje:

```text
http://127.0.0.1:5000
```

### Paleidimas per Render

1. Prisijunk prie Render
2. Sukurk naują `Web Service`
3. Prijunk GitHub repo `zilvis565-dev/palletiq`
4. Render automatiškai panaudos:
   - build command: `pip install -r requirements.txt`
   - start command: `gunicorn app:app`
5. Po deploy atsidaryk sugeneruotą URL

### Kaip veikia

1. Įklijuoji `items CSV` į formą
2. Sistema nuskaito `boxes.csv`
3. Sistema nuskaito `pallets.csv`
4. Parodo vieno konteinerio rezultatą
5. Parodo kelių konteinerių rezultatą

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
