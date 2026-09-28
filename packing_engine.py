from dataclasses import dataclass
from typing import List, Tuple, Dict
import csv


@dataclass
class Item:
    sku: str
    length: int
    width: int
    height: int
    weight: float
    qty: int = 1
    can_rotate: bool = True


@dataclass
class OrderLine:
    box_code: str
    qty: int


@dataclass
class BoxType:
    box_code: str
    length: int
    width: int
    height: int
    weight: float
    can_rotate: bool = True


@dataclass
class PackedItem:
    sku: str
    x: int
    y: int
    z: int
    length: int
    width: int
    height: int
    weight: float
    container_code: str


@dataclass
class Space:
    x: int
    y: int
    z: int
    length: int
    width: int
    height: int


@dataclass
class Container:
    code: str
    type: str
    length: int
    width: int
    height: int
    max_weight: float
    tare_weight: float
    cost: float
    active: bool = True


def get_orientations(item: Item) -> List[Tuple[int, int, int]]:
    dims = [item.length, item.width, item.height]
    if not item.can_rotate:
        return [(item.length, item.width, item.height)]

    orientations = set()
    for a in dims:
        for b in dims:
            for c in dims:
                if sorted((a, b, c)) == sorted(dims):
                    orientations.add((a, b, c))
    return sorted(list(orientations))


def expand_items(items: List[Item]) -> List[Item]:
    expanded = []
    for item in items:
        for _ in range(item.qty):
            expanded.append(
                Item(
                    sku=item.sku,
                    length=item.length,
                    width=item.width,
                    height=item.height,
                    weight=item.weight,
                    qty=1,
                    can_rotate=item.can_rotate,
                )
            )
    return expanded


def expand_order_lines(order_lines: List[OrderLine], box_master: List[BoxType]) -> List[Item]:
    box_lookup = {b.box_code: b for b in box_master}
    items = []
    for line in order_lines:
        if line.box_code not in box_lookup:
            raise ValueError(f'Box code not found in box master: {line.box_code}')
        box = box_lookup[line.box_code]
        items.append(
            Item(
                sku=box.box_code,
                length=box.length,
                width=box.width,
                height=box.height,
                weight=box.weight,
                qty=line.qty,
                can_rotate=box.can_rotate,
            )
        )
    return items


def item_volume(item: Item) -> int:
    return item.length * item.width * item.height


def space_volume(space: Space) -> int:
    return space.length * space.width * space.height


def container_volume(container: Container) -> int:
    return container.length * container.width * container.height


def can_fit(space: Space, dims: Tuple[int, int, int]) -> bool:
    l, w, h = dims
    return l <= space.length and w <= space.width and h <= space.height


def score_placement(space: Space, dims: Tuple[int, int, int]) -> Tuple[int, int, int]:
    l, w, h = dims
    leftover = (space.length - l) + (space.width - w) + (space.height - h)
    return (space.z, leftover, space_volume(space) - (l * w * h))


def split_space(space: Space, px: int, py: int, pz: int, pl: int, pw: int, ph: int) -> List[Space]:
    new_spaces = []

    right = Space(px + pl, py, pz, space.x + space.length - (px + pl), space.width, space.height)
    front = Space(px, py + pw, pz, pl, space.y + space.width - (py + pw), space.height)
    above = Space(px, py, pz + ph, pl, pw, space.z + space.height - (pz + ph))

    for s in [right, front, above]:
        if s.length > 0 and s.width > 0 and s.height > 0:
            new_spaces.append(s)
    return new_spaces


def prune_spaces(spaces: List[Space]) -> List[Space]:
    pruned = []
    for i, s1 in enumerate(spaces):
        contained = False
        for j, s2 in enumerate(spaces):
            if i != j:
                if (
                    s1.x >= s2.x and s1.y >= s2.y and s1.z >= s2.z and
                    s1.x + s1.length <= s2.x + s2.length and
                    s1.y + s1.width <= s2.y + s2.width and
                    s1.z + s1.height <= s2.z + s2.height
                ):
                    contained = True
                    break
        if not contained:
            pruned.append(s1)
    return pruned


