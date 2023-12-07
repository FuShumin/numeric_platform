from flask import Flask, request, jsonify
from common import *
from lp import *
from utils import *

app = Flask(__name__)


# 外部订单排队叫号算法
@app.route('/external_orders_queueing', methods=['POST'])
def external_orders_queueing():
    data = request.json  # 获取 JSON 格式的数据
    # 解析仓库数据
    warehouses = [Warehouse(w['warehouse_id'], [Dock(**d) for d in w['docks']]) for w in data['warehouses']]

    # 解析订单数据
    orders = [Order(**o) for o in data['orders']]

    # 打印仓库和订单数据用于验证
    for warehouse in warehouses:
        print(warehouse)

    for order in orders:
        print(order)

    # SECTION 1 划分装卸车任务类型
    # 根据订单类型分别创建装车和卸车订单的列表
    loading_orders = [order for order in orders if order.order_type == 2]
    unloading_orders = [order for order in orders if order.order_type == 1]
    # 创建两个新的仓库列表，分别用于装车和卸车任务
    loading_warehouses = []
    unloading_warehouses = []

    # 遍历所有的仓库
    for warehouse in warehouses:
        # 为装车任务筛选月台
        loading_docks = [dock for dock in warehouse.docks if dock.dock_type in [2, 3]]
        # 设置效率并添加到装车仓库列表
        for dock in loading_docks:
            dock.set_efficiency(2)
        if loading_docks:
            loading_warehouses.append(Warehouse(warehouse.id, loading_docks))

        # 为卸车任务筛选月台
        unloading_docks = [dock for dock in warehouse.docks if dock.dock_type in [1, 3]]
        # 设置效率并添加到卸车仓库列表
        for dock in unloading_docks:
            dock.set_efficiency(1)
        if unloading_docks:
            unloading_warehouses.append(Warehouse(warehouse.id, unloading_docks))

    # 打印装车订单
    print("装车订单:")
    for order in loading_orders:
        print(
            f"Order ID: {order.id}, Priority: {order.priority}, Sequential: {order.sequential}, Required Carriage: {order.required_carriage}, Order Type: {order.order_type}")

    # 打印卸车订单
    print("\n卸车订单:")
    for order in unloading_orders:
        print(
            f"Order ID: {order.id}, Priority: {order.priority}, Sequential: {order.sequential}, Required Carriage: {order.required_carriage}, Order Type: {order.order_type}")

    # 打印仓库信息
    print("\n装车仓库, 月台:")
    for warehouse in loading_warehouses:
        print(f"Loading Warehouse ID: {warehouse.id}")
        for dock in warehouse.docks:
            print(f"  Dock ID: {dock.id}, Efficiency: {dock.efficiency}")

    print("\n卸车仓库, 月台:")
    for warehouse in unloading_warehouses:
        print(f"Unloading Warehouse ID: {warehouse.id}")
        for dock in warehouse.docks:
            print(f"  Dock ID: {dock.id}, Efficiency: {dock.efficiency}")

    # SECTION 2 生成按序路径
    loading_order_routes = generate_specific_order_route(loading_orders)
    unloading_order_routes = generate_specific_order_route(unloading_orders)

    # 打印路线
    print("\n装车订单的特定路径:")
    for order_id, route in loading_order_routes.items():
        print(f"Order ID: {order_id}, Route: {route}")

    print("\n卸车订单的特定路径:")
    for order_id, route in unloading_order_routes.items():
        print(f"Order ID: {order_id}, Route: {route}")

    # SECTION 3 对装车订单进行一阶段线性规划
    # 读取已有时间表
    filename = "local_schedule.csv"
    loaded_schedule = load_and_prepare_schedule(filename, loading_orders)
    existing_busy_time, busy_slots = calculate_busy_times_and_windows(loaded_schedule, loading_warehouses)

    loading_model = create_lp_model(loading_orders, loading_warehouses, existing_busy_time)
    loading_model.solve()
    # TODO when problem is infeasible，raise error/logs
    loading_var_dicts = loading_model.variablesDict()
    loading_order_dock_assignments, loading_latest_completion_time = parse_optimization_result(loading_model, orders,
                                                                                               warehouses)
    print("Order Dock Assignments:", loading_order_dock_assignments)
    print("Latest Completion Time:", loading_latest_completion_time)
    # SECTION 3.5 对装车订单二阶段排队规划
    loading_queue_model = create_queue_model(loading_orders, loading_warehouses, loading_order_dock_assignments,
                                             loading_order_routes, busy_slots)
    loading_queue_model.solve()
    # TODO when problem is infeasible，raise error/logs
    loading_start_times, loading_end_times = parse_queue_results(loading_queue_model, loading_orders,
                                                                 loading_warehouses)
    # 显示排队结果
    print("Start Times:", loading_start_times)
    print("End Times:", loading_end_times)
    # SECTION 3.8 数据持久化
    # plot_order_times_on_docks(loading_start_times, loading_end_times, loading_warehouses, busy_slots)

    loading_schedule = generate_schedule(loading_start_times, loading_end_times, "queue")
    # 保存时间表到文件
    save_schedule_to_file(loading_schedule, filename)
    # SECTION 4 卸车订单的处理, 同上
    # 查找每个月台已占用的忙碌时间窗口
    loaded_schedule = load_and_prepare_schedule(filename, unloading_orders)
    existing_busy_time, busy_slots = calculate_busy_times_and_windows(loaded_schedule, warehouses)

    unloading_model = create_lp_model(unloading_orders, unloading_warehouses, existing_busy_time)
    unloading_model.solve()
    # TODO when problem is infeasible，raise error/logs
    var_dicts = unloading_model.variablesDict()
    unloading_order_dock_assignments, unloading_latest_completion_time = parse_optimization_result(unloading_model,
                                                                                                   unloading_orders,
                                                                                                   unloading_warehouses)

    unloading_queue_model = create_queue_model(unloading_orders, unloading_warehouses, unloading_order_dock_assignments,
                                               unloading_order_routes, busy_slots)
    unloading_queue_model.solve()
    # TODO when problem is infeasible，raise error/logs
    unloading_start_times, unloading_end_times = parse_queue_results(unloading_queue_model, unloading_orders,
                                                                     unloading_warehouses)
    # plot_order_times_on_docks(unloading_start_times, unloading_end_times, busy_slots)

    unloading_schedule = generate_schedule(unloading_start_times, unloading_end_times, "queue")
    save_schedule_to_file(unloading_schedule, filename)

    # SECTION 5 提取全部订单结果，解析成出参格式
    try:
        schedule = pd.concat([loading_schedule, unloading_schedule], ignore_index=True)
        parsed_result = parse_schedule(schedule)
        return jsonify({
            "code": 0,
            "message": "处理成功。",
            "data": parsed_result
        })

    except Exception as e:
        print(e)
        # 返回错误信息
        return jsonify({
            "code": 1,
            "message": "处理过程中发生错误。"
        }), 500


