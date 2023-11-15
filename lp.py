# /path/to/optimization_model.py
import random

import pandas as pd
import numpy as np
from scipy.optimize import linprog
from itertools import permutations
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, LpInteger, value
import pulp
from dataclasses import dataclass
from typing import List


@dataclass
class Order:
    order_id: int
    warehouse_loads: List[int]
    priority: int


@dataclass
class Dock:
    dock_id: int
    loading_efficiency: float


@dataclass
class Warehouse:
    warehouse_id: int
    docks: List[Dock]


def create_lp_model(orders, warehouses):
    # 从仓库中提取所有月台
    docks = [dock for warehouse in warehouses for dock in warehouse.docks]

    # 初始化问题
    model = LpProblem("Vehicle_Scheduling_with_Queue", LpMinimize)

    # 决策变量
    x = pulp.LpVariable.dicts("OrderWarehouseDock",
                              ((order.order_id, warehouse.warehouse_id, dock.dock_id)
                               for order in orders
                               for warehouse in warehouses
                               for dock in warehouse.docks),
                              cat='Binary')
    start_times = LpVariable.dicts("Start_Time",
                                   ((order.order_id, dock.dock_id) for order in orders for dock in docks),
                                   lowBound=0, cat=LpInteger)
    end_times = LpVariable.dicts("End_Time",
                                 ((order.order_id, dock.dock_id) for order in orders for dock in docks),
                                 lowBound=0, cat=LpInteger)

    # 目标函数 - 最小化所有订单的结束时间
    model += lpSum([end_times[order.order_id, dock.dock_id] for order in orders for dock in docks])

    # 约束
    # 每个订单必须在每个仓库的一个月台装货
    for order in orders:
        for warehouse in warehouses:
            model += lpSum([x[order.order_id, warehouse.warehouse_id, dock.dock_id] for dock in warehouse.docks]) == 1

    # 装货时间约束
    for order in orders:
        for dock in docks:
            load_time = order.warehouse_loads[warehouse.warehouse_id] / dock.loading_efficiency
            model += end_times[order.order_id, dock.dock_id] >= start_times[order.order_id, dock.dock_id] + load_time

    # 排队约束
    for dock in docks:
        for i, o1 in enumerate(orders):
            for o2 in orders[i + 1:]:
                model += start_times[o2.order_id, dock.dock_id] >= end_times[o1.order_id, dock.dock_id]

    return model


def parse_optimization_result(model, orders, warehouses):
    order_warehouse_dock = {}
    timestamps = {}

    for order in orders:
        order_warehouse_dock[order.order_id] = []
        timestamps[order.order_id] = 0

        for warehouse in warehouses:
            for dock in warehouse.docks:
                var_key = (order.order_id, warehouse.warehouse_id, dock.dock_id)
                if pulp.value(model.variablesDict()[var_key]) == 1:
                    order_warehouse_dock[order.order_id].append((warehouse.warehouse_id, dock.dock_id))
                    load_time = order.warehouse_loads[warehouse.warehouse_id] / dock.loading_efficiency
                    timestamps[order.order_id] += load_time

    return order_warehouse_dock, timestamps




orders = [
    Order(0, [100, 150, 200], 1),
    Order(1, [200, 100, 150], 2),
    Order(2, [150, 200, 100], 3),
    # ...其他订单
]

warehouses = [
    Warehouse(0, [Dock(0, 10), Dock(1, 15), Dock(2, 20), Dock(3, 25)]),
    Warehouse(1, [Dock(0, 12), Dock(1, 18), Dock(2, 22), Dock(3, 24)]),
    Warehouse(2, [Dock(0, 14), Dock(1, 16), Dock(2, 19), Dock(3, 21)]),
    # ...其他仓库
]


def generate_test_data(num_orders, num_warehouses, num_docks_per_warehouse):
    orders = [Order(order_id=i, warehouse_loads=[random.randint(10, 100) for _ in range(num_warehouses)],
                    priority=random.randint(1, 3)) for i in range(num_orders)]

    docks = [Dock(dock_id=j, loading_efficiency=random.uniform(0.5, 1.5)) for j in range(num_docks_per_warehouse)]
    warehouses = [Warehouse(warehouse_id=i, docks=docks) for i in range(num_warehouses)]

    return orders, warehouses


def main():
    num_orders = 15  # 订单数量
    num_warehouses = 3  # 仓库数量
    num_docks_per_warehouse = 4  # 每个仓库的月台数量

    orders, warehouses = generate_test_data(num_orders, num_warehouses, num_docks_per_warehouse)

    model = create_lp_model(orders, warehouses)
    model.solve()

    order_warehouse_dock, timestamps = parse_optimization_result(model, orders, warehouses)

    # 打印结果
    for order_id in order_warehouse_dock:
        print(f"Order {order_id}:")
        print("  Warehouse-Dock assignments:", order_warehouse_dock[order_id])
        print("  Total loading time:", timestamps[order_id], "time units")
        print()


if __name__ == "__main__":
    main()
