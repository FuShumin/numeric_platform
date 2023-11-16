# /path/to/optimization_model.py
import random

import pandas as pd
import numpy as np
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, LpInteger, value
import pulp
from visualization import *


class Order:
    def __init__(self, order_id, warehouse_loads, priority):
        self.id = order_id
        self.warehouse_loads = warehouse_loads
        self.priority = priority

    def __str__(self):
        return f"Order(ID: {self.id}, Load: {self.warehouse_loads})"


class Dock:
    def __init__(self, dock_id, efficiency):
        self.id = dock_id
        self.efficiency = efficiency

    def __str__(self):
        return f"Dock(ID: {self.id}, Efficiency: {self.efficiency})"


class Warehouse:
    def __init__(self, warehouse_id, docks):
        self.id = warehouse_id
        self.docks = docks

    def __str__(self):
        return f"Warehouse(ID: {self.id}, Docks: {[str(dock) for dock in self.docks]})"


def create_lp_model(orders, warehouses):
    model = LpProblem("Vehicle_Scheduling_with_Queue", LpMinimize)

    # 月台分配决策变量
    owd = LpVariable.dicts("OrderWarehouseDock",
                           [(o.id, w.id, d.id) for o in orders for w in warehouses for d in w.docks],
                           cat='Binary')

    # 排队位置变量
    queue_position = LpVariable.dicts("Queue_Position",
                                      [(o.id, w.id, d.id) for o in orders for w in warehouses for d in w.docks],
                                      lowBound=0, cat=LpInteger)

    # 最迟完成时间变量
    latest_completion_time = LpVariable("Latest_Completion_Time", lowBound=0, cat=LpInteger)

    # 目标函数：最小化最迟的订单完成时间
    model += latest_completion_time

    # 装货时间约束
    for warehouse in warehouses:
        for dock in warehouse.docks:
            dock_completion_time = LpVariable(f"DockCompletionTime_{warehouse.id}_{dock.id}", lowBound=0, cat=LpInteger)
            model += dock_completion_time <= latest_completion_time  # 最迟完成时间为最长的一条月台队列完成的时间
            total_load = pulp.lpSum(order.warehouse_loads[warehouse.id] * owd[order.id, warehouse.id, dock.id]
                                    for order in orders if order.warehouse_loads[warehouse.id] > 0)  # 每个仓库的月台队列 总载货量
            model += dock_completion_time >= total_load / dock.efficiency  # 月台完成时间为总载货量/该月台效率

    # 确保每个订单在所有装货量非零的仓库中只选择一个月台
    for order in orders:
        for warehouse in warehouses:
            if order.warehouse_loads[warehouse.id] > 0:
                model += pulp.lpSum(owd[order.id, warehouse.id, dock.id] for dock in warehouse.docks) == 1

    # 排队顺序约束： 不会出现多个相同的q_od在同一月台位置
    for warehouse in warehouses:
        for dock in warehouse.docks:
            for o1 in orders:
                for o2 in orders:
                    if o1.id != o2.id and owd[o1.id, warehouse.id, dock.id] == owd[o2.id, warehouse.id, dock.id]:
                        model += (queue_position[o1.id, warehouse.id, dock.id] != queue_position[
                                     o2.id, warehouse.id, dock.id])

    return model
    #  有的仓库可能load为0
    #  检查逻辑
    #  解析函数
    # TODO 月台排队顺序 - 2阶段
    # TODO 仓库顺序 - 2阶段后
    # TODO 运单优先级约束 - 2阶段
    # TODO 生成方案之前，已经有月台正在排队的情况。