@app.route('/internal_orders_queueing', methods=['POST'])
def internal_orders_queueing():
    data = request.json  # 获取 JSON 格式的数据
    # 解析仓库数据
    warehouses = [Warehouse(w['warehouse_id'], [Dock(**d) for d in w['docks']], w.get('location', None)) for w in
                  data['warehouses']]
    # 解析订单数据
    orders = [Order(**o) for o in data['orders']]
    # 解析车辆数据
    vehicles = [Vehicle(**v) for v in data['vehicles']]
    # 解析车厢数据
    carriages = [Carriage(**c) for c in data['carriages']]

    # 打印仓库和订单数据用于验证
    for warehouse in warehouses:
        print(warehouse)

    for order in orders:
        print(order)

    for vehicle in vehicles:
        print(vehicle)

    for carriage in carriages:
        print(carriage)

    # SECTION 1 划分装卸车任务类型
    # 根据订单类型分别创建装车和卸车订单的列表
    loading_orders = [order for order in orders if order.order_type == 2]
    unloading_orders = [order for order in orders if order.order_type == 1]
    # 创建两个新的仓库列表，分别用于装车和卸车任务
    loading_warehouses = []
    unloading_warehouses = []
    # 遍历所有的仓库
    for warehouse in warehouses:
        # 为装车任务筛选月台
        loading_docks = [dock for dock in warehouse.docks if dock.dock_type in [2, 3]]
        # 设置效率并添加到装车仓库列表
        for dock in loading_docks:
            dock.set_efficiency(2)
        if loading_docks:
            loading_warehouses.append(Warehouse(warehouse.id, loading_docks))

        # 为卸车任务筛选月台
        unloading_docks = [dock for dock in warehouse.docks if dock.dock_type in [1, 3]]
        # 设置效率并添加到卸车仓库列表
        for dock in unloading_docks:
            dock.set_efficiency(1)
        if unloading_docks:
            unloading_warehouses.append(Warehouse(warehouse.id, unloading_docks))
    # 打印装车订单
    print("装车订单:")
    for order in loading_orders:
        print(
            f"Order ID: {order.id}, Priority: {order.priority}, Sequential: {order.sequential}, Required Carriage: {order.required_carriage}, Order Type: {order.order_type}")

    # 打印卸车订单
    print("\n卸车订单:")
    for order in unloading_orders:
        print(
            f"Order ID: {order.id}, Priority: {order.priority}, Sequential: {order.sequential}, Required Carriage: {order.required_carriage}, Order Type: {order.order_type}")

    # 打印仓库信息
    print("\n装车仓库, 月台:")
    for warehouse in loading_warehouses:
        print(f"Loading Warehouse ID: {warehouse.id}")
        for dock in warehouse.docks:
            print(f"  Dock ID: {dock.id}, Efficiency: {dock.efficiency}")

    print("\n卸车仓库, 月台:")
    for warehouse in unloading_warehouses:
        print(f"Unloading Warehouse ID: {warehouse.id}")
        for dock in warehouse.docks:
            print(f"  Dock ID: {dock.id}, Efficiency: {dock.efficiency}")

    # SECTION 2 生成按序路径
    loading_order_routes = generate_specific_order_route(loading_orders)
    unloading_order_routes = generate_specific_order_route(unloading_orders)

    # 打印路线
    print("\n装车订单的特定路径:")
    for order_id, route in loading_order_routes.items():
        print(f"Order ID: {order_id}, Route: {route}")

    print("\n卸车订单的特定路径:")
    for order_id, route in unloading_order_routes.items():
        print(f"Order ID: {order_id}, Route: {route}")

    # SECTION 3 对装车订单进行一阶段线性规划
    # 读取已有时间表
    filename = "internal_schedule.csv"
    loaded_schedule = load_and_prepare_schedule(filename, loading_orders)
    existing_busy_time, busy_slots = calculate_busy_times_and_windows(loaded_schedule, loading_warehouses)

    loading_model = create_lp_model(loading_orders, loading_warehouses, existing_busy_time)
    loading_model.solve()
    # TODO when problem is infeasible，raise error/logs
    loading_order_dock_assignments, loading_latest_completion_time = parse_optimization_result(loading_model,
                                                                                               orders,
                                                                                               warehouses)
    print("Order Dock Assignments:", loading_order_dock_assignments)
    print("Latest Completion Time:", loading_latest_completion_time)
    # SECTION 3.5 对装车订单二阶段排队规划
    loading_queue_model = create_queue_model(loading_orders, loading_warehouses, loading_order_dock_assignments,
                                             loading_order_routes, busy_slots)
    loading_queue_model.solve()
    # TODO when problem is infeasible，raise error/logs
    loading_start_times, loading_end_times = parse_queue_results(loading_queue_model, loading_orders,
                                                                 loading_warehouses)
    # 显示排队结果
    print("Start Times:", loading_start_times)
    print("End Times:", loading_end_times)
    # SECTION 3.8 数据持久化
    # plot_order_times_on_docks(loading_start_times, loading_end_times, loading_warehouses, busy_slots)
    loading_schedule = generate_schedule(loading_start_times, loading_end_times, "queue")
    # 保存时间表到文件
    save_schedule_to_file(loading_schedule, filename)
    # SECTION 4 卸车订单的处理, 同上
    # 查找每个月台已占用的忙碌时间窗口
    loaded_schedule = load_and_prepare_schedule(filename, unloading_orders)
    existing_busy_time, busy_slots = calculate_busy_times_and_windows(loaded_schedule, warehouses)

    unloading_model = create_lp_model(unloading_orders, unloading_warehouses, existing_busy_time)
    unloading_model.solve()
    # TODO when problem is infeasible，raise error/logs
    unloading_order_dock_assignments, unloading_latest_completion_time = parse_optimization_result(unloading_model,
                                                                                                   unloading_orders,
                                                                                                   unloading_warehouses)

    unloading_queue_model = create_queue_model(unloading_orders, unloading_warehouses,
                                               unloading_order_dock_assignments,
                                               unloading_order_routes, busy_slots)
    unloading_queue_model.solve()
    # TODO when problem is infeasible，raise error/logs
    unloading_start_times, unloading_end_times = parse_queue_results(unloading_queue_model, unloading_orders,
                                                                     unloading_warehouses)
    # plot_order_times_on_docks(unloading_start_times, unloading_end_times, busy_slots)

    unloading_schedule = generate_schedule(unloading_start_times, unloading_end_times, "queue")
    save_schedule_to_file(unloading_schedule, filename)

    # SECTION 5 提取全部订单结果，解析成出参格式
    try:
        schedule = pd.concat([loading_schedule, unloading_schedule], ignore_index=True)
        parsed_result = parse_schedule(schedule)
        parsed_internal_result = parse_internal_schedule(schedule)
        internal_result = assign_carriages_to_orders(parsed_internal_result, carriages, warehouses, vehicles, orders)
        internal_result = [entry for entry in internal_result if entry['carriage_id'] is not None]
        return jsonify({"code": 0,
                        "message": "处理成功。",
                        "data": {
                            "order_sequences": parsed_result['order_sequences'],
                            "carriage_vehicle_dock_assignments": internal_result,
                        }})

    except Exception as e:
        print(e)
        # 返回错误信息
        return jsonify({"code": 1, "message": "处理过程中发生错误。"}), 500


