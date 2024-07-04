"""FinTableExtractor."""
import json
import logging
import os
import re

import pandas as pd

logger = logging.getLogger(__name__)


class FinTableProcessor:
    """FinTableProcessor."""

    def __init__(self, txt_path):
        """FinTableProcessor."""
        self.txt_path = txt_path
        self.all_data = []
        self.all_table = []
        self.all_title = []

    def read_file(self):
        """Read file and store data in self.all_data."""
        with open(self.txt_path, "r") as file:
            for line in file:
                data = eval(line)
                print(data)
                # ignore页眉 and 页脚
                if data and data["type"] not in ["页眉", "页脚"] and data["inside"] != "":
                    self.all_data.append(data)

    def process_text_data(self):
        """Text data processing to level 1 and level 2 titles."""
        for i in range(len(self.all_data)):
            data = self.all_data[i]
            inside_content = data.get("inside")
            content_type = data.get("type")
            if content_type == "text":
                # use regex to match the first level title
                first_level_match = re.match(
                    r"§(\d+)+([\u4e00-\u9fa5]+)", inside_content.strip()
                )
                second_level_match = re.match(
                    r"(\d+\.\d+)([\u4e00-\u9fa5]+)", inside_content.strip()
                )
                first_num_match = re.match(r"^§(\d+)$", inside_content.strip())
                # get all level 1 titles
                title_name = [
                    dictionary["first_title"]
                    for dictionary in self.all_title
                    if "first_title" in dictionary
                ]
                if first_level_match:
                    first_title_text = first_level_match.group(2)
                    first_title_num = first_level_match.group(1)
                    first_title = first_title_num + first_title_text
                    # the title does not contain "..." and is not in the title list
                    # , add it to the title list
                    if first_title not in title_name and (
                        int(first_title_num) == 1
                        or int(first_title_num) - int(self.all_title[-1]["id"]) == 1
                    ):
                        current_entry = {
                            "id": first_title_num,
                            "first_title": first_title,
                            "second_title": [],
                            "table": [],
                        }
                        self.all_title.append(current_entry)

                elif second_level_match:
                    second_title_name = second_level_match.group(0)
                    second_title = second_level_match.group(1)
                    first_title = second_title.split(".")[0]
                    if (int(first_title) - 1 >= len(self.all_title)) or int(
                        first_title
                    ) - 1 < 0:
                        continue
                    else:
                        titles = [
                            sub_item["title"]
                            for sub_item in self.all_title[int(first_title) - 1][
                                "second_title"
                            ]
                        ]
                        if second_title_name not in titles:
                            self.all_title[int(first_title) - 1]["second_title"].append(
                                {"title": second_title_name, "table": []}
                            )
                elif first_num_match:
                    first_num = first_num_match.group(1)
                    first_text = self.all_data[i + 1].get("inside")
                    first_title = first_num_match.group(1) + first_text
                    # if the title does not contain "..." and is not in the title list
                    if (
                        "..." not in first_text
                        and first_title not in title_name
                        and (
                            int(first_num) == 1
                            or int(first_num) - int(self.all_title[-1]["id"]) == 1
                        )
                    ):
                        current_entry = {
                            "id": first_num,
                            "first_title": first_title,
                            "second_title": [],
                            "table": [],
                        }
                        self.all_title.append(current_entry)

    def process_excel_data(self):
        """Process excel data."""
        temp_table = []
        temp_title = None

        for i in range(len(self.all_data)):
            data = self.all_data[i]
            inside_content = data.get("inside")
            content_type = data.get("type")
            if content_type == "excel":
                temp_table.append(inside_content)
                if temp_title is None:
                    for j in range(i - 1, -1, -1):
                        if self.all_data[j]["type"] == "excel":
                            break
                        if self.all_data[j]["type"] == "text":
                            content = self.all_data[j]["inside"]
                            if re.match(r"^\d+\.\d+", content) or content.startswith(
                                "§"
                            ):
                                temp_title = content.strip()
                                break
            elif content_type == "text" and temp_title is not None:
                self.all_table.append({"title": temp_title, "table": temp_table})
                temp_title = None
                temp_table = []

    def process_tables(self):
        """Process table data."""
        for table in self.all_table:
            title = table["title"]
            table_content = table["table"]
            first_match = re.match(r"§(\d+)(.+)", title)
            second_match = re.match(r"(\d+)\.(\d+)(.+)", title)
            try:
                if first_match:
                    first_title = first_match.group(1)
                    text_part = first_match.group(2)
                    table_pair = {
                        "table_name": text_part,
                        "table_content": table_content,
                    }
                    # self.all_title
                    for item in self.all_title:
                        # if the title is in the title list, add the table to the title
                        if item["id"] == first_title:
                            item["table"].append(table_pair)
                            break

                elif second_match:
                    for index, char in enumerate(title):
                        if not char.isdigit() and char != ".":
                            break
                    table_name = title[index:]
                    first_title, second_title = (
                        second_match.group(1),
                        int(second_match.group(2)) - 1,
                    )
                    table_pair = {
                        "table_name": table_name,
                        "table_content": table_content,
                    }
                    for item in self.all_title:
                        if item["id"] == first_title:
                            item["second_title"][second_title]["table"].append(
                                table_pair
                            )
            except Exception:
                # if the title is not in the title list, print an error message
                print(
                    "Error: file exist title error, file,{} title, {}".format(
                        self.txt_path, title
                    )
                )
                break

    def create_excel_files(self, output_folder):
        """Create excel files."""
        for item in self.all_title:
            first_title = item["first_title"]
            second_title = item["second_title"]
            folder_path = os.path.join(output_folder, first_title)
            os.makedirs(folder_path, exist_ok=True)
            first_title_table_data = item["table"]
            try:
                if first_title_table_data != []:
                    for table_item in first_title_table_data:
                        table_name = table_item["table_name"]
                        excel_name = f"{table_name}.xlsx"
                        excel_path = os.path.join(folder_path, excel_name)
                        table_content = table_item["table_content"]
                        table_content = [eval(item) for item in table_content]
                        # Use the first sublist as column names and
                        # the remaining sublists as data rows

                        # The number of columns in the first row is
                        # the maximum number of columns
                        max_cols = len(table_content[0])
                        for row in table_content:
                            # If the number of columns in the current row exceeds
                            # the maximum number of columns
                            if len(row) > max_cols:
                                for i in range(max_cols, len(row)):
                                    # Merge excess values ​​into the maximum
                                    # number of columns of the current row
                                    row[max_cols - 1] += "," + row[i]
                                del row[max_cols:]

                        # 创建 DataFrame
                        df = pd.DataFrame(table_content[1:], columns=table_content[0])
                        df.to_excel(excel_path, index=False)
                else:
                    for table_item in second_title:
                        second_folder_path = os.path.join(
                            folder_path, table_item["title"]
                        )
                        os.makedirs(second_folder_path, exist_ok=True)
                        for table in table_item["table"]:
                            table_name = table["table_name"].replace("/", "或")
                            table_content = table["table_content"]
                            table_content = [eval(item) for item in table_content]
                            excel_name = f"{table_name}.xlsx"
                            excel_path = os.path.join(second_folder_path, excel_name)
                            # The number of columns in the first row is the maximum
                            # number of columns
                            max_cols = len(table_content[0])
                            for row in table_content:
                                # If the number of columns in the current row exceeds
                                # the maximum number of columns
                                if len(row) > max_cols:
                                    # Merge excess values ​​into the maximum
                                    # number of columns of the current row
                                    for i in range(max_cols, len(row)):
                                        row[max_cols - 1] += "," + row[i]
                                    del row[max_cols:]
                            # create DataFrame
                            df = pd.DataFrame(
                                table_content[1:], columns=table_content[0]
                            )
                            df.to_excel(excel_path, index=False)
            except Exception:
                # match column contains year, month, date.
                logger.error(
                    "Error: 文件<{}>中的表格<{}>有误，拆分处理".format(self.txt_path, table_name)
                )
                pattern = r"\d{4}年\d{1,2}月\d{1,2}日"
                # Iterate through the column names of the first row
                for i, column_name in enumerate(table_content[0]):
                    # If the column name matches the format containing year,
                    # month and day
                    if re.search(pattern, column_name):
                        # Merge the current column name and the adjacent column
                        # names on the left and right
                        table_content[0][i - 1] = " ".join(
                            [column_name, table_content[0][i - 1]]
                        )
                        table_content[0][i + 1] = " ".join(
                            [column_name, table_content[0][i + 1]]
                        )
                        # Delete the current column and adjacent columns to the
                        # left and right
                        del table_content[0][i]
                print(table_content)
                df = pd.DataFrame(table_content[1:], columns=table_content[0])
                df.to_excel(excel_path, index=False)

        all_title_path = os.path.join(output_folder, "all_data.json")
        all_table_path = os.path.join(output_folder, "all_table.json")
        with open(all_table_path, "w", encoding="utf-8") as f:
            json.dump(self.all_table, f, ensure_ascii=False, indent=4)
        with open(all_title_path, "w", encoding="utf-8") as f:
            json.dump(self.all_title, f, ensure_ascii=False, indent=4)


