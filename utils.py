from common import Warehouse, Dock, Order


def parse_input_data(data):
    # 解析订单数据
    orders = []
    for order_data in data['orders']:
        order_id = order_data['order_id']
        warehouse_loads = {wl['warehouse_id']: wl['load'] for wl in order_data['warehouse_loads']}
        priority = order_data['priority']
        sequential = order_data['sequential']
        required_carriage = order_data['required_carriage']
        order_type = order_data['order_type']
        orders.append(Order(order_id, warehouse_loads, priority, sequential, required_carriage, order_type))

    # 解析仓库和月台数据
    warehouses = []
    for warehouse_data in data['warehouses']:
        warehouse_id = warehouse_data['warehouse_id']
        docks = []
        for dock_data in warehouse_data['docks']:
            dock_id = dock_data['dock_id']
            outbound_efficiency = dock_data['outbound_efficiency']
            inbound_efficiency = dock_data['inbound_efficiency']
            weight = dock_data['weight']
            dock_type = dock_data['dock_type']
            compatible_carriage = dock_data['compatible_carriage']
            docks.append(Dock(dock_id, outbound_efficiency, inbound_efficiency, weight, dock_type, compatible_carriage))
        warehouses.append(Warehouse(warehouse_id, docks))

    return orders, warehouses

