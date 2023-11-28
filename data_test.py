from common import *

# %%
# 假设的订单数据
orders_data = [
    {
        'order_id': 1,
        'warehouse_loads': {0: 20, 1: 30},
        'priority': 1,
        'sequential': False,
        'required_carriage': "重型车",
        'order_type': "装车"
    },
    {
        'order_id': 2,
        'warehouse_loads': {0: 10, 1: 0},
        'priority': 2,
        'sequential': True,
        'required_carriage': "轻型车",
        'order_type': "卸车"
    }
]

# 假设的仓库和月台数据
warehouses_data = [
    {
        'warehouse_id': 0,
        'docks': [
            {'dock_id': 0, 'outbound_efficiency': 1.0, 'inbound_efficiency': 0.5, 'weight': 1, 'dock_type': "装车", 'compatible_carriage': ["轻型车", "重型车"]},
            {'dock_id': 1, 'outbound_efficiency': 0.8, 'inbound_efficiency': 0.6, 'weight': 1, 'dock_type': "通用", 'compatible_carriage': ["轻型车", "重型车"]}
        ]
    },
    {
        'warehouse_id': 1,
        'docks': [
            {'dock_id': 0, 'outbound_efficiency': 1.0, 'inbound_efficiency': 0.5, 'weight': 1, 'dock_type': "装车", 'compatible_carriage': ["重型车"]},
            {'dock_id': 1, 'outbound_efficiency': 0.8, 'inbound_efficiency': 0.6, 'weight': 1, 'dock_type': "通用", 'compatible_carriage': ["轻型车", "重型车"]}
        ]
    }
]

# 创建订单和仓库对象
orders = [Order(od['order_id'], od['warehouse_loads'], od['priority'], od['sequential'], od['required_carriage'], od['order_type']) for od in orders_data]
warehouses = []
for wd in warehouses_data:
    docks = [Dock(d['dock_id'], d['outbound_efficiency'], d['inbound_efficiency'], d['weight'], d['dock_type'], d['compatible_carriage']) for d in wd['docks']]
    warehouse = Warehouse(wd['warehouse_id'], docks)
    warehouses.append(warehouse)

# 测试：根据订单类型设置月台效率
for order in orders:
    for warehouse in warehouses:
        for dock in warehouse.docks:
            dock.set_efficiency(order.order_type)
            print(f"Order {order.id}, Dock {dock.id}, Efficiency: {dock.efficiency}")
