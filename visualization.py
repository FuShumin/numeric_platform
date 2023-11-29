import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import matplotlib.colors as mcolors


def plot_order_times_on_docks(start_times, end_times, warehouses, busy_windows=None):
    plt.figure(figsize=(15, 10))
    colors = plt.cm.tab10.colors

    # 为了更准确地创建仓库月台标签，基于 start_times 和 end_times 字典
    dock_labels = []
    for key in start_times.keys():
        label = f"W{key[1]}D{key[2]}"
        if label not in dock_labels:
            dock_labels.append(label)

    dock_positions = range(len(dock_labels))

    # 绘制订单时间
    for (order_id, warehouse_id, dock_id), start in start_times.items():
        end = end_times[(order_id, warehouse_id, dock_id)]
        dock_label = f"W{warehouse_id}D{dock_id}"
        if dock_label in dock_labels:
            dock_pos = dock_positions[dock_labels.index(dock_label)]
            plt.plot([dock_pos, dock_pos], [start, end], color=colors[order_id % len(colors)], linewidth=10)
        else:
            print(f"Warning: Dock label {dock_label} not found in dock_labels.")

    # 绘制忙碌时间窗口
    if busy_windows:
        for dock_key, windows in busy_windows.items():
            warehouse_id, dock_id = dock_key
            dock_label = f"W{warehouse_id}D{dock_id}"
            if dock_label in dock_labels:
                dock_pos = dock_positions[dock_labels.index(dock_label)]
                for start, end in windows:
                    plt.gca().add_patch(patches.Rectangle((dock_pos - 0.1, start), 0.2, end - start,
                                                          hatch='/', fill=False, edgecolor='black'))
            else:
                print(f"Warning: Dock label {dock_label} not found in dock_labels for busy windows.")

    plt.xlabel("Warehouse-Dock")
    plt.ylabel("Time (Minutes)")
    plt.title("Order and Busy Time Windows in each Dock")
    plt.xticks(dock_positions, dock_labels, rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.show()