def create_queue_model(orders, warehouses, order_dock_assignments):
    model = LpProblem("Queue_Optimization", LpMinimize)

    # 变量定义
    queue_positions = LpVariable.dicts("Queue_Position",
                                       [(order.id, warehouse.id, dock.id) for order in orders for warehouse in
                                        warehouses for dock in warehouse.docks],
                                       lowBound=0, cat=LpInteger)

    # 目标函数：暂定为最小化总排队位置
    model += lpSum(
        queue_positions[order.id, warehouse.id, dock.id] for order in orders for warehouse in warehouses for dock in
        warehouse.docks)

    # 排队位置约束
    for warehouse in warehouses:
        for dock in warehouse.docks:
            # 根据优先级排序
            orders_in_dock = [order for order in orders if order_dock_assignments[order.id][warehouse.id] == dock.id]
            orders_in_dock.sort(key=lambda order: order.priority, reverse=True)

            for i in range(len(orders_in_dock)):
                for j in range(i + 1, len(orders_in_dock)):
                    # 确保具有更高优先级的订单排在前面
                    model += queue_positions[orders_in_dock[i].id, warehouse.id, dock.id] < queue_positions[
                        orders_in_dock[j].id, warehouse.id, dock.id]

    # 求解模型
    model.solve()

    # 解析结果
    queue_order = {}
    for warehouse in warehouses:
        queue_order[warehouse.id] = {}
        for dock in warehouse.docks:
            queue_order[warehouse.id][dock.id] = sorted(
                [(order.id, value(queue_positions[order.id, warehouse.id, dock.id])) for order in orders],
                key=lambda x: x[1])

    return queue_order


def parse_optimization_result(model, orders, warehouses):
    # 获取决策变量的值
    vars_dict = model.variablesDict()

    # 解析月台分配
    order_dock_assignments = {}
    order_queue_positions = {}
    for order in orders:
        for warehouse in warehouses:
            for dock in warehouse.docks:
                owd_var = f"OrderWarehouseDock_({order.id},_{warehouse.id},_{dock.id})"
                queue_pos_var = f"Queue_Position_({order.id},_{warehouse.id},_{dock.id})"
                if owd_var in vars_dict and pulp.value(vars_dict[owd_var]) == 1:
                    if order.id not in order_dock_assignments:
                        order_dock_assignments[order.id] = {}
                    order_dock_assignments[order.id][warehouse.id] = dock.id
                    # 仅当订单被分配到该月台时，获取其排队位置
                    order_queue_positions.setdefault(order.id, {})[warehouse.id] = pulp.value(
                        vars_dict.get(queue_pos_var, 0))

    # 解析最迟完成时间
    latest_completion_time = pulp.value(vars_dict["Latest_Completion_Time"])

    return order_dock_assignments, order_queue_positions, latest_completion_time


def generate_test_data(num_orders, num_docks_per_warehouse, num_warehouses):
    # 生成仓库
    warehouses = [Warehouse(warehouse_id=i, docks=[]) for i in range(num_warehouses)]

    # 为每个仓库生成月台并赋予独立的效率
    for warehouse in warehouses:
        warehouse.docks = [Dock(dock_id=i, efficiency=random.uniform(0.5, 1.5))
                           for i in range(num_docks_per_warehouse)]

    # 生成订单
    orders = [Order(order_id=i,
                    warehouse_loads=[random.randint(10, 50) for _ in range(num_warehouses)],
                    priority=random.randint(1, 10))  # 假设优先级范围为 1 到 10
              for i in range(num_orders)]

    return orders, warehouses


def main():
    orders, warehouses = generate_test_data(num_orders=10, num_docks_per_warehouse=4, num_warehouses=4)
    # 打印订单信息
    for order in orders:
        print(order)

    # 打印仓库信息
    for warehouse in warehouses:
        print(warehouse)

    model = create_lp_model(orders, warehouses)
    model.solve()

    order_dock_assignments, order_queue_positions, latest_completion_time = parse_optimization_result(model, orders,
                                                                                                      warehouses)
    print("Order Dock Assignments:", order_dock_assignments)
    print("Order Queue Positions:", order_queue_positions)
    print("Latest Completion Time:", latest_completion_time)
    visualize_queue_by_docks_colored(order_dock_assignments, order_queue_positions, warehouses, num_orders=10)


if __name__ == "__main__":
    main()
