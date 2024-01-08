from common import Warehouse, Dock, Order, Carriage, WarehouseLoad, generate_schedule
import pandas as pd
import math
from datetime import datetime, timedelta
import copy


def parse_schedule(schedule):
    order_sequences = {}
    order_dock_assignments = {}
    docks_queues = {}

    # 解析订单的仓库路线和月台分配
    for _, row in schedule.iterrows():
        order_id = int(row['Order ID'])  # 确保使用整数
        warehouse_id = int(row['Warehouse ID'])
        dock_id = int(row['Dock ID'])

        # 更新订单的仓库路线
        if order_id not in order_sequences:
            order_sequences[order_id] = []
        if warehouse_id not in order_sequences[order_id]:
            order_sequences[order_id].append(warehouse_id)

        # 更新订单的月台分配
        if order_id not in order_dock_assignments:
            order_dock_assignments[order_id] = {}
        order_dock_assignments[order_id][warehouse_id] = dock_id

    # 解析每个月台的排队信息
    for _, row in schedule.iterrows():
        dock_key = (int(row['Warehouse ID']), int(row['Dock ID']))  # 作为元组处理，包括仓库ID和月台ID
        if dock_key not in docks_queues:
            docks_queues[dock_key] = {"warehouse_id": dock_key[0], "dock_id": dock_key[1], "queue": []}

        queue_item = {
            "position": len(docks_queues[dock_key]["queue"]) + 1,
            "order_id": int(row['Order ID']),
            "start_time": str(row['Start Time']),
            "end_time": str(row['End Time'])
        }
        docks_queues[dock_key]["queue"].append(queue_item)

    # Convert dock queues to a list
    docks_queues_list = [value for value in docks_queues.values()]

    return {
        "order_sequences": order_sequences,
        "order_dock_assignments": order_dock_assignments,
        "docks_queues": docks_queues_list
    }


def parse_internal_schedule(schedule):
    orders_first_warehouse_info = []

    # 记录每个订单的仓库路线
    order_warehouse_sequence = {}

    # 确定每个订单的仓库路线顺序
    for _, row in schedule.iterrows():
        order_id = int(row['Order ID'])
        warehouse_id = int(row['Warehouse ID'])

        if order_id not in order_warehouse_sequence:
            order_warehouse_sequence[order_id] = []

        if warehouse_id not in order_warehouse_sequence[order_id]:
            order_warehouse_sequence[order_id].append(warehouse_id)

    # 对于每个订单的第一个仓库，提取相应的月台和装卸时间
    for order_id, warehouses in order_warehouse_sequence.items():
        if warehouses:
            first_warehouse_id = warehouses[0]
            # 从schedule中找到对应的第一个条目
            for _, row in schedule.iterrows():
                if int(row['Order ID']) == order_id and int(row['Warehouse ID']) == first_warehouse_id:
                    dock_id = int(row['Dock ID'])
                    start_time = pd.to_datetime(row['Start Time'])
                    end_time = pd.to_datetime(row['End Time'])
                    duration_minutes = (end_time - start_time).total_seconds() / 60

                    orders_first_warehouse_info.append({
                        "order_id": order_id,
                        "warehouse_id": first_warehouse_id,
                        "dock_id": dock_id,
                        "lay_time": duration_minutes
                    })
                    break

    return orders_first_warehouse_info


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # 地球半径（千米）

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c  # 结果单位为千米
    return distance


