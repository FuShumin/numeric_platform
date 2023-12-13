import copy
import random

from flask import jsonify

from common import Warehouse, Dock, Order, Carriage, Vehicle, WarehouseLoad, generate_schedule
from utils import haversine_distance, find_closest_vehicle


def parse_internal_data(request_data):
    """
    解析请求数据，初始化仓库、订单、车辆和车厢的数据模型。
    参数:
        request_data: 包含仓库、订单、车辆和车厢信息的请求数据。
    返回:
        初始化后的仓库、订单、车辆和车厢对象。
    """
    warehouses = [Warehouse(w['warehouse_id'], [Dock(**d) for d in w['docks']], w.get('location', None)) for w in
                  request_data['warehouses']]
    orders = [Order(**o) for o in request_data['orders']]
    vehicles = [Vehicle(**v) for v in request_data['vehicles']]
    carriages = [Carriage(**c) for c in request_data['carriages']]
    return warehouses, orders, vehicles, carriages


def classify_orders(orders):
    loading_orders = [order for order in orders if order.order_type == 1]  # 1=内部出库单
    unloading_orders = [order for order in orders if order.order_type == 2]  # 2=内部入库单
    return loading_orders, unloading_orders


def create_response(order_sequences, carriage_vehicle_dock_assignments):
    return jsonify({"code": 0,
                    "message": "处理成功。",
                    "data": {"order_sequences": order_sequences,
                             "carriage_vehicle_dock_assignments": carriage_vehicle_dock_assignments}})


def generate_loading_route(cargo_operations):
    loading_operations = [op for op in cargo_operations if op.operation == 1]
    warehouse_aggregate = {}
    for op in loading_operations:
        if op.warehouse_id not in warehouse_aggregate:
            warehouse_aggregate[op.warehouse_id] = []
        warehouse_aggregate[op.warehouse_id].append(op)

    optimized_loading_route = []
    for warehouse_id in warehouse_aggregate:
        optimized_loading_route.extend(warehouse_aggregate[warehouse_id])

    return optimized_loading_route


def generate_unloading_route(cargo_operations, cargo_stack):
    cargo_stack_copy = copy.deepcopy(cargo_stack)
    unloading_route = []
    unloading_operations = [op for op in cargo_operations if op.operation == 2]

    for i in range(len(cargo_stack_copy) - 1, -1, -1):
        stack_op = cargo_stack_copy[i]
        for operation in unloading_operations:
            # 从栈顶部（最后一个装载的货物）开始寻找匹配货物
            if stack_op.cargo_type == operation.cargo_type and stack_op.quantity == operation.quantity:
                # 卸载操作
                unloading_route.append(
                    WarehouseLoad(operation.warehouse_id, stack_op.cargo_type, operation.quantity, 2))
                break

    return unloading_route


# 装货路线和卸货路线 去重
def extract_unique_warehouse_ids(route):
    seen_warehouses = set()
    unique_warehouses = []
    for operation in route:
        if operation.warehouse_id not in seen_warehouses:
            seen_warehouses.add(operation.warehouse_id)
            unique_warehouses.append(operation.warehouse_id)
    return unique_warehouses


def parse_cargo_operations(order):
    cargo_operations = []

    for load in order.warehouse_loads:
        # 提取需要的信息
        warehouse_id = load.warehouse_id
        item_code = load.cargo_type
        quantity = load.quantity
        operation = load.operation

        # 创建 WarehouseLoad 对象并添加到列表
        cargo_operations.append(WarehouseLoad(warehouse_id, item_code, quantity, operation))

    return cargo_operations


def calculate_total_quantity(cargo_stack, first_warehouse_id):
    total_quantity = 0
    for load in cargo_stack:
        if load.warehouse_id == first_warehouse_id:
            total_quantity += load.quantity
    return total_quantity


