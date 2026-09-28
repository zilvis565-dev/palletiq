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

    right = Space(
        x=px + pl,
        y=py,
        z=pz,
        length=space.x + space.length - (px + pl),
        width=space.width,
        height=space.height,
    )
    if right.length > 0 and right.width > 0 and right.height > 0:
        new_spaces.append(right)

    front = Space(
        x=px,
        y=py + pw,
        z=pz,
        length=pl,
        width=space.y + space.width - (py + pw),
        height=space.height,
    )
    if front.length > 0 and front.width > 0 and front.height > 0:
        new_spaces.append(front)

    above = Space(
        x=px,
        y=py,
        z=pz + ph,
        length=pl,
        width=pw,
        height=space.z + space.height - (pz + ph),
    )
    if above.length > 0 and above.width > 0 and above.height > 0:
        new_spaces.append(above)

    return new_spaces


def prune_spaces(spaces: List[Space]) -> List[Space]:
    pruned = []
    for i, s1 in enumerate(spaces):
        contained = False
        for j, s2 in enumerate(spaces):
            if i != j:
                if (
                    s1.x >= s2.x
                    and s1.y >= s2.y
                    and s1.z >= s2.z
                    and s1.x + s1.length <= s2.x + s2.length
                    and s1.y + s1.width <= s2.y + s2.width
                    and s1.z + s1.height <= s2.z + s2.height
                ):
                    contained = True
                    break
        if not contained:
            pruned.append(s1)
    return pruned


def pack_into_container(items: List[Item], container: Container) -> Dict:
    if not container.active:
        return {
            'success': False,
            'reason': 'Container inactive',
            'container': container,
            'placements': [],
            'unplaced_items': items,
            'used_volume': 0,
            'total_volume': container_volume(container),
            'utilization': 0.0,
            'total_weight': 0.0,
        }

    total_item_weight = sum(i.weight for i in items)
    if total_item_weight + container.tare_weight > container.max_weight:
        return {
            'success': False,
            'reason': 'Weight limit exceeded',
            'container': container,
            'placements': [],
            'unplaced_items': items,
            'used_volume': 0,
            'total_volume': container_volume(container),
            'utilization': 0.0,
            'total_weight': total_item_weight + container.tare_weight,
        }

    spaces = [Space(0, 0, 0, container.length, container.width, container.height)]
    placements = []
    unplaced = []

    sorted_items = sorted(
        items,
        key=lambda i: (item_volume(i), max(i.length, i.width, i.height), i.weight),
        reverse=True,
    )

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

        packed = PackedItem(
            sku=item.sku,
            x=chosen_space.x,
            y=chosen_space.y,
            z=chosen_space.z,
            length=l,
            width=w,
            height=h,
            weight=item.weight,
            container_code=container.code,
        )
        placements.append(packed)

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
    active_containers = [c for c in containers if c.active]
    results = [pack_into_container(expanded, container) for container in active_containers]
    successful = [r for r in results if r['success']]

    if not successful:
        return {
            'success': False,
            'reason': 'No container could fit all items',
            'all_results': results,
        }

    if mode == 'smallest_fit':
        successful.sort(key=lambda r: (r['total_volume'], r['container'].cost, -r['utilization']))
    elif mode == 'cheapest':
        successful.sort(key=lambda r: (r['container'].cost, r['total_volume']))
    elif mode == 'best_utilization':
        successful.sort(key=lambda r: (-r['utilization'], r['container'].cost))
    else:
        successful.sort(key=lambda r: (r['total_volume'], r['container'].cost))

    best = successful[0]
    return {
        'success': True,
        'selected_container': best['container'],
        'placements': best['placements'],
        'utilization': best['utilization'],
        'used_volume': best['used_volume'],
        'total_volume': best['total_volume'],
        'total_weight': best['total_weight'],
        'all_results': results,
    }


def choose_box_then_pallet(items: List[Item], boxes: List[Container], pallets: List[Container], mode: str = 'smallest_fit') -> Dict:
    box_result = choose_best_container(items, boxes, mode)
    if box_result['success']:
        box_result['selection_policy'] = 'box_first'
        return box_result

    pallet_result = choose_best_container(items, pallets, mode)
    if pallet_result['success']:
        pallet_result['selection_policy'] = 'box_first_fallback_to_pallet'
        return pallet_result

    return {
        'success': False,
        'reason': 'No box or pallet could fit all items',
        'box_results': box_result.get('all_results', []),
        'pallet_results': pallet_result.get('all_results', []),
    }


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

            candidate = (
                -placed_count,
                attempt['total_volume'],
                attempt['container'].cost,
                -attempt['utilization'],
                attempt,
            )

            if best_result is None or candidate[:-1] < best_result[:-1]:
                best_result = candidate

        if best_result is None:
            return {
                'success': False,
                'reason': 'Could not place remaining items into any container',
                'shipments': shipments,
                'unplaced_items': remaining_items,
            }

        chosen = best_result[-1]
        shipments.append(chosen)
        remaining_items = chosen['unplaced_items']

    total_cost = sum(s['container'].cost for s in shipments)
    total_weight = sum(s['total_weight'] for s in shipments)
    total_used_volume = sum(s['used_volume'] for s in shipments)
    total_volume = sum(s['total_volume'] for s in shipments)

    return {
        'success': True,
        'selection_policy': 'multiple_containers',
        'shipments': shipments,
        'shipment_count': len(shipments),
        'total_cost': total_cost,
        'total_weight': total_weight,
        'total_used_volume': total_used_volume,
        'total_volume': total_volume,
        'overall_utilization': total_used_volume / total_volume if total_volume > 0 else 0.0,
        'unplaced_items': [],
    }


