import random

import pandas as pd
import numpy as np
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpContinuous, LpInteger, value
import pulp
from visualization import *


class Order:
    def __init__(self, order_id, warehouse_loads, priority, sequential):
        self.id = order_id
        self.warehouse_loads = warehouse_loads
        self.priority = priority
        self.sequential = sequential

    def __str__(self):
        return f"Order(ID: {self.id}, Load: {self.warehouse_loads}, Priority:{self.priority}, Sequential:{self.sequential})"


class Dock:
    def __init__(self, dock_id, efficiency, weight):
        self.id = dock_id
        self.efficiency = efficiency
        self.weight = weight

    def __str__(self):
        return f"Dock(ID: {self.id}, Efficiency: {self.efficiency}, Weight:{self.weight})"


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

    # 最迟完成时间变量（不考虑顺序的压缩时间量）
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

    return model
    #  有的仓库可能load为0
    #  检查逻辑
    #  解析函数
    #  按序路线


def generate_specific_order_route(orders, warehouses):
    specific_order_route = {}

    for order in orders:
        if order.sequential:
            route = []
            for warehouse in sorted(warehouses, key=lambda w: w.id):
                route.append(warehouse.id)
            specific_order_route[order.id] = route

    return specific_order_route
    # TODO 载货量为0的仓库去除 【测试】
    # TODO 仓库是否按序 【测试】
    # 月台排队顺序 - 2阶段
    # TODO 提取仓库顺序，月台排队顺序 - 2阶段后
    # 运单优先级约束 - 2阶段
    # TODO 生成方案之前，已经有月台正在排队的情况。增量设计


def create_queue_model(orders, warehouses, order_dock_assignments, specific_order_route):
    model = LpProblem("Queue_Optimization", LpMinimize)

    # 定义开始时间和结束时间变量
    start_times = LpVariable.dicts("Start_Time",
                                   [(order.id, warehouse.id, dock.id) for order in orders for warehouse in warehouses
                                    for dock in warehouse.docks],
                                   lowBound=0, cat=LpContinuous)

    end_times = LpVariable.dicts("End_Time",
                                 [(order.id, warehouse.id, dock.id) for order in orders for warehouse in warehouses for
                                  dock in warehouse.docks],
                                 lowBound=0, cat=LpContinuous)

    # 目标函数：最小化最迟订单的结束时间
    latest_end_time = LpVariable("Latest_End_Time", lowBound=0, cat=LpContinuous)
    model += latest_end_time

    # 添加决策变量：每个非按序订单在每个仓库的访问顺序
    visit_order = LpVariable.dicts("Visit_Order",
                                   [(order.id, w.id) for order in orders if order.id not in specific_order_route for w
                                    in warehouses],
                                   lowBound=0, cat=LpInteger)

    # 仓库路线约束
    for order in orders:
        if order.id not in specific_order_route:
            # 获取订单里的仓库个数
            assigned_warehouses = list(order_dock_assignments[order.id].keys())
            num_warehouses = len(assigned_warehouses)

            # 确保访问顺序是连续的且不重复
            model += lpSum(visit_order[(order.id, w.id)] for w in warehouses if w.id in assigned_warehouses) == sum(
                range(num_warehouses))
            for pos in range(num_warehouses):
                model += lpSum(
                    visit_order[(order.id, w.id)] == pos for w in warehouses if w.id in assigned_warehouses) == 1

            # 添加约束以确保访问顺序与时间安排一致
            for i in range(num_warehouses):
                for j in range(i + 1, num_warehouses):
                    w_id1 = assigned_warehouses[i]
                    w_id2 = assigned_warehouses[j]
                    dock_id1 = order_dock_assignments[order.id][w_id1]
                    dock_id2 = order_dock_assignments[order.id][w_id2]
                    model += start_times[order.id, w_id2, dock_id2] >= end_times[order.id, w_id1, dock_id1] + (
                            visit_order[(order.id, w_id2)] - visit_order[(order.id, w_id1)] - 1) * 5
        else:
            # 按序订单的仓库路线约束
            expected_route = specific_order_route[order.id]
            for i in range(1, len(expected_route)):
                prev_warehouse = expected_route[i - 1]
                curr_warehouse = expected_route[i]
                assigned_dock = order_dock_assignments[order.id][prev_warehouse]
                model += end_times[order.id, prev_warehouse, assigned_dock] <= start_times[
                    order.id, curr_warehouse, order_dock_assignments[order.id][curr_warehouse]]

    # 约束条件 首先排序订单优先级。
    for warehouse in warehouses:
        for dock in warehouse.docks:
            orders_in_dock = [order for order in orders if order_dock_assignments[order.id][warehouse.id] == dock.id]
            orders_in_dock.sort(key=lambda order: order.priority, reverse=True)  # 每个月台列的订单排出一个优先级。

            for i in range(len(orders_in_dock)):
                order = orders_in_dock[i]
                processing_time = order.warehouse_loads[warehouse.id] / dock.efficiency  # TODO 加权
                model += end_times[order.id, warehouse.id, dock.id] == start_times[
                    order.id, warehouse.id, dock.id] + processing_time
                model += end_times[order.id, warehouse.id, dock.id] <= latest_end_time  # 最迟完成时间

                # 优先级约束：优先级高的订单先完成 结束时间<=下一个优先级排序订单的开始时间
                if i < len(orders_in_dock) - 1:
                    next_order = orders_in_dock[i + 1]
                    model += end_times[order.id, warehouse.id, dock.id] <= start_times[
                        next_order.id, warehouse.id, dock.id]

            # 同一时间同一月台仅一个订单
            for i in range(len(orders_in_dock)):
                for j in range(i + 1, len(orders_in_dock)):
                    model += end_times[orders_in_dock[i].id, warehouse.id, dock.id] <= start_times[
                        orders_in_dock[j].id, warehouse.id, dock.id]

    return model


