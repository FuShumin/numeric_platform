from flask import Flask, request, jsonify, abort
from lp import *
from utils import *
from pulp import PULP_CBC_CMD, LpStatus
from internal_utils import *
app = Flask(__name__)


# 外部订单排队叫号算法
@app.route('/external_orders_queueing', methods=['POST'])
def external_orders_queueing():
    data = request.json  # 获取 JSON 格式的数据
    # 解析仓库数据
    warehouses = [Warehouse(w['warehouse_id'], [Dock(**d) for d in w['docks']]) for w in data['warehouses']]

    # 解析订单数据
    orders = [Order(**o) for o in data['orders']]

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

    # SECTION 2 生成按序路径
    loading_order_routes = generate_specific_order_route(loading_orders)
    unloading_order_routes = generate_specific_order_route(unloading_orders)

    # SECTION 3 对装车订单进行一阶段线性规划
    # 读取已有时间表
    filename = "local_schedule.csv"
    loaded_schedule = load_and_prepare_schedule(filename, loading_orders)
    existing_busy_time, busy_slots = calculate_busy_times_and_windows(loaded_schedule, loading_warehouses)

    loading_model = create_lp_model(loading_orders, loading_warehouses, existing_busy_time)
    loading_model.solve(solver=PULP_CBC_CMD(msg=False))
    print("-" * 8, "loading_model", "-" * 8)
    print("Status:", LpStatus[loading_model.status])
    print("Objective =", value(loading_model.objective))
    print("=" * 10)

    # TODO when problem is infeasible，raise error/logs
    loading_var_dicts = loading_model.variablesDict()
    loading_order_dock_assignments, loading_latest_completion_time = parse_optimization_result(loading_model, orders,
                                                                                               warehouses)
    print("Order Dock Assignments:", loading_order_dock_assignments)
    print("Latest Completion Time:", loading_latest_completion_time)
    # SECTION 3.5 对装车订单二阶段排队规划
    loading_queue_model = create_queue_model(loading_orders, loading_warehouses, loading_order_dock_assignments,
                                             loading_order_routes, busy_slots)
    loading_queue_model.solve(solver=PULP_CBC_CMD(msg=False))
    print("-" * 8, "loading_queue_model", "-" * 8, )
    print("Status:", LpStatus[loading_queue_model.status])
    print("Objective =", value(loading_queue_model.objective))
    print("=" * 10)
    # TODO when problem is infeasible，raise error/logs
    loading_start_times, loading_end_times = parse_queue_results(loading_queue_model, loading_orders,
                                                                 loading_warehouses)

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
    unloading_model.solve(solver=PULP_CBC_CMD(msg=False))
    print("-" * 8, "unloading_model", "-" * 8, )
    print("Status:", LpStatus[unloading_model.status])
    print("Objective =", value(unloading_model.objective))
    print("=" * 10)
    # TODO when problem is infeasible，raise error/logs
    var_dicts = unloading_model.variablesDict()
    unloading_order_dock_assignments, unloading_latest_completion_time = parse_optimization_result(unloading_model,
                                                                                                   unloading_orders,
                                                                                                   unloading_warehouses)

    unloading_queue_model = create_queue_model(unloading_orders, unloading_warehouses, unloading_order_dock_assignments,
                                               unloading_order_routes, busy_slots)
    unloading_queue_model.solve(solver=PULP_CBC_CMD(msg=False))
    print("-" * 8, "unloading_queue_model", "-" * 8, )
    print("Status:", LpStatus[unloading_queue_model.status])
    print("Objective =", value(unloading_queue_model.objective))
    print("=" * 10)
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
    warehouses, orders, vehicles, carriages = parse_internal_data(data)
    # 根据订单类型分别创建装车和卸车订单的列表
    loading_orders, unloading_orders = classify_orders(orders)
    # 创建两个新的仓库列表，分别用于装车和卸车任务
    loading_warehouses, unloading_warehouses = create_warehouses(warehouses)
    # 异常检查：确保订单中的"required_carriage"字段不为空
    for order in orders:
        if order.required_carriage is None:
            #abort(400, "缺少需求车型")
            abort(400, "订单 {} 缺少需求车型 'required_carriage'".format(order.id))

    # 初始化变量
    order_sequences = None
    carriage_vehicle_dock_assignments = None
    try:
        # SECTION 内部入库单
        if loading_orders:
            order_sequences, carriage_vehicle_dock_assignments = process_loading_orders(
                loading_orders, warehouses, carriages)
        # SECTION 内部出库单
        elif unloading_orders:
            order_sequences, carriage_vehicle_dock_assignments = process_unloading_orders(
                unloading_orders, warehouses, carriages, vehicles)

        # 确保变量已被赋值
        if order_sequences is None or carriage_vehicle_dock_assignments is None:
            raise ValueError("未能成功生成订单序列或车辆装载分配。")

        response = create_response(order_sequences, carriage_vehicle_dock_assignments)
        return response

    except Exception as e:
        print(e)
        # 返回错误信息
        return jsonify({"code": 1, "message": f"处理过程中发生错误：{e}。"}), 400


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

            if order_info.get('perform_dock_matching'):
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
                "perform_vehicle_matching": order_info.get("perform_vehicle_matching"),
                "perform_dock_matching": order_info.get("perform_dock_matching"),
                "add_cx_task": order_info.get("add_cx_task"),
                "sort_no": order_info.get("sort_no")
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
