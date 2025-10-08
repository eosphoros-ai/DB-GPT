class ExcelUtils:
    @staticmethod
    def get_cell_value_as_string(cell) -> str:
        if cell is None:
            return ""
        value = cell.value
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def is_row_empty(row) -> bool:
        if row is None:
            return True
        return all(cell.value is None or str(cell.value).strip() == "" for cell in row)
