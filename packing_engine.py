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
    return list(orientations)


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
        width=pw,
        height=ph,
    )
    if right.length > 0 and right.width > 0 and right.height > 0:
        new_spaces.append(right)

    front = Space(
        x=px,
        y=py + pw,
        z=pz,
        length=space.length,
        width=space.y + space.width - (py + pw),
        height=ph,
    )
    if front.length > 0 and front.width > 0 and front.height > 0:
        new_spaces.append(front)

    above = Space(
        x=px,
        y=py,
        z=pz + ph,
        length=space.length,
        width=space.width,
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
        }

    total_item_weight = sum(i.weight for i in items)
    if total_item_weight + container.tare_weight > container.max_weight:
        return {
            'success': False,
            'reason': 'Weight limit exceeded',
            'container': container,
            'placements': [],
            'unplaced_items': items,
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
    total_volume = container.length * container.width * container.height
    utilization = used_volume / total_volume if total_volume > 0 else 0

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


def main():
    items = load_items_from_csv('items_sample.csv')
    boxes = load_containers_from_csv('boxes.csv')
    pallets = load_containers_from_csv('pallets.csv')
    all_containers = boxes + pallets

    result = choose_best_container(items, all_containers, mode='smallest_fit')

    if result['success']:
        selected = result['selected_container']
        print(f'Selected container: {selected.code} ({selected.type})')
        print(f'Utilization: {result['utilization']:.2%}')
        print(f'Used volume: {result['used_volume']}')
        print(f'Total volume: {result['total_volume']}')
        print(f'Total weight: {result['total_weight']}')
        print('Placements:')
        for p in result['placements']:
            print(f' - {p.sku}: pos=({p.x},{p.y},{p.z}), size=({p.length},{p.width},{p.height})')
    else:
        print('No suitable container found')
        for r in result['all_results']:
            print(r['container'].code, r['reason'])


if __name__ == '__main__':
    main()
