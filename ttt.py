# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/26 下午7:54
'''
import re
import sys

# for compatibility with easy_install; see #2198
__requires__ = 'dbgpt'

try:
    from importlib.metadata import distribution
    print('1111')
except ImportError:
    try:
        print(2)
        from importlib_metadata import distribution
    except ImportError:
        print(3)
        from pkg_resources import load_entry_point


def importlib_load_entry_point(spec, group, name):
    dist_name, _, _ = spec.partition('==')
    print(dist_name)
    print(distribution(dist_name).entry_points)
    matches = (
        entry_point
        for entry_point in distribution(dist_name).entry_points
        if entry_point.group == group and entry_point.name == name
    )
    return next(matches).load()


globals().setdefault('load_entry_point', importlib_load_entry_point)


if __name__ == '__main__':
    print(sys.argv[0])
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    print(sys.argv[0])
    sys.exit(load_entry_point('dbgpt', 'console_scripts', 'dbgpt')())