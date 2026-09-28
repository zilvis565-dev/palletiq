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

1. Gali įklijuoti CSV tekstą arba įkelti CSV failus
2. Gali redaguoti `items`, `boxes` ir `pallets`
3. Gali paspausti `Užkrauti pavyzdinius duomenis`
4. Gali paspausti `Išvalyti formą`
5. Sistema parodo rezultatų santrauką
6. Sistema parodo vieno konteinerio rezultatą
7. Sistema parodo kelių konteinerių rezultatą
8. Gali atsisiųsti rezultatus kaip CSV

### CSV struktūra

#### items CSV
- `sku`
- `length`
- `width`
- `height`
- `weight`
- `qty`
- `can_rotate`

#### boxes ir pallets CSV
- `code`
- `type`
- `length`
- `width`
- `height`
- `max_weight`
- `tare_weight`
- `cost`
- `active`
