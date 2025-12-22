from typing import Optional

from dbgpt_serve.evaluate.service.benchmark.models import FileParseTypeEnum


class StorageUtil:
    """
    Storage-related utility class
    """

    YUQUE_URL_PREFIX = "https://yuque.com"

    GITHUB_FALCON_PREFIX = "https://github.com/eosphoros-ai/Falcon"

    @staticmethod
    def get_file_parse_type(file_path: Optional[str]) -> FileParseTypeEnum:
        """Get file parsing type based on file path

        Args:
            file_path: File path or URL

        Returns:
            FileParseTypeEnum: File parsing type enumeration

        Raises:
            ValueError: When file_path is empty or None
        """
        if not file_path or file_path.strip() == "":
            raise ValueError("filePath is null")

        if file_path.strip().startswith(StorageUtil.YUQUE_URL_PREFIX):
            return FileParseTypeEnum.YU_QUE
        if file_path.strip().startswith(StorageUtil.GITHUB_FALCON_PREFIX):
            return FileParseTypeEnum.GITHUB

        return FileParseTypeEnum.EXCEL
