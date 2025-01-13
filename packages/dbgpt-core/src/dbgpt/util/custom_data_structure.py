from collections import OrderedDict, deque


class FixedSizeDict(OrderedDict):
    def __init__(self, max_size):
        super().__init__()
        self.max_size = max_size

    def __setitem__(self, key, value):
        if len(self) >= self.max_size:
            self.popitem(last=False)
        super().__setitem__(key, value)


class FixedSizeList:
    def __init__(self, max_size):
        self.max_size = max_size
        self.list = deque(maxlen=max_size)

    def append(self, value):
        self.list.append(value)

    def __getitem__(self, index):
        return self.list[index]

    def __setitem__(self, index, value):
        self.list[index] = value

    def __len__(self):
        return len(self.list)

    def __str__(self):
        return str(list(self.list))
