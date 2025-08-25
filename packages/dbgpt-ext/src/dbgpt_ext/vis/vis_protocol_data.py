import copy
import json
import uuid
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from jinja2 import Template

from dbgpt._private.pydantic import BaseModel
from dbgpt.util.json_utils import serialize


class UpdateType(Enum):
    INCR = "incr"
    ALL = "all"


class VisTreeNode(BaseModel):
    uid: str
    cmp_tag: Optional[str] = None
    childs: Optional[List["VisTreeNode"]] = []


class ComponentData(BaseModel):
    type: UpdateType = UpdateType.ALL
    tag: Optional[str] = None
    content: Optional[Union[str, List[str]]] = None
    data: Optional[Any] = None
    is_dict_vis: bool = True


DEFAULT_COMPONENT_UID = "root"
NESTED_FIELD = "markdown"
LIST_NESTED_FIELD = "items"


class ComponentParser:
    def __init__(self):
        # 存储结构
        self.component_tree: List[Dict] = []  # 根组件列表
        self.component_cache: Dict[str, ComponentData] = defaultdict(
            ComponentData
        )  # 组件缓存
        self.stack: List[Dict] = []  # 解析栈
        self.current_uid: str = None  # 当前组件UID

        self.component_content_list_cache = defaultdict(list)

        self.vis_tree: Optional[VisTreeNode] = self.init_vis_tree()
        self.component_cache[DEFAULT_COMPONENT_UID] = ComponentData(
            type="all", tag=None, content="", data=None, is_dict_vis=False
        )

    def simpe_parse(self, text: str, cpm_chache: dict) -> Tuple[List[VisTreeNode], str]:
        lines = text.split("\n")
        content = ""
        childs = []
        for i in range(len(lines)):
            line = lines[i]

            stripped = line.strip()
            if not stripped.startswith("```"):
                uid = uuid.uuid4().hex
                type = "all"
                child_content = ""
                is_vis_cmp = False
                # 处理非协议文本部分
                if i >= 1:
                    marker_line = lines[i - 1]
                    marker = marker_line[3:].strip()
                    if marker and len(marker) > 0:
                        is_vis_cmp = True
                else:
                    # 如果非协议记录文本，直接返回本行解析
                    if line:
                        content = content + "\n" + line
                    continue

                cmp_data = line
                is_dic_vis = False
                try:
                    # 如果能解析成json 需要进一步处理嵌套
                    cmp_data = json.loads(stripped)
                    if isinstance(cmp_data, list):
                        uid = uuid.uuid4().hex
                        type = "all"
                        list_uid = uuid.uuid4().hex
                        self.component_content_list_cache[list_uid] = []
                        cmp_childs = []
                        for item in cmp_data:
                            if NESTED_FIELD in item:
                                tm_childs, child_content = self.simpe_parse(
                                    NESTED_FIELD, cpm_chache
                                )
                                cmp_childs.extend(tm_childs)
                                self.component_content_list_cache[list_uid].append(
                                    child_content
                                )
                            else:
                                cmp_childs = []
                                self.component_content_list_cache[list_uid].append(item)
                        child_content = f"$list{list_uid}"
                    else:
                        uid = cmp_data.get("uid", uuid.uuid4().hex)
                        type = cmp_data.get("type", None)
                        if NESTED_FIELD in cmp_data:
                            # 有嵌套
                            cmp_childs, child_content = self.simpe_parse(
                                cmp_data[NESTED_FIELD], cpm_chache
                            )
                        else:
                            if LIST_NESTED_FIELD in cmp_data and isinstance(
                                cmp_data[LIST_NESTED_FIELD], list
                            ):
                                uid = uuid.uuid4().hex
                                type = "all"
                                list_uid = uuid.uuid4().hex
                                self.component_content_list_cache[list_uid] = []
                                cmp_childs = []
                                for item in cmp_data:
                                    if NESTED_FIELD in item:
                                        tm_childs, child_content = self.simpe_parse(
                                            NESTED_FIELD, cpm_chache
                                        )
                                        cmp_childs.extend(tm_childs)
                                        self.component_content_list_cache[
                                            list_uid
                                        ].append(child_content)
                                    else:
                                        cmp_childs = []
                                        self.component_content_list_cache[
                                            list_uid
                                        ].append(item)
                                child_content = f"$list{list_uid}"
                            # 没有嵌套
                            cmp_childs = []
                            child_content = None
                    content = content + "\n" + f"{{{{cmp['{uid}']}}}}"
                    childs.append(
                        VisTreeNode(uid=uid, childs=cmp_childs, cmp_tag=marker)
                    )
                    is_dic_vis = True
                except Exception:
                    # 如果里面是非json，直接当文本处理即可
                    childs = []
                    content = content + "\n" + line
                cpm_chache[uid] = ComponentData(
                    type=UpdateType(type),
                    tag=marker,
                    content=child_content,
                    data=cmp_data,
                    is_dict_vis=is_dic_vis,
                )

        return childs, content

    def _tree_merge(
        self,
        old_node: VisTreeNode,
        new_node: VisTreeNode,
        new_cmp_cache: dict[str, ComponentData],
    ):
        if not old_node:
            return
        old_childs_uid_map = {node.uid: node for node in old_node.childs}
        for node in new_node.childs:
            if node.uid not in old_childs_uid_map:
                old_node.childs.append(copy.deepcopy(node))
                ## 新增子结点, 父结点内容更新
                self.component_cache[old_node.uid].content += new_cmp_cache[
                    new_node.uid
                ].content
            else:
                if node.childs and len(node.childs) > 0:
                    self._tree_merge(old_childs_uid_map[node.uid], node, new_cmp_cache)

    def _cmp_data_merge(
        self, new_cmp_data: dict, old_cmp_data: dict, merge_type: UpdateType
    ):
        exclude_properties = ["uid", "type"]
        ## 处理需要增量拼接的字段
        content_properties = ["markdown"]

        result = copy.deepcopy(old_cmp_data)
        for key, value in new_cmp_data.items():
            if key in exclude_properties:
                continue
            if not value:
                continue
            if key in result:
                # 列表合并：拼接而非覆盖
                if isinstance(result[key], list) and isinstance(value, list):
                    if UpdateType.ALL == merge_type:
                        result[key] = value
                    else:
                        result[key] += value
                # 字典递归
                elif isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._cmp_data_merge(value, result[key], merge_type)
                # 其他类型增量
                else:
                    if UpdateType.ALL == merge_type:
                        result[key] = copy.deepcopy(value)
                    else:
                        ## 区分需要增量拼接的字段，和进行数据替换的字段
                        if key in content_properties:
                            result[key] += copy.deepcopy(value)
                        else:
                            result[key] = copy.deepcopy(value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def update(self, vis_chunk):
        # 解析新增chunk
        new_cmp_cache: dict[str, ComponentData] = {}
        childs, content = self.simpe_parse(vis_chunk, new_cmp_cache)

        ## 组件嵌套结构更新
        # 新增组件只判断child 里是否有新增即可，不需要所有组件判断
        for child in childs:
            ## 新增的根结点组件不在组件缓存中，代表新增，直接整棵树放到根节点后面，并进行content更新
            if child.uid not in self.component_cache:
                self.vis_tree.childs.append(child)
                ## 新增子结点, 父结点内容更新
                self.component_cache[DEFAULT_COMPONENT_UID].content += content
            else:
                for item in self.vis_tree.childs:
                    if item.uid == child.uid:
                        self._tree_merge(item, child, new_cmp_cache)
                        break

        # 进行组件内容更新，所有组件从组件数据缓存中进行数据合并更新
        for uid, new_cmp in new_cmp_cache.items():
            if uid in self.component_cache:
                # 组件已经存在，数据按规则更新
                self.component_cache[uid].data = self._cmp_data_merge(
                    new_cmp.data, self.component_cache[uid].data, new_cmp.type
                )
            else:
                # 新增组件缓存记录
                self.component_cache[uid] = new_cmp

        # 触发 流式渲染
        return self.gen_vis_content()

    def gen_vis_content(self):
        """基于最新组件树生成全量流式vis协议 （如果不考考虑但容器，可以基于组件树，使用根节点的所有子节点构建容器，这样 可以拆分组件渲染粒度，防止组件互相影响）."""
        context = {
            "cmp": {},
        }
        all_vis_content = self._process_vis_tree(self.vis_tree, context)

        return all_vis_content

    def _process_vis_tree(self, tree: VisTreeNode, context: dict) -> str:
        component_data: ComponentData = self.component_cache[tree.uid]
        if tree.childs and len(tree.childs) > 0:
            for child in tree.childs:
                child_vis_content = self._process_vis_tree(child, context)
                context["cmp"][child.uid] = child_vis_content
                ## 处理完的vis content 要替换进组件位置

            template = Template(component_data.content)
            cmp_vis = template.render(context)

            # 有组件引用，当前组件里的mardkown 里组件信息是错的，需要从content还原
            if component_data.tag:
                if component_data.is_dict_vis:
                    if isinstance(component_data.data, list):
                        content_list = self.component_content_list_cache[tree.uid]
                        for i in range(component_data.data):
                            item = component_data.data[i]
                            lst_itm_content = content_list[i]
                            item_template = Template(lst_itm_content)
                            item_vis = item_template.render(context)
                            if isinstance(item, dict):
                                if NESTED_FIELD in item:
                                    component_data.data[i][NESTED_FIELD] = item_vis
                                else:
                                    # 没有markdown的对象不处理？ 数据已经合并
                                    component_data.data[i] = lst_itm_content
                            else:
                                print("Warning:嵌套列表数据，类型暂时不支持增量更新")
                    else:
                        component_data.data[NESTED_FIELD] = cmp_vis
                    vis_content = f"```{component_data.tag}\n{json.dumps(component_data.data, default=serialize, ensure_ascii=False)}\n```"
                else:
                    vis_content = f"```{component_data.tag}\n{cmp_vis}\n```"
            else:
                vis_content = cmp_vis
            return vis_content

        else:
            vis_content = component_data.content
            if component_data.tag and component_data.is_dict_vis:
                vis_content = f"```{component_data.tag}\n{json.dumps(component_data.data, default=serialize, ensure_ascii=False)}\n```"

            return vis_content

    def init_vis_tree(self) -> VisTreeNode:
        return VisTreeNode(uid=DEFAULT_COMPONENT_UID, childs=[])

    def _reset_parser(self):
        """重置解析状态"""
        self.component_cache = {}
        self.current_uid = None
        self.vis_tree = self.init_vis_tree()
        self.component_content_list_cache = {}

    def get_component_cache(self) -> Dict[str, ComponentData]:
        """获取组件缓存"""
        return self.component_cache
