#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import datetime
import json
import os
import shutil
import sys
import time
import uuid
from urllib.parse import urljoin

import gradio as gr
import requests


ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

from pilot.commands.command_mange import CommandRegistry

from pilot.scene.base_chat import BaseChat

from pilot.configs.config import Config
from pilot.configs.model_config import (
    DATASETS_DIR,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
    LLM_MODEL_CONFIG,
    LOGDIR,
    VECTOR_SEARCH_TOP_K,
)

from pilot.conversation import (
    SeparatorStyle,
    conv_qa_prompt_template,
    conv_templates,
    conversation_sql_mode,
    conversation_types,
    chat_mode_title,
    default_conversation,
)
from pilot.common.plugins import scan_plugins

from pilot.prompts.generator import PluginPromptGenerator
from pilot.server.gradio_css import code_highlight_css
from pilot.server.gradio_patch import Chatbot as grChatbot
from pilot.server.vectordb_qa import KnownLedgeBaseQA
from pilot.source_embedding.knowledge_embedding import KnowledgeEmbedding
from pilot.utils import build_logger, server_error_msg
from pilot.vector_store.extract_tovec import (
    get_vector_storelist,
    knownledge_tovec_st,
    load_knownledge_from_doc,
)

from pilot.commands.command import execute_ai_response_json
from pilot.scene.base import ChatScene
from pilot.scene.chat_factory import ChatFactory
from pilot.language.translation_handler import get_lang_text


# 加载插件
CFG = Config()
logger = build_logger("webserver", LOGDIR + "webserver.log")
headers = {"User-Agent": "dbgpt Client"}

no_change_btn = gr.Button.update()
enable_btn = gr.Button.update(interactive=True)
disable_btn = gr.Button.update(interactive=True)

enable_moderation = False
models = []
dbs = []
vs_list = [get_lang_text("create_knowledge_base")] + get_vector_storelist()
autogpt = False
vector_store_client = None
vector_store_name = {"vs_name": ""}

priority = {"vicuna-13b": "aaa"}

CHAT_FACTORY = ChatFactory()

DB_SETTINGS = {
    "user": CFG.LOCAL_DB_USER,
    "password": CFG.LOCAL_DB_PASSWORD,
    "host": CFG.LOCAL_DB_HOST,
    "port": CFG.LOCAL_DB_PORT,
}


llm_native_dialogue = get_lang_text("knowledge_qa_type_llm_native_dialogue")
default_knowledge_base_dialogue = get_lang_text(
    "knowledge_qa_type_default_knowledge_base_dialogue"
)
add_knowledge_base_dialogue = get_lang_text(
    "knowledge_qa_type_add_knowledge_base_dialogue"
)

url_knowledge_dialogue = get_lang_text(
    "knowledge_qa_type_url_knowledge_dialogue"
)

knowledge_qa_type_list = [
    llm_native_dialogue,
    default_knowledge_base_dialogue,
    add_knowledge_base_dialogue,
]


def get_simlar(q):
    docsearch = knownledge_tovec_st(os.path.join(DATASETS_DIR, "plan.md"))
    docs = docsearch.similarity_search_with_score(q, k=1)

    contents = [dc.page_content for dc, _ in docs]
    return "\n".join(contents)


def gen_sqlgen_conversation(dbname):
    message = ""
    db_connect = CFG.local_db.get_session(dbname)
    schemas = CFG.local_db.table_simple_info(db_connect)
    for s in schemas:
        message += s+ ";"
    return get_lang_text("sql_schema_info").format(dbname, message)


def plugins_select_info():
    plugins_infos: dict = {}
    for plugin in CFG.plugins:
        plugins_infos.update({f"【{plugin._name}】=>{plugin._description}": plugin._name})
    return plugins_infos


get_window_url_params = """
function() {
    const params = new URLSearchParams(window.location.search);
    url_params = Object.fromEntries(params);
    console.log(url_params);
    gradioURL = window.location.href
    if (!gradioURL.endsWith('?__theme=dark')) {
        window.location.replace(gradioURL + '?__theme=dark');
    }
    return url_params;
    }
"""


