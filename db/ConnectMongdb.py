# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2023/9/3 18:51
'''
import pickle
import socket
from copy import deepcopy
from datetime import datetime
import os, sys
import gridfs


def get_local_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        local_ip = sock.getsockname()[0]
        return local_ip
    except Exception as e:
        print(e)
    finally:
        # socket.close(0)
        pass


if get_local_ip() == '172.23.52.25' or get_local_ip() == '172.23.52.26':
    mode = 'dev'
else:
    mode = 'prd'

if mode == 'dev':
    from configs.MongdbConfig_test import ip, username, password, authSource, mongo_collection, mongo_database, \
        chat_history_number, memory_collection, dataanalysisprompt, atl_custome_app, organizations_collection_name, \
        users_collection_name, dbgpt_db_collection
else:
    from configs.MongdbConfig import ip, username, password, authSource, mongo_collection, mongo_database, \
        chat_history_number, memory_collection, dataanalysisprompt, atl_custome_app, organizations_collection_name, \
        users_collection_name, dbgpt_db_collection

# from utils.Tools import calLeadTimeByColor

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pymongo import MongoClient, ASCENDING

from bson import ObjectId


class MyMongdb():
    def __init__(self, userId=''):
        self.chats_history_number = chat_history_number
        self.client = MongoClient(f"mongodb://{ip}",
                                  username=username,
                                  password=password,
                                  authSource=authSource,
                                  authMechanism='SCRAM-SHA-256')
        self.mongo_database = mongo_database
        self.memory_collection_name = memory_collection
        self.dbgpt_db_collection_name = dbgpt_db_collection
        self.mongo_collection_name = mongo_collection
        self.prompt_collection_name = dataanalysisprompt
        self.atl_custome_app_collection_name = atl_custome_app
        self.organizations_collection_name = organizations_collection_name
        self.users_collection_name = users_collection_name
        self.userId = userId
        self.fs = gridfs.GridFS(self.client[mongo_database])

    def set_chatId(self, chatId):
        self.chatId = chatId

    def set_dataId(self, dataId):
        self.dataId = dataId

    def get_operate_time(self):
        operation_dt_now = datetime.now()
        self.operation_dt = operation_dt_now.strftime("%Y/%m/%d %H:%M:%S")

    def prepare_data(self, who='human', response_dict={}):

        self.get_operate_time()
        self.insert_new_one = {'obj': who,
                               'value': 'response',
                               'quote': [],
                               'systemPrompt': '',
                               'visible': True,
                               'responseTime': 0,
                               'responseTimeAll': 0,
                               'chatTime': self.operation_dt,
                               '_id': ObjectId()}
        self.insert_new_one.update(response_dict)

    def get_history(self):
        self.locate_condition()
        if not self.condition: return ''

        self.history = [{'role': i['obj'], 'elements': i['value']} for i in
                        self.condition['content'][self.condition['history_index']:]]
        return self.history

    def locate_condition(self):
        db = self.client[self.mongo_database]

        self.collection = db[self.mongo_collection_name]
        self.condition = self.collection.find_one({'_id': ObjectId(self.chatId), 'userId': ObjectId(
            self.userId)}) if self.userId else self.collection.find_one({'_id': ObjectId(self.chatId)})

    def update_one_record(self, who='human', content={}):
        self.prepare_data(who=who, response_dict=content)
        self.locate_condition()
        self.collection.update_one(self.condition, {'$push': {'content': self.insert_new_one}})
        if who.lower() in ('human', 'user'):
            self.collection.update_one(self.condition, {'$set': {'title': content['value']}})
        if who.lower() in ('ai', 'system', 'assistant'):
            self.collection.update_one(self.condition, {'$set': {'latestChat': content['value']}})

    def close(self):
        self.client.close()

    def uploadDataFrame(self, df):
        # 取哈希值的前12个字节，转换为ObjectId
        self.object_id = ObjectId(self.chatId)

        if not (res := self.fs.exists(_id=self.object_id)):
            self.fs.put(pickle.dumps(df), _id=self.object_id, chatId=self.object_id, userId=self.userId)
        print('upload to mongodb')
        return self.chatId

    def uploadDataFrameByDataId(self, df):
        # 取哈希值的前12个字节，转换为ObjectId
        self.object_id = ObjectId(self.dataId)

        if not (res := self.fs.exists(_id=self.object_id)):
            self.fs.put(pickle.dumps(df), _id=self.object_id, chatId=self.object_id, userId=self.userId)
        print('upload to mongodb')
        return self.chatId

    def uploadDataFrameByInfo(self, df, department, data_source, start_time, end_time):

        # 取哈希值的前24个字节，转换为ObjectId
        data_id = ObjectId(self.dataId)
        self.fs.put(pickle.dumps(df), _id=data_id, department=department, data_source=data_source,
                    start_time=start_time, end_time=end_time)
        print('upload to mongodb by dataid')
        return data_id

    def uploadFileFS(self, file):
        # 取哈希值的前12个字节，转换为ObjectId
        self.object_id = ObjectId(self.chatId)
        if not (res := self.fs.exists(_id=self.object_id)):
            self.fs.put(pickle.dumps(file[0]), _id=self.object_id, filename=file[0].name, chatId=self.object_id,
                        userId=self.userId)
        print('upload to mongodb')
        return self.chatId

    def existFSFile(self):
        return self.fs.exists(_id=ObjectId(self.dataId))

    def getFSFile(self, _id):
        return self.fs.get(_id)

    # @calLeadTimeByColor(color=33)
    def getFSDataFrame(self):
        fs_stream = self.fs.get(ObjectId(self.dataId)).read()
        res = pickle.loads(fs_stream)
        return res

    def chat_exists(self, chat_id):
        self.locate_condition()
        is_exists = self.collection.find_one({"_id": ObjectId(chat_id)})
        return is_exists

    def init_chat_history(self):
        init_dict = {'_id': ObjectId(self.chatId),
                     'userId': ObjectId(self.userId),
                     'loadAmount': -1,
                     'title': '',
                     'customTitle': '',
                     'latestChat': '',
                     'content': [],
                     'expiredTime': '',
                     'updateTime': '',
                     'history_index': 0,
                     'app': 'data_analyze',
                     'uploadFilesId': [],
                     'systemMessage': [],
                     '__v': '',
                     'chat_messages': ''
                     }
        self.locate_condition()
        if self.chatId != '' and not self.condition:
            self.collection.insert_one(init_dict)

    def setClear(self):
        self.locate_condition()
        content_len = len(self.condition['content'])
        self.collection.update_one(self.condition, {'$set': {'history_index': content_len}})
        print('set history index')

    def deleteFS(self, data_id):
        self.fs.delete(ObjectId(data_id))

    def findFS(self):
        '''bk FS find code'''
        start_time = datetime(2023, 10, 17)
        end_time = datetime(2023, 10, 20)
        uploaded_files = self.fs.find({"uploadDate": {"$gte": start_time, "$lte": end_time}}).sort('uploadDate',
                                                                                                   ASCENDING).allow_disk_use(
            True)
        for f in uploaded_files:
            print(f.userId)

    def memory_condition(self):

        db = self.client[self.mongo_database]
        self.memory_collection = db[self.memory_collection_name]

    def promptExists(self, prompt):
        find_one = {'prompt': prompt.strip(),
                    'data_id': ObjectId(self.dataId),
                    }
        prompt_exists = self.memory_collection.find_one(find_one)
        return prompt_exists

    def insertPromptMemory(self, prompt, answer, data_source, department):
        init_dict = {'data_id': ObjectId(self.dataId),
                     'data_source': data_source,
                     'department': department,
                     'prompt': prompt.strip(),
                     'answer': answer.strip(),
                     'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                     }

        self.memory_collection.insert_one(init_dict)

    def getPromptMemory(self, prompt):
        init_dict = {'data_id': ObjectId(self.dataId),
                     'prompt': prompt.strip(),
                     }

        return self.memory_collection.find_one(init_dict)

    def uploadPicFS(self, pic_path):
        with open(pic_path, 'rb') as f:
            contents = f.read()
        self.fs.put(contents, pic_path=pic_path)

    def getPicFS(self, pic_path):

        content = self.fs.find_one({'pic_path': pic_path})
        return content

    def promptInit(self):
        db = self.client[self.mongo_database]
        self.prompt_collection = db[self.prompt_collection_name]

    def setPromptList(self, promp_dict):
        self.promptInit()
        '''
        {'department':
            {'module':
                {'columns':
                    [
                        {'key':'简写', 'value':'繁写'},
                        {'key':'简写1', 'value':'繁写1'},
                    ]
                }
            }
        }
        '''

        document = deepcopy(promp_dict)
        del document['create_time']
        del document['update_time']
        if not self.prompt_collection.find_one(document):
            self.prompt_collection.insert_one(promp_dict)

    def getPromptList(self, department, module):
        self.promptInit()
        res = self.prompt_collection.find({
            'department': department,
            'module': module,
            'isshow': 'true',
            'create_time': {'$regex': '.*'},
        })
        res.sort('create_time', -1)
        return res

    def delPrompt(self, prompt_dict):
        self.promptInit()
        res = self.prompt_collection.find_one(prompt_dict)
        if res is None: return
        document = deepcopy(res)
        document['isshow'] = 'false'
        document['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        res = self.prompt_collection.replace_one(res, document)
        return res

    def registApp(self, address='质量', name='数据分析', intro="这个是质量数据分析", mode='add'):
        db = self.client[self.mongo_database]
        self.atl_custome_app_collection = db[self.atl_custome_app_collection_name]

        if mode == 'remove':
            self.atl_custome_app_collection.delete_one({'address': address})
            return f"{address} App already {mode} !!"
        regist_dict = {
            'name': name,
            'avatar': '/icon/logo.png',
            'share': {
                'isShare': False,
                'isShareDetail': False,
                'intro': '',
                'collection': 1,
                'sharedUser': [],
                'sharedDepartment': [],
            },
            'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'createTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '__v': 1,
            'intro': intro,
            'mobileVisible': True,
            'address': address,
            'admin': [''],
        }

        # if not self.atl_custome_app_collection.find({'address':department}):

        regist = deepcopy(regist_dict)

        if not self.atl_custome_app_collection.find_one({'address': address}):
            self.atl_custome_app_collection.insert_one(regist_dict)
        else:
            del regist['createTime']
            self.atl_custome_app_collection.update_one({'address': address}, {'$set': regist})
        return f"{address} App already {mode} !!"

    def getOrganizations(self):
        db = self.client[self.mongo_database]
        self.organizations_collection = db[self.organizations_collection_name]
        return self.organizations_collection.find()

    def getUsers(self):
        db = self.client[self.mongo_database]
        self.users_collection = db[self.users_collection_name]
        return self.users_collection.find()

    def getAppsRight(self, address):
        db = self.client[self.mongo_database]
        self.atl_custome_app_collection = db[self.atl_custome_app_collection_name]
        return self.atl_custome_app_collection.find_one({
            'address': address
        })

    def objectIdToUserOrDepartment(self, who='user', Object_ids=[]):
        Object_ids = [ObjectId(i) for i in Object_ids]
        db = self.client[self.mongo_database]
        self.atl_custome_app_collection = db[self.atl_custome_app_collection_name]
        if who == 'user':
            self.collection_name = db[self.users_collection_name]
        if who == 'department':
            self.collection_name = db[self.organizations_collection_name]
        results = self.collection_name.find({'_id': {'$in': Object_ids}})
        return results

    def updateAppRight(self, address, list_temp=[], who='user', mode='add'):
        db = self.client[self.mongo_database]
        self.atl_custome_app_collection = db[self.atl_custome_app_collection_name]
        print(self.atl_custome_app_collection)
        if who == 'department' and mode == 'add':
            res = self.atl_custome_app_collection.update_one({'address': address},
                                                             {'$addToSet': {
                                                                 'share.sharedDepartment': {'$each': list_temp}}},
                                                             upsert=True)
        if who == 'user' and mode == 'add':
            res = self.atl_custome_app_collection.update_one({'address': address},
                                                             {'$addToSet': {'share.sharedUser': {'$each': list_temp}}},
                                                             upsert=True)

        if who == 'department' and mode == 'remove':
            res = self.atl_custome_app_collection.update_one({'address': address},
                                                             {'$pullAll': {'share.sharedDepartment': list_temp}})
        if who == 'user' and mode == 'remove':
            res = self.atl_custome_app_collection.update_one({'address': address},
                                                             {'$pullAll': {'share.sharedUser': list_temp}})
        if who == 'department' and mode == 'clearAll':
            res = self.atl_custome_app_collection.update_one({'address': address},
                                                             {'$set': {'share.sharedDepartment': []}})
        if who == 'user' and mode == 'clearAll':
            res = self.atl_custome_app_collection.update_one({'address': address},
                                                             {'$set': {'share.sharedUser': []}})

        # 检查操作是否被确认
        print("Acknowledged:", res.acknowledged)

        # 检查匹配的文档数量
        print("Matched Count:", res.matched_count)

        # 检查被修改的文档数量
        print("Modified Count:", res.modified_count)

        # 检查是否有upsert操作，并得到插入文档的_id
        print("Upserted ID:", res.upserted_id)

        if res.acknowledged:
            return {'message': 'ok', 'modify_count': res.modified_count}
        else:
            return {'message': 'ng'}

    def init_shared(self):
        db = self.client[self.mongo_database]
        self.users_collection = db[self.users_collection_name]
        return self.users_collection.find({'dataAuth': 'y'})

    def userIdGetId(self, ids=[]):
        db = self.client[self.mongo_database]
        self.users_collection = db[self.users_collection_name]

        def append_zero(i_temp):
            i_temp = str(i_temp)
            if len(i_temp) < 8:
                i_temp = '0' * (8 - len(i_temp)) + i_temp
            return i_temp

        in_list = [append_zero(i) for i in ids]
        return self.users_collection.find({'username': {'$in': in_list}})

    def get_init_class_messages(self):
        self.locate_condition()
        chat_messages = self.condition.get('chat_messages', '')

        if chat_messages != '':
            chat_messages = pickle.loads(chat_messages)
        return chat_messages

    def set_class_messages(self, chat_messages):
        db = self.client[self.mongo_database]

        self.collection = db[self.mongo_collection_name]
        res = self.collection.update_one({'_id': ObjectId(self.chatId)},
                                         {'$set': {'chat_messages': pickle.dumps(chat_messages)}})
        if res.modified_count > 0:
            return 'OK'
        else:
            return 'NG'

    def get_datasource_by_data_id(self):
        fs_info = self.fs.find_one({'_id': ObjectId(self.dataId)})
        return fs_info

    def get_fs_by_department_and_datasource(self, datasource, department='质量'):
        return self.fs.find({'data_source': datasource, 'department': department})

    def delete_chat_memory(self, datasource, department='质量'):
        # 删除聊天记录
        db = self.client[self.mongo_database]

        self.collection = db[self.memory_collection_name]
        query = {'data_source': datasource, 'department': department}
        # 使用 find 方法查询文档但不删除
        documents = self.collection.find(query)
        print(query)
        for document in documents:
            print(document)
        result = self.collection.delete_many(query)
        return result

    def check_user_app_permission(self, department, user_id):
        db = self.client[self.mongo_database]
        self.atl_custome_app_collection = db[self.atl_custome_app_collection_name]
        result = self.atl_custome_app_collection.find_one({'name': department, 'share.sharedUser': user_id})
        self.users_collection = db[self.users_collection_name]
        result2 = self.users_collection.find_one({'_id': ObjectId(user_id), 'dataAuth': 'y'})
        print(result2)
        return True if result or result2 else False

    def check_manage_app_permission(self, department, user_id):
        db = self.client[self.mongo_database]
        self.atl_custome_app_collection = db[self.atl_custome_app_collection_name]
        result = self.atl_custome_app_collection.find_one({'name': department, 'admin': user_id})
        self.users_collection = db[self.users_collection_name]
        result2 = self.users_collection.find_one({'_id': ObjectId(user_id), 'dataAuth': 'y'})
        return True if result or result2 else False

    def updateDataAppRight(self, department, user_id_list=[], mode='add'):
        '''
        变更某个用户的数据分析的管理员权限
        ['64ae505e74c3cc80266ee97b', '64ae506474c3cc80266eefaa']
        皮建雅                         李秋盈
        '''
        if mode not in ['add', 'remove']: return 'mode is error ,it must be in ["add","remove"]'
        # user_id_list = [ObjectId(id) for id in user_id_list]
        db = self.client[self.mongo_database]
        self.users_collection = db[self.users_collection_name]
        #
        # update_filter = {'_id': {'$in': user_id_list}}  # 更新所有文档，如果需要指定条件，可以修改这个字典
        # 指定要更新的内容
        # update_data = {'$set': {'dataAuth': 'y' else 'n'}}

        # 使用update_many()批量更新多个文档
        self.atl_custome_app_collection = db[self.atl_custome_app_collection_name]
        if mode == 'add':
            res = self.atl_custome_app_collection.update_one({'address': department},
                                                             {'$addToSet': {
                                                                 'admin': {'$each': user_id_list}}},
                                                             upsert=True)
        elif mode == 'remove':
            res = self.atl_custome_app_collection.update_one({'address': department},
                                                             {'$pullAll': {'admin': user_id_list}})

        # 输出结果
        return f'Modified {res.modified_count} documents.'

    def create_db(self):
        '''
        dbgpt -- create db
        '''
        db = self.client[self.mongo_database]
        self.dbgpt_db = db[self.dbgpt_db_collection_name]
        self.condition = self.dbgpt_db.find_one({'_id': ObjectId(self.chatId), 'userId': ObjectId(
            self.userId)}) if self.userId else self.collection.find_one({'_id': ObjectId(self.chatId)})

    def registDBGPTDB(self, address='hr_chinese_fk', name='hr_chinese_fk', intro="这个是质量数据分析", mode='add'):
        db = self.client[self.mongo_database]
        self.dbgpt_db = db[self.dbgpt_db_collection_name]

        if mode == 'remove' or mode == 'delete' :
            self.dbgpt_db.delete_one({'address': address})
            return f"{address} App already {mode} !!"
        regist_dict = {
            'name': name,
            'user_id':self.userId,
            'avatar': '/icon/logo.png',
            'share': {
                'isShare': False,
                'isShareDetail': False,
                'intro': '',
                'collection': 1,
                'sharedUser': [],
                'sharedDepartment': [],
            },
            'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'createTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '__v': 1,
            'intro': intro,
            'mobileVisible': True,
            'address': address,
            'admin': [''],
        }

        regist = deepcopy(regist_dict)

        if not self.dbgpt_db.find_one({'address': address}):
            self.dbgpt_db.insert_one(regist_dict)
            return True
        else:
            print('db already exists, please change db name ')
            return False


    def check_user_dbgpt_db_permission(self, department, user_id):
        db = self.client[self.mongo_database]
        self.dbgpt_db = db[self.dbgpt_db_collection_name]
        result = self.dbgpt_db.find_one({'name': department, 'share.sharedUser': user_id})
        self.users_collection = db[self.users_collection_name]
        result2 = self.users_collection.find_one({'_id': ObjectId(user_id), 'dataAuth': 'y'})
        return True if result or result2 else False

    def check_manage_dbgpt_db_permission(self, department, user_id):
        db = self.client[self.mongo_database]
        self.dbgpt_db = db[self.dbgpt_db_collection_name]
        result = self.dbgpt_db.find_one({'name': department, 'admin': user_id})
        self.users_collection = db[self.users_collection_name]
        result2 = self.users_collection.find_one({'_id': ObjectId(user_id), 'dataAuth': 'y'})
        return True if result or result2 else False


if __name__ == '__main__':
    # fileId = '64f6cad6338fe11429ca5892'
    # chatId = '8babd990c8a6147d356f0eff'
    # userId = '647d3d3a9b6625f349d50e3f'
    chat_id = 'b89a67fd5224df8752e04f1a'
    data_id = '32e03b66e073e8e7a05956d8'
    user_id = '648ac64b12e0f97e93bca160'
    file_path = r"/datas/liab/8月不良率原始---MEShead49.xlsx"


    def createdbgpt_db():
        my = MyMongdb()
        my.registDBGPTDB()

    def check_user_right():
        my = MyMongdb()

        print(my.check_user_dbgpt_db_permission(department='hr_chinese_fk', user_id='648ab6c467031cb4fade1398'))
        print(my.check_manage_dbgpt_db_permission(department='hr_chinese_fk', user_id='648ab6c467031cb4fade1398'))


    createdbgpt_db()
    check_user_right()