def process_loading_orders(loading_orders, warehouses, carriages):
    """

    :param loading_orders: 内部入库单
    :param warehouses: 仓库信息
    :param carriages: 车厢信息
    :return: 仓库路线，车厢id
    """
    order_sequences = {}
    carriage_vehicle_dock_assignments = []

    for order in loading_orders:
        order_id = str(order.id)
        cargo_operations = parse_cargo_operations(order)
        loading_route = generate_loading_route(cargo_operations)

        cargo_stack = [operation for operation in loading_route if operation.operation == 1]  # 1 =装货， 2=卸货
        unloading_route = generate_unloading_route(cargo_operations, cargo_stack)

        unique_loading_ids = extract_unique_warehouse_ids(loading_route)
        unique_unloading_ids = extract_unique_warehouse_ids(unloading_route)
        combined_warehouse_ids = unique_loading_ids + unique_unloading_ids
        order_sequences[order_id] = combined_warehouse_ids
        first_warehouse_id = combined_warehouse_ids[0]
        first_warehouse = next((w for w in warehouses if w.id == first_warehouse_id), None)
        warehouse_location = first_warehouse.location
        closest_carriage = min(
            (c for c in carriages if c.state == 0),
            key=lambda c: haversine_distance(c.location['latitude'], c.location['longitude'],
                                             warehouse_location['latitude'], warehouse_location['longitude']),
            default=None
        )
        if closest_carriage:
            closest_carriage.state = 1
        carriage_vehicle_dock_assignments.append({"order_id": order.id,
                                                  "carriage_id": closest_carriage.id})

    return order_sequences, carriage_vehicle_dock_assignments


def process_unloading_orders(unloading_orders, warehouses, carriages, vehicles):
    order_sequences = {}
    carriage_vehicle_dock_assignments = []

    for order in unloading_orders:
        order_info = {}
        order_id = str(order.id)
        order_info["order_id"] = order.id
        required_carriage = order.required_carriage
        cargo_operations = parse_cargo_operations(order)
        loading_route = generate_loading_route(cargo_operations)

        cargo_stack = [operation for operation in loading_route if operation.operation == 1]  # 假设 1 代表装货
        unloading_route = generate_unloading_route(cargo_operations, cargo_stack)
        # 提取并去重仓库ID
        unique_loading_ids = extract_unique_warehouse_ids(loading_route)
        unique_unloading_ids = extract_unique_warehouse_ids(unloading_route)
        # 合并装货和卸货路线的仓库ID
        combined_warehouse_ids = unique_loading_ids + unique_unloading_ids
        order_sequences[order_id] = combined_warehouse_ids

        first_warehouse_id = combined_warehouse_ids[0]
        first_load = calculate_total_quantity(cargo_stack, first_warehouse_id)
        order_info["warehouse_id"] = first_warehouse_id
        first_warehouse = next((w for w in warehouses if w.id == first_warehouse_id), None)
        compatible_docks = [dock for dock in first_warehouse.docks if
                            (dock.dock_type == 2 or dock.dock_type == 3) and required_carriage in
                            dock.compatible_carriage]
        compatible_docks.sort(key=lambda x: (-x.outbound_efficiency, random.random()))
        if compatible_docks:
            assigned_dock = compatible_docks[0]
            assigned_dock_id = assigned_dock.id
            order_info["dock_id"] = assigned_dock_id
            lay_time = first_load / assigned_dock.efficiency  # TODO 加权
            order_info["lay_time"] = lay_time
            # 判断月台是否已有符合条件的车厢
            matching_carriage = next((c for c in carriages if c.current_dock_id == assigned_dock_id
                                      and c.type == required_carriage
                                      and c.state == 0), None)
            if matching_carriage:
                # 如果找到匹配的车厢，则分配该车厢并无须分配车辆
                order_info["carriage_id"] = matching_carriage.id
                # 更新车厢状态
                matching_carriage.state = 1
                order_info['vehicle_id'] = None
            else:
                # 如果没有找到匹配的车厢，根据距离寻找车厢
                warehouse_location = first_warehouse.location
                closest_carriage = min(
                    (c for c in carriages if c.type == required_carriage and c.state == 0),
                    key=lambda c: haversine_distance(c.location['latitude'], c.location['longitude'],
                                                     warehouse_location['latitude'],
                                                     warehouse_location['longitude']),
                    default=None
                )
                if closest_carriage:
                    order_info["carriage_id"] = closest_carriage.id
                    closest_carriage.state = 1

                    # 为车厢选择合适的车辆
                    closest_vehicle = find_closest_vehicle(closest_carriage.location, vehicles)
                    order_info["vehicle_id"] = closest_vehicle.id if closest_vehicle else None
                    closest_vehicle.state = 1  # 更新车辆状态
                else:
                    order_info["carriage_id"] = None
                    order_info["vehicle_id"] = None
        carriage_vehicle_dock_assignments.append(order_info)

    return order_sequences, carriage_vehicle_dock_assignments