def load_demo(url_params, request: gr.Request):
    logger.info(f"load_demo. ip: {request.client.host}. params: {url_params}")

    # dbs = get_database_list()
    dropdown_update = gr.Dropdown.update(visible=True)
    if dbs:
        gr.Dropdown.update(choices=dbs)

    state = default_conversation.copy()

    unique_id = uuid.uuid1()
    state.conv_id = str(unique_id)

    return (
        state,
        dropdown_update,
        gr.Chatbot.update(visible=True),
        gr.Textbox.update(visible=True),
        gr.Button.update(visible=True),
        gr.Row.update(visible=True),
        gr.Accordion.update(visible=True),
    )


def get_conv_log_filename():
    t = datetime.datetime.now()
    name = os.path.join(LOGDIR, f"{t.year}-{t.month:02d}-{t.day:02d}-conv.json")
    return name


def regenerate(state, request: gr.Request):
    logger.info(f"regenerate. ip: {request.client.host}")
    state.messages[-1][-1] = None
    state.skip_next = False
    return (state, state.to_gradio_chatbot(), "") + (disable_btn,) * 5


def clear_history(request: gr.Request):
    logger.info(f"clear_history. ip: {request.client.host}")
    state = None
    return (state, [], "") + (disable_btn,) * 5


def add_text(state, text, request: gr.Request):
    logger.info(f"add_text. ip: {request.client.host}. len: {len(text)}")
    if len(text) <= 0:
        state.skip_next = True
        return (state, state.to_gradio_chatbot(), "") + (no_change_btn,) * 5

    """ Default support 4000 tokens, if tokens too lang, we will cut off  """
    text = text[:4000]
    state.append_message(state.roles[0], text)
    state.append_message(state.roles[1], None)
    state.skip_next = False
    ### TODO
    state.last_user_input = text
    return (state, state.to_gradio_chatbot(), "") + (disable_btn,) * 5


def post_process_code(code):
    sep = "\n```"
    if sep in code:
        blocks = code.split(sep)
        if len(blocks) % 2 == 1:
            for i in range(1, len(blocks), 2):
                blocks[i] = blocks[i].replace("\\_", "_")
        code = sep.join(blocks)
    return code


def get_chat_mode(selected, mode, sql_mode, db_selector) -> ChatScene:
    if chat_mode_title['chat_use_plugin'] == selected:
        return ChatScene.ChatExecution
    elif chat_mode_title['knowledge_qa']  == selected:
        if mode == conversation_types["default_knownledge"]:
            return ChatScene.ChatKnowledge
        elif mode == conversation_types["custome"]:
            return ChatScene.ChatNewKnowledge
    else:
        if sql_mode == conversation_sql_mode["auto_execute_ai_response"] and db_selector:
            return ChatScene.ChatWithDb

    return ChatScene.ChatNormal

def chatbot_callback(state, message):
    print(f"chatbot_callback:{message}")
    state.messages[-1][-1] = f"{message}"
    yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5


