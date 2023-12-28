import logging
import os
import oss2
import uuid
from datetime import datetime
from oss2.credentials import EnvironmentVariableCredentialsProvider

from pilot.configs.config import Config

logger = logging.getLogger(__name__)
CFG = Config()

os.environ['OSS_ACCESS_KEY_ID'] = CFG.OSS_ACCESS_KEY_ID
os.environ['OSS_ACCESS_KEY_SECRET'] = CFG.OSS_ACCESS_KEY_SECRET


def generate_oss_key(filename: str):
    """
        generate oss key by file name, timestamp + filename + uuid(32)
    """
    timestamp_millis = int(datetime.now().timestamp() * 1000)

    unique_id = uuid.uuid4().hex

    unique_filename = f"{timestamp_millis}_{filename}_{unique_id}"

    return unique_filename


def put_obj_from_file(oss_key: str, local_file_path, bucket_name: str):
    """
        upload local file to oss, you should give the oss file path, local file path and bucket,
        ensure oss_file_path is unique address and not exist, otherwise upload will raise exception.

        oss_file_path and local_file_path should contain postfix of file such as '.txt'

        params:
        oss_key: generate a unique key for current file
        local_file_path -- file to upload
        bucket_name
    """
    try:
        auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
        bucket = oss2.Bucket(auth, CFG.OSS_ENDPOINT, bucket_name)
        resp = bucket.put_object_from_file(oss_key, local_file_path)
        return resp is not None and resp.status == 200
    except Exception as ex:
        err_info = f"upload file failed: {str(ex)}"
        logger.error(err_info)
        raise err_info


def get_object_to_file(oss_key: str, local_file_path, bucket: str):
    """
        download file from oss
        params:
        oss_key -- oss_key file to download
        local_file_path -- local file path
        bucket_name
    """
    auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
    bucket = oss2.Bucket(auth, CFG.OSS_ENDPOINT, bucket)
    resp = bucket.get_object_to_file(oss_key, local_file_path)
    return resp is not None and resp.status == 200


def delete_object(oss_key: str, bucket_name: str):
    """
        delete oss file by oss_key.

        params:
        oss_key -- file key to delete
        bucket_name
    """
    auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
    bucket = oss2.Bucket(auth, CFG.OSS_ENDPOINT, bucket_name)
    dr = bucket.delete_object(oss_key)
    print(dr)


def get_download_url_with_timeout(oss_file_key: str, time_seconds: int, bucket_name: str):
    """
    get download url with timeout
    params:
        oss_file_key: osskey
        time_seconds: valid seconds.
        bucket_name: bucket
    """
    auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
    bucket = oss2.Bucket(auth, CFG.OSS_ENDPOINT, bucket_name)
    download_url = bucket.sign_url('GET', oss_file_key, time_seconds)
    return download_url


def delete_file(file_path):
    """
    delete local file

    params:
    file_path -- file to delete
    """

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Can not delete file `{file_path}` Error: {e}")
    else:
        print(f"File {file_path} is not exist!")
