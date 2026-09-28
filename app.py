from flask import Flask, render_template, request, send_file
import csv
import io
import os
import json
from collections import Counter
from packing_engine import (
    OrderLine,
    BoxType,
    Container,
    expand_order_lines,
    choose_best_container,
    choose_multiple_containers,
    export_single_result_to_csv,
    export_multiple_results_to_csv,
)

app = Flask(__name__)

LAST_SINGLE_RESULT_PATH = 'results.csv'
LAST_MULTI_RESULT_PATH = 'results_multi.csv'

ORDER_HEADERS = ['box_code', 'qty']
BOX_MASTER_HEADERS = ['box_code', 'length', 'width', 'height', 'weight', 'can_rotate']
PALLET_HEADERS = ['code', 'type', 'length', 'width', 'height', 'max_weight', 'tare_weight', 'cost', 'active']


def validate_headers(actual_headers, expected_headers, label):
    if actual_headers != expected_headers:
        raise ValueError(f"{label} antraštės neteisingos. Turi būti: {','.join(expected_headers)}")


def parse_order_lines_csv_text(csv_text: str):
    text = csv_text.strip()
    if not text:
        raise ValueError('Order lines CSV yra tuščias')
    reader = csv.DictReader(io.StringIO(text))
    validate_headers(reader.fieldnames, ORDER_HEADERS, 'Order lines CSV')
    rows = []
    for idx, row in enumerate(reader, start=2):
        try:
            rows.append(OrderLine(box_code=row['box_code'], qty=int(row['qty'])))
        except Exception as e:
            raise ValueError(f'Klaida Order lines CSV eilutėje {idx}: {e}')
    return rows


def parse_box_master_csv_text(csv_text: str):
    text = csv_text.strip()
    if not text:
        raise ValueError('Box master CSV yra tuščias')
    reader = csv.DictReader(io.StringIO(text))
    validate_headers(reader.fieldnames, BOX_MASTER_HEADERS, 'Box master CSV')
    rows = []
    for idx, row in enumerate(reader, start=2):
        try:
            rows.append(BoxType(box_code=row['box_code'], length=int(row['length']), width=int(row['width']), height=int(row['height']), weight=float(row['weight']), can_rotate=bool(int(row['can_rotate']))))
        except Exception as e:
            raise ValueError(f'Klaida Box master CSV eilutėje {idx}: {e}')
    return rows


def parse_pallets_csv_text(csv_text: str):
    text = csv_text.strip()
    if not text:
        raise ValueError('Pallets CSV yra tuščias')
    reader = csv.DictReader(io.StringIO(text))
    validate_headers(reader.fieldnames, PALLET_HEADERS, 'Pallets CSV')
    rows = []
    for idx, row in enumerate(reader, start=2):
        try:
            rows.append(Container(code=row['code'], type=row['type'], length=int(row['length']), width=int(row['width']), height=int(row['height']), max_weight=float(row['max_weight']), tare_weight=float(row['tare_weight']), cost=float(row['cost']), active=bool(int(row['active']))))
        except Exception as e:
            raise ValueError(f'Klaida Pallets CSV eilutėje {idx}: {e}')
    return rows


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


def serialize_pallet_options(pallets):
    return [{'code': p.code, 'label': f"{p.code} {p.length}x{p.width}x{p.height}"} for p in pallets]


def build_summary(single_result, multi_result):
    summary = {}
    if single_result and single_result.get('success'):
        summary['single_pallet'] = f"{single_result['selected_container'].code}"
        summary['single_utilization'] = f"{single_result['utilization'] * 100:.2f}%"
    if multi_result and multi_result.get('success'):
        summary['shipment_count'] = multi_result['shipment_count']
        summary['overall_utilization'] = f"{multi_result['overall_utilization'] * 100:.2f}%"
        summary['total_cost'] = multi_result['total_cost']
    return summary


def build_counts(placements):
    counts = Counter([p.sku for p in placements])
    return [{'sku': sku, 'qty': qty} for sku, qty in sorted(counts.items())]


def build_visualization_payload(single_result, multi_result):
    visuals = {'single': None, 'multi': []}

    if single_result and single_result.get('success'):
        visuals['single'] = {
            'container': {
                'code': single_result['selected_container'].code,
                'length': single_result['selected_container'].length,
                'width': single_result['selected_container'].width,
                'height': single_result['selected_container'].height,
            },
            'utilization': round(single_result['utilization'] * 100, 2),
            'total_weight': single_result['total_weight'],
            'counts': build_counts(single_result['placements']),
            'placements': [
                {
                    'sku': p.sku,
                    'x': p.x,
                    'y': p.y,
                    'z': p.z,
                    'length': p.length,
                    'width': p.width,
                    'height': p.height,
                }
                for p in single_result['placements']
            ],
        }

    if multi_result and multi_result.get('success'):
        for idx, shipment in enumerate(multi_result['shipments'], start=1):
            visuals['multi'].append({
                'index': idx,
                'container': {
                    'code': shipment['container'].code,
                    'length': shipment['container'].length,
                    'width': shipment['container'].width,
                    'height': shipment['container'].height,
                },
                'utilization': round(shipment['utilization'] * 100, 2),
                'total_weight': shipment['total_weight'],
                'counts': build_counts(shipment['placements']),
                'placements': [
                    {
                        'sku': p.sku,
                        'x': p.x,
                        'y': p.y,
                        'z': p.z,
                        'length': p.length,
                        'width': p.width,
                        'height': p.height,
                    }
                    for p in shipment['placements']
                ],
            })

    return visuals


