from typing import List
from decimal import Decimal
import logging

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
            field_map = {}
            index = 0
            for field_name in field_names:
                data_map.update({f"{field_name}": [row[index] for row in datas]})
                index += 1
                if not data_map[field_name]:
                    field_map.update({f"{field_name}": False})
                else:
                    field_map.update(
                        {
                            f"{field_name}": all(
                                isinstance(item, (int, float, Decimal))
                                for item in data_map[field_name]
                            )
                        }
                    )

            for field_name in field_names[1:]:
                if not field_map[field_name]:
                    logger.info("More than 2 non-numeric column:" + field_name)
                else:
                    for data in datas:
                        value_item = ValueItem(
                            name=data[0],
                            type=field_name,
                            value=data[field_names.index(field_name)],
                        )
                        values.append(value_item)
            return field_names, values
        except Exception as e:
            logger.debug("Prepare Chart Data Failed!" + str(e))
            raise ValueError("Prepare Chart Data Failed!")

    def get_chart_values_by_db(self, db_name: str, chart_sql: str):
        logger.info(f"get_chart_values_by_db:{db_name},{chart_sql}")
        db_conn = CFG.LOCAL_DB_MANAGE.get_connect(db_name)
        return self.get_chart_values_by_conn(db_conn, chart_sql)
