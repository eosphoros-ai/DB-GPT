class FileClient:
    async def read_file(self, conv_uid, file_key, is_oss: bool = False) -> str:
        return None

    async def write_file(
        self, conv_uid, file_name, content, is_increment: bool = False
    ):
        oss_key = f"{conv_uid}_{file_name}"

        return False, oss_key

    async def delete_file(self, conv_uid, file_key, is_oss: bool = False):
        return None
