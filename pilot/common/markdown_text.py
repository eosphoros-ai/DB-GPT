import  markdown2
import pandas as pd

def datas_to_table_html(data):
    df = pd.DataFrame(data)
    table_style = """\n<style>\n    table {\n        border-collapse: collapse;\n        width: 100%;\n    }\n    th, td {\n        border: 1px solid blue;\n        padding: 5px;\n        text-align: left;\n    }\n    th {\n        background-color: #f2f2f2;\n    }\n</style>\n"""
    html_table = df.to_html(index=False, header=False, border = True)
    return table_style + html_table



def generate_markdown_table(data):
    """\n    生成 Markdown 表格\n    data: 一个包含表头和表格内容的二维列表\n    """
    # 获取表格列数
    num_cols = len(data[0])
    # 生成表头
    header = "| "
    for i in range(num_cols):
        header += data[0][i] + " | "

    # 生成分隔线
    separator = "| "
    for i in range(num_cols):
        separator += "--- | "

    # 生成表格内容
    content = ""
    for row in data[1:]:
        content += "| "
        for i in range(num_cols):
            content += str(row[i]) + " | "
        content += "\n"

    # 合并表头、分隔线和表格内容
    table = header + "\n" + separator + "\n" + content

    return table

def generate_htm_table(data):
    markdown_text = generate_markdown_table(data)
    html_table = markdown2.markdown(markdown_text, extras=["tables"])
    return html_table


if __name__ == "__main__":
    mk_text = "| user_name | phone | email | city | create_time | last_login_time | \n| --- | --- | --- | --- | --- | --- | \n| zhangsan | 123 | None | 上海 | 2023-05-13 09:09:09 | None | \n| hanmeimei | 123 | None | 上海 | 2023-05-13 09:09:09 | None | \n| wangwu | 123 | None | 上海 | 2023-05-13 09:09:09 | None | \n| test1 | 123 | None | 成都 | 2023-05-12 09:09:09 | None | \n| test2 | 123 | None | 成都 | 2023-05-11 09:09:09 | None | \n| test3 | 23 | None | 成都 | 2023-05-12 09:09:09 | None | \n| test4 | 23 | None | 成都 | 2023-05-09 09:09:09 | None | \n| test5 | 123 | None | 上海 | 2023-05-08 09:09:09 | None | \n| test6 | 123 | None | 成都 | 2023-05-08 09:09:09 | None | \n| test7 | 23 | None | 上海 | 2023-05-10 09:09:09 | None |\n"

    print(generate_htm_table(mk_text))