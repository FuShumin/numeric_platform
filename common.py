import pulp
import random
import pandas as pd
from datetime import datetime, timedelta


class Order:
    def __init__(self, order_id, warehouse_loads, priority, sequential, required_carriage, order_type):
        self.id = order_id
        self.warehouse_loads = []
        for wl in warehouse_loads:
            if isinstance(wl, dict):
                # 检查并提取需要的字段
                warehouse_id = wl.get('warehouse_id')
                cargo_type = wl.get('item_code', None)  # 使用 item_code 作为 cargo_type
                quantity = wl.get('load', None)
                operation = wl.get('loadUnloadStatus', None)  # 使用 loadUnloadStatus 作为 operation

                # 如果字段完整，则创建 WarehouseLoad 对象
                if all([warehouse_id is not None, quantity is not None, operation is not None]):
                    self.warehouse_loads.append(WarehouseLoad(warehouse_id, cargo_type, quantity, operation))
                else:
                    # 否则，保持原样
                    self.warehouse_loads.append(wl)
            else:
                self.warehouse_loads.append(wl)
        self.priority = priority
        self.sequential = sequential
        self.required_carriage = required_carriage
        self.order_type = order_type

    def __str__(self):
        return f"Order(ID: {self.id}, Load: {self.warehouse_loads}, Priority:{self.priority}, Required Carriage: {self.required_carriage}, Type: {self.order_type}, Sequential:{self.sequential})"


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
        if order_type == 2 or self.dock_type == 3:     # 2=月台出库，车辆装货, 1=月台入库，车辆卸货
            self.efficiency = self.outbound_efficiency
        elif order_type == 1 or self.dock_type == 3:
            self.efficiency = self.inbound_efficiency

    def __str__(self):
        return f"Dock(ID: {self.id}, Outbound Efficiency: {self.outbound_efficiency}, Inbound Efficiency: {self.inbound_efficiency}, Efficiency: {self.efficiency}, Weight: {self.weight}, Type: {self.dock_type}, Compatible Carriage: {self.compatible_carriage})"


class WarehouseLoad:
    def __init__(self, warehouse_id, cargo_type, quantity, operation):
        self.warehouse_id = warehouse_id
        self.cargo_type = cargo_type
        self.quantity = quantity
        self.operation = operation  # 1='load' ；2 = 'unload'

    def __repr__(self):
        return f"WarehouseLoad({self.warehouse_id}, '{self.cargo_type}', {self.quantity}, '{self.operation}')"


class Warehouse:
    def __init__(self, warehouse_id, docks, location=None):
        self.id = warehouse_id
        self.docks = docks
        self.location = location

    def __str__(self):
        return f"Warehouse(ID: {self.id}, Docks: {[str(dock) for dock in self.docks]}, Location:{self.location})"


class Carriage:
    def __init__(self, carriage_id, location, carriage_type, carriage_state, current_dock_id,
                 current_warehouse_id=None):
        self.id = carriage_id
        self.location = location
        self.type = carriage_type
        self.state = carriage_state
        self.current_dock_id = current_dock_id
        self.current_warehouse_id = current_warehouse_id

    def __str__(self):
        return (f"Carriage(ID: {self.id}, Location: {self.location}, Type: {self.type}, "
                f"State: {self.state}, Current Dock ID: {self.current_dock_id}, Current Warehouse ID: {self.current_warehouse_id})")


class Vehicle:
    def __init__(self, vehicle_id, location, vehicle_state, vehicle_workload):
        self.id = vehicle_id
        self.location = location
        self.state = vehicle_state
        self.workload = vehicle_workload

    def __str__(self):
        return (f"Vehicle(ID: {self.id}, Location: {self.location}, State: {self.state}, "
                f"Workload: {self.workload})")


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
    updated_schedule.drop_duplicates(subset=["Order ID", "Warehouse ID", "Dock ID"],
                                     inplace=True)  # TODO 添加逻辑：应以最新的OWD为准，覆盖掉旧的
    # 清理7天以上的旧数据
    updated_schedule = filter_old_data(updated_schedule)
    # 保存到 CSV 文件
    updated_schedule.to_csv(filename, index=False)


def load_and_prepare_schedule(filename, orders):
    """
    加载调度文件，并准备数据以便后续处理。

    :param filename: 调度数据的文件名。
    :return: 准备好的 DataFrame。
    """

    def get_order_ids_from_orders(orders):
        return [order.id for order in orders]

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
        # 获取 orders 中的订单 ID 列表
        order_ids = get_order_ids_from_orders(orders)
        # 筛选掉已在 orders 中的订单
        loaded_schedule = loaded_schedule[~loaded_schedule['Order ID'].isin(order_ids)]

        return loaded_schedule

    except FileNotFoundError:
        # 如果文件不存在，返回一个空的 DataFrame
        return pd.DataFrame(columns=["Order ID", "Warehouse ID", "Dock ID", "Start Time", "End Time"])


def generate_schedule(start_times, end_times, drop_or_queue):
    """
    从开始和结束时间生成一个日程表。

    :param drop_or_queue: 判断是内外部车辆排队接口使用还是甩挂调度接口使用
    :param start_times: 开始时间的字典，键是（订单ID，仓库ID，装卸口ID）。
    :param end_times: 结束时间的字典，键是（订单ID，仓库ID，装卸口ID）。
    :return: 包含日程表信息的DataFrame。
    """
    # 如果输入为空，则返回空的DataFrame
    if not start_times and not end_times:
        return pd.DataFrame(columns=["Order ID", "Warehouse ID", "Dock ID", "Start Time", "End Time"])
    else:
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
        # schedule_df['Start Time'] = schedule_df['Start Time'].apply(convert_to_readable_format)
        # schedule_df['End Time'] = schedule_df['End Time'].apply(convert_to_readable_format)
        schedule_df['Start Time'] = schedule_df['Start Time'].apply(
            lambda x: convert_to_readable_format(x, drop_or_queue))
        schedule_df['End Time'] = schedule_df['End Time'].apply(
            lambda x: convert_to_readable_format(x, drop_or_queue))
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
    :return: 两部字典组成的元组 - 一个是每个装卸口的总繁忙时间，另一个是繁忙时间窗口。
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


def convert_to_readable_format(minutes, drop_or_queue):
    """
    将从现在开始的分钟数转换为可读的日期时间格式。

    :param drop_or_queue: 判断甩挂调度接口使用还是内外部车辆调度接口
    :param minutes: 当前时间起的分钟数。
    :return: 格式为'YYYY-MM-DD HH:MM:SS'的可读日期时间字符串。
    """
    if drop_or_queue == "queue":
        current_time = datetime.now()
        future_time = current_time + timedelta(minutes=minutes)
        return future_time.strftime('%Y-%m-%d %H:%M:%S')
    if drop_or_queue == "drop":
        return minutes.strftime('%Y-%m-%d %H:%M:%S')


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
    pass


if __name__ == "__main__":
    main()
