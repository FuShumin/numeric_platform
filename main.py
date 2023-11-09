import random
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import copy
NUM_DOCKS = 10  # 月台数量
NUM_VEHICLES = 10  # 车辆数量
MAX_DOCK_VISITS = 10  # 一台车所需到达月台数的最大值
loading_times = [30] * NUM_DOCKS  # 每个月台初始装卸时间设置为30分钟

# 生成模拟数据，月台和车辆
docks = [{'id': f'Dock {i + 1}', 'next_available_time': 0} for i in range(NUM_DOCKS)]
vehicles = [{'id': f'Vehicle {i + 1}',
             'required_docks': random.sample([dock['id'] for dock in docks], random.randint(1, MAX_DOCK_VISITS)),
             'next_available_time': 0} for i in range(NUM_VEHICLES)]
vehciles_bkup = copy.deepcopy(vehicles)
"""
码头和车辆可用性跟踪
月台可用性字典： 算法维护一个字典 dock_availability，该字典记录每个码头的下一个可用时间。
经过排序的车辆队列： 车辆列表 vehicles_queue 根据它们的下一个可用时间和需要访问的月台数量来排序，确保下一个被调度的总是最早可用的车辆。
迭代调度
持续循环： 一个 while 循环运行，直到所有车辆都访问了它们所有需要的码头，这表现为 required_docks 列表为空。
内部循环遍历车辆： 一个内部 for 循环遍历排序后的车辆列表，根据它们可用性的顺序处理它们的调度。
动态调度码头访问
选择码头： 对于每辆车，选择下一个访问的码头是基于该车辆所需的码头的可用性。选择的码头是最先变得可用的码头，与车辆自己的可用时间相比较。
调度： 一旦选择了码头，算法就会在考虑到车辆和码头下一次可用时间的基础上，尽早安排车辆访问。
记录调度： 访问在全局调度列表中记录，并相应地更新每辆车的码头序列。
更新机制
时间更新： 在安排访问后，访问的结束时间被用来更新车辆和码头的下一个可用时间。
移除码头： 已访问的码头从车辆的 required_docks 列表中移除，表明该访问要求已经完成。
为下一次迭代重新排序
重新排序车辆： 在每个调度决策之后，车辆列表会重新排序，以反映最新的可用时间。这一步对于保持车辆调度顺序的正确性至关重要。
算法目标
最大化码头利用率： 通过总是选择最早可用的码头进行调度，并根据可用性进行排序，算法旨在减少码头的空闲时间。
防止重叠： 通过在每次安排访问后更新可用时间，调度确保没有车辆同时被安排到多个码头。
完成必要的访问： 算法循环直到所有车辆访问了所有它们需要的码头，满足模拟的目标。
"""