@app.route('/', methods=['GET', 'POST'])
def index():
    single_result = None
    multi_result = None
    error_message = None
    summary = None
    visuals = {'single': None, 'multi': []}

    order_lines_text = load_text_file('order_lines.csv')
    box_master_text = load_text_file('box_master.csv')
    pallets_text = load_text_file('pallets.csv')

    sample_order_lines = order_lines_text
    sample_box_master = box_master_text
    sample_pallets = pallets_text

    pallet_strategy = 'mixed'
    selected_single_pallet = ''
    selected_pallet_codes = []
    pallet_options = []

    if request.method == 'POST':
        action = request.form.get('action', 'run')
        if action == 'sample':
            order_lines_text = sample_order_lines
            box_master_text = sample_box_master
            pallets_text = sample_pallets
        elif action == 'clear':
            order_lines_text = ''
            box_master_text = ''
            pallets_text = ''
        else:
            order_lines_text = request.form.get('order_lines_csv', '').strip()
            box_master_text = request.form.get('box_master_csv', '').strip()
            pallets_text = request.form.get('pallets_csv', '').strip()

            uploaded_order_lines = decode_uploaded_file(request.files.get('order_lines_file'), 'order lines')
            uploaded_box_master = decode_uploaded_file(request.files.get('box_master_file'), 'box master')
            uploaded_pallets = decode_uploaded_file(request.files.get('pallets_file'), 'pallets')

            if uploaded_order_lines:
                order_lines_text = uploaded_order_lines.strip()
            if uploaded_box_master:
                box_master_text = uploaded_box_master.strip()
            if uploaded_pallets:
                pallets_text = uploaded_pallets.strip()

        pallet_strategy = request.form.get('pallet_strategy', 'mixed')
        selected_single_pallet = request.form.get('single_pallet_code', '')
        selected_pallet_codes = request.form.getlist('selected_pallet_codes')

        try:
            order_lines = parse_order_lines_csv_text(order_lines_text)
            box_master = parse_box_master_csv_text(box_master_text)
            pallets = parse_pallets_csv_text(pallets_text)
            pallet_options = serialize_pallet_options(pallets)
            items = expand_order_lines(order_lines, box_master)

            if pallet_strategy == 'single':
                filtered_pallets = [p for p in pallets if p.code == selected_single_pallet]
                if not filtered_pallets:
                    raise ValueError('Pasirink vieną paletę')
                single_result = choose_best_container(items, filtered_pallets, mode='smallest_fit')
                if single_result.get('success'):
                    single_result['selection_policy'] = 'single_pallet'
                multi_result = choose_multiple_containers(items, filtered_pallets, mode='smallest_fit')
            elif pallet_strategy == 'selected':
                filtered_pallets = [p for p in pallets if p.code in selected_pallet_codes]
                if not filtered_pallets:
                    raise ValueError('Pasirink bent vieną paletę iš sąrašo')
                single_result = choose_best_container(items, filtered_pallets, mode='smallest_fit')
                if single_result.get('success'):
                    single_result['selection_policy'] = 'selected_pallet_pool'
                multi_result = choose_multiple_containers(items, filtered_pallets, mode='smallest_fit')
            else:
                single_result = choose_best_container(items, pallets, mode='smallest_fit')
                if single_result.get('success'):
                    single_result['selection_policy'] = 'best_single_pallet_type'
                multi_result = choose_multiple_containers(items, pallets, mode='smallest_fit')

            export_single_result_to_csv(single_result, LAST_SINGLE_RESULT_PATH)
            export_multiple_results_to_csv(multi_result, LAST_MULTI_RESULT_PATH)
            summary = build_summary(single_result, multi_result)
            visuals = build_visualization_payload(single_result, multi_result)
        except Exception as e:
            error_message = str(e)
    else:
        try:
            pallets = parse_pallets_csv_text(pallets_text)
            pallet_options = serialize_pallet_options(pallets)
        except Exception:
            pallet_options = []

    return render_template(
        'index.html',
        order_lines_text=order_lines_text,
        box_master_text=box_master_text,
        pallets_text=pallets_text,
        single_result=single_result,
        multi_result=multi_result,
        error_message=error_message,
        summary=summary,
        pallet_strategy=pallet_strategy,
        selected_single_pallet=selected_single_pallet,
        selected_pallet_codes=selected_pallet_codes,
        pallet_options=pallet_options,
        visuals_json=json.dumps(visuals),
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
