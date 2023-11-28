import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

import matplotlib.colors as mcolors


def plot_order_times_on_docks(start_times, end_times, busy_windows=None):
    """
    绘制每个订单在不同仓库月台上的时间窗口，以及忙碌时间窗口。

    :param start_times: 开始时间的字典，键为 (订单ID, 仓库ID, 月台ID)，值为开始时间。
    :param end_times: 结束时间的字典，键为 (订单ID, 仓库ID, 月台ID)，值为结束时间。
    :param busy_windows: 忙碌时间窗口的字典，键为 (仓库ID, 月台ID)，值为时间窗口的列表。
    """

    plt.figure(figsize=(15, 10))
    colors = plt.cm.tab10.colors

    # 创建仓库月台标签和对应的数值坐标
    dock_labels = [f"W{w_id}D{d_id}" for w_id in range(len(warehouses)) for d_id in range(len(warehouses[0].docks))]
    dock_positions = range(len(dock_labels))

    # 绘制订单时间
    for (order_id, warehouse_id, dock_id), start in start_times.items():
        end = end_times[(order_id, warehouse_id, dock_id)]
        dock_pos = dock_positions[dock_labels.index(f"W{warehouse_id}D{dock_id}")]
        plt.plot([dock_pos, dock_pos], [start, end], color=colors[order_id % len(colors)], linewidth=10)

    # 绘制忙碌时间窗口
    if busy_windows:
        for dock_key, windows in busy_windows.items():
            warehouse_id, dock_id = dock_key
            dock_pos = dock_positions[dock_labels.index(f"W{warehouse_id}D{dock_id}")]
            for start, end in windows:
                plt.gca().add_patch(patches.Rectangle((dock_pos - 0.1, start), 0.2, end - start,
                                                      hatch='/', fill=False, edgecolor='black'))

    plt.xlabel("Warehouse-Dock")
    plt.ylabel("Time (Hr)")
    plt.title("Order and Busy Time Windows in each Dock")
    plt.xticks(dock_positions, dock_labels, rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.show()
