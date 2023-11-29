from common import Warehouse, Dock, Order


def parse_schedule(schedule):
    order_sequences = {}
    order_dock_assignments = {}
    docks_queues = {}

    # 解析订单的仓库路线和月台分配
    for _, row in schedule.iterrows():
        order_id = str(row['Order ID'])
        warehouse_id = str(row['Warehouse ID'])
        dock_id = row['Dock ID']

        # 更新订单的仓库路线
        if order_id not in order_sequences:
            order_sequences[order_id] = []
        if warehouse_id not in order_sequences[order_id]:
            order_sequences[order_id].append(warehouse_id)

        # 更新订单的月台分配
        if order_id not in order_dock_assignments:
            order_dock_assignments[order_id] = {}
        order_dock_assignments[order_id][warehouse_id] = dock_id

    # 解析每个月台的排队信息
    for _, row in schedule.iterrows():
        dock_key = f"{row['Warehouse ID']}-{row['Dock ID']}"
        if dock_key not in docks_queues:
            docks_queues[dock_key] = {"dock_id": row['Dock ID'], "queue": []}

        queue_item = {
            "position": len(docks_queues[dock_key]["queue"]) + 1,
            "order_id": row['Order ID'],
            "start_time": str(row['Start Time']),
            "end_time": str(row['End Time'])
        }
        docks_queues[dock_key]["queue"].append(queue_item)

    # Convert dock queues to a list
    docks_queues_list = list(docks_queues.values())

    return {
        "order_sequences": order_sequences,
        "order_dock_assignments": order_dock_assignments,
        "docks_queues": docks_queues_list
    }
