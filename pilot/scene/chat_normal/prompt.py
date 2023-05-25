import builtins


def stream_write_and_read(lst):
    # 对lst使用yield from进行可迭代对象的扁平化
    yield from lst
    while True:
        val = yield
        lst.append(val)


if __name__ == "__main__":
    # 创建一个空列表
    my_list = []

    # 使用生成器写入数据
    stream_writer = stream_write_and_read(my_list)
    next(stream_writer)
    stream_writer.send(10)
    print(1)
    stream_writer.send(20)
    print(2)
    stream_writer.send(30)
    print(3)

    # 使用生成器读取数据
    stream_reader = stream_write_and_read(my_list)
    next(stream_reader)
    print(stream_reader.send(None))
    print(stream_reader.send(None))
    print(stream_reader.send(None))
