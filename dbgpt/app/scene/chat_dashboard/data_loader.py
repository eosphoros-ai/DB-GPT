import datetime
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
        try:
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
                # try to find string index
                string_index = next(
                    (
                        index
                        for index, value in enumerate(datas[0])
                        if isinstance(value, str)
                    ),
                    -1,
                )

                # try to find datetime index
                datetime_index = next(
                    (
                        index
                        for index, value in enumerate(datas[0])
                        if isinstance(value, (datetime.date, datetime.datetime))
                    ),
                    -1,
                )

                # on the other aspect the primary key including "id"
                id_index = next(
                    (index for index, value in enumerate(field_names) if "id" in value),
                    -1,
                )
                # while there are no datetime and there are no string
                if string_index == -1 and datetime_index == -1 and id_index == -1:
                    # ignore Null Value in the data
                    result = [
                        sum(values for values in data if values is not None)
                        for data in zip(*datas)
                    ]
                    for index, field_name in enumerate(field_names):
                        value_item = ValueItem(
                            name=field_name,
                            type=f"{field_name}_amount",
                            value=str(result[index]),
                        )
                        values.append(value_item)

                # there are string index (or/and) datetime; first choose string->datetime->id
                else:
                    # triple judge index
                    primary_index = (
                        string_index
                        if string_index != -1
                        else (datetime_index if datetime_index != -1 else id_index)
                    )
                    temp_field_name = field_names[:primary_index]
                    temp_field_name.extend(field_names[primary_index + 1 :])
                    for field_name in temp_field_name:
                        for data in datas:
                            # None Data won't be ok for the chart
                            if not any(item is None for item in data):
                                value_item = ValueItem(
                                    name=str(data[primary_index]),
                                    type=field_name,
                                    value=str(data[field_names.index(field_name)])
                                    if not isinstance(
                                        type(data[field_names.index(field_name)]),
                                        (datetime.datetime, datetime.date),
                                    )
                                    else str(
                                        data[field_names.index(field_name)].strftime(
                                            "%Y%m%d"
                                        )
                                    ),
                                )
                                values.append(value_item)

                            # handle None Data as "0" for number and "19700101" for datetime
                            else:
                                value_item = ValueItem(
                                    name=data[string_index],
                                    type=field_name,
                                    value="0"
                                    if not isinstance(
                                        type(data[field_names.index(field_name)]),
                                        (datetime.datetime, datetime.date),
                                    )
                                    else "19700101",
                                )
                                values.append(value_item)
            return field_names, values
        except Exception as e:
            logger.exception(f"get_chart_values_by_conn failed:{str(e)}")
            raise e

    def get_chart_values_by_db(self, db_name: str, chart_sql: str):
        logger.info(f"get_chart_values_by_db:{db_name},{chart_sql}")
        db_conn = CFG.local_db_manager.get_connector(db_name)
        return self.get_chart_values_by_conn(db_conn, chart_sql)
