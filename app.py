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


def parse_order_lines_form(form):
    box_codes = form.getlist('order_box_code[]')
    qtys = form.getlist('order_qty[]')
    rows = []
    for code, qty in zip(box_codes, qtys):
        code = (code or '').strip()
        qty = (qty or '').strip()
        if not code and not qty:
            continue
        if not code:
            raise ValueError('Order eilutėje trūksta box code')
        if not qty:
            raise ValueError(f'Order eilutėje {code} trūksta qty')
        rows.append(OrderLine(box_code=code, qty=int(qty)))
    return rows


def parse_box_master_form(form):
    codes = form.getlist('box_code[]')
    lengths = form.getlist('box_length[]')
    widths = form.getlist('box_width[]')
    heights = form.getlist('box_height[]')
    weights = form.getlist('box_weight[]')
    rotates = form.getlist('box_can_rotate[]')
    rows = []
    for code, l, w, h, wt, r in zip(codes, lengths, widths, heights, weights, rotates):
        code = (code or '').strip()
        if not code:
            continue
        rows.append(BoxType(box_code=code, length=int(l), width=int(w), height=int(h), weight=float(wt), can_rotate=str(r) == '1'))
    return rows


def parse_pallets_form(form):
    codes = form.getlist('pallet_code[]')
    types = form.getlist('pallet_type[]')
    lengths = form.getlist('pallet_length[]')
    widths = form.getlist('pallet_width[]')
    heights = form.getlist('pallet_height[]')
    max_weights = form.getlist('pallet_max_weight[]')
    tare_weights = form.getlist('pallet_tare_weight[]')
    costs = form.getlist('pallet_cost[]')
    actives = form.getlist('pallet_active[]')
    rows = []
    for code, t, l, w, h, mw, tw, c, a in zip(codes, types, lengths, widths, heights, max_weights, tare_weights, costs, actives):
        code = (code or '').strip()
        if not code:
            continue
        rows.append(Container(code=code, type=t or 'PALLET', length=int(l), width=int(w), height=int(h), max_weight=float(mw), tare_weight=float(tw), cost=float(c), active=str(a) == '1'))
    return rows


