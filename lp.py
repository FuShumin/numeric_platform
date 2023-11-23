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
        return f"Order(ID: {self.id}, Load: {self.warehouse_loads}, Priority:{self.priority})"


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

    # 按序订单的时间约束
    for order_id in specific_order_route:
        expected_route = specific_order_route[order_id]
        for i in range(1, len(expected_route)):
            prev_warehouse = expected_route[i - 1]
            curr_warehouse = expected_route[i]
            assigned_dock = order_dock_assignments[order_id][prev_warehouse]
            model += end_times[order_id, prev_warehouse, assigned_dock] <= start_times[
                order_id, curr_warehouse, order_dock_assignments[order_id][curr_warehouse]]

    # 对于每个订单，确保在任何给定时间只在一个月台上作业，但是非按序订单还没有优化排序 改这个
    M = 100000
    for order in orders:
        assigned_docks = [(w_id, d_id) for w_id, d_id in order_dock_assignments[order.id].items()]

        for i in range(len(assigned_docks)):
            w_id1, d_id1 = assigned_docks[i]
            for j in range(i + 1, len(assigned_docks)):
                w_id2, d_id2 = assigned_docks[j]

                # 引入辅助二元变量，表示订单在两个月台中的先后顺序
                before = LpVariable(f"Order_{order.id}_Dock_{w_id1}_{d_id1}_Before_Dock_{w_id2}_{d_id2}", 0, 1,
                                    LpInteger)

                '''
                添加约束，确保两个月台作业的时间不重叠， 
                大M方法：几乎总是成立的约束将变得不具有约束性。
                如果before=1，则下面的约束不具有约束性，第一个作业在第二个作业之前完成
                如果before=0，则上面的约束不具有约束性，同时保证第二个作业在第一个作业之前完成
                '''
                model += end_times[order.id, w_id1, d_id1] <= start_times[order.id, w_id2, d_id2] + (1 - before) * M
                model += end_times[order.id, w_id2, d_id2] <= start_times[order.id, w_id1, d_id1] + before * M

    return model


def parse_queue_results(model, orders, warehouses):
    # Retrieve decision variables
    start_times_values = {}
    end_times_values = {}
    vars_dict = model.variablesDict()

    for order in orders:
        for warehouse in warehouses:
            for dock in warehouse.docks:
                # Variable names as defined in the model
                start_var_name = f"Start_Time_({order.id},_{warehouse.id},_{dock.id})"
                end_var_name = f"End_Time_({order.id},_{warehouse.id},_{dock.id})"

                # Retrieve and store the values of the variables
                if start_var_name in vars_dict:
                    start_times_values[(order.id, warehouse.id, dock.id)] = vars_dict[start_var_name].varValue
                if end_var_name in vars_dict:
                    end_times_values[(order.id, warehouse.id, dock.id)] = vars_dict[end_var_name].varValue

    return start_times_values, end_times_values


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
                    sequential=random.choice([True, False]))  # 假设优先级范围为 1 到 10
              for i in range(num_orders)]

    return orders, warehouses


def parse_order_sequence_and_queue(start_times, end_times):
    # 初始化存储结构
    order_sequences = {}
    dock_queues = {}

    # 解析每个订单的仓库顺序
    for (order_id, warehouse_id, dock_id), start_time in start_times.items():
        if order_id not in order_sequences:
            order_sequences[order_id] = []
        order_sequences[order_id].append((warehouse_id, start_time, end_times[(order_id, warehouse_id, dock_id)]))

    # 对每个订单的仓库访问顺序按开始时间进行排序
    for order_id in order_sequences:
        order_sequences[order_id].sort(key=lambda x: x[1])

    # 解析每个月台的排队顺序
    for (order_id, warehouse_id, dock_id), start_time in start_times.items():
        if dock_id not in dock_queues:
            dock_queues[dock_id] = []
        dock_queues[dock_id].append((order_id, start_time, end_times[(order_id, warehouse_id, dock_id)]))

    # 对每个月台的排队顺序按开始时间进行排序
    for dock_id in dock_queues:
        dock_queues[dock_id].sort(key=lambda x: x[1])

    return order_sequences, dock_queues


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
    vars_dict = queue_model.variablesDict()
    start_times, end_times = parse_queue_results(queue_model, orders, warehouses)
    # 显示排队结果
    print("Start Times:", start_times)
    print("End Times:", end_times)
    plot_order_times_on_docks(start_times, end_times)

    # order_sequences, dock_queues = parse_order_sequence_and_queue(start_times, end_times)
    #
    # # 打印每个订单的仓库顺序
    # for order_id in order_sequences:
    #     print(f"Order {order_id}:")
    #     for warehouse_id, start, end in order_sequences[order_id]:
    #         print(f"  Warehouse {warehouse_id}: Start at {start}, End at {end}")
    #
    # # 打印每个月台上的排队顺序
    # for dock_id in dock_queues:
    #     print(f"Dock {dock_id}:")
    #     for order_id, start, end in dock_queues[dock_id]:
    #         print(f"  Order {order_id}: Start at {start}, End at {end}")


if __name__ == "__main__":
    main()