def pack_into_container(items: List[Item], container: Container) -> Dict:
    if not container.active:
        return {'success': False, 'reason': 'Container inactive', 'container': container, 'placements': [], 'unplaced_items': items, 'used_volume': 0, 'total_volume': container_volume(container), 'utilization': 0.0, 'total_weight': 0.0}

    total_item_weight = sum(i.weight for i in items)
    if total_item_weight + container.tare_weight > container.max_weight:
        return {'success': False, 'reason': 'Weight limit exceeded', 'container': container, 'placements': [], 'unplaced_items': items, 'used_volume': 0, 'total_volume': container_volume(container), 'utilization': 0.0, 'total_weight': total_item_weight + container.tare_weight}

    spaces = [Space(0, 0, 0, container.length, container.width, container.height)]
    placements = []
    unplaced = []

    sorted_items = sorted(items, key=lambda i: (item_volume(i), max(i.length, i.width, i.height), i.weight), reverse=True)

    for item in sorted_items:
        best_choice = None
        for space_idx, space in enumerate(spaces):
            for dims in get_orientations(item):
                if can_fit(space, dims):
                    score = score_placement(space, dims)
                    candidate = (score, space_idx, space, dims)
                    if best_choice is None or candidate[0] < best_choice[0]:
                        best_choice = candidate

        if best_choice is None:
            unplaced.append(item)
            continue

        _, space_idx, chosen_space, dims = best_choice
        l, w, h = dims
        placements.append(PackedItem(item.sku, chosen_space.x, chosen_space.y, chosen_space.z, l, w, h, item.weight, container.code))
        used_space = spaces.pop(space_idx)
        spaces.extend(split_space(used_space, chosen_space.x, chosen_space.y, chosen_space.z, l, w, h))
        spaces = prune_spaces(spaces)

    used_volume = sum(p.length * p.width * p.height for p in placements)
    total_volume = container_volume(container)
    utilization = used_volume / total_volume if total_volume > 0 else 0.0

    return {
        'success': len(unplaced) == 0,
        'reason': None if len(unplaced) == 0 else 'Not all items fit',
        'container': container,
        'placements': placements,
        'unplaced_items': unplaced,
        'used_volume': used_volume,
        'total_volume': total_volume,
        'utilization': utilization,
        'total_weight': total_item_weight + container.tare_weight,
    }


def choose_best_container(items: List[Item], containers: List[Container], mode: str = 'smallest_fit') -> Dict:
    expanded = expand_items(items)
    results = [pack_into_container(expanded, c) for c in containers if c.active]
    successful = [r for r in results if r['success']]
    if not successful:
        return {'success': False, 'reason': 'No container could fit all items', 'all_results': results}

    if mode == 'smallest_fit':
        successful.sort(key=lambda r: (r['total_volume'], r['container'].cost, -r['utilization']))
    elif mode == 'cheapest':
        successful.sort(key=lambda r: (r['container'].cost, r['total_volume']))
    elif mode == 'best_utilization':
        successful.sort(key=lambda r: (-r['utilization'], r['container'].cost))

    best = successful[0]
    return {'success': True, 'selected_container': best['container'], 'placements': best['placements'], 'utilization': best['utilization'], 'used_volume': best['used_volume'], 'total_volume': best['total_volume'], 'total_weight': best['total_weight'], 'all_results': results}


