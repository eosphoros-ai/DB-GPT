import markdown2
import pandas as pd


def datas_to_table_html(data):
    df = pd.DataFrame(data[1:], columns=data[0])
    table_style = """<style> 
        table{border-collapse:collapse;width:60%;height:80%;margin:0 auto;float:right;border: 1px solid #007bff; background-color:#CFE299}th,td{border:1px solid #ddd;padding:3px;text-align:center}th{background-color:#C9C3C7;color: #fff;font-weight: bold;}tr:nth-child(even){background-color:#7C9F4A}tr:hover{background-color:#333}
     </style>"""
    html_table = df.to_html(index=False, escape=False)

    html = f"<html><head>{table_style}</head><body>{html_table}</body></html>"

    return html.replace("\n", " ")


def generate_markdown_table(data):
    """\n    生成 Markdown 表格\n    data: 一个包含表头和表格内容的二维列表\n"""
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
    # mk_text = "| user_name | phone | email | city | create_time | last_login_time | \n| --- | --- | --- | --- | --- | --- | \n| zhangsan | 123 | None | 上海 | 2023-05-13 09:09:09 | None | \n| hanmeimei | 123 | None | 上海 | 2023-05-13 09:09:09 | None | \n| wangwu | 123 | None | 上海 | 2023-05-13 09:09:09 | None | \n| test1 | 123 | None | 成都 | 2023-05-12 09:09:09 | None | \n| test2 | 123 | None | 成都 | 2023-05-11 09:09:09 | None | \n| test3 | 23 | None | 成都 | 2023-05-12 09:09:09 | None | \n| test4 | 23 | None | 成都 | 2023-05-09 09:09:09 | None | \n| test5 | 123 | None | 上海 | 2023-05-08 09:09:09 | None | \n| test6 | 123 | None | 成都 | 2023-05-08 09:09:09 | None | \n| test7 | 23 | None | 上海 | 2023-05-10 09:09:09 | None |\n"
    # print(generate_htm_table(mk_text))

    table_style = """<style>\n  table {\n    border-collapse: collapse;\n   width: 100%;\n }\n     th, td {\n  border: 1px solid #ddd;\n     padding: 8px;\n   text-align: center;\n line-height: 150px;  \n  }\n                  th {\n                    background-color: #f2f2f2;\n                    color: #333;\n                    font-weight: bold;\n                  }\n                  tr:nth-child(even) {\n                    background-color: #f9f9f9;\n                  }\n                  tr:hover {\n                    background-color: #f2f2f2;\n                  }\n                </style>"""

    print(table_style.replace("\n", " "))
