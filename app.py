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
    loading_orders = [order for order in orders if order.order_type == "装车"]
    unloading_orders = [order for order in orders if order.order_type == "卸车"]
    # 创建两个新的仓库列表，分别用于装车和卸车任务
    loading_warehouses = []
    unloading_warehouses = []

    # 遍历所有的仓库
    for warehouse in warehouses:
        # 为装车任务筛选月台
        loading_docks = [dock for dock in warehouse.docks if dock.dock_type in ["装车", "通用"]]
        # 设置效率并添加到装车仓库列表
        for dock in loading_docks:
            dock.set_efficiency("装车")
        if loading_docks:
            loading_warehouses.append(Warehouse(warehouse.id, loading_docks))

        # 为卸车任务筛选月台
        unloading_docks = [dock for dock in warehouse.docks if dock.dock_type in ["卸车", "通用"]]
        # 设置效率并添加到卸车仓库列表
        for dock in unloading_docks:
            dock.set_efficiency("卸车")
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
    loading_model = create_lp_model(loading_orders, loading_warehouses)
    loading_model.solve()
    loading_var_dicts = loading_model.variablesDict()
    order_dock_assignments, latest_completion_time = parse_optimization_result(loading_model, orders, warehouses)
    print("Order Dock Assignments:", order_dock_assignments)
    print("Latest Completion Time:", latest_completion_time)
    # SECTION 3.5 对装车订单二阶段排队规划
    queue_model = create_queue_model(orders, warehouses, order_dock_assignments, loading_order_routes)
    queue_model.solve()

    return jsonify({"message": "Algorithm 1 processed the data"})


@app.route('/internal_orders_queueing', methods=['POST'])
def internal_orders_queueing():
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

    return jsonify({"message": "Success"})


if __name__ == '__main__':
    app.run(debug=True)
