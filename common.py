import pulp
import random
import pandas as pd


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


def save_schedule_to_file(schedule, filename):
    """
    Saves the schedule to a file.
    :param schedule: Schedule data, either as a dictionary or DataFrame.
    :param filename: Name of the file to save the schedule.
    """
    # Convert to DataFrame if schedule is not already in that format
    if not isinstance(schedule, pd.DataFrame):
        schedule = pd.DataFrame(schedule)

    # Determine the format from filename extension
    if filename.endswith('.csv'):
        schedule.to_csv(filename, index=False)
    elif filename.endswith('.json'):
        schedule.to_json(filename, orient='records', lines=True)
    else:
        raise ValueError("Unsupported file format. Please use .csv or .json")


def generate_schedule(start_times, end_times):
    """
    Generates a schedule from the start and end times.

    :param start_times: Dictionary of start times, keys are (order ID, warehouse ID, dock ID).
    :param end_times: Dictionary of end times, keys are (order ID, warehouse ID, dock ID).
    :return: DataFrame with the schedule information.
    """
    schedule_data = []

    for key in start_times.keys():
        order_id, warehouse_id, dock_id = key
        start = start_times[key]
        end = end_times[key]
        schedule_data.append({
            "Order ID": order_id,
            "Warehouse ID": warehouse_id,
            "Dock ID": dock_id,
            "Start Time": start,
            "End Time": end
        })

    # Convert the list of dictionaries to a DataFrame
    schedule_df = pd.DataFrame(schedule_data)
    return schedule_df


def load_schedule_from_file(filename):
    """
    Loads the schedule from a file.
    :param filename: Name of the file to load the schedule from.
    :return: Schedule data as a DataFrame.
    """
    if filename.endswith('.csv'):
        return pd.read_csv(filename)
    elif filename.endswith('.json'):
        return pd.read_json(filename, orient='records', lines=True)
    else:
        raise ValueError("Unsupported file format. Please use .csv or .json")


def analyze_existing_schedule(start_times, end_times, warehouses):
    """
    Analyzes the existing schedule to find free time slots on each dock.

    :param start_times: Dictionary of start times.
    :param end_times: Dictionary of end times.
    :param warehouses: List of Warehouse objects.
    :return: Dictionary with free time slots for each dock.
    """
    free_slots = {}
    for warehouse in warehouses:
        for dock in warehouse.docks:
            dock_key = (warehouse.id, dock.id)
            busy_slots = [(start_times[(order_id, warehouse.id, dock.id)],
                           end_times[(order_id, warehouse.id, dock.id)])
                          for order_id in start_times if (order_id, warehouse.id, dock.id) in start_times]
            busy_slots.sort()  # Sort by start time
            free_slots[dock_key] = find_free_slots(busy_slots)
    return free_slots


def find_free_slots(busy_slots):
    """
    Finds free time slots based on busy slots.

    :param busy_slots: List of tuples representing busy time slots.
    :return: List of tuples representing free time slots.
    """
    free_slots = []
    end_of_last_busy_slot = 0
    for start, end in busy_slots:
        if start > end_of_last_busy_slot:
            free_slots.append((end_of_last_busy_slot, start))
        end_of_last_busy_slot = end
    # Assuming the dock operates in a fixed time range, e.g., 0-24 hours
    if end_of_last_busy_slot < 24:
        free_slots.append((end_of_last_busy_slot, 24))
    return free_slots
