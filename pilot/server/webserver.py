#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import threading
import traceback
import argparse
import datetime
import os
import shutil
import sys
import uuid

import gradio as gr

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

from pilot.embedding_engine.knowledge_type import KnowledgeType

from pilot.summary.db_summary_client import DBSummaryClient

from pilot.scene.base_chat import BaseChat

from pilot.configs.config import Config
from pilot.configs.model_config import (
    DATASETS_DIR,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
    LLM_MODEL_CONFIG,
    LOGDIR,
)

from pilot.conversation import (
    conversation_sql_mode,
    conversation_types,
    chat_mode_title,
    default_conversation,
)

from pilot.server.gradio_css import code_highlight_css
from pilot.server.gradio_patch import Chatbot as grChatbot
from pilot.embedding_engine.embedding_engine import EmbeddingEngine
from pilot.utils import build_logger
from pilot.vector_store.extract_tovec import (
    get_vector_storelist,
    knownledge_tovec_st,
)

from pilot.scene.base import ChatScene
from pilot.scene.chat_factory import ChatFactory
from pilot.language.translation_handler import get_lang_text
from pilot.server.webserver_base import server_init


import uvicorn
from fastapi import BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi import FastAPI, applications
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pilot.openapi.api_v1.api_v1 import router as api_v1, validation_exception_handler

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
# db_summary = {"dbsummary": ""}

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

url_knowledge_dialogue = get_lang_text("knowledge_qa_type_url_knowledge_dialogue")

knowledge_qa_type_list = [
    llm_native_dialogue,
    default_knowledge_base_dialogue,
    add_knowledge_base_dialogue,
]


def swagger_monkey_patch(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.10.3/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.10.3/swagger-ui.css",
    )


applications.get_swagger_ui_html = swagger_monkey_patch

app = FastAPI()
origins = ["*"]

# 添加跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# app.mount("static", StaticFiles(directory="static"), name="static")
app.include_router(api_v1)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


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
        message += s + ";"
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


def get_chat_mode(selected, param=None) -> ChatScene:
    if chat_mode_title["chat_use_plugin"] == selected:
        return ChatScene.ChatExecution
    elif chat_mode_title["sql_generate_diagnostics"] == selected:
        sql_mode = param
        if sql_mode == conversation_sql_mode["auto_execute_ai_response"]:
            return ChatScene.ChatWithDbExecute
        else:
            return ChatScene.ChatWithDbQA
    else:
        mode = param
        if mode == conversation_types["default_knownledge"]:
            return ChatScene.ChatDefaultKnowledge
        elif mode == conversation_types["custome"]:
            return ChatScene.ChatNewKnowledge
        elif mode == conversation_types["url"]:
            return ChatScene.ChatUrlKnowledge
        else:
            return ChatScene.ChatNormal


def chatbot_callback(state, message):
    print(f"chatbot_callback:{message}")
    state.messages[-1][-1] = f"{message}"
    yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5


