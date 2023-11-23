import matplotlib.pyplot as plt
import numpy as np

import matplotlib.colors as mcolors


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