def http_bot(
        state, selected, plugin_selector, mode, sql_mode, db_selector, url_input, temperature, max_new_tokens, request: gr.Request
):
    logger.info(f"User message send!{state.conv_id},{selected},{mode},{sql_mode},{db_selector},{plugin_selector}")
    start_tstamp = time.time()
    scene:ChatScene = get_chat_mode(selected, mode, sql_mode, db_selector)
    print(f"now chat scene:{scene.value}")
    model_name = CFG.LLM_MODEL

    if ChatScene.ChatWithDb == scene:
        logger.info("chat with db mode use new architecture design！")
        chat_param = {
            "chat_session_id": state.conv_id,
            "db_name": db_selector,
            "user_input": state.last_user_input,
        }
        chat: BaseChat = CHAT_FACTORY.get_implementation(scene.value, **chat_param)
        chat.call()

        state.messages[-1][-1] = chat.current_ai_response()
        yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5

    elif ChatScene.ChatExecution == scene:
        logger.info("plugin mode use new architecture design！")
        chat_param = {
            "chat_session_id": state.conv_id,
            "plugin_selector": plugin_selector,
            "user_input": state.last_user_input,
        }
        chat: BaseChat = CHAT_FACTORY.get_implementation(scene.value, **chat_param)
        strem_generate =  chat.stream_call()

        for msg in strem_generate:
            state.messages[-1][-1] = msg
            yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5

        # def generate_numbers():
        #     for i in range(10):
        #         time.sleep(0.5)
        #         yield f"Message:{i}"
        #
        # def showMessage(message):
        #      return message
        #
        # for n in generate_numbers():
        #     state.messages[-1][-1] = n + "▌"
        #     yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5
    else:

        dbname = db_selector
        # TODO 这里的请求需要拼接现有知识库, 使得其根据现有知识库作答, 所以prompt需要继续优化
        if state.skip_next:
            # This generate call is skipped due to invalid inputs
            yield (state, state.to_gradio_chatbot()) + (no_change_btn,) * 5
            return

        if len(state.messages) == state.offset + 2:
            query = state.messages[-2][1]

            template_name = "conv_one_shot"
            new_state = conv_templates[template_name].copy()
            # prompt 中添加上下文提示, 根据已有知识对话, 上下文提示是否也应该放在第一轮, 还是每一轮都添加上下文?
            # 如果用户侧的问题跨度很大, 应该每一轮都加提示。
            if db_selector:
                new_state.append_message(
                    new_state.roles[0], gen_sqlgen_conversation(dbname) + query
                )
                new_state.append_message(new_state.roles[1], None)
            else:
                new_state.append_message(new_state.roles[0], query)
                new_state.append_message(new_state.roles[1], None)

            new_state.conv_id = uuid.uuid4().hex
            state = new_state
        else:
            ### 后续对话
            query = state.messages[-2][1]
            # 第一轮对话需要加入提示Prompt
            if mode == conversation_types["custome"]:
                template_name = "conv_one_shot"
                new_state = conv_templates[template_name].copy()
                # prompt 中添加上下文提示, 根据已有知识对话, 上下文提示是否也应该放在第一轮, 还是每一轮都添加上下文?
                # 如果用户侧的问题跨度很大, 应该每一轮都加提示。
                if db_selector:
                    new_state.append_message(
                        new_state.roles[0], gen_sqlgen_conversation(dbname) + query
                    )
                    new_state.append_message(new_state.roles[1], None)
                else:
                    new_state.append_message(new_state.roles[0], query)
                    new_state.append_message(new_state.roles[1], None)
                state = new_state

        prompt = state.get_prompt()
        skip_echo_len = len(prompt.replace("</s>", " ")) + 1
        if mode == conversation_types["default_knownledge"] and not db_selector:
            vector_store_config = {
                "vector_store_name": "default",
                "vector_store_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
            }
            knowledge_embedding_client = KnowledgeEmbedding(
                file_path="",
                model_name=LLM_MODEL_CONFIG["text2vec"],
                local_persist=False,
                vector_store_config=vector_store_config,
            )
            query = state.messages[-2][1]
            docs = knowledge_embedding_client.similar_search(query, VECTOR_SEARCH_TOP_K)
            prompt = KnownLedgeBaseQA.build_knowledge_prompt(query, docs, state)
            state.messages[-2][1] = query
            skip_echo_len = len(prompt.replace("</s>", " ")) + 1

        if mode == conversation_types["custome"] and not db_selector:
            print("vector store name: ", vector_store_name["vs_name"])
            vector_store_config = {
                "vector_store_name": vector_store_name["vs_name"],
                "text_field": "content",
                "vector_store_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
            }
            knowledge_embedding_client = KnowledgeEmbedding(
                file_path="",
                model_name=LLM_MODEL_CONFIG["text2vec"],
                local_persist=False,
                vector_store_config=vector_store_config,
            )
            query = state.messages[-2][1]
            docs = knowledge_embedding_client.similar_search(query, VECTOR_SEARCH_TOP_K)
            prompt = KnownLedgeBaseQA.build_knowledge_prompt(query, docs, state)

            state.messages[-2][1] = query
            skip_echo_len = len(prompt.replace("</s>", " ")) + 1

        if mode == conversation_types["url"] and  url_input:
            print("url: ", url_input)
            vector_store_config = {
                "vector_store_name": url_input,
                "text_field": "content",
                "vector_store_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
            }
            knowledge_embedding_client = KnowledgeEmbedding(
                file_path=url_input,
                model_name=LLM_MODEL_CONFIG["text2vec"],
                local_persist=False,
                vector_store_config=vector_store_config,
            )

            query = state.messages[-2][1]
            docs = knowledge_embedding_client.similar_search(query, VECTOR_SEARCH_TOP_K)
            prompt = KnownLedgeBaseQA.build_knowledge_prompt(query, docs, state)

            state.messages[-2][1] = query
            skip_echo_len = len(prompt.replace("</s>", " ")) + 1

        # Make requests
        payload = {
            "model": model_name,
            "prompt": prompt,
            "temperature": float(temperature),
            "max_new_tokens": int(max_new_tokens),
            "stop": state.sep
            if state.sep_style == SeparatorStyle.SINGLE
            else state.sep2,
        }
        logger.info(f"Requert: \n{payload}")

        # 流式输出
        state.messages[-1][-1] = "▌"
        yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5

        try:
            # Stream output
            response = requests.post(
                urljoin(CFG.MODEL_SERVER, "generate_stream"),
                headers=headers,
                json=payload,
                stream=True,
                timeout=20,
            )
            for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
                if chunk:
                    data = json.loads(chunk.decode())

                    """ TODO Multi mode output handler,  rewrite this for multi model, use adapter mode.
                    """
                    if data["error_code"] == 0:
                        if "vicuna" in CFG.LLM_MODEL:
                            output = data["text"][skip_echo_len:].strip()
                        else:
                            output = data["text"].strip()

                        output = post_process_code(output)
                        state.messages[-1][-1] = output + "▌"
                        yield (state, state.to_gradio_chatbot()) + (
                            disable_btn,
                        ) * 5
                    else:
                        output = (
                            data["text"] + f" (error_code: {data['error_code']})"
                        )
                        state.messages[-1][-1] = output
                        yield (state, state.to_gradio_chatbot()) + (
                            disable_btn,
                            disable_btn,
                            disable_btn,
                            enable_btn,
                            enable_btn,
                        )
                        return

        except requests.exceptions.RequestException as e:
            state.messages[-1][-1] = server_error_msg + f" (error_code: 4)"
            yield (state, state.to_gradio_chatbot()) + (
                disable_btn,
                disable_btn,
                disable_btn,
                enable_btn,
                enable_btn,
            )
            return

        state.messages[-1][-1] = state.messages[-1][-1][:-1]
        yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5

        # 记录运行日志
        finish_tstamp = time.time()
        logger.info(f"{output}")

        with open(get_conv_log_filename(), "a") as fout:
            data = {
                "tstamp": round(finish_tstamp, 4),
                "type": "chat",
                "model": model_name,
                "start": round(start_tstamp, 4),
                "finish": round(start_tstamp, 4),
                "state": state.dict(),
                "ip": request.client.host,
            }
            fout.write(json.dumps(data) + "\n")


