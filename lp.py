# /path/to/optimization_model.py
import pandas as pd
import numpy as np
from scipy.optimize import linprog
from itertools import permutations
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


def create_lp_model(orders: List[Order], warehouses: List[Warehouse]):
    model = pulp.LpProblem("Vehicle_Scheduling", pulp.LpMinimize)

    # 创建变量
    x = pulp.LpVariable.dicts("OrderWarehouseDock",
                              (range(len(orders)), range(len(warehouses)), range(len(warehouses[0].docks))),
                              cat='Binary')

    # 目标函数
    model += pulp.lpSum([x[o][w][d] * orders[o].warehouse_loads[w] / warehouses[w].docks[d].loading_efficiency
                         for o in range(len(orders))
                         for w in range(len(warehouses))
                         for d in range(len(warehouses[w].docks))])

    # 约束条件
    # 每个订单必须在每个仓库的一个月台装货
    for o in range(len(orders)):
        for w in range(len(warehouses)):
            model += pulp.lpSum([x[o][w][d] for d in range(len(warehouses[w].docks))]) == 1

    # 每个月台同时只能有一辆车作业
    for w in range(len(warehouses)):
        for d in range(len(warehouses[w].docks)):
            model += pulp.lpSum([x[o][w][d] for o in range(len(orders))]) <= 1

    # 求解模型
    model.solve()

    return model


class Order:
    def __init__(self, order_id, warehouse_loads, priority):
        self.order_id = order_id
        self.warehouse_loads = warehouse_loads
        self.priority = priority


class Warehouse:
    def __init__(self, warehouse_id, docks):
        self.warehouse_id = warehouse_id
        self.docks = docks


class Dock:
    def __init__(self, dock_id, loading_efficiency):
        self.dock_id = dock_id
        self.loading_efficiency = loading_efficiency


def parse_optimization_result(result, orders, warehouses):
    order_warehouse_dock = {}
    timestamps = {}

    for o in range(len(orders)):
        order_warehouse_dock[o] = []
        timestamps[o] = 0

        for w in range(len(warehouses)):
            for d in range(len(warehouses[w].docks)):
                var_key = f"OrderWarehouseDock_{o}_{w}_{d}"
                if pulp.value(result.variablesDict()[var_key]) == 1:
                    order_warehouse_dock[o].append((w, d))
                    timestamps[o] += orders[o].warehouse_loads[w] / warehouses[w].docks[d].loading_efficiency

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

result = create_lp_model(orders, warehouses)
order_warehouse_dock, timestamps = parse_optimization_result(result, orders, warehouses)