def export_single_result_to_csv(result: Dict, file_path: str = 'results.csv') -> None:
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'container_code',
            'container_type',
            'selection_policy',
            'utilization',
            'used_volume',
            'total_volume',
            'total_weight',
            'sku',
            'x',
            'y',
            'z',
            'length',
            'width',
            'height',
            'item_weight',
        ])

        if not result['success']:
            return

        selected = result['selected_container']
        policy = result.get('selection_policy', 'single_container')
        for p in result['placements']:
            writer.writerow([
                selected.code,
                selected.type,
                policy,
                result['utilization'],
                result['used_volume'],
                result['total_volume'],
                result['total_weight'],
                p.sku,
                p.x,
                p.y,
                p.z,
                p.length,
                p.width,
                p.height,
                p.weight,
            ])


def export_multiple_results_to_csv(result: Dict, file_path: str = 'results_multi.csv') -> None:
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'shipment_no',
            'container_code',
            'container_type',
            'utilization',
            'used_volume',
            'total_volume',
            'total_weight',
            'sku',
            'x',
            'y',
            'z',
            'length',
            'width',
            'height',
            'item_weight',
        ])

        if not result['success']:
            return

        for idx, shipment in enumerate(result['shipments'], start=1):
            container = shipment['container']
            for p in shipment['placements']:
                writer.writerow([
                    idx,
                    container.code,
                    container.type,
                    shipment['utilization'],
                    shipment['used_volume'],
                    shipment['total_volume'],
                    shipment['total_weight'],
                    p.sku,
                    p.x,
                    p.y,
                    p.z,
                    p.length,
                    p.width,
                    p.height,
                    p.weight,
                ])


def load_items_from_csv(file_path: str) -> List[Item]:
    items = []
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
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


def load_containers_from_csv(file_path: str) -> List[Container]:
    containers = []
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
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


def print_result(result: Dict) -> None:
    if result['success'] and 'selected_container' in result:
        selected = result['selected_container']
        print(f"Selected container: {selected.code} ({selected.type})")
        if 'selection_policy' in result:
            print(f"Selection policy: {result['selection_policy']}")
        print(f"Utilization: {result['utilization']:.2%}")
        print(f"Used volume: {result['used_volume']}")
        print(f"Total volume: {result['total_volume']}")
        print(f"Total weight: {result['total_weight']}")
        print('Placements:')
        for p in result['placements']:
            print(
                f" - {p.sku}: pos=({p.x},{p.y},{p.z}), "
                f"size=({p.length},{p.width},{p.height})"
            )
    elif result['success'] and 'shipments' in result:
        print(f"Selection policy: {result['selection_policy']}")
        print(f"Shipment count: {result['shipment_count']}")
        print(f"Total cost: {result['total_cost']}")
        print(f"Total weight: {result['total_weight']}")
        print(f"Overall utilization: {result['overall_utilization']:.2%}")
        for idx, shipment in enumerate(result['shipments'], start=1):
            container = shipment['container']
            print(f"Shipment {idx}: {container.code} ({container.type})")
            print(f" - Utilization: {shipment['utilization']:.2%}")
            print(f" - Used volume: {shipment['used_volume']}")
            print(f" - Total volume: {shipment['total_volume']}")
            print(f" - Total weight: {shipment['total_weight']}")
            for p in shipment['placements']:
                print(
                    f"   - {p.sku}: pos=({p.x},{p.y},{p.z}), "
                    f"size=({p.length},{p.width},{p.height})"
                )
    else:
        print(result['reason'])
        if 'box_results' in result:
            print('Box attempts:')
            for r in result['box_results']:
                print(f" - {r['container'].code}: {r['reason']}")
        if 'pallet_results' in result:
            print('Pallet attempts:')
            for r in result['pallet_results']:
                print(f" - {r['container'].code}: {r['reason']}")
        elif 'all_results' in result:
            print('Container attempts:')
            for r in result['all_results']:
                print(f" - {r['container'].code}: {r['reason']}")
        if 'unplaced_items' in result and result['unplaced_items']:
            print('Unplaced items:')
            for item in result['unplaced_items']:
                print(f" - {item.sku}: {item.length}x{item.width}x{item.height}, weight={item.weight}")


def main():
    items = load_items_from_csv('items_sample.csv')
    boxes = load_containers_from_csv('boxes.csv')
    pallets = load_containers_from_csv('pallets.csv')

    single_result = choose_box_then_pallet(items, boxes, pallets, mode='smallest_fit')
    print('=== SINGLE CONTAINER RESULT ===')
    print_result(single_result)
    export_single_result_to_csv(single_result, 'results.csv')

    all_containers = boxes + pallets
    multi_result = choose_multiple_containers(items, all_containers, mode='smallest_fit')
    print('\n=== MULTI CONTAINER RESULT ===')
    print_result(multi_result)
    export_multiple_results_to_csv(multi_result, 'results_multi.csv')


if __name__ == '__main__':
    main()