def to_order_lines_text(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(ORDER_HEADERS)
    for r in rows:
        writer.writerow([r.box_code, r.qty])
    return out.getvalue().strip()


def to_box_master_text(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(BOX_MASTER_HEADERS)
    for r in rows:
        writer.writerow([r.box_code, r.length, r.width, r.height, r.weight, 1 if r.can_rotate else 0])
    return out.getvalue().strip()


def to_pallets_text(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(PALLET_HEADERS)
    for r in rows:
        writer.writerow([r.code, r.type, r.length, r.width, r.height, r.max_weight, r.tare_weight, r.cost, 1 if r.active else 0])
    return out.getvalue().strip()


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
            'container': {'code': single_result['selected_container'].code, 'length': single_result['selected_container'].length, 'width': single_result['selected_container'].width, 'height': single_result['selected_container'].height},
            'utilization': round(single_result['utilization'] * 100, 2),
            'total_weight': single_result['total_weight'],
            'counts': build_counts(single_result['placements']),
            'placements': [{'sku': p.sku, 'x': p.x, 'y': p.y, 'z': p.z, 'length': p.length, 'width': p.width, 'height': p.height} for p in single_result['placements']],
        }
    if multi_result and multi_result.get('success'):
        for idx, shipment in enumerate(multi_result['shipments'], start=1):
            visuals['multi'].append({
                'index': idx,
                'container': {'code': shipment['container'].code, 'length': shipment['container'].length, 'width': shipment['container'].width, 'height': shipment['container'].height},
                'utilization': round(shipment['utilization'] * 100, 2),
                'total_weight': shipment['total_weight'],
                'counts': build_counts(shipment['placements']),
                'placements': [{'sku': p.sku, 'x': p.x, 'y': p.y, 'z': p.z, 'length': p.length, 'width': p.width, 'height': p.height} for p in shipment['placements']],
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

    order_lines_rows = parse_order_lines_csv_text(order_lines_text)
    box_master_rows = parse_box_master_csv_text(box_master_text)
    pallets_rows = parse_pallets_csv_text(pallets_text)

    pallet_strategy = 'mixed'
    selected_single_pallet = ''
    selected_pallet_codes = []
    pallet_options = serialize_pallet_options(pallets_rows)
    big_boxes_bottom = True
    heavier_boxes_bottom = True
    min_support_ratio_value = 0.85
    prefer_same_sku_blocks = True
    minimize_mixing = True
    finish_current_sku_first = True
    layer_purity = True
    strict_no_mix = False
    grouping_strength = 3
    prefer_floor_spread = True
    delay_vertical_stacking = True
    floor_layer_priority_strength = 4
    strict_layer_first = True

    if request.method == 'POST':
        action = request.form.get('action', 'run')
        use_table_input = request.form.get('input_mode', 'table') == 'table'

        if action == 'sample':
            order_lines_text = sample_order_lines
            box_master_text = sample_box_master
            pallets_text = sample_pallets
            order_lines_rows = parse_order_lines_csv_text(order_lines_text)
            box_master_rows = parse_box_master_csv_text(box_master_text)
            pallets_rows = parse_pallets_csv_text(pallets_text)
        elif action == 'clear':
            order_lines_text = ''
            box_master_text = ''
            pallets_text = ''
            order_lines_rows = []
            box_master_rows = []
            pallets_rows = []
        else:
            try:
                if use_table_input:
                    order_lines_rows = parse_order_lines_form(request.form)
                    box_master_rows = parse_box_master_form(request.form)
                    pallets_rows = parse_pallets_form(request.form)
                    order_lines_text = to_order_lines_text(order_lines_rows) if order_lines_rows else ''
                    box_master_text = to_box_master_text(box_master_rows) if box_master_rows else ''
                    pallets_text = to_pallets_text(pallets_rows) if pallets_rows else ''
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
                    order_lines_rows = parse_order_lines_csv_text(order_lines_text)
                    box_master_rows = parse_box_master_csv_text(box_master_text)
                    pallets_rows = parse_pallets_csv_text(pallets_text)
            except Exception as e:
                error_message = str(e)

        pallet_strategy = request.form.get('pallet_strategy', 'mixed')
        selected_single_pallet = request.form.get('single_pallet_code', '')
        selected_pallet_codes = request.form.getlist('selected_pallet_codes')
        big_boxes_bottom = request.form.get('big_boxes_bottom') == 'on'
        heavier_boxes_bottom = request.form.get('heavier_boxes_bottom') == 'on'
        min_support_ratio_value = float(request.form.get('min_support_ratio_value', '0.85') or '0.85')
        min_support_ratio_value = max(0.0, min(1.0, min_support_ratio_value))
        prefer_same_sku_blocks = request.form.get('prefer_same_sku_blocks') == 'on'
        minimize_mixing = request.form.get('minimize_mixing') == 'on'
        finish_current_sku_first = request.form.get('finish_current_sku_first') == 'on'
        layer_purity = request.form.get('layer_purity') == 'on'
        strict_no_mix = request.form.get('strict_no_mix') == 'on'
        grouping_strength = int(request.form.get('grouping_strength', '3') or '3')
        grouping_strength = max(1, min(5, grouping_strength))
        prefer_floor_spread = request.form.get('prefer_floor_spread') == 'on'
        delay_vertical_stacking = request.form.get('delay_vertical_stacking') == 'on'
        floor_layer_priority_strength = int(request.form.get('floor_layer_priority_strength', '4') or '4')
        floor_layer_priority_strength = max(1, min(5, floor_layer_priority_strength))
        strict_layer_first = request.form.get('strict_layer_first') == 'on'
        pallet_options = serialize_pallet_options(pallets_rows)

        if action == 'run' and not error_message:
            try:
                items = expand_order_lines(order_lines_rows, box_master_rows)
                pallets = pallets_rows
                common_kwargs = {
                    'mode': 'smallest_fit',
                    'big_boxes_bottom': big_boxes_bottom,
                    'heavier_boxes_bottom': heavier_boxes_bottom,
                    'min_support_ratio_value': min_support_ratio_value,
                    'prefer_same_sku_blocks': prefer_same_sku_blocks,
                    'minimize_mixing': minimize_mixing,
                    'finish_current_sku_first': finish_current_sku_first,
                    'layer_purity': layer_purity,
                    'strict_no_mix': strict_no_mix,
                    'grouping_strength': grouping_strength,
                    'prefer_floor_spread': prefer_floor_spread,
                    'delay_vertical_stacking': delay_vertical_stacking,
                    'floor_layer_priority_strength': floor_layer_priority_strength,
                    'strict_layer_first': strict_layer_first,
                }

                if pallet_strategy == 'single':
                    filtered_pallets = [p for p in pallets if p.code == selected_single_pallet]
                    if not filtered_pallets:
                        raise ValueError('Pasirink vieną paletę')
                    single_result = choose_best_container(items, filtered_pallets, **common_kwargs)
                    if single_result.get('success'):
                        single_result['selection_policy'] = 'single_pallet'
                    multi_result = choose_multiple_containers(items, filtered_pallets, **common_kwargs)
                elif pallet_strategy == 'selected':
                    filtered_pallets = [p for p in pallets if p.code in selected_pallet_codes]
                    if not filtered_pallets:
                        raise ValueError('Pasirink bent vieną paletę iš sąrašo')
                    single_result = choose_best_container(items, filtered_pallets, **common_kwargs)
                    if single_result.get('success'):
                        single_result['selection_policy'] = 'selected_pallet_pool'
                    multi_result = choose_multiple_containers(items, filtered_pallets, **common_kwargs)
                else:
                    single_result = choose_best_container(items, pallets, **common_kwargs)
                    if single_result.get('success'):
                        single_result['selection_policy'] = 'best_single_pallet_type'
                    multi_result = choose_multiple_containers(items, pallets, **common_kwargs)

                export_single_result_to_csv(single_result, LAST_SINGLE_RESULT_PATH)
                export_multiple_results_to_csv(multi_result, LAST_MULTI_RESULT_PATH)
                summary = build_summary(single_result, multi_result)
                visuals = build_visualization_payload(single_result, multi_result)
            except Exception as e:
                error_message = str(e)

    return render_template(
        'index.html',
        order_lines_text=order_lines_text,
        box_master_text=box_master_text,
        pallets_text=pallets_text,
        order_lines_rows=order_lines_rows,
        box_master_rows=box_master_rows,
        pallets_rows=pallets_rows,
        single_result=single_result,
        multi_result=multi_result,
        error_message=error_message,
        summary=summary,
        pallet_strategy=pallet_strategy,
        selected_single_pallet=selected_single_pallet,
        selected_pallet_codes=selected_pallet_codes,
        pallet_options=pallet_options,
        visuals_json=json.dumps(visuals),
        big_boxes_bottom=big_boxes_bottom,
        heavier_boxes_bottom=heavier_boxes_bottom,
        min_support_ratio_value=min_support_ratio_value,
        prefer_same_sku_blocks=prefer_same_sku_blocks,
        minimize_mixing=minimize_mixing,
        finish_current_sku_first=finish_current_sku_first,
        layer_purity=layer_purity,
        strict_no_mix=strict_no_mix,
        grouping_strength=grouping_strength,
        prefer_floor_spread=prefer_floor_spread,
        delay_vertical_stacking=delay_vertical_stacking,
        floor_layer_priority_strength=floor_layer_priority_strength,
        strict_layer_first=strict_layer_first,
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
