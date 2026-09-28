from flask import Flask, render_template, request
import csv
import io
from packing_engine import (
    Item,
    Container,
    choose_box_then_pallet,
    choose_multiple_containers,
    load_items_from_csv,
)

app = Flask(__name__)


def parse_items_csv_text(csv_text: str):
    items = []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    for row in reader:
        items.append(
            Item(
                sku=row['sku'],
                length=int(row['length']),
                width=int(row['width']),
                height=int(row['height']),
                weight=float(row['weight']),
                qty=int(row['qty']),
                can_rotate=bool(int(row['can_rotate'])),
            )
        )
    return items


def parse_containers_csv_text(csv_text: str):
    containers = []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    for row in reader:
        containers.append(
            Container(
                code=row['code'],
                type=row['type'],
                length=int(row['length']),
                width=int(row['width']),
                height=int(row['height']),
                max_weight=float(row['max_weight']),
                tare_weight=float(row['tare_weight']),
                cost=float(row['cost']),
                active=bool(int(row['active'])),
            )
        )
    return containers


def load_text_file(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        return f.read()


@app.route('/', methods=['GET', 'POST'])
def index():
    single_result = None
    multi_result = None
    error_message = None

    items_text = load_text_file('items_sample.csv')
    boxes_text = load_text_file('boxes.csv')
    pallets_text = load_text_file('pallets.csv')

    if request.method == 'POST':
        items_text = request.form.get('items_csv', '').strip()
        boxes_text = request.form.get('boxes_csv', '').strip()
        pallets_text = request.form.get('pallets_csv', '').strip()

        try:
            items = parse_items_csv_text(items_text)
            boxes = parse_containers_csv_text(boxes_text)
            pallets = parse_containers_csv_text(pallets_text)

            single_result = choose_box_then_pallet(items, boxes, pallets, mode='smallest_fit')
            multi_result = choose_multiple_containers(items, boxes + pallets, mode='smallest_fit')
        except Exception as e:
            error_message = str(e)

    return render_template(
        'index.html',
        items_text=items_text,
        boxes_text=boxes_text,
        pallets_text=pallets_text,
        single_result=single_result,
        multi_result=multi_result,
        error_message=error_message,
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