block_css = (
    code_highlight_css
    + """
        pre {
            white-space: pre-wrap;       /* Since CSS 2.1 */
            white-space: -moz-pre-wrap;  /* Mozilla, since 1999 */
            white-space: -pre-wrap;      /* Opera 4-6 */
            white-space: -o-pre-wrap;    /* Opera 7 */
            word-wrap: break-word;       /* Internet Explorer 5.5+ */
        }
        #notice_markdown th {
            display: none;
        }
            """
)


def change_sql_mode(sql_mode):
    if sql_mode in [get_lang_text("sql_generate_mode_direct")]:
        return gr.update(visible=True)
    else:
        return gr.update(visible=False)


def change_mode(mode):
    if mode in [add_knowledge_base_dialogue]:
        return gr.update(visible=True)
    else:
        return gr.update(visible=False)



def build_single_model_ui():
    notice_markdown = get_lang_text("db_gpt_introduction")
    learn_more_markdown = get_lang_text("learn_more_markdown")

    state = gr.State()
    gr.Markdown(notice_markdown, elem_id="notice_markdown")

    with gr.Accordion(
        get_lang_text("model_control_param"), open=False, visible=False
    ) as parameter_row:
        temperature = gr.Slider(
            minimum=0.0,
            maximum=1.0,
            value=0.7,
            step=0.1,
            interactive=True,
            label="Temperature",
        )

        max_output_tokens = gr.Slider(
            minimum=0,
            maximum=1024,
            value=512,
            step=64,
            interactive=True,
            label=get_lang_text("max_input_token_size"),
        )

    tabs = gr.Tabs()

    def on_select(evt: gr.SelectData):  # SelectData is a subclass of EventData
        print(f"You selected {evt.value} at {evt.index} from {evt.target}")
        return evt.value

    selected = gr.Textbox(show_label=False, visible=False, placeholder="Selected")
    tabs.select(on_select, None, selected)

    with tabs:
        tab_sql = gr.TabItem(get_lang_text("sql_generate_diagnostics"), elem_id="SQL")
        with tab_sql:
            # TODO A selector to choose database
            with gr.Row(elem_id="db_selector"):
                db_selector = gr.Dropdown(
                    label=get_lang_text("please_choose_database"),
                    choices=dbs,
                    value=dbs[0] if len(models) > 0 else "",
                    interactive=True,
                    show_label=True,
                ).style(container=False)

            sql_mode = gr.Radio(
                [
                    get_lang_text("sql_generate_mode_direct"),
                    get_lang_text("sql_generate_mode_none"),
                ],
                show_label=False,
                value=get_lang_text("sql_generate_mode_none"),
            )
            sql_vs_setting = gr.Markdown(get_lang_text("sql_vs_setting"))
            sql_mode.change(fn=change_sql_mode, inputs=sql_mode, outputs=sql_vs_setting)

        tab_plugin = gr.TabItem(get_lang_text("chat_use_plugin"), elem_id="PLUGIN")
        # tab_plugin.select(change_func)
        with tab_plugin:
            print("tab_plugin in...")
            with gr.Row(elem_id="plugin_selector"):
                # TODO
                plugin_selector = gr.Dropdown(
                    label=get_lang_text("select_plugin"),
                    choices=list(plugins_select_info().keys()),
                    value="",
                    interactive=True,
                    show_label=True,
                    type="value"
                ).style(container=False)

                def plugin_change(evt: gr.SelectData):  # SelectData is a subclass of EventData
                    print(f"You selected {evt.value} at {evt.index} from {evt.target}")
                    return plugins_select_info().get(evt.value)

                plugin_selected = gr.Textbox(show_label=False, visible=False, placeholder="Selected")
                plugin_selector.select(plugin_change, None, plugin_selected)

        tab_qa = gr.TabItem(get_lang_text("knowledge_qa"), elem_id="QA")
        with tab_qa:
            mode = gr.Radio(
                [
                    llm_native_dialogue,
                    default_knowledge_base_dialogue,
                    add_knowledge_base_dialogue,
                    url_knowledge_dialogue,
                ],
                show_label=False,
                value=llm_native_dialogue,
            )
            vs_setting = gr.Accordion(
                get_lang_text("configure_knowledge_base"), open=False
            )
            mode.change(fn=change_mode, inputs=mode, outputs=vs_setting)

            url_input = gr.Textbox(label=get_lang_text("url_input_label"), lines=1, interactive=True)
            def show_url_input(evt:gr.SelectData):
                if evt.value == url_knowledge_dialogue:
                    return gr.update(visible=True)
                else:
                    return gr.update(visible=False)
            mode.select(fn=show_url_input, inputs=None, outputs=url_input)


            with vs_setting:
                vs_name = gr.Textbox(
                    label=get_lang_text("new_klg_name"), lines=1, interactive=True
                )
                vs_add = gr.Button(get_lang_text("add_as_new_klg"))
                with gr.Column() as doc2vec:
                    gr.Markdown(get_lang_text("add_file_to_klg"))
                    with gr.Tab(get_lang_text("upload_file")):
                        files = gr.File(
                            label=get_lang_text("add_file"),
                            file_types=[".txt", ".md", ".docx", ".pdf"],
                            file_count="multiple",
                            allow_flagged_uploads=True,
                            show_label=False,
                        )

                        load_file_button = gr.Button(
                            get_lang_text("upload_and_load_to_klg")
                        )
                    with gr.Tab(get_lang_text("upload_folder")):
                        folder_files = gr.File(
                            label=get_lang_text("add_folder"),
                            accept_multiple_files=True,
                            file_count="directory",
                            show_label=False,
                        )
                        load_folder_button = gr.Button(
                            get_lang_text("upload_and_load_to_klg")
                        )

    with gr.Blocks():
        chatbot = grChatbot(elem_id="chatbot", visible=False).style(height=550)
        with gr.Row():
            with gr.Column(scale=20):
                textbox = gr.Textbox(
                    show_label=False,
                    placeholder="Enter text and press ENTER",
                    visible=False,
                ).style(container=False)
            with gr.Column(scale=2, min_width=50):
                send_btn = gr.Button(value=get_lang_text("send"), visible=False)

    with gr.Row(visible=False) as button_row:
        regenerate_btn = gr.Button(value=get_lang_text("regenerate"), interactive=False)
        clear_btn = gr.Button(value=get_lang_text("clear_box"), interactive=False)

    gr.Markdown(learn_more_markdown)
    btn_list = [regenerate_btn, clear_btn]
    regenerate_btn.click(regenerate, state, [state, chatbot, textbox] + btn_list).then(
        http_bot,
        [state, selected, plugin_selected, mode, sql_mode, db_selector, url_input, temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )
    clear_btn.click(clear_history, None, [state, chatbot, textbox] + btn_list)

    textbox.submit(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, selected, plugin_selected, mode, sql_mode, db_selector, url_input, temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )

    send_btn.click(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, selected, plugin_selected, mode, sql_mode, db_selector, url_input,  temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )
    vs_add.click(
        fn=save_vs_name, show_progress=True, inputs=[vs_name], outputs=[vs_name]
    )
    load_file_button.click(
        fn=knowledge_embedding_store,
        show_progress=True,
        inputs=[vs_name, files],
        outputs=[vs_name],
    )
    load_folder_button.click(
        fn=knowledge_embedding_store,
        show_progress=True,
        inputs=[vs_name, folder_files],
        outputs=[vs_name],
    )
    return state, chatbot, textbox, send_btn, button_row, parameter_row


def build_webdemo():
    with gr.Blocks(
        title=get_lang_text("database_smart_assistant"),
        # theme=gr.themes.Base(),
        theme=gr.themes.Default(),
        css=block_css,
    ) as demo:
        url_params = gr.JSON(visible=False)
        (
            state,
            chatbot,
            textbox,
            send_btn,
            button_row,
            parameter_row,
        ) = build_single_model_ui()

        if args.model_list_mode == "once":
            demo.load(
                load_demo,
                [url_params],
                [
                    state,
                    chatbot,
                    textbox,
                    send_btn,
                    button_row,
                    parameter_row,
                ],
                _js=get_window_url_params,
            )
        else:
            raise ValueError(f"Unknown model list mode: {args.model_list_mode}")
    return demo


def save_vs_name(vs_name):
    vector_store_name["vs_name"] = vs_name
    return vs_name


def knowledge_embedding_store(vs_id, files):
    # vs_path = os.path.join(VS_ROOT_PATH, vs_id)
    if not os.path.exists(os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, vs_id)):
        os.makedirs(os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, vs_id))
    for file in files:
        filename = os.path.split(file.name)[-1]
        shutil.move(
            file.name, os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, vs_id, filename)
        )
        knowledge_embedding_client = KnowledgeEmbedding(
            file_path=os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, vs_id, filename),
            model_name=LLM_MODEL_CONFIG["text2vec"],
            local_persist=False,
            vector_store_config={
                "vector_store_name": vector_store_name["vs_name"],
                "vector_store_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
            },
        )
        knowledge_embedding_client.knowledge_embedding()

    logger.info("knowledge embedding success")
    return os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, vs_id, vs_id + ".vectordb")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int)
    parser.add_argument("--concurrency-count", type=int, default=10)
    parser.add_argument(
        "--model-list-mode", type=str, default="once", choices=["once", "reload"]
    )
    parser.add_argument("--share", default=False, action="store_true")

    args = parser.parse_args()
    logger.info(f"args: {args}")
    # 配置初始化
    cfg = Config()

    dbs = cfg.local_db.get_database_list()

    cfg.set_plugins(scan_plugins(cfg, cfg.debug_mode))

    # 加载插件可执行命令
    command_categories = [
        "pilot.commands.built_in.audio_text",
        "pilot.commands.built_in.image_gen",
    ]
    # 排除禁用命令
    command_categories = [
        x for x in command_categories if x not in cfg.disabled_command_categories
    ]
    command_registry = CommandRegistry()
    for command_category in command_categories:
        command_registry.import_commands(command_category)

    cfg.command_registry = command_registry

    logger.info(args)
    demo = build_webdemo()
    demo.queue(
        concurrency_count=args.concurrency_count, status_update_rate=10, api_open=False
    ).launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        max_threads=200,
    )
