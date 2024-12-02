import json
import logging
import xml.etree.ElementTree as ET
from typing import Dict, NamedTuple

import numpy as np
import pandas as pd
import sqlparse

from dbgpt._private.config import Config
from dbgpt.core.interface.output_parser import BaseOutputParser
from dbgpt.util.json_utils import serialize

from ...exceptions import AppActionException

CFG = Config()


class SqlAction(NamedTuple):
    sql: str
    thoughts: Dict
    display: str

    def to_dict(self) -> Dict[str, Dict]:
        return {
            "sql": self.sql,
            "thoughts": self.thoughts,
            "display": self.display,
        }


logger = logging.getLogger(__name__)


class DbChatOutputParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def is_sql_statement(self, statement):
        parsed = sqlparse.parse(statement)
        if not parsed:
            return False
        for stmt in parsed:
            if stmt.get_type() != "UNKNOWN":
                return True
        return False

    def parse_prompt_response(self, model_out_text):
        clean_str = super().parse_prompt_response(model_out_text)
        logger.info(f"clean prompt response: {clean_str}")
        # Compatible with community pure sql output model
        if self.is_sql_statement(clean_str):
            return SqlAction(clean_str, "", "")
        else:
            try:
                response = json.loads(clean_str, strict=False)
                for key in sorted(response):
                    if key.strip() == "sql":
                        sql = response[key]
                    if key.strip() == "thoughts":
                        thoughts = response[key]
                    if key.strip() == "display_type":
                        display = response[key]
                return SqlAction(sql, thoughts, display)
            except Exception as e:
                logger.error(f"json load failed:{clean_str}")
                return SqlAction("", clean_str, "")
    
    def parse_vector_data_with_pca(self, df):
        try:
            from sklearn.decomposition import PCA
        except ImportError:
            raise ImportError(
                "Could not import scikit-learn package. "
                "Please install it with `pip install scikit-learn`."
            )
        
        _, ncol = df.shape
        vec_col = -1
        for i_col in range(ncol):
            if isinstance(df.iloc[:, i_col][0], list):
                vec_col = i_col
                break
            elif isinstance(df.iloc[:, i_col][0], bytes):
                sample = df.iloc[:, i_col][0]
                if isinstance(json.loads(sample.decode()), list):
                    vec_col = i_col
                    break
        if vec_col == -1:
            return df
        df.iloc[:, vec_col] = df.iloc[:, vec_col].apply(lambda x: json.loads(x.decode()))
        X = np.array(df.iloc[:, vec_col].tolist())

        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X)

        new_df = pd.DataFrame()
        for i_col in range(ncol):
            if i_col == vec_col:
                continue
            col_name = df.columns[i_col]
            new_df[col_name] = df[col_name]
        new_df["__x"] = [pos[0] for pos in X_pca]
        new_df["__y"] = [pos[1] for pos in X_pca]
        return new_df

    def parse_view_response(self, speak, data, prompt_response) -> str:
        param = {}
        api_call_element = ET.Element("chart-view")
        err_msg = None
        success = False
        try:
            if not prompt_response.sql or len(prompt_response.sql) <= 0:
                raise AppActionException("Can not find sql in response", speak)

            df = data(prompt_response.sql)
            param["type"] = prompt_response.display
            
            if param["type"] == "response_vector_chart":
                df = self.parse_vector_data_with_pca(df)
                param["type"] = "response_scatter_chart"

            param["sql"] = prompt_response.sql
            param["data"] = json.loads(
                df.to_json(orient="records", date_format="iso", date_unit="s")
            )
            view_json_str = json.dumps(param, default=serialize, ensure_ascii=False)
            success = True
        except Exception as e:
            logger.error("parse_view_response error!" + str(e))
            err_param = {
                "sql": f"{prompt_response.sql}",
                "type": "response_table",
                "data": [],
            }
            # err_param["err_msg"] = str(e)
            err_msg = str(e)
            view_json_str = json.dumps(err_param, default=serialize, ensure_ascii=False)

        # api_call_element.text = view_json_str
        api_call_element.set("content", view_json_str)
        result = ET.tostring(api_call_element, encoding="utf-8")
        if not success:
            view_content = (
                f'{speak} \\n <span style="color:red">ERROR!</span>'
                f"{err_msg} \n {result.decode('utf-8')}"
            )
            raise AppActionException("Generate view content failed", view_content)
        else:
            return speak + "\n" + result.decode("utf-8")
