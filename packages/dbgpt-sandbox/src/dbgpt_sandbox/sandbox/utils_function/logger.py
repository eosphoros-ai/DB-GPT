from colorama import Fore, Style, init

# 初始化 colorama（Windows 下必须）
init(autoreset=True)


def print_log(level: str, msg: str):
    COLORS = {
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "DEBUG": Fore.BLUE,
    }
    color = COLORS.get(level.upper(), "")
    print(f"{color}{level.upper()}:{Style.RESET_ALL} {msg}")