def choose_multiple_containers(items: List[Item], containers: List[Container], mode: str = 'smallest_fit') -> Dict:
    remaining_items = expand_items(items)
    shipments = []
    while remaining_items:
        best_result = None
        for container in containers:
            attempt = pack_into_container(remaining_items, container)
            placed_count = len(attempt['placements'])
            if placed_count == 0:
                continue
            candidate = (-placed_count, attempt['total_volume'], attempt['container'].cost, -attempt['utilization'], attempt)
            if best_result is None or candidate[:-1] < best_result[:-1]:
                best_result = candidate
        if best_result is None:
            return {'success': False, 'reason': 'Could not place remaining items into any container', 'shipments': shipments, 'unplaced_items': remaining_items}
        chosen = best_result[-1]
        shipments.append(chosen)
        remaining_items = chosen['unplaced_items']

    total_cost = sum(s['container'].cost for s in shipments)
    total_weight = sum(s['total_weight'] for s in shipments)
    total_used_volume = sum(s['used_volume'] for s in shipments)
    total_volume = sum(s['total_volume'] for s in shipments)
    return {'success': True, 'selection_policy': 'multiple_containers', 'shipments': shipments, 'shipment_count': len(shipments), 'total_cost': total_cost, 'total_weight': total_weight, 'total_used_volume': total_used_volume, 'total_volume': total_volume, 'overall_utilization': total_used_volume / total_volume if total_volume > 0 else 0.0, 'unplaced_items': []}


def load_order_lines_from_csv(file_path: str) -> List[OrderLine]:
    rows = []
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(OrderLine(box_code=row['box_code'], qty=int(row['qty'])))
    return rows


def load_box_master_from_csv(file_path: str) -> List[BoxType]:
    rows = []
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(BoxType(box_code=row['box_code'], length=int(row['length']), width=int(row['width']), height=int(row['height']), weight=float(row['weight']), can_rotate=bool(int(row['can_rotate']))))
    return rows


def load_containers_from_csv(file_path: str) -> List[Container]:
    containers = []
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            containers.append(Container(code=row['code'], type=row['type'], length=int(row['length']), width=int(row['width']), height=int(row['height']), max_weight=float(row['max_weight']), tare_weight=float(row['tare_weight']), cost=float(row['cost']), active=bool(int(row['active']))))
    return containers


def export_single_result_to_csv(result: Dict, file_path: str = 'results.csv') -> None:
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['container_code', 'container_type', 'selection_policy', 'utilization', 'used_volume', 'total_volume', 'total_weight', 'sku', 'x', 'y', 'z', 'length', 'width', 'height', 'item_weight'])
        if not result.get('success') or 'selected_container' not in result:
            return
        selected = result['selected_container']
        policy = result.get('selection_policy', 'single_container')
        for p in result['placements']:
            writer.writerow([selected.code, selected.type, policy, result['utilization'], result['used_volume'], result['total_volume'], result['total_weight'], p.sku, p.x, p.y, p.z, p.length, p.width, p.height, p.weight])


def export_multiple_results_to_csv(result: Dict, file_path: str = 'results_multi.csv') -> None:
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['shipment_no', 'container_code', 'container_type', 'utilization', 'used_volume', 'total_volume', 'total_weight', 'sku', 'x', 'y', 'z', 'length', 'width', 'height', 'item_weight'])
        if not result.get('success'):
            return
        for idx, shipment in enumerate(result['shipments'], start=1):
            container = shipment['container']
            for p in shipment['placements']:
                writer.writerow([idx, container.code, container.type, shipment['utilization'], shipment['used_volume'], shipment['total_volume'], shipment['total_weight'], p.sku, p.x, p.y, p.z, p.length, p.width, p.height, p.weight])


def main():
    order_lines = load_order_lines_from_csv('order_lines.csv')
    box_master = load_box_master_from_csv('box_master.csv')
    pallets = load_containers_from_csv('pallets.csv')
    items = expand_order_lines(order_lines, box_master)

    single_result = choose_best_container(items, pallets, mode='smallest_fit')
    multi_result = choose_multiple_containers(items, pallets, mode='smallest_fit')
    export_single_result_to_csv(single_result, 'results.csv')
    export_multiple_results_to_csv(multi_result, 'results_multi.csv')


if __name__ == '__main__':
    main()
