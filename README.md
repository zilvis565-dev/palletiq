## PalletIQ

PalletIQ dabar orientuotas į realų užsakymo paletavimo scenarijų:
- yra `order_lines`
- yra `box_master`
- yra `pallets`
- sistema gali parinkti vieną geriausią paletę arba mišrų skirtingų palečių rinkinį

### Failai

- `packing_engine.py` — skaičiavimo logika
- `app.py` — web aplikacija
- `templates/index.html` — atnaujintas UI
- `order_lines.csv` — užsakymo eilutės
- `box_master.csv` — dėžių master duomenys
- `pallets.csv` — galimų palečių sąrašas
- `requirements.txt` — priklausomybės
- `render.yaml` — Render deploy konfigūracija

### CSV struktūros

#### order_lines.csv
```csv
box_code,qty
BX001,20
BX002,30
BX003,40
```

#### box_master.csv
```csv
box_code,length,width,height,weight,can_rotate
BX001,400,300,250,5,1
BX002,500,250,200,6,1
BX003,300,200,150,3,1
```

#### pallets.csv
```csv
code,type,length,width,height,max_weight,tare_weight,cost,active
EUR,PALLET,1200,800,1600,500,25,12,1
IND,PALLET,1200,1000,1600,700,30,15,1
```

### Palečių strategijos

- `Leisti skirtingas paletes`
- `Viena konkreti paletė`
- `Pasirinktos paletės iš sąrašo`

### Paleidimas lokaliai

```bash
pip install -r requirements.txt
python app.py
```

### Paleidimas per Render

- build command: `pip install -r requirements.txt`
- start command: `gunicorn app:app`
