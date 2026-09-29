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
            expanded.append(Item(item.sku, item.length, item.width, item.height, item.weight, 1, item.can_rotate))
    return expanded


def expand_order_lines(order_lines: List[OrderLine], box_master: List[BoxType]) -> List[Item]:
    box_lookup = {b.box_code: b for b in box_master}
    items = []
    for line in order_lines:
        if line.box_code not in box_lookup:
            raise ValueError(f'Box code not found in box master: {line.box_code}')
        box = box_lookup[line.box_code]
        items.append(Item(box.box_code, box.length, box.width, box.height, box.weight, line.qty, box.can_rotate))
    return items


def item_volume(item: Item) -> int:
    return item.length * item.width * item.height


def item_base_area(item: Item) -> int:
    return item.length * item.width


def space_volume(space: Space) -> int:
    return space.length * space.width * space.height


def container_volume(container: Container) -> int:
    return container.length * container.width * container.height


def can_fit(space: Space, dims: Tuple[int, int, int]) -> bool:
    l, w, h = dims
    return l <= space.length and w <= space.width and h <= space.height


def rectangles_overlap_area(ax, ay, aw, ah, bx, by, bw, bh) -> int:
    overlap_x = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    overlap_y = max(0, min(ay + ah, by + bh) - max(ay, by))
    return overlap_x * overlap_y


def support_ratio(placements: List[PackedItem], x: int, y: int, z: int, l: int, w: int) -> float:
    if z == 0:
        return 1.0
    support_area = 0
    for p in placements:
        if p.z + p.height == z:
            support_area += rectangles_overlap_area(x, y, l, w, p.x, p.y, p.length, p.width)
    base_area = l * w
    if base_area == 0:
        return 0.0
    return min(1.0, support_area / base_area)


def score_placement(space: Space, dims: Tuple[int, int, int], item: Item, placements: List[PackedItem], current_sku: str | None = None, prefer_same_sku_blocks: bool = False, minimize_mixing: bool = False, layer_purity: bool = False, strict_no_mix: bool = False, grouping_strength: int = 2) -> Tuple[int, int, int, int, int, int]:
    l, w, h = dims
    leftover = (space.length - l) + (space.width - w) + (space.height - h)
    same_sku_penalty = 0
    mix_penalty = 0
    level_penalty = 0
    factor = max(1, grouping_strength)

    if prefer_same_sku_blocks and current_sku and item.sku != current_sku:
        same_sku_penalty = 30000 * factor

    existing_skus = {p.sku for p in placements}
    level_skus = {p.sku for p in placements if p.z == space.z}

    if strict_no_mix and existing_skus and item.sku not in existing_skus:
        mix_penalty += 200000 * factor
    elif minimize_mixing and existing_skus and item.sku not in existing_skus:
        mix_penalty += 20000 * factor

    if layer_purity and level_skus and item.sku not in level_skus:
        level_penalty += (15000 + len(level_skus) * 4000) * factor

    return (same_sku_penalty, mix_penalty, level_penalty, space.z, leftover, space_volume(space) - (l * w * h))


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


def sort_items(items: List[Item], big_boxes_bottom: bool = False, heavier_boxes_bottom: bool = False, group_by_sku: bool = False) -> List[Item]:
    if group_by_sku and big_boxes_bottom and heavier_boxes_bottom:
        return sorted(items, key=lambda i: (i.sku, item_volume(i), item_base_area(i), i.weight, max(i.length, i.width, i.height)), reverse=True)
    if group_by_sku and big_boxes_bottom:
        return sorted(items, key=lambda i: (i.sku, item_volume(i), item_base_area(i), max(i.length, i.width, i.height), i.weight), reverse=True)
    if group_by_sku and heavier_boxes_bottom:
        return sorted(items, key=lambda i: (i.sku, i.weight, item_volume(i), item_base_area(i), max(i.length, i.width, i.height)), reverse=True)
    if big_boxes_bottom and heavier_boxes_bottom:
        return sorted(items, key=lambda i: (item_volume(i), item_base_area(i), i.weight, max(i.length, i.width, i.height)), reverse=True)
    if big_boxes_bottom:
        return sorted(items, key=lambda i: (item_volume(i), item_base_area(i), max(i.length, i.width, i.height), i.weight), reverse=True)
    if heavier_boxes_bottom:
        return sorted(items, key=lambda i: (i.weight, item_volume(i), item_base_area(i), max(i.length, i.width, i.height)), reverse=True)
    return sorted(items, key=lambda i: (item_volume(i), max(i.length, i.width, i.height), i.weight), reverse=True)


