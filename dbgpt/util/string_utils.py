import re


def is_all_chinese(text):
    ### Determine whether the string is pure Chinese
    pattern = re.compile(r"^[一-龥]+$")
    match = re.match(pattern, text)
    return match is not None


def is_number_chinese(text):
    ### Determine whether the string is numbers and Chinese
    pattern = re.compile(r"^[\d一-龥]+$")
    match = re.match(pattern, text)
    return match is not None


def is_chinese_include_number(text):
    ### Determine whether the string is pure Chinese or Chinese containing numbers
    pattern = re.compile(r"^[一-龥]+[\d一-龥]*$")
    match = re.match(pattern, text)
    return match is not None


def is_scientific_notation(string):
    # 科学计数法的正则表达式
    pattern = r"^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$"
    # 使用正则表达式匹配字符串
    match = re.match(pattern, str(string))
    # 判断是否匹配成功
    if match is not None:
        return True
    else:
        return False


def extract_content(long_string, s1, s2, is_include: bool = False):
    # extract text
    match_map = {}
    start_index = long_string.find(s1)
    while start_index != -1:
        if is_include:
            end_index = long_string.find(s2, start_index + len(s1) + 1)
            extracted_content = long_string[start_index : end_index + len(s2)]
        else:
            end_index = long_string.find(s2, start_index + len(s1))
            extracted_content = long_string[start_index + len(s1) : end_index]
        if extracted_content:
            match_map[start_index] = extracted_content
        start_index = long_string.find(s1, start_index + 1)
    return match_map


def extract_content_open_ending(long_string, s1, s2, is_include: bool = False):
    # extract text  open ending
    match_map = {}
    start_index = long_string.find(s1)
    while start_index != -1:
        if long_string.find(s2, start_index) <= 0:
            end_index = len(long_string)
        else:
            if is_include:
                end_index = long_string.find(s2, start_index + len(s1) + 1)
            else:
                end_index = long_string.find(s2, start_index + len(s1))
        if is_include:
            extracted_content = long_string[start_index : end_index + len(s2)]
        else:
            extracted_content = long_string[start_index + len(s1) : end_index]
        if extracted_content:
            match_map[start_index] = extracted_content
        start_index = long_string.find(s1, start_index + 1)
    return match_map


def _to_str(x, charset="utf8", errors="strict"):
    if x is None or isinstance(x, str):
        return x

    if isinstance(x, bytes):
        return x.decode(charset, errors)

    return str(x)
