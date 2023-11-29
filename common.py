import pulp
import random
import pandas as pd
from datetime import datetime, timedelta


class Order:
    def __init__(self, order_id, warehouse_loads, priority, sequential, required_carriage, order_type):
        self.id = order_id
        self.warehouse_loads = warehouse_loads  # 字典，键为仓库 ID，值为负载
        self.priority = priority
        self.sequential = sequential
        self.required_carriage = required_carriage
        self.order_type = order_type

    def __str__(self):
        return f"Order(ID: {self.id}, Load: {self.warehouse_loads}, Priority:{self.priority}, Carriage: {self.required_carriage}, Type: {self.order_type}, Sequential:{self.sequential})"


class Dock:
    def __init__(self, dock_id, outbound_efficiency, inbound_efficiency, weight, dock_type, compatible_carriage):
        self.id = dock_id
        self.outbound_efficiency = outbound_efficiency
        self.inbound_efficiency = inbound_efficiency
        self.efficiency = None
        self.weight = weight
        self.dock_type = dock_type
        self.compatible_carriage = compatible_carriage

    def set_efficiency(self, order_type):
        if order_type == "装车" or self.dock_type == "通用":
            self.efficiency = self.outbound_efficiency
        elif order_type == "卸车" or self.dock_type == "通用":
            self.efficiency = self.inbound_efficiency

    def __str__(self):
        return f"Dock(ID: {self.id}, Outbound Efficiency: {self.outbound_efficiency}, Inbound Efficiency: {self.inbound_efficiency}, Efficiency: {self.efficiency}, Weight: {self.weight}, Type: {self.dock_type}, Compatible Carriage: {self.compatible_carriage})"


# for dock in docks:
#     dock.set_efficiency(order_type)

class Warehouse:
    def __init__(self, warehouse_id, docks):
        self.id = warehouse_id
        self.docks = docks

    def __str__(self):
        return f"Warehouse(ID: {self.id}, Docks: {[str(dock) for dock in self.docks]})"


def parse_queue_results(model, orders, warehouses):
    # 获取模型的决策变量
    start_times_values = {}
    end_times_values = {}
    vars_dict = model.variablesDict()

    for order in orders:
        for warehouse in warehouses:
            for dock in warehouse.docks:
                # 用模型里同样的名字定义
                start_var_name = f"Start_Time_({order.id},_{warehouse.id},_{dock.id})"
                end_var_name = f"End_Time_({order.id},_{warehouse.id},_{dock.id})"

                # 获取并储存决策变量的值
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


def save_schedule_to_file(schedule, filename="test_schedule.csv"):
    def load_existing_schedule():
        try:
            return pd.read_csv(filename)
        except FileNotFoundError:
            return pd.DataFrame(columns=["Order ID", "Warehouse ID", "Dock ID", "Start Time", "End Time"])

    def filter_old_data(df):
        # 获取7天前的日期时间
        cutoff_date = datetime.now() - timedelta(days=7)

        # 将 'End Time' 列从字符串转换为 datetime
        df['End Time'] = pd.to_datetime(df['End Time'])

        # 保留结束时间在7天内的数据
        return df[df['End Time'] >= cutoff_date]

    existing_schedule = load_existing_schedule()
    existing_schedule['Start Time'] = pd.to_datetime(existing_schedule['Start Time'])
    existing_schedule['End Time'] = pd.to_datetime(existing_schedule['End Time'])

    # 合并现有和新的调度数据
    updated_schedule = pd.concat([existing_schedule, schedule], ignore_index=True)

    # 去除重复项
    updated_schedule.drop_duplicates(subset=["Order ID", "Warehouse ID", "Dock ID", "Start Time", "End Time"],
                                     inplace=True)
    # 清理7天以上的旧数据
    updated_schedule = filter_old_data(updated_schedule)
    # 保存到 CSV 文件
    updated_schedule.to_csv(filename, index=False)


def load_and_prepare_schedule(filename):
    """
    加载调度文件，并准备数据以便后续处理。

    :param filename: 调度数据的文件名。
    :return: 准备好的 DataFrame。
    """
    try:
        loaded_schedule = pd.read_csv(filename)

        # 获取当前时间的时间戳
        current_timestamp = datetime.now().timestamp()

        # 将 'End Time' 转换为时间戳并剔除过去的时间段
        loaded_schedule['End Time'] = loaded_schedule['End Time'].apply(convert_str_to_timestamp)
        loaded_schedule = loaded_schedule[loaded_schedule['End Time'] > current_timestamp]

        # 转换时间为模型可用的分钟格式
        loaded_schedule['Start Time'] = loaded_schedule['Start Time'].apply(convert_to_model_format)
        loaded_schedule['End Time'] = loaded_schedule['End Time'].apply(timestamp_to_str)
        loaded_schedule['End Time'] = loaded_schedule['End Time'].apply(convert_to_model_format)

        # 检查负数的 start_time 设为 0
        loaded_schedule['Start Time'] = loaded_schedule['Start Time'].apply(lambda x: max(x, 0))

        return loaded_schedule

    except FileNotFoundError:
        # 如果文件不存在，返回一个空的 DataFrame
        return pd.DataFrame(columns=["Order ID", "Warehouse ID", "Dock ID", "Start Time", "End Time"])