def parse_queue_results(model, orders, warehouses, order_dock_assignments, specific_order_route):
    start_times_values = {}
    end_times_values = {}
    order_routes = {}
    vars_dict = model.variablesDict()

    # 解析开始和结束时间
    for order in orders:
        for warehouse in warehouses:
            for dock in warehouse.docks:
                start_var_name = f"Start_Time_({order.id},_{warehouse.id},_{dock.id})"
                end_var_name = f"End_Time_({order.id},_{warehouse.id},_{dock.id})"

                if start_var_name in vars_dict:
                    start_times_values[(order.id, warehouse.id, dock.id)] = vars_dict[start_var_name].varValue
                if end_var_name in vars_dict:
                    end_times_values[(order.id, warehouse.id, dock.id)] = vars_dict[end_var_name].varValue

    # 解析仓库路线
    for order in orders:
        if order.id in specific_order_route:
            # 按序订单使用特定的路线
            order_routes[order.id] = specific_order_route[order.id]
        else:
            # 非按序订单根据 visit_order 变量确定路线
            visit_order_values = {w_id: vars_dict[f"Visit_Order_({order.id},_{w_id})"].varValue for w_id in
                                  order_dock_assignments[order.id]}
            sorted_warehouses = sorted(visit_order_values, key=visit_order_values.get)
            order_routes[order.id] = sorted_warehouses

    return start_times_values, end_times_values, order_routes


def parse_optimization_result(model, orders, warehouses):
    # 获取决策变量的值
    vars_dict = model.variablesDict()

    # 解析月台分配
    order_dock_assignments = {}
    for order in orders:
        for warehouse in warehouses:
            for dock in warehouse.docks:
                owd_var = f"OrderWarehouseDock_({order.id},_{warehouse.id},_{dock.id})"
                if owd_var in vars_dict and pulp.value(vars_dict[owd_var]) == 1:
                    if order.id not in order_dock_assignments:
                        order_dock_assignments[order.id] = {}
                    order_dock_assignments[order.id][warehouse.id] = dock.id

    # 解析最迟完成时间
    latest_completion_time = pulp.value(vars_dict["Latest_Completion_Time"])

    return order_dock_assignments, latest_completion_time


def generate_test_data(num_orders, num_docks_per_warehouse, num_warehouses):
    # 生成仓库
    warehouses = [Warehouse(warehouse_id=i, docks=[]) for i in range(num_warehouses)]

    # 为每个仓库生成月台并赋予独立的效率
    for warehouse in warehouses:
        warehouse.docks = [Dock(dock_id=i, efficiency=random.uniform(0.5, 1.5), weight=random.randint(0, 3))
                           for i in range(num_docks_per_warehouse)]

    # 生成订单
    orders = [Order(order_id=i,
                    warehouse_loads=[random.randint(10, 50) for _ in range(num_warehouses)],
                    priority=random.randint(1, 1),
                    sequential=random.choice([True, False]))
              for i in range(num_orders)]

    return orders, warehouses


def main():
    orders, warehouses = generate_test_data(num_orders=10, num_docks_per_warehouse=4, num_warehouses=4)
    specific_order_route = generate_specific_order_route(orders, warehouses)

    # 打印订单信息
    for order in orders:
        print(order)

    # 打印仓库信息
    for warehouse in warehouses:
        print(warehouse)

    model = create_lp_model(orders, warehouses)
    model.solve()

    order_dock_assignments, latest_completion_time = parse_optimization_result(model, orders, warehouses)
    print("Order Dock Assignments:", order_dock_assignments)
    print("Latest Completion Time:", latest_completion_time)
    queue_model = create_queue_model(orders, warehouses, order_dock_assignments, specific_order_route)
    queue_model.solve()
    start_times, end_times, order_routes = parse_queue_results(queue_model, orders, warehouses, order_dock_assignments,
                                                               specific_order_route)
    # 显示排队结果
    print("Start Times:", start_times)
    print("End Times:", end_times)
    print("order_routes", order_routes)
    plot_order_times_on_docks(start_times, end_times)


if __name__ == "__main__":
    main()