def pack_into_container(items: List[Item], container: Container, big_boxes_bottom: bool = False, heavier_boxes_bottom: bool = False, min_support_ratio_value: float = 0.85, prefer_same_sku_blocks: bool = False, minimize_mixing: bool = False, finish_current_sku_first: bool = False, layer_purity: bool = False, strict_no_mix: bool = False, grouping_strength: int = 2) -> Dict:
    if not container.active:
        return {'success': False, 'reason': 'Container inactive', 'container': container, 'placements': [], 'unplaced_items': items, 'used_volume': 0, 'total_volume': container_volume(container), 'utilization': 0.0, 'total_weight': 0.0}

    total_item_weight = sum(i.weight for i in items)
    if total_item_weight + container.tare_weight > container.max_weight:
        return {'success': False, 'reason': 'Weight limit exceeded', 'container': container, 'placements': [], 'unplaced_items': items, 'used_volume': 0, 'total_volume': container_volume(container), 'utilization': 0.0, 'total_weight': total_item_weight + container.tare_weight}

    spaces = [Space(0, 0, 0, container.length, container.width, container.height)]
    placements = []
    unplaced = []
    sorted_items = sort_items(items, big_boxes_bottom=big_boxes_bottom, heavier_boxes_bottom=heavier_boxes_bottom, group_by_sku=(prefer_same_sku_blocks or finish_current_sku_first or strict_no_mix))
    current_sku = sorted_items[0].sku if sorted_items and finish_current_sku_first else None

    for item in sorted_items:
        best_choice = None
        for space_idx, space in enumerate(spaces):
            for dims in get_orientations(item):
                if can_fit(space, dims):
                    l, w, h = dims
                    ratio = support_ratio(placements, space.x, space.y, space.z, l, w)
                    if ratio < min_support_ratio_value:
                        continue
                    score = score_placement(space, dims, item, placements, current_sku=current_sku, prefer_same_sku_blocks=prefer_same_sku_blocks or finish_current_sku_first, minimize_mixing=minimize_mixing, layer_purity=layer_purity, strict_no_mix=strict_no_mix, grouping_strength=grouping_strength)
                    candidate = (score, space_idx, space, dims)
                    if best_choice is None or candidate[0] < best_choice[0]:
                        best_choice = candidate

        if best_choice is None:
            unplaced.append(item)
            continue

        _, space_idx, chosen_space, dims = best_choice
        l, w, h = dims
        placements.append(PackedItem(item.sku, chosen_space.x, chosen_space.y, chosen_space.z, l, w, h, item.weight, container.code))
        if finish_current_sku_first:
            current_sku = item.sku
        used_space = spaces.pop(space_idx)
        spaces.extend(split_space(used_space, chosen_space.x, chosen_space.y, chosen_space.z, l, w, h))
        spaces = prune_spaces(spaces)

    used_volume = sum(p.length * p.width * p.height for p in placements)
    total_volume = container_volume(container)
    utilization = used_volume / total_volume if total_volume > 0 else 0.0
    return {'success': len(unplaced) == 0, 'reason': None if len(unplaced) == 0 else 'Not all items fit', 'container': container, 'placements': placements, 'unplaced_items': unplaced, 'used_volume': used_volume, 'total_volume': total_volume, 'utilization': utilization, 'total_weight': total_item_weight + container.tare_weight}


def choose_best_container(items: List[Item], containers: List[Container], mode: str = 'smallest_fit', big_boxes_bottom: bool = False, heavier_boxes_bottom: bool = False, min_support_ratio_value: float = 0.85, prefer_same_sku_blocks: bool = False, minimize_mixing: bool = False, finish_current_sku_first: bool = False, layer_purity: bool = False, strict_no_mix: bool = False, grouping_strength: int = 2) -> Dict:
    expanded = expand_items(items)
    results = [pack_into_container(expanded, c, big_boxes_bottom=big_boxes_bottom, heavier_boxes_bottom=heavier_boxes_bottom, min_support_ratio_value=min_support_ratio_value, prefer_same_sku_blocks=prefer_same_sku_blocks, minimize_mixing=minimize_mixing, finish_current_sku_first=finish_current_sku_first, layer_purity=layer_purity, strict_no_mix=strict_no_mix, grouping_strength=grouping_strength) for c in containers if c.active]
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


def choose_multiple_containers(items: List[Item], containers: List[Container], mode: str = 'smallest_fit', big_boxes_bottom: bool = False, heavier_boxes_bottom: bool = False, min_support_ratio_value: float = 0.85, prefer_same_sku_blocks: bool = False, minimize_mixing: bool = False, finish_current_sku_first: bool = False, layer_purity: bool = False, strict_no_mix: bool = False, grouping_strength: int = 2) -> Dict:
    remaining_items = expand_items(items)
    shipments = []
    while remaining_items:
        best_result = None
        for container in containers:
            attempt = pack_into_container(remaining_items, container, big_boxes_bottom=big_boxes_bottom, heavier_boxes_bottom=heavier_boxes_bottom, min_support_ratio_value=min_support_ratio_value, prefer_same_sku_blocks=prefer_same_sku_blocks, minimize_mixing=minimize_mixing, finish_current_sku_first=finish_current_sku_first, layer_purity=layer_purity, strict_no_mix=strict_no_mix, grouping_strength=grouping_strength)
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
    single_result = choose_best_container(items, pallets, mode='smallest_fit', big_boxes_bottom=True, heavier_boxes_bottom=True, min_support_ratio_value=0.85, prefer_same_sku_blocks=True, minimize_mixing=True, finish_current_sku_first=True, layer_purity=True, strict_no_mix=False, grouping_strength=3)
    multi_result = choose_multiple_containers(items, pallets, mode='smallest_fit', big_boxes_bottom=True, heavier_boxes_bottom=True, min_support_ratio_value=0.85, prefer_same_sku_blocks=True, minimize_mixing=True, finish_current_sku_first=True, layer_purity=True, strict_no_mix=False, grouping_strength=3)
    export_single_result_to_csv(single_result, 'results.csv')
    export_multiple_results_to_csv(multi_result, 'results_multi.csv')


if __name__ == '__main__':
    main()
