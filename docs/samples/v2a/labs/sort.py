def bubble_sort(values: list[int]) -> list[int]:
    """冒泡排序：重复比较相邻元素，较大值向后移动。"""
    ordered = list(values)
    length = len(ordered)
    for pass_index in range(length):
        swapped = False
        for index in range(0, length - 1 - pass_index):
            if ordered[index] > ordered[index + 1]:
                ordered[index], ordered[index + 1] = ordered[index + 1], ordered[index]
                swapped = True
        if not swapped:
            break
    return ordered
