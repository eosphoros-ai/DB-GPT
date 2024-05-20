import logging
from decimal import Decimal
from typing import List

from dbgpt._private.config import Config
from dbgpt.app.scene.chat_dashboard.data_preparation.report_schma import ValueItem

CFG = Config()
logger = logging.getLogger(__name__)


class DashboardDataLoader:
    def get_sql_value(self, db_conn, chart_sql: str):
        return db_conn.query_ex(chart_sql)

    def get_chart_values_by_conn(self, db_conn, chart_sql: str):
        field_names, datas = db_conn.query_ex(chart_sql)
        return self.get_chart_values_by_data(field_names, datas, chart_sql)

    def get_chart_values_by_data(self, field_names, datas, chart_sql: str):
        logger.info(f"get_chart_values_by_conn:{chart_sql}")
        # try:
        values: List[ValueItem] = []
        data_map = {}

        data_map.update(
            {
                f"{field_name}": [row[index] for row in datas]
                for index, field_name in enumerate(field_names)
            }
        )
        # to Check Whether there are data in it
        if len(datas) != 0:
            # find the first string column
            str_index = next(
                (
                    index
                    for index, value in enumerate(datas[0])
                    if isinstance(value, str)
                ),
                1,
            )
            if type(datas[0][str_index]) == str:
                tempFieldName = field_names[:str_index]
                tempFieldName.extend(field_names[str_index + 1 :])
                for field_name in tempFieldName:
                    for data in datas:
                        # None Data won't be ok for the chart
                        if not any(item is None for item in data):
                            value_item = ValueItem(
                                name=data[str_index],
                                type=field_name,
                                value=str(data[field_names.index(field_name)]),
                            )
                            values.append(value_item)
                        else:
                            value_item = ValueItem(
                                name=data[str_index],
                                type=field_name,
                                value="0",
                            )
                            values.append(value_item)
            else:
                result = [sum(values) for values in zip(*datas)]
                for index, field_name in enumerate(field_names):
                    value_item = ValueItem(
                        name=field_name,
                        type=f"{field_name}_count",
                        value=str(result[index]),
                    )
                    values.append(value_item)
            return field_names, values
        else:
            return field_names, [
                ValueItem(name=f"{field_name}", type=f"{field_name}", value="0")
                for index, field_name in enumerate(field_names)
            ]

    def get_chart_values_by_db(self, db_name: str, chart_sql: str):
        logger.info(f"get_chart_values_by_db:{db_name},{chart_sql}")
        db_conn = CFG.local_db_manager.get_connector(db_name)
        return self.get_chart_values_by_conn(db_conn, chart_sql)