@app.route('/drop_pull_scheduling', methods=['POST'])
def drop_pull_scheduling():
    data = request.json  # 获取 JSON 格式的数据
    filename = "DropPull_schedule.csv"

    try:
        parsed_orders = parse_order_carriage_info(data)
        orders = [order_info['order'] for order_info in parsed_orders]
        loaded_schedule = load_and_prepare_schedule(filename, orders)
        vehicles = [Vehicle(**v) for v in data['vehicles']]
        vehicle_dock_assignments = []
        # 打印解析结果
        set_efficiency_for_docks(parsed_orders)
        for order_info in parsed_orders:
            if order_info.get('is_last'):
                if order_info.get('perform_vehicle_matching'):
                    carriage_location = order_info['carriage'].location
                    closest_vehicle = find_closest_vehicle(carriage_location, vehicles)
                    if closest_vehicle:
                        order_info['matched_vehicle_id'] = closest_vehicle.id
                        closest_vehicle.state = 1
                    else:
                        order_info['matched_vehicle_id'] = None
                assignment = {
                    "order_id": order_info["order"].id,
                    "vehicle_id": order_info.get("matched_vehicle_id"),
                    "warehouse_id": None,
                    "dock_id": None,
                    "lay_time": None,
                    "is_last": order_info.get("is_last")
                }
                vehicle_dock_assignments.append(assignment)
            else:
                # 遍历 parsed_orders 并找到最早且效率最高的月台
                selected_dock_id = find_earliest_and_efficient_dock(order_info, loaded_schedule)
                # 更新 order_info 以包含选定的月台 ID
                order_info["selected_dock_id"] = selected_dock_id
                lay_time = calculate_lay_time(order_info)
                order_info["lay_time"] = lay_time

                # SECTION 匹配车辆
                if order_info.get('perform_vehicle_matching'):
                    carriage_location = order_info['carriage'].location
                    closest_vehicle = find_closest_vehicle(carriage_location, vehicles)
                    if closest_vehicle:
                        order_info['matched_vehicle_id'] = closest_vehicle.id
                        closest_vehicle.state = 1
                    else:
                        order_info['matched_vehicle_id'] = None
                assignment = {
                    "order_id": order_info["order"].id,
                    "vehicle_id": order_info.get("matched_vehicle_id"),
                    "warehouse_id": order_info["warehouse"].id,
                    "dock_id": order_info.get("selected_dock_id"),
                    "lay_time": order_info.get("lay_time"),
                    "is_last": order_info.get("is_last")
                }
                vehicle_dock_assignments.append(assignment)

        schedule = generate_schedule_from_orders(parsed_orders)
        save_schedule_to_file(schedule, filename)

        return jsonify({
            "code": 0,
            "message": "处理成功。",
            "data": vehicle_dock_assignments,
        })

    except Exception as e:
        print(e)
        # 返回错误信息
        return jsonify({
            "code": 1,
            "message": "处理过程中发生错误。"
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