def find_closest_vehicle(carriage_location, vehicles):
    """根据车辆的位置和工作负载找到最合适的车辆"""
    # 过滤出状态为空闲的车辆
    available_vehicles = [v for v in vehicles if v.state == 0]

    if not available_vehicles:
        return None

    def calculate_average_workload(vehicles):
        if not vehicles:
            return 0  # 如果列表为空，返回 0

        total_workload = sum(vehicle.workload for vehicle in vehicles)
        return total_workload / len(vehicles)

    average_workload = calculate_average_workload(vehicles)

    # 计算每辆车的得分
    def calculate_vehicle_score(vehicle, carriage_location, average_workload):
        distance = haversine_distance(vehicle.location['latitude'], vehicle.location['longitude'],
                                      carriage_location['latitude'], carriage_location['longitude'])
        # 防止除以零的错误
        if average_workload == 0:
            workload_factor = 1  # 如果平均工作量为0，设置默认工作量因子为1
        else:
            workload_factor = 1 + (vehicle.workload - average_workload) / average_workload

        # 额外检查，确保工作量因子是合理的
        workload_factor = max(workload_factor, 0)
        return distance + workload_factor

    # 选择工作负载和距离的综合最优车辆
    return min(available_vehicles, key=lambda v: calculate_vehicle_score(v, carriage_location, average_workload))