def http_bot(
    state,
    selected,
    temperature,
    max_new_tokens,
    plugin_selector,
    mode,
    sql_mode,
    db_selector,
    url_input,
    knowledge_name,
):
    logger.info(
        f"User message send!{state.conv_id},{selected},{plugin_selector},{mode},{sql_mode},{db_selector},{url_input}"
    )
    if chat_mode_title["sql_generate_diagnostics"] == selected:
        scene: ChatScene = get_chat_mode(selected, sql_mode)
    elif chat_mode_title["chat_use_plugin"] == selected:
        scene: ChatScene = get_chat_mode(selected)
    else:
        scene: ChatScene = get_chat_mode(selected, mode)

    print(f"chat scene:{scene.value}")

    if ChatScene.ChatWithDbExecute == scene:
        chat_param = {
            "chat_session_id": state.conv_id,
            "db_name": db_selector,
            "user_input": state.last_user_input,
        }
    elif ChatScene.ChatWithDbQA == scene:
        chat_param = {
            "chat_session_id": state.conv_id,
            "db_name": db_selector,
            "user_input": state.last_user_input,
        }
    elif ChatScene.ChatExecution == scene:
        chat_param = {
            "chat_session_id": state.conv_id,
            "plugin_selector": plugin_selector,
            "user_input": state.last_user_input,
        }
    elif ChatScene.ChatNormal == scene:
        chat_param = {
            "chat_session_id": state.conv_id,
            "user_input": state.last_user_input,
        }
    elif ChatScene.ChatDefaultKnowledge == scene:
        chat_param = {
            "chat_session_id": state.conv_id,
            "user_input": state.last_user_input,
        }
    elif ChatScene.ChatNewKnowledge == scene:
        chat_param = {
            "chat_session_id": state.conv_id,
            "user_input": state.last_user_input,
            "knowledge_name": knowledge_name,
        }
    elif ChatScene.ChatUrlKnowledge == scene:
        chat_param = {
            "chat_session_id": state.conv_id,
            "user_input": state.last_user_input,
            "url": url_input,
        }
    else:
        state.messages[-1][-1] = f"ERROR: Can't support scene!{scene}"
        yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5

    chat: BaseChat = CHAT_FACTORY.get_implementation(scene.value(), **chat_param)
    if not chat.prompt_template.stream_out:
        logger.info("not stream out, wait model response!")
        state.messages[-1][-1] = chat.nostream_call()
        yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5
    else:
        logger.info("stream out start!")
        try:
            response = chat.stream_call()
            for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
                if chunk:
                    msg = chat.prompt_template.output_parser.parse_model_stream_resp_ex(
                        chunk, chat.skip_echo_len
                    )
                    state.messages[-1][-1] = msg
                    chat.current_message.add_ai_message(msg)
                    yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5
            chat.memory.append(chat.current_message)
        except Exception as e:
            print(traceback.format_exc())
            state.messages[-1][
                -1
            ] = f"""<span style=\"color:red\">ERROR!</span>{str(e)} """
            yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5


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
                get_lang_text("configure_knowledge_base"), open=False, visible=False
            )
            mode.change(fn=change_mode, inputs=mode, outputs=vs_setting)

            url_input = gr.Textbox(
                label=get_lang_text("url_input_label"),
                lines=1,
                interactive=True,
                visible=False,
            )

            def show_url_input(evt: gr.SelectData):
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

            # db_selector.change(fn=db_selector_changed, inputs=db_selector)

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
                    type="value",
                ).style(container=False)

                def plugin_change(
                    evt: gr.SelectData,
                ):  # SelectData is a subclass of EventData
                    print(f"You selected {evt.value} at {evt.index} from {evt.target}")
                    print(f"user plugin:{plugins_select_info().get(evt.value)}")
                    return plugins_select_info().get(evt.value)

                plugin_selected = gr.Textbox(
                    show_label=False, visible=False, placeholder="Selected"
                )
                plugin_selector.select(plugin_change, None, plugin_selected)

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

    params = [plugin_selected, mode, sql_mode, db_selector, url_input, vs_name]

    btn_list = [regenerate_btn, clear_btn]
    regenerate_btn.click(regenerate, state, [state, chatbot, textbox] + btn_list).then(
        http_bot,
        [state, selected, temperature, max_output_tokens] + params,
        [state, chatbot] + btn_list,
    )
    clear_btn.click(clear_history, None, [state, chatbot, textbox] + btn_list)

    textbox.submit(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, selected, temperature, max_output_tokens] + params,
        [state, chatbot] + btn_list,
    )

    send_btn.click(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, selected, temperature, max_output_tokens] + params,
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
        knowledge_embedding_client = EmbeddingEngine(
            knowledge_source=os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, vs_id, filename),
            knowledge_type=KnowledgeType.DOCUMENT.value,
            model_name=LLM_MODEL_CONFIG["text2vec"],
            vector_store_config={
                "vector_store_name": vector_store_name["vs_name"],
                "vector_store_type": CFG.VECTOR_STORE_TYPE,
                "vector_store_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
            },
        )
        knowledge_embedding_client.knowledge_embedding()

    logger.info("knowledge embedding success")
    return vs_id


def async_db_summery():
    client = DBSummaryClient()
    thread = threading.Thread(target=client.init_db_summary)
    thread.start()


def signal_handler(sig, frame):
    print("in order to avoid chroma db atexit problem")
    os._exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model_list_mode", type=str, default="once", choices=["once", "reload"]
    )
    parser.add_argument(
        "-new", "--new", action="store_true", help="enable new http mode"
    )

    # old version server config
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=CFG.WEB_SERVER_PORT)
    parser.add_argument("--concurrency-count", type=int, default=10)
    parser.add_argument("--share", default=False, action="store_true")

    # init server config
    args = parser.parse_args()
    server_init(args)
    dbs = CFG.local_db.get_database_list()
    demo = build_webdemo()
    demo.queue(
        concurrency_count=args.concurrency_count,
        status_update_rate=10,
        api_open=False,
    ).launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        max_threads=200,
    )
