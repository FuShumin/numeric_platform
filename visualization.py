import matplotlib.pyplot as plt
import numpy as np

import matplotlib.colors as mcolors


def visualize_queue_by_docks_colored(order_dock_assignments, order_queue_positions, warehouses, num_orders):
    # 确定网格大小和每个仓库的月台数量
    num_docks = [len(wh.docks) for wh in warehouses]
    total_docks = sum(num_docks)

    # 初始化网格
    grid = np.full((num_orders, total_docks), -1)  # 使用 -1 作为未分配的标志

    # 为每个订单分配颜色
    colors = list(mcolors.TABLEAU_COLORS)[:num_orders]
    color_map = {order_id: colors[order_id] for order_id in range(num_orders)}

    # 填充网格并记录位置
    dock_positions = {}  # 记录每个月台在网格中的位置
    idx = 0
    for wh_id, wh_docks in enumerate(num_docks):
        for dock_id in range(wh_docks):
            dock_positions[(wh_id, dock_id)] = idx
            for order_id, wh_docks_assigned in order_dock_assignments.items():
                if dock_id == wh_docks_assigned.get(wh_id):
                    pos = order_queue_positions.get(order_id, {}).get(wh_id, 0)
                    grid[pos, idx] = order_id  # 使用订单ID填充网格
            idx += 1

    # 创建图表
    fig, ax = plt.subplots(figsize=(10, 6))
    for (x, y), order_id in np.ndenumerate(grid):
        if order_id >= 0:
            ax.add_patch(plt.Rectangle((y, x), 1, 1, color=color_map[order_id]))

    # 设置 x 轴标签
    ax.set_xticks([dock_positions[(wh_id, 0)] for wh_id in range(len(warehouses))])
    ax.set_xticklabels([f'Warehouse {wh_id}' for wh_id in range(len(warehouses))])


    ax.set_yticks(range(num_orders))
    ax.set_yticklabels([f'Queue Position {o_id}' for o_id in range(num_orders)])
    ax.set_xlim(0, total_docks)
    ax.set_ylim(0, num_orders)
    ax.invert_yaxis()  # 反转 y 轴，使得订单 0 在顶部

    ax.set_title('Order Queue Positions by Docks')
    ax.grid(which='major', axis='both', linestyle='-', color='k', linewidth=1)
    ax.set_aspect('equal')

    plt.show()


def plot_order_times_on_docks(start_times, end_times):
    """
    绘制每个订单在不同仓库月台上的时间窗口。

    :param start_times: 开始时间的字典，键为 (订单ID, 仓库ID, 月台ID)，值为开始时间。
    :param end_times: 结束时间的字典，键为 (订单ID, 仓库ID, 月台ID)，值为结束时间。
    """
    plt.figure(figsize=(15, 10))
    colors = plt.cm.tab10.colors  # 颜色集

    for key in start_times.keys():
        order_id, warehouse_id, dock_id = key
        start = start_times[key]
        end = end_times[key]
        plt.plot([f"W{warehouse_id}D{dock_id}", f"W{warehouse_id}D{dock_id}"], [start, end],
                 color=colors[order_id % len(colors)], linewidth=10)

    plt.xlabel("Warehouse-Dock")
    plt.ylabel("Time (Hr)")
    plt.title("Order ending time in each dock")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.show()