def assign_carriages_to_orders(parsed_internal_result, carriages, warehouses, vehicles, orders):
    for order_info in parsed_internal_result:
        order_id = order_info["order_id"]
        assigned_dock_id = order_info["dock_id"]
        warehouse_id = order_info["warehouse_id"]
        warehouse_location = next((w.location for w in warehouses if w.id == warehouse_id), None)
        orders_dict = {order.id: order for order in orders}
        order = orders_dict.get(order_id)
        if not order:
            continue  # 如果找不到订单，跳过当前循环

        required_carriage = order.required_carriage
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
            if warehouse_location:
                closest_carriage = min(
                    (c for c in carriages if c.type == required_carriage and c.state == 0),
                    key=lambda c: haversine_distance(c.location['latitude'], c.location['longitude'],
                                                     warehouse_location['latitude'], warehouse_location['longitude']),
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

    return parsed_internal_result


def parse_order_carriage_info(data):
    # 解析 JSON 数据
    order_carriage_info = data['order_carriage_info']

    parsed_orders = []

    for info in order_carriage_info:
        # 解析订单信息

        # 创建 Order 对象
        order = Order(
            info['order_id'],
            [],
            None,
            None,
            info['required_carriage'],
            info['order_type']
        )

        # 解析车厢信息
        carriage = Carriage(
            info['carriage_id'],
            info['carriage_location'],
            None,
            None,
            None,
            None,
        )

        # 解析仓库信息
        docks = [Dock(**dock_info) for dock_info in info['next_warehouse']['docks']]
        warehouse = Warehouse(info['next_warehouse']['warehouse_id'], docks)

        # 添加 perform_vehicle_matching
        perform_vehicle_matching = info.get('perform_vehicle_matching', True)
        perform_dock_matching = info.get('perform_dock_matching', True)
        add_cx_task = info.get('add_cx_task', True)
        sort_no = info.get('sort_no', None)
        current_dock_id = info.get('current_dock_id', None)
        load = info.get('load', 0)
        # 将解析后的对象添加到列表
        parsed_orders.append({
            "order": order,
            "carriage": carriage,
            "warehouse": warehouse,
            "perform_vehicle_matching": perform_vehicle_matching,
            "load": load,
            "perform_dock_matching": perform_dock_matching,
            "add_cx_task": add_cx_task,  # 后端传递参数
            "sort_no": sort_no,  # 后端传递参数
            "current_dock_id": current_dock_id  # 后端传递参数
        })

    return parsed_orders


def set_efficiency_for_docks(parsed_orders):
    for order_info in parsed_orders:
        order_type = order_info["order"].order_type
        warehouse = order_info["warehouse"]

        # 根据订单类型筛选月台
        if order_type == 2:
            filtered_docks = [dock for dock in warehouse.docks if dock.dock_type in [2, 3]]
        elif order_type == 1:
            filtered_docks = [dock for dock in warehouse.docks if dock.dock_type in [1, 3]]
        else:
            filtered_docks = warehouse.docks  # 如果订单类型不是 1 或 2，不进行筛选

        # 为筛选后的月台设置效率
        for dock in filtered_docks:
            dock.set_efficiency(order_type)

    return parsed_orders


def find_earliest_and_efficient_dock(order_info, loaded_schedule):
    earliest_time = float('inf')
    highest_efficiency = 0
    selected_dock_id = None
    required_carriage = order_info['order'].required_carriage  # 获取订单所需的车型

    for dock in order_info["warehouse"].docks:
        # 检查月台是否兼容订单所需的车型
        if required_carriage not in dock.compatible_carriage:
            continue  # 如果不兼容，则跳过此月台

        # 查找该月台在调度表中的所有条目
        dock_schedule = loaded_schedule[loaded_schedule['Dock ID'] == dock.id]

        # 获取月台的历史分配次数，如果没有历史记录，则默认为0
        historical_assignments_count = dock_schedule.shape[0] if not dock_schedule.empty else 0
        # historical_assignments_count = historical_assignments.get(dock.id, 0)
        # 如果月台没有安排，则认为它立即可用
        if dock_schedule.empty:
            available_time = 0
        else:
            # 获取最晚的结束时间作为可用时间
            available_time = max(0, dock_schedule['End Time'].max())
            # available_time = dock_schedule['End Time'].max()

        # 考虑历史分配情况，如果月台分配较多，则降低其优先级
        adjusted_efficiency = dock.efficiency / (historical_assignments_count + 1)

        # 检查月台是否早于当前最早时间，且效率高于当前最高效率
        if available_time < earliest_time or (available_time == earliest_time and dock.efficiency > highest_efficiency):
            earliest_time = available_time
            highest_efficiency = adjusted_efficiency
            selected_dock_id = dock.id

    return selected_dock_id


def calculate_lay_time(order_info):
    selected_dock_id = order_info.get("selected_dock_id")
    if selected_dock_id is None:
        return None  # 如果没有选择月台，则无法计算 lay_time

    # 通过月台id 选取月台对象
    selected_dock = next((dock for dock in order_info["warehouse"].docks if dock.id == selected_dock_id), None)
    if selected_dock is None or selected_dock.efficiency == 0:
        return None  # 如果没有找到月台或月台效率为 0，则无法计算 lay_time

    # 计算 lay_time
    load = order_info.get("load", 0)
    lay_time = load / selected_dock.efficiency  # TODO 缺少权重参与
    return lay_time


def generate_schedule_from_orders(parsed_orders):
    start_times = {}
    end_times = {}

    current_time = datetime.now()

    for order_info in parsed_orders:
        order_id = order_info["order"].id
        warehouse_id = order_info["warehouse"].id
        selected_dock_id = order_info.get("selected_dock_id")
        lay_time_minutes = order_info.get("lay_time")  # 确保这是分钟数

        if selected_dock_id is not None and lay_time_minutes is not None:
            # 计算开始和结束时间
            start_time = current_time
            end_time = start_time + timedelta(minutes=lay_time_minutes)

            key = (order_id, warehouse_id, selected_dock_id)
            start_times[key] = start_time
            end_times[key] = end_time

    schedule_df = generate_schedule(start_times, end_times, "drop")
    return schedule_df


# 内部订单装货路线聚合仓库


def main():
    cargo_operations = [
        WarehouseLoad(1, 'A', 400, 'load'),
        WarehouseLoad(2, 'B', 200, 'load'),
        WarehouseLoad(1, 'C', 100, 'load'),

        WarehouseLoad(3, 'A', 400, 'unload'),
        WarehouseLoad(4, 'B', 200, 'unload'),
        WarehouseLoad(3, 'C', 100, 'unload'),
    ]
    loading_route = generate_loading_route(cargo_operations)

    # 创建装卸货堆栈
    cargo_stack = []
    for operation in loading_route:
        if operation.operation == '1':
            cargo_stack.append(operation)

    unloading_route = generate_unloading_route(cargo_operations, cargo_stack)

    # 提取并去重仓库ID
    unique_loading_ids = extract_unique_warehouse_ids(loading_route)
    unique_unloading_ids = extract_unique_warehouse_ids(unloading_route)

    # 合并装货和卸货路线的仓库ID
    combined_warehouse_ids = unique_loading_ids + unique_unloading_ids
