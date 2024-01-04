from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpContinuous, LpInteger, value
from visualization import *
from common import *


def create_lp_model(orders, warehouses, total_busy_time=None):
    model = LpProblem("Vehicle_Scheduling_with_Queue", LpMinimize)
    if total_busy_time is None:
        total_busy_time = {}
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
            dock_key = (warehouse.id, dock.id)
            dock_completion_time = LpVariable(f"DockCompletionTime_{warehouse.id}_{dock.id}", lowBound=0, cat=LpInteger)
            model += dock_completion_time <= latest_completion_time  # 最迟完成时间为最长的一条月台队列完成的时间
            existing_dock_queueingTime = total_busy_time.get(dock_key, 0)
            # 每个仓库的月台队列 总载货量
            total_load = pulp.lpSum(
                next((load['load'] for load in order.warehouse_loads if load['warehouse_id'] == warehouse.id), 0) * owd[
                    order.id, warehouse.id, dock.id]
                for order in orders if
                order.warehouse_loads and any(load['warehouse_id'] == warehouse.id for load in order.warehouse_loads)
            )
            model += dock_completion_time >= total_load / dock.efficiency + existing_dock_queueingTime
            # 月台完成时间为总载货量/该月台效率

    # 确保每个订单在所有装货量非零的仓库中只选择一个月台
    for order in orders:
        for warehouse in warehouses:
            # 寻找与当前仓库匹配的 load 值
            load_for_warehouse = next(
                (load['load'] for load in order.warehouse_loads if load['warehouse_id'] == warehouse.id), 0)

            # 如果找到的 load 值大于 0，添加约束
            if load_for_warehouse > 0:
                model += pulp.lpSum(owd[order.id, warehouse.id, dock.id] for dock in warehouse.docks) == 1
            else:
                model += pulp.lpSum(owd[order.id, warehouse.id, dock.id] for dock in warehouse.docks) == 0

            for dock in warehouse.docks:
                if order.required_carriage not in dock.compatible_carriage:
                    model += owd[order.id, warehouse.id, dock.id] == 0

    return model
    #  检查逻辑
    #  解析函数
    #  按序路线


def generate_specific_order_route(orders):
    specific_order_route = {}

    for order in orders:
        if order.sequential:
            # 获取订单中仓库负载的仓库ID，并按照出现的顺序创建路径
            route = [load['warehouse_id'] for load in order.warehouse_loads]
            specific_order_route[order.id] = route

    return specific_order_route

    # 仓库是否按序 【测试】
    # 月台排队顺序 - 2阶段
    #  解析提取仓库顺序，月台排队顺序
    # 运单优先级约束 - 2阶段
    #  生成方案之前，已经有月台正在排队的情况，增量调度更新


def create_queue_model(orders, warehouses, order_dock_assignments, specific_order_route, busy_windows=None):
    if busy_windows is None:
        busy_windows = {}
    M = 100000
    model = LpProblem("Queue_Optimization", LpMinimize)
    fixed_cost = 6  # 驶入驶离固定耗时4+2分钟
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
            # 列出所有的在这个仓库-月台上的订单
            orders_in_dock = [order for order in orders if order.id in order_dock_assignments and warehouse.id in order_dock_assignments[order.id] and order_dock_assignments[order.id][warehouse.id] == dock.id]
            orders_in_dock.sort(key=lambda order: order.priority, reverse=True)  # 给每个月台列的订单排出一个优先级。

            for i in range(len(orders_in_dock)):
                order = orders_in_dock[i]
                processing_time = fixed_cost + next((load['load'] for load in order.warehouse_loads if load['warehouse_id'] == warehouse.id), 0) / (dock.efficiency+0.0000001)
                # TODO 加权
                model += end_times[order.id, warehouse.id, dock.id] == start_times[
                    order.id, warehouse.id, dock.id] + processing_time
                model += end_times[order.id, warehouse.id, dock.id] <= latest_end_time  # 最迟完成时间

                # 优先级约束：优先级高的订单先完成 结束时间<=下一个优先级排序订单的开始时间
                if i < len(orders_in_dock) - 1:
                    next_order = orders_in_dock[i + 1]
                    if order.priority != next_order.priority:
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

    # 【约束】对于每个非按序订单，确保在任何给定时间只在一个月台上作业
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

    # 【约束】订单作业窗口不与已存在的忙碌时间窗口重叠
    for order in orders:
        for warehouse in warehouses:
            load_for_warehouse = next(
                (load['load'] for load in order.warehouse_loads if load['warehouse_id'] == warehouse.id), 0)
            if load_for_warehouse > 0:
                dock_id = order_dock_assignments[order.id][warehouse.id]
                dock_key = (warehouse.id, dock_id)
                existing_windows = busy_windows.get(dock_key, [])

                # 对于每个忙碌时间窗口，添加不重叠的约束
                for idx, (busy_start, busy_end) in enumerate(existing_windows):
                    # 为每个忙碌时间窗口创建一个唯一的overlap辅助决策变量
                    overlap = LpVariable(f"Overlap_{order.id}_{warehouse.id}_{dock_id}_{idx}", 0, 1, LpInteger)

                    # 添加不与忙碌时间窗口重叠的约束
                    model += end_times[order.id, warehouse.id, dock_id] <= busy_start + (1 - overlap) * M
                    model += busy_end <= start_times[order.id, warehouse.id, dock_id] + overlap * M

    return model


def main():
    orders, warehouses = generate_test_data(num_orders=10, num_docks_per_warehouse=4, num_warehouses=4)
    specific_order_route = generate_specific_order_route(orders)

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
    start_times, end_times = parse_queue_results(queue_model, orders, warehouses)
    # 显示排队结果
    print("Start Times:", start_times)
    print("End Times:", end_times)
    # 可视化绘制
    plot_order_times_on_docks(start_times, end_times)
    # 生成时间表
    schedule = generate_schedule(start_times, end_times)
    print(schedule)
    # 保存时间表到文件
    filename = "test_schedule.csv"
    save_schedule_to_file(schedule, filename)
    # 从文件加载时间表
    loaded_schedule = load_schedule_from_file(filename)


if __name__ == "__main__":
    main()
