from flask import Flask, render_template, request, send_file
import csv
import io
import os
from packing_engine import (
    Item,
    Container,
    choose_box_then_pallet,
    choose_multiple_containers,
    export_single_result_to_csv,
    export_multiple_results_to_csv,
)

app = Flask(__name__)

LAST_SINGLE_RESULT_PATH = 'results.csv'
LAST_MULTI_RESULT_PATH = 'results_multi.csv'


ITEM_HEADERS = ['sku', 'length', 'width', 'height', 'weight', 'qty', 'can_rotate']
CONTAINER_HEADERS = ['code', 'type', 'length', 'width', 'height', 'max_weight', 'tare_weight', 'cost', 'active']


def validate_headers(actual_headers, expected_headers, label):
    if actual_headers != expected_headers:
        raise ValueError(
            f"{label} antraštės neteisingos. Turi būti tiksliai: {','.join(expected_headers)}"
        )


def parse_items_csv_text(csv_text: str):
    text = csv_text.strip()
    if not text:
        raise ValueError('Items CSV yra tuščias')

    reader = csv.DictReader(io.StringIO(text))
    validate_headers(reader.fieldnames, ITEM_HEADERS, 'Items CSV')

    items = []
    for idx, row in enumerate(reader, start=2):
        try:
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
        except Exception as e:
            raise ValueError(f'Klaida Items CSV eilutėje {idx}: {e}')
    return items


def parse_containers_csv_text(csv_text: str, label: str):
    text = csv_text.strip()
    if not text:
        raise ValueError(f'{label} yra tuščias')

    reader = csv.DictReader(io.StringIO(text))
    validate_headers(reader.fieldnames, CONTAINER_HEADERS, label)

    containers = []
    for idx, row in enumerate(reader, start=2):
        try:
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
        except Exception as e:
            raise ValueError(f'Klaida {label} eilutėje {idx}: {e}')
    return containers


def load_text_file(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        return f.read()


def decode_uploaded_file(file_storage, label: str) -> str:
    if not file_storage or not file_storage.filename:
        return ''
    try:
        return file_storage.read().decode('utf-8-sig')
    except Exception as e:
        raise ValueError(f'Nepavyko nuskaityti {label} failo: {e}')


def build_summary(single_result, multi_result):
    summary = {}
    if single_result and single_result.get('success'):
        summary['single_container'] = f"{single_result['selected_container'].code} ({single_result['selected_container'].type})"
        summary['single_utilization'] = f"{single_result['utilization'] * 100:.2f}%"
    if multi_result and multi_result.get('success'):
        summary['shipment_count'] = multi_result['shipment_count']
        summary['overall_utilization'] = f"{multi_result['overall_utilization'] * 100:.2f}%"
        summary['total_cost'] = multi_result['total_cost']
    return summary


@app.route('/', methods=['GET', 'POST'])
def index():
    single_result = None
    multi_result = None
    error_message = None
    summary = None

    sample_items = load_text_file('items_sample.csv')
    sample_boxes = load_text_file('boxes.csv')
    sample_pallets = load_text_file('pallets.csv')

    items_text = sample_items
    boxes_text = sample_boxes
    pallets_text = sample_pallets

    if request.method == 'POST':
        action = request.form.get('action', 'run')

        if action == 'sample':
            items_text = sample_items
            boxes_text = sample_boxes
            pallets_text = sample_pallets
        elif action == 'clear':
            items_text = ''
            boxes_text = ''
            pallets_text = ''
        else:
            items_text = request.form.get('items_csv', '').strip()
            boxes_text = request.form.get('boxes_csv', '').strip()
            pallets_text = request.form.get('pallets_csv', '').strip()

            uploaded_items = decode_uploaded_file(request.files.get('items_file'), 'items')
            uploaded_boxes = decode_uploaded_file(request.files.get('boxes_file'), 'boxes')
            uploaded_pallets = decode_uploaded_file(request.files.get('pallets_file'), 'pallets')

            if uploaded_items:
                items_text = uploaded_items.strip()
            if uploaded_boxes:
                boxes_text = uploaded_boxes.strip()
            if uploaded_pallets:
                pallets_text = uploaded_pallets.strip()

            try:
                items = parse_items_csv_text(items_text)
                boxes = parse_containers_csv_text(boxes_text, 'Boxes CSV')
                pallets = parse_containers_csv_text(pallets_text, 'Pallets CSV')

                single_result = choose_box_then_pallet(items, boxes, pallets, mode='smallest_fit')
                multi_result = choose_multiple_containers(items, boxes + pallets, mode='smallest_fit')

                export_single_result_to_csv(single_result, LAST_SINGLE_RESULT_PATH)
                export_multiple_results_to_csv(multi_result, LAST_MULTI_RESULT_PATH)
                summary = build_summary(single_result, multi_result)
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
        summary=summary,
    )


@app.route('/download/single')
def download_single():
    if os.path.exists(LAST_SINGLE_RESULT_PATH):
        return send_file(LAST_SINGLE_RESULT_PATH, as_attachment=True)
    return 'Single result file not found', 404


@app.route('/download/multi')
def download_multi():
    if os.path.exists(LAST_MULTI_RESULT_PATH):
        return send_file(LAST_MULTI_RESULT_PATH, as_attachment=True)
    return 'Multi result file not found', 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