class FinTableExtractor:
    """Fin Report Table Extractor."""

    def __init__(self, file_name):
        """Fin Report Table Extractor."""
        self.file_name = file_name

    # extract text between check_re_1-check_re_2

    def cut_all_text(self, check, check_re_1, check_re_2, all_text, line_dict, text):
        """Cut all text."""
        if check is False and re.search(check_re_1, all_text):
            check = True
        if check and line_dict["type"] not in ["页眉", "页脚"]:
            if not re.search(check_re_2, all_text):
                if line_dict["inside"] != "":
                    text = text + line_dict["inside"] + "\n"
            else:
                check = False
        return text, check

    def extract_base_col(self):
        """Extract base info col."""
        allname = self.file_name.split("\\")[-1]
        date, name, stock, short_name, year, else1 = allname.split("__")
        stock2, short_name2, mail, address1, address2 = "", "", "", "", ""
        chinese_name, chinese_name2, english_name, english_name2, web, boss = (
            "",
            "",
            "",
            "",
            "",
            "",
        )
        all_person, person11, person12, person13, person14, person15 = (
            "",
            "",
            "",
            "",
            "",
            "",
        )
        person21, person22, person23, person24, person25, person26, person27 = (
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
        with open(self.file_name, "r", encoding="utf-8") as file:

            lines = file.readlines()
            for i in range(len(lines)):
                line = lines[i]
                line = line.replace("\n", "")
                line_dict = json.loads(line)
                try:
                    if line_dict["type"] not in ["页眉", "页脚", "text"]:
                        if stock2 == "" and re.search(
                            "股票代码'|证券代码'", line_dict["inside"]
                        ):
                            middle = (
                                line_dict["inside"]
                                + "\n"
                                + json.loads(lines[i + 1].replace("\n", ""))["inside"]
                            )
                            stock2_re = re.search("(?:0|6|3)\d{5}", middle)
                            if stock2_re:
                                stock2 = stock2_re.group()
                            answer_list = eval(line_dict["inside"]) + eval(
                                json.loads(lines[i + 1].replace("\n", ""))["inside"]
                            )
                            for _answer in answer_list:
                                if not re.search(
                                    "代码|股票|简称|交易所|A股|A 股|公司|上交所|科创版|名称", _answer
                                ) and _answer not in ["", " "]:
                                    short_name2 = _answer
                                    break

                        def check_answers(
                            answer,
                            keywords_re,
                            check_chinese,
                            _answer=_answer,
                            line_dict=line_dict,
                            answer_list=answer_list,
                        ):
                            if answer == "" and re.search(
                                keywords_re, line_dict["inside"]
                            ):
                                answer_list = eval(line_dict["inside"])
                                for _answer in answer_list:
                                    keywords_re = keywords_re.replace("'", "")
                                    if check_chinese:
                                        if (
                                            not re.search(keywords_re, _answer)
                                            and not re.search(
                                                "[\u4e00-\u9fa5]", _answer
                                            )
                                            and _answer not in ["", " "]
                                        ):
                                            answer = _answer
                                            break
                                    else:
                                        if not re.search(
                                            keywords_re, _answer
                                        ) and _answer not in ["", " "]:
                                            answer = _answer
                                            break
                            return answer

                        def check_person_answers(
                            answer,
                            all_answer,
                            keywords_re,
                            check_chinese,
                            _answer=_answer,
                            line_dict=line_dict,
                            answer_list=answer_list,
                        ):
                            if (
                                answer == ""
                                and all_answer != ""
                                and re.search(keywords_re, line_dict["inside"])
                            ):
                                answer_list = eval(line_dict["inside"])
                                for _answer in answer_list:
                                    keywords_re = keywords_re.replace("'", "")
                                    if check_chinese:
                                        if (
                                            not re.search(keywords_re, _answer)
                                            and not re.search(
                                                "[\u4e00-\u9fa5]", _answer
                                            )
                                            and _answer not in ["", " "]
                                        ):
                                            answer = _answer
                                            break
                                    else:
                                        if not re.search(
                                            keywords_re, _answer
                                        ) and _answer not in ["", " "]:
                                            answer = _answer
                                            break

                            return answer

                        mail = check_answers(mail, "'电子信箱|电子信箱'", True)
                        address1 = check_answers(address1, "'注册地址|注册地址'", False)
                        address2 = check_answers(address2, "'办公地址|办公地址'", False)
                        chinese_name = check_answers(
                            chinese_name, "'公司的中文名称|公司的中文名称'", False
                        )
                        chinese_name2 = check_answers(
                            chinese_name2, "'中文简称|中文简称'", False
                        )
                        english_name = check_answers(
                            english_name, "'公司的外文名称|公司的外文名称(?:（如有）)？'", True
                        )
                        english_name2 = check_answers(
                            english_name2,
                            "'公司的外文名称缩写|公司的外文名称缩写(?:（如有）)？" "" "" "'",
                            True,
                        )
                        web = check_answers(
                            web, "'公司(?:国际互联网)?网址|公司(?:国际互联网)?网址'", True
                        )
                        boss = check_answers(boss, "'公司的法定代表人|公司的法定代表人'", False)
                        all_person = check_answers(
                            all_person,
                            "'(?:报告期末)?在职员工的数量合计(?:（人）)?|(?:报告期末)?在职员工"
                            "的数量合计(?:（人）)?'",
                            True,
                        )
                        person11 = check_person_answers(
                            person11, all_person, "'生产人员|生产人员'", True
                        )
                        person12 = check_person_answers(
                            person12, all_person, "'销售人员|销售人员'", True
                        )
                        person13 = check_person_answers(
                            person13, all_person, "'技术人员|技术人员'", True
                        )
                        person14 = check_person_answers(
                            person14, all_person, "'财务人员|财务人员'", True
                        )
                        person15 = check_person_answers(
                            person15, all_person, "'行政人员|行政人员'", True
                        )

                        person21 = check_person_answers(
                            person21, all_person, "本科及以上'", True
                        )
                        person22 = check_person_answers(
                            person22, all_person, "本科'", True
                        )
                        person23 = check_person_answers(
                            person23, all_person, "硕士及以上'", True
                        )
                        person24 = check_person_answers(
                            person24, all_person, "硕士'", True
                        )
                        person25 = check_person_answers(
                            person25, all_person, "博士及以上'", True
                        )
                        person26 = check_person_answers(
                            person26, all_person, "博士'", True
                        )

                        person27 = check_answers(person27, "公司研发人员的数量'", True)

                        if (
                            stock2 != ""
                            and mail != ""
                            and address1 != ""
                            and address2 != ""
                            and chinese_name != ""
                            and chinese_name2 != ""
                            and english_name != ""
                            and english_name2 != ""
                            and web != ""
                            and boss != ""
                            and all_person != ""
                            and person11 != ""
                            and person12 != ""
                            and person13 != ""
                            and person14 != ""
                            and person15 != ""
                            and person21 != ""
                            and person22 != ""
                            and person23 != ""
                            and person24 != ""
                            and person25 != ""
                            and person26 != ""
                            and person27 != ""
                        ):
                            break
                except Exception:
                    print(line_dict)
        new_row = {
            "文件名": allname,
            "日期": date,
            "公司名称": name,
            "股票代码": stock,
            "股票简称": short_name,
            "年份": year,
            "类型": "年度报告",
            "代码": stock2,
            "简称": short_name2,
            "电子信箱": mail,
            "注册地址": address1,
            "办公地址": address2,
            "中文名称": chinese_name,
            "中文简称": chinese_name2,
            "外文名称": english_name,
            "外文名称缩写": english_name2,
            "公司网址": web,
            "法定代表人": boss,
            "职工总数": all_person,
            "生产人员": person11,
            "销售人员": person12,
            "技术人员": person13,
            "财务人员": person14,
            "行政人员": person15,
            "本科及以上人员": person21,
            "本科人员": person22,
            "硕士及以上人员": person23,
            "硕士人员": person24,
            "博士及以上人员": person25,
            "博士人员": person26,
            "研发人数": person27,
            "全文": str(lines),
        }
        print("finish " + self.file_name)
        return new_row

    # 提取指定文本
    def extract_fin_data(self):
        """Extract financial data."""
        allname = self.file_name.split("\\")[-1]
        date, name, stock, short_name, year, else1 = allname.split("__")
        all_text = ""
        text1, text2, text3, text4, text5 = (
            "",
            "",
            "",
            "",
            "",
        )

        check1, check2, check3, check4, check5 = (
            False,
            False,
            False,
            False,
            False,
        )

        answer_dict = {}
        list2 = [
            "货币资金",
            "结算备付金",
            "拆出资金",
            "交易性金融资产",
            "以公允价值计量且其变动计入当期损益的金融资产",
            "衍生金融资产",
            "应收票据",
            "应收账款",
            "应收款项融资",
            "预付款项",
            "应收保费",
            "应收分保账款",
            "应收分保合同准备金",
            "其他应收款",
            "应收利息",
            "应收股利",
            "买入返售金融资产",
            "存货",
            "合同资产",
            "持有待售资产",
            "一年内到期的非流动资产",
            "其他流动资产",
            "流动资产合计",
            "发放贷款和垫款",
            "债权投资",
            "可供出售金融资产",
            "其他债权投资",
            "持有至到期投资",
            "长期应收款",
            "长期股权投资",
            "其他权益工具投资",
            "其他非流动金融资产",
            "投资性房地产",
            "固定资产",
            "在建工程",
            "生产性生物资产",
            "油气资产",
            "使用权资产",
            "无形资产",
            "开发支出",
            "商誉",
            "长期待摊费用",
            "递延所得税资产",
            "其他非流动资产",
            "非流动资产合计",
            "资产总计",
            "短期借款",
            "向中央银行借款",
            "拆入资金",
            "交易性金融负债",
            "以公允价值计量且其变动计入当期损益的金融负债",
            "衍生金融负债",
            "应付票据",
            "应付账款",
            "预收款项",
            "合同负债",
            "卖出回购金融资产款",
            "吸收存款及同业存放",
            "代理买卖证券款",
            "代理承销证券款",
            "应付职工薪酬",
            "应交税费",
            "其他应付款",
            "应付利息",
            "应付股利",
            "应付手续费及佣金",
            "应付分保账款",
            "持有待售负债",
            "一年内到期的非流动负债",
            "其他流动负债",
            "流动负债合计",
            "保险合同准备金",
            "长期借款",
            "应付债券",
            "租赁负债",
            "长期应付款",
            "长期应付职工薪酬",
            "预计负债",
            "递延收益",
            "递延所得税负债",
            "其他非流动负债",
            "非流动负债合计",
            "负债合计",
            "股本",
            "实收资本",
            "其他权益工具",
            "资本公积",
            "库存股",
            "其他综合收益",
            "专项储备",
            "盈余公积",
            "一般风险准备",
            "未分配利润",
            "归属于母公司所有者权益合计",
            "少数股东权益",
            "所有者权益合计",
            "负债和所有者权益总计",
            "营业总收入",
            "营业收入",
            "利息收入",
            "已赚保费",
            "手续费及佣金收入",
            "营业总成本",
            "营业成本",
            "利息支出",
            "手续费及佣金支出",
            "退保金",
            "赔付支出净额",
            "提取保险责任合同准备金净额",
            "保单红利支出",
            "分保费用",
            "税金及附加",
            "销售费用",
            "管理费用",
            "研发费用",
            "财务费用",
            "利息费用",
            "其他收益",
            "投资收益",
            "其中：对联营企业和合营企业的投资收益",
            "以摊余成本计量的金融资产终止确认收益",
            "汇兑收益",
            "净敞口套期收益",
            "公允价值变动收益",
            "信用减值损失",
            "资产减值损失",
            "资产处置收益",
            "营业利润",
            "营业外收入",
            "营业外支出",
            "利润总额",
            "所得税费用",
            "净利润",
            "按经营持续性分类",
            "持续经营净利润",
            "终止经营净利润",
            "按所有权归属分类",
            "归属于母公司所有者的净利润",
            "少数股东损益",
            "其他综合收益的税后净额",
            "归属母公司所有者的其他综合收益的税后净额",
            "不能重分类进损益的其他综合收益",
            "重新计量设定受益计划变动额",
            "权益法下不能转损益的其他综合收益",
            "其他权益工具投资公允价值变动",
            "企业自身信用风险公允价值变动",
            "其他",
            "将重分类进损益的其他综合收益",
            "权益法下可转损益的其他综合收益",
            "其他债权投资公允价值变动",
            "可供出售金融资产公允价值变动损益",
            "金融资产重分类计入其他综合收益的金额",
            "持有至到期投资重分类为可供出售金融资产损益",
            "其他债权投资信用减值准备",
            "现金流量套期储备",
            "外币财务报表折算差额",
            "其他",
            "归属于少数股东的其他综合收益的税后净额",
            "综合收益总额",
            "归属于母公司所有者的综合收益总额",
            "归属于少数股东的综合收益总额",
            "基本每股收益",
            "稀释每股收益",
            "销售商品、提供劳务收到的现金",
            "客户存款和同业存放款项净增加额",
            "向中央银行借款净增加额",
            "向其他金融机构拆入资金净增加额",
            "收到原保险合同保费取得的现金",
            "收到再保业务现金净额",
            "保户储金及投资款净增加额",
            "收取利息、手续费及佣金的现金",
            "拆入资金净增加额",
            "回购业务资金净增加额",
            "代理买卖证券收到的现金净额",
            "收到的税费返还",
            "收到其他与经营活动有关的现金",
            "经营活动现金流入小计",
            "购买商品、接受劳务支付的现金",
            "客户贷款及垫款净增加额",
            "存放中央银行和同业款项净增加额",
            "支付原保险合同赔付款项的现金",
            "拆出资金净增加额",
            "支付利息、手续费及佣金的现金",
            "支付保单红利的现金",
            "支付给职工以及为职工支付的现金",
            "支付的各项税费",
            "支付其他与经营活动有关的现金",
            "经营活动现金流出小计",
            "经营活动产生的现金流量净额",
            "收回投资收到的现金",
            "取得投资收益收到的现金",
            "处置固定资产、无形资产和其他长期资产收回的现金净额",
            "处置子公司及其他营业单位收到的现金净额",
            "收到其他与投资活动有关的现金",
            "投资活动现金流入小计",
            "购建固定资产、无形资产和其他长期资产支付的现金",
            "投资支付的现金",
            "质押贷款净增加额",
            "取得子公司及其他营业单位支付的现金净额",
            "支付其他与投资活动有关的现金",
            "投资活动现金流出小计",
            "投资活动产生的现金流量净额",
            "吸收投资收到的现金",
            "子公司吸收少数股东投资收到的现金",
            "取得借款收到的现金",
            "收到其他与筹资活动有关的现金",
            "筹资活动现金流入小计",
            "偿还债务支付的现金",
            "分配股利、利润或偿付利息支付的现金",
            "子公司支付给少数股东的股利、利润",
            "支付其他与筹资活动有关的现金",
            "筹资活动现金流出小计",
            "筹资活动产生的现金流量净额",
            "汇率变动对现金及现金等价物的影响",
            "现金及现金等价物净增加额",
            "期初现金及现金等价物余额",
            "期末现金及现金等价物余额",
        ]
        for _l in list2:
            answer_dict[_l] = ""

        with open(self.file_name, "r", encoding="utf-8") as file:

            lines = file.readlines()
            for line in lines:
                line = line.replace("\n", "")
                line_dict = json.loads(line)
                try:
                    if line_dict["type"] not in ["页眉", "页脚"]:
                        all_text = all_text + line_dict["inside"]

                    # 合并资产负债表
                    text1, check1 = self.cut_all_text(
                        check1,
                        "(?:财务报表.{0,15}|1、)(?:合并资产负债表)$",
                        "(?:母公司资产负债表)$",
                        all_text,
                        line_dict,
                        text1,
                    )
                    # 母公司资产负债表
                    text2, check2 = self.cut_all_text(
                        check2,
                        "(?:负责人.{0,15}|2、)(?:母公司资产负债表)$",
                        "(?:合并利润表)$",
                        all_text,
                        line_dict,
                        text2,
                    )
                    # 合并利润表
                    text3, check3 = self.cut_all_text(
                        check3,
                        "(?:负责人.{0,15}|3、)(?:合并利润表)$",
                        "(?:母公司利润表)$",
                        all_text,
                        line_dict,
                        text3,
                    )
                    # 母公司利润表
                    text4, check4 = self.cut_all_text(
                        check4,
                        "(?:负责人.{0,15}|4、)(?:母公司利润表)$",
                        "(?:合并现金流量表)$",
                        all_text,
                        line_dict,
                        text4,
                    )
                    # 合并现金流量表
                    text5, check5 = self.cut_all_text(
                        check5,
                        "(?:负责人.{0,15}|5、)(?:合并现金流量表)$",
                        "(?:母公司现金流量表)$",
                        all_text,
                        line_dict,
                        text5,
                    )
                    if re.search("(?:负责人.{0,15}|6、)(?:母公司现金流量表)$", all_text):
                        break

                except Exception:
                    print(line_dict)
                    pass

            cut1_len = len(text1.split("合并资产负债表")[0])
            # cut2_len = len(text2.split("母公司资产负债表")[0])
            cut3_len = len(text3.split("合并利润表")[0])
            # cut4_len = len(text4.split("母公司利润表")[0])
            cut5_len = len(text5.split("合并现金流量表")[0])

            # cut6_len = len(text6.split('母公司现金流量表')[0])
            # cut7_len = len(text7.split('合并所有者权益变动表')[0])
            # cut8_len = len(text8.split('母公司所有者权益变动表')[0])

            def check_data(answer_dict, text_check, addwords, stop_re):
                text_list = text_check.split("\n")
                data = []
                check_len = 0
                for _t in text_list:
                    if (
                        re.search("\['项目", _t)
                        and not re.search("调整数", _t)
                        and check_len == 0
                    ):
                        check_len = len(eval(_t))
                    if re.search("^[\[]", _t):
                        try:
                            text_l = eval(_t)
                            text_l[0] = (
                                text_l[0]
                                .replace(" ", "")
                                .replace("(", "（")
                                .replace(")", "）")
                                .replace(":", "：")
                                .replace("／", "/")
                            )
                            cut_re = re.match(
                                "(?:[一二三四五六七八九十]、|（[一二三四五六七八九十]）|\d\.|"
                                "加：|减：|其中：|（元/股）)",
                                text_l[0],
                            )
                            if cut_re:
                                text_l[0] = text_l[0].replace(cut_re.group(), "")
                            text_l[0] = text_l[0].split("（")[0]
                            if (
                                check_len != 0
                                and check_len == len(text_l)
                                and re.search("[\u4e00-\u9fa5]", text_l[0])
                            ):
                                data.append(text_l)
                        except Exception:
                            print(_t)
                    if data != [] and re.search(stop_re, _t):
                        break

                # print(data)
                if data != []:
                    df = pd.DataFrame(data[1:], columns=data[0])
                    df.replace("", "无", inplace=True)
                    if year + addwords in df.columns and "项目" in df.columns:
                        df = df.drop_duplicates(subset="项目", keep="first")
                        for key in answer_dict:
                            try:
                                match_answer = df[df["项目"] == key]
                                if not match_answer.empty and answer_dict[key] == "":
                                    answer_dict[key] = match_answer[
                                        year + addwords
                                    ].values[0]
                            except Exception:
                                print(key)
                return answer_dict

            answer_dict = check_data(answer_dict, text1[cut1_len:], "12月31日", "合并资产负债表")
            answer_dict = check_data(answer_dict, text3[cut3_len:], "度", "合并利润表")
            answer_dict = check_data(answer_dict, text5[cut5_len:], "度", "合并现金流量表")
            new_row = {
                "文件名": allname,
                "日期": date,
                "公司名称": name,
                "股票代码": stock,
                "股票简称": short_name,
                "年份": year,
                "类型": "年度报告",
                "合并资产负债表": text1[cut1_len:],
                "合并利润表": text3[cut3_len:],
                "合并现金流量表": text5[cut5_len:],
                "全文": str(lines),
            }
            for key in answer_dict:
                new_row[key] = answer_dict[key]
            print("finish " + self.file_name)
            return new_row

    # 提取其他列
    def extract_other_col(self):
        """Extract other col."""
        allname = self.file_name.split("\\")[-1]
        date, name, stock, short_name, year, else1 = allname.split("__")
        cut1, cut2, cut3, cut4, cut5, cut6, cut7, cut8, cut9, cut10 = (
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
        (
            check_cut1,
            check_cut2,
            check_cut3,
            check_cut4,
            check_cut5,
            check_cut6,
            check_cut7,
            check_cut8,
            check_cut9,
            check_cut10,
        ) = (False, False, False, False, False, False, False, False, False, False)
        cut11, cut12, cut13, cut14, cut15, cut16, cut17, cut18, cut19, cut20 = (
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
        (
            check_cut11,
            check_cut12,
            check_cut13,
            check_cut14,
            check_cut15,
            check_cut16,
            check_cut17,
            check_cut18,
            check_cut19,
            check_cut20,
        ) = (False, False, False, False, False, False, False, False, False, False)
        cut21, cut22, cut23, cut24, cut25, cut26, cut27 = (
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
        (
            check_cut21,
            check_cut22,
            check_cut23,
            check_cut24,
            check_cut25,
            check_cut26,
            check_cut27,
        ) = (False, False, False, False, False, False, False)
        with open(self.file_name, "r", encoding="utf-8") as file:

            lines = file.readlines()
            for i in range(len(lines)):
                line = lines[i]
                line = line.replace("\n", "")
                line_dict = json.loads(line)
                # print(line_dict)
                try:
                    if line_dict["type"] not in ["页眉", "页脚"]:

                        def check_answers(
                            answer,
                            keywords_re,
                            keywords_stop_re,
                            check_cut,
                            line_dict=line_dict,
                        ):
                            if (
                                check_cut is False
                                and answer == ""
                                and re.search(keywords_re, line_dict["inside"])
                            ):
                                check_cut = True
                                answer = str(line_dict["inside"]).replace("", "")
                            elif (
                                re.search(keywords_stop_re, line_dict["inside"])
                                or len(answer) >= 2000
                                or len(re.findall("是.否", answer)) >= 2
                                or len(re.findall("适用.不适用", answer)) >= 2
                                or len(re.findall("第(?:一|二|三|四|五|六|七|八|九|十)节", answer))
                                >= 2
                            ):
                                check_cut = False
                            elif check_cut:
                                answer = (
                                    answer
                                    + "\n"
                                    + str(line_dict["inside"]).replace("", "")
                                )
                            return answer, check_cut

                        def check_answers2(
                            answer,
                            keywords_re,
                            keywords_stop_re,
                            check_cut,
                            line_dict=line_dict,
                        ):
                            if (
                                check_cut is False
                                and answer == ""
                                and re.search(keywords_re, line_dict["inside"])
                            ):
                                check_cut = True
                                answer = str(line_dict["inside"]).replace("", "")
                            elif (
                                re.search(keywords_stop_re, line_dict["inside"])
                                or len(answer) >= 2000
                                or len(re.findall("第(?:一|二|三|四|五|六|七|八|九|十)节", answer))
                                >= 2
                            ):
                                check_cut = False
                            elif check_cut:
                                answer = (
                                    answer
                                    + "\n"
                                    + str(line_dict["inside"]).replace("", "")
                                )
                            return answer, check_cut

                        cut1, check_cut1 = check_answers(
                            cut1,
                            "(?:\.|、|\)|）)(?:审计意见|保留意见)$",
                            "(?:形成审计意见的基础|形成保留意见的基础)$",
                            check_cut1,
                        )
                        cut2, check_cut2 = check_answers(
                            cut2, "(?:关键审计事项)$", "(?:其他信息)$", check_cut2
                        )
                        cut3, check_cut3 = check_answers(
                            cut3, "主要会计数据和财务指标", "分季度主要财务指标", check_cut3
                        )
                        cut4, check_cut4 = check_answers(
                            cut4, "公司主要销售客户情况", "公司主要供应商情况", check_cut4
                        )
                        cut5, check_cut5 = check_answers(
                            cut5, "公司主要供应商情况", "研发投入|费用", check_cut5
                        )
                        cut6, check_cut6 = check_answers2(
                            cut6, "(?:研发投入|近三年公司研发投入金额及占营业收入的比例)$", "现金流", check_cut6
                        )
                        cut7, check_cut7 = check_answers(
                            cut7, "(?:现金流)$", "非主营业务情况", check_cut7
                        )
                        cut8, check_cut8 = check_answers(
                            cut8, "(?:资产及负债状况)$", "投资状况分析", check_cut8
                        )
                        cut9, check_cut9 = check_answers(
                            cut9, "重大资产和股权出售", "主要控股参股公司分析", check_cut9
                        )
                        cut10, check_cut10 = check_answers(
                            cut10, "主要控股参股公司分析", "公司未来发展的展望", check_cut10
                        )
                        cut11, check_cut11 = check_answers(
                            cut11, "公司未来发展的展望", "接待调研、沟通、采访等活动登记表", check_cut11
                        )
                        cut12, check_cut12 = check_answers(
                            cut12,
                            "与上年度财务报告相比，合并报表范围发生变化的情况说明",
                            "聘任、解聘会计师事务所情况",
                            check_cut12,
                        )
                        cut13, check_cut13 = check_answers2(
                            cut13,
                            "聘任、解聘会计师事务所情况",
                            "面临(?:暂停上市|终止上市|退市).{0,10}情况",
                            check_cut13,
                        )
                        cut14, check_cut14 = check_answers(
                            cut14,
                            "面临(?:暂停上市|终止上市|退市).{0,10}情况",
                            "破产重整相关事项",
                            check_cut14,
                        )
                        cut15, check_cut15 = check_answers(
                            cut15, "破产重整相关事项", "重大诉讼、仲裁事项", check_cut15
                        )
                        cut16, check_cut16 = check_answers(
                            cut16, "重大诉讼、仲裁事项", "处罚及整改情况", check_cut16
                        )
                        cut17, check_cut17 = check_answers(
                            cut17, "处罚及整改情况", "公司及其控股股东、实际控制人的诚信状况", check_cut17
                        )
                        cut18, check_cut18 = check_answers(
                            cut18,
                            "公司及其控股股东、实际控制人的诚信状况",
                            "公司股权激励计划、员工持股计划或其他员工激励措施的实施情况",
                            check_cut18,
                        )
                        cut19, check_cut19 = check_answers2(
                            cut19, "重大关联交易", "重大合同及其履行情况", check_cut19
                        )
                        cut20, check_cut20 = check_answers2(
                            cut20, "重大合同及其履行情况", "其他重大事项的说明", check_cut20
                        )
                        cut21, check_cut21 = check_answers(
                            cut21,
                            "重大环保问题|环境保护相关的情况",
                            "社会责任情况|重要事项|股份变动情况|其他重大事项的说明",
                            check_cut21,
                        )
                        cut22, check_cut22 = check_answers(
                            cut22, "社会责任情况", "重要事项|股份变动情况|其他重大事项的说明", check_cut22
                        )
                        cut23, check_cut23 = check_answers(
                            cut23, "公司董事、监事、高级管理人员变动情况", "任职情况", check_cut23
                        )
                        cut24, check_cut24 = check_answers2(
                            cut24, "公司员工情况", "培训计划", check_cut24
                        )
                        cut25, check_cut25 = check_answers(
                            cut25,
                            "对会计师事务所本报告期“非标准审计报告”的说明",
                            "董事会对该事项的意见|独立董事意见|监事会意见|消除有关事项及其影响的" "具体措施",
                            check_cut25,
                        )
                        cut26, check_cut26 = check_answers(
                            cut26, "公司控股股东情况", "同业竞争情况|重大事项", check_cut26
                        )
                        cut27, check_cut27 = check_answers(
                            cut27,
                            "(?:\.|、|\)|）)(?:审计报告)$",
                            "审计报告正文|(?:\.|、|\)|）)(?:审计意见|保留意见)$",
                            check_cut27,
                        )

                except Exception:
                    logger.error(line_dict)
        new_row = {
            "文件名": allname,
            "日期": date,
            "公司名称": name,
            "股票代码": stock,
            "股票简称": short_name,
            "年份": year,
            "类型": "年度报告",
            "审计意见": cut1,
            "关键审计事项": cut2,
            "主要会计数据和财务指标": cut3,
            "主要销售客户": cut4,
            "主要供应商": cut5,
            "研发投入": cut6,
            "现金流": cut7,
            "资产及负债状况": cut8,
            "重大资产和股权出售": cut9,
            "主要控股参股公司分析": cut10,
            "公司未来发展的展望": cut11,
            "合并报表范围发生变化的情况说明": cut12,
            "聘任、解聘会计师事务所情况": cut13,
            "面临退市情况": cut14,
            "破产重整相关事项": cut15,
            "重大诉讼、仲裁事项": cut16,
            "处罚及整改情况": cut17,
            "公司及其控股股东、实际控制人的诚信状况": cut18,
            "重大关联交易": cut19,
            "重大合同及其履行情况": cut20,
            "重大环保问题": cut21,
            "社会责任情况": cut22,
            "公司董事、监事、高级管理人员变动情况": cut23,
            "公司员工情况": cut24,
            "非标准审计报告的说明": cut25,
            "公司控股股东情况": cut26,
            "审计报告": cut27,
            "全文": str(lines),
        }
        print("finished " + self.file_name)
        return new_row