def generate_schedule(start_times, end_times):
    """
    从开始和结束时间生成一个日程表。

    :param start_times: 开始时间的字典，键是（订单ID，仓库ID，装卸口ID）。
    :param end_times: 结束时间的字典，键是（订单ID，仓库ID，装卸口ID）。
    :return: 包含日程表信息的DataFrame。
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

    # 字典列表转化为 DataFrame
    schedule_df = pd.DataFrame(schedule_data)
    # 应用时间格式转换
    schedule_df['Start Time'] = schedule_df['Start Time'].apply(convert_to_readable_format)
    schedule_df['End Time'] = schedule_df['End Time'].apply(convert_to_readable_format)
    return schedule_df


def load_schedule_from_file(filename):
    """
    从文件加载日程表。
    :param filename: 加载日程表的文件名。
    :return: DataFrame格式的日程表数据。
    """
    if filename.endswith('.csv'):
        return pd.read_csv(filename)
    elif filename.endswith('.json'):
        return pd.read_json(filename, orient='records', lines=True)
    else:
        raise ValueError("Unsupported file format. Please use .csv or .json")


def calculate_busy_times_and_windows(loaded_schedule, warehouses):
    """
    计算每个装卸口的总繁忙时间和繁忙时间窗口。

    :param loaded_schedule: 包含日程表数据的DataFrame。
    :param warehouses: 仓库对象列表。
    :return: 两个字典组成的元组 - 一个是每个装卸口的总繁忙时间，另一个是繁忙时间窗口。
    """
    total_busy_time = {}
    busy_windows = {}
    for warehouse in warehouses:
        for dock in warehouse.docks:
            dock_key = (warehouse.id, dock.id)
            # Filter busy slots for the specific warehouse and dock
            busy_slots = loaded_schedule[(loaded_schedule['Warehouse ID'] == warehouse.id) &
                                         (loaded_schedule['Dock ID'] == dock.id)]
            busy_slots = list(zip(busy_slots['Start Time'], busy_slots['End Time']))

            # Calculate total busy time for the dock
            total_busy = sum(end - start for start, end in busy_slots)
            total_busy_time[dock_key] = total_busy

            # Store busy windows
            busy_windows[dock_key] = busy_slots

    return total_busy_time, busy_windows


def convert_to_readable_format(minutes):
    """
    将从现在开始的分钟数转换为可读的日期时间格式。

    :param minutes: 当前时间起的分钟数。
    :return: 格式为'YYYY-MM-DD HH:MM:SS'的可读日期时间字符串。
    """
    current_time = datetime.now()
    future_time = current_time + timedelta(minutes=minutes)
    return future_time.strftime('%Y-%m-%d %H:%M:%S')


def convert_str_to_timestamp(time_str):
    """
    将日期时间字符串转换为时间戳。

    :param time_str: 格式为'YYYY-MM-DD HH:MM:SS'的日期时间字符串。
    :return: 对应的时间戳。
    """
    return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').timestamp()


def timestamp_to_str(timestamp):
    """
    将时间戳转换为可读的日期时间字符串。

    :param timestamp: 时间戳。
    :return: 格式为'YYYY-MM-DD HH:MM:SS'的日期时间字符串。
    """
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def convert_to_model_format(date_time_str):
    """
    将可读的日期时间字符串转换为从当前时间起的分钟数。

    :param date_time_str: 格式为'YYYY-MM-DD HH:MM:SS'的可读日期时间字符串。
    :return: 从当前时间起的分钟数。
    """
    if not isinstance(date_time_str, str):
        raise ValueError("Expected a string in the format 'YYYY-MM-DD HH:MM:SS', got: {}".format(date_time_str))

    try:
        parsed_time = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        return (parsed_time - current_time).total_seconds() / 60
    except ValueError as e:
        raise ValueError("Error parsing date-time string: {}. Error: {}".format(date_time_str, e))


def main():
    orders, warehouses = generate_test_data(num_orders=10, num_docks_per_warehouse=4, num_warehouses=4)
    schedule = generate_schedule(start_times, end_times)
    filename = "test_schedule.csv"
    save_schedule_to_file(schedule, filename)

    loaded_schedule = load_and_prepare_schedule(filename)

    # 查找每个月台已占用的忙碌时间窗口
    existing_busy_time, busy_slots = calculate_busy_times_and_windows(loaded_schedule, warehouses)

    model = create_lp_model(orders, warehouses, existing_busy_time)
    model.solve()

    order_dock_assignments, latest_completion_time = parse_optimization_result(model, orders, warehouses)
    queue_model = create_queue_model(orders, warehouses, order_dock_assignments, specific_order_route, busy_slots)
    queue_model.solve()
    start_times, end_times = parse_queue_results(queue_model, orders, warehouses)
    plot_order_times_on_docks(start_times, end_times, busy_slots)
    schedule_new = generate_schedule(start_times, end_times)
    schedule_new['Start Time'] = schedule_new['Start Time'].apply(convert_to_readable_format)
    schedule_new['End Time'] = schedule_new['End Time'].apply(convert_to_readable_format)
    save_schedule_to_file(schedule_new, "test_schedule.csv")


if __name__ == "__main__":
    main()
