from flask import Flask, render_template, request
import csv
import io
from packing_engine import (
    load_items_from_csv,
    load_containers_from_csv,
    choose_box_then_pallet,
    choose_multiple_containers,
)

app = Flask(__name__)


def parse_items_csv_text(csv_text: str):
    items = []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    for row in reader:
        items.append({
            'sku': row['sku'],
            'length': int(row['length']),
            'width': int(row['width']),
            'height': int(row['height']),
            'weight': float(row['weight']),
            'qty': int(row['qty']),
            'can_rotate': bool(int(row['can_rotate'])),
        })
    return items


def build_items(item_dicts):
    from packing_engine import Item
    return [Item(**item) for item in item_dicts]


@app.route('/', methods=['GET', 'POST'])
def index():
    single_result = None
    multi_result = None
    items_text = ''

    if request.method == 'POST':
        items_text = request.form.get('items_csv', '').strip()
        if items_text:
            item_dicts = parse_items_csv_text(items_text)
            items = build_items(item_dicts)
        else:
            items = load_items_from_csv('items_sample.csv')
            with open('items_sample.csv', encoding='utf-8') as f:
                items_text = f.read()

        boxes = load_containers_from_csv('boxes.csv')
        pallets = load_containers_from_csv('pallets.csv')

        single_result = choose_box_then_pallet(items, boxes, pallets, mode='smallest_fit')
        multi_result = choose_multiple_containers(items, boxes + pallets, mode='smallest_fit')
    else:
        with open('items_sample.csv', encoding='utf-8') as f:
            items_text = f.read()

    return render_template(
        'index.html',
        items_text=items_text,
        single_result=single_result,
        multi_result=multi_result,
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
