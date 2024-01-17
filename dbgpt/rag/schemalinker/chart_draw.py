from typing import Optional

from dbgpt.datasource.rdbms.base import RDBMSDatabase


class ChartDraw:
    """Chart Draw"""

    def __init__(self, connection: Optional[RDBMSDatabase] = None, **kwargs):
        """
        Args:
            connection (Optional[RDBMSDatabase]): RDBMSDatabase connection
        """
        super().__init__(**kwargs)
        self._connection = connection

    def chart_draw(self, sql: str) -> str:
        """get chart data and draw by matplotlib
        Args:
            sql (str): sql text
        """
        # df: (Pandas) DataFrame
        df = self._connection.run_to_df(command=sql, fetch="all")
        # draw chart
        import matplotlib.pyplot as plt

        category_column = df.columns[0]
        count_column = df.columns[1]
        plt.figure(figsize=(8, 4))
        plt.bar(df[category_column], df[count_column])
        plt.xlabel(category_column)
        plt.ylabel(count_column)
        plt.show()
        return str(df)