def generate_maximized_schedules(vehicles, docks, loading_times):
    dock_availability = {dock['id']: 0 for dock in docks}  # 追踪每一个月台的下一个可用窗口
    # 初始化车辆队列，优先调度需求多的车辆
    vehicles_queue = sorted(vehicles, key=lambda v: (-len(v['required_docks']), v['next_available_time']))

    global_schedules = []  # 追踪所有月台的安排
    dock_sequences = {vehicle['id']: [] for vehicle in vehicles}  # 初始化每辆车的装车路线

    while any(vehicle['required_docks'] for vehicle in vehicles_queue):
        for vehicle in vehicles_queue:
            if not vehicle['required_docks']:  # 如果车辆没有剩余需求则继续
                continue

            # 寻找下一个可用的月台和车辆的需求月台匹配的最优选择
            next_docks = sorted((max(dock_availability[dock_id], vehicle['next_available_time']), dock_id)
                                for dock_id in vehicle['required_docks'])
            # 选择最适合的月台
            _, next_dock_id = min(next_docks, key=lambda x: x[0] - vehicle['next_available_time'] if x[0] >= vehicle[
                'next_available_time'] else float('inf'))
            dock_index = int(next_dock_id.split(' ')[1]) - 1  # 获取月台索引
            specific_loading_time = loading_times[dock_index]  # 获取特定月台的装卸时间

            # 计算开始和结束时间
            start_time = max(vehicle['next_available_time'], dock_availability[next_dock_id])
            end_time = start_time + specific_loading_time

            # 创建调度
            global_schedules.append({
                'vehicle_id': vehicle['id'],
                'dock_id': next_dock_id,
                'start_time': start_time,
                'end_time': end_time
            })

            # 更新车辆和月台的可用时间
            vehicle['next_available_time'] = end_time
            dock_availability[next_dock_id] = end_time

            # 更新车辆月台序列
            dock_sequences[vehicle['id']].append(next_dock_id)

            # 从required_docks移除该月台
            vehicle['required_docks'].remove(next_dock_id)

        # 重新排序车辆队列，考虑需求数量和可用时间
        vehicles_queue.sort(key=lambda v: (-len(v['required_docks']), v['next_available_time']))

    # 所有调度完成后，找到最后完成的车辆时间
    last_finish_time = max(vehicle['next_available_time'] for vehicle in vehicles)

    return global_schedules, dock_sequences, last_finish_time


# 准备绘图数据
def prepare_plot_data(fixed_schedules):
    plot_data = {dock['id']: [] for dock in docks}
    for schedule in fixed_schedules:
        plot_data[schedule['dock_id']].append((schedule['vehicle_id'], schedule['start_time'], schedule['end_time']))
    return plot_data


# 绘制结果
def plot_dock_schedules(plot_data, dock_sequences):
    # Determine the number of subplots needed based on the number of docks
    num_plots = len(plot_data)
    fig, axes = plt.subplots(nrows=num_plots, ncols=1, figsize=(15, num_plots * 2), sharex=True)

    # Check if we have a single plot, not an array of plots
    if num_plots == 1:
        axes = [axes]

    # Set the colors for each vehicle for consistency in plotting
    colors = list(mcolors.TABLEAU_COLORS)  # Get a list of color names
    vehicle_colors = {vehicle_id: colors[i % len(colors)] for i, vehicle_id in enumerate(dock_sequences)}

    # Plot the schedules for each dock
    for ax, (dock_id, schedules) in zip(axes, plot_data.items()):
        for schedule in schedules:
            vehicle_id, start_time, end_time = schedule
            ax.barh(y=dock_id, width=end_time - start_time, left=start_time, color=vehicle_colors[vehicle_id])
            ax.text((start_time + end_time) / 2, dock_id, str(vehicle_id), ha='center', va='center')

        ax.set_title(f"Schedule for {dock_id}")
        ax.set_xlabel("Time (minutes)")
        ax.set_ylabel("Dock ID")

    # Set the legend for the vehicles
    # Create custom artists for the legend to represent the vehicles
    custom_lines = [plt.Line2D([0], [0], color=vehicle_colors[v_id], lw=4) for v_id in dock_sequences]
    fig.legend(custom_lines, dock_sequences, title="Vehicles", loc='upper center', ncol=len(dock_sequences) // 2 + 1)

    # Adjust layout to prevent overlap and set a common x-label
    fig.tight_layout()
    plt.subplots_adjust(top=0.9)  # Adjust the top to make space for the legend
    fig.text(0.5, 0.04, 'Time (minutes)', ha='center', va='center')  # Common x-label

    # Show the plot
    plt.show()


intelligent_schedules, intelligent_dock_sequences, last_finish_time = generate_maximized_schedules(vehicles, docks,
                                                                                                   loading_times)
intelligent_schedules, intelligent_dock_sequences
plot_data = prepare_plot_data(intelligent_schedules)
plot_dock_schedules(plot_data, intelligent_dock_sequences)

# %% test
# vehicles_needing_dock = {vehicle_id: docks for vehicle_id, docks in dock_sequences.items() if 'Platform 7' in docks}
