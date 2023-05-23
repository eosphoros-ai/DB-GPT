#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import shutil
import uuid
import json
import sys
import time
import gradio as gr
import datetime
import requests
from urllib.parse import urljoin

from langchain import PromptTemplate


ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

from pilot.configs.model_config import KNOWLEDGE_UPLOAD_ROOT_PATH, LLM_MODEL_CONFIG, VECTOR_SEARCH_TOP_K
from pilot.server.vectordb_qa import KnownLedgeBaseQA
from pilot.connections.mysql import MySQLOperator
from pilot.source_embedding.knowledge_embedding import KnowledgeEmbedding
from pilot.vector_store.extract_tovec import get_vector_storelist, load_knownledge_from_doc, knownledge_tovec_st

from pilot.configs.model_config import LOGDIR,  DATASETS_DIR

from pilot.plugins import scan_plugins
from pilot.configs.config import Config
from pilot.commands.command_mange import CommandRegistry
from pilot.prompts.auto_mode_prompt import AutoModePrompt
from pilot.prompts.generator import PromptGenerator

from pilot.commands.exception_not_commands import NotCommands



from pilot.conversation import (
    default_conversation,
    conv_templates,
    conversation_types,
    conversation_sql_mode,
    SeparatorStyle, conv_qa_prompt_template
)

from pilot.utils import (
    build_logger,
    server_error_msg,
)

from pilot.server.gradio_css import code_highlight_css
from pilot.server.gradio_patch import Chatbot as grChatbot

from pilot.commands.command import execute_ai_response_json

logger = build_logger("webserver", LOGDIR + "webserver.log")
headers = {"User-Agent": "dbgpt Client"}

no_change_btn = gr.Button.update()
enable_btn = gr.Button.update(interactive=True)
disable_btn = gr.Button.update(interactive=True)

enable_moderation = False
models = []
dbs = []
vs_list = ["新建知识库"] + get_vector_storelist()
autogpt = False
vector_store_client = None
vector_store_name = {"vs_name": ""}

priority = {
    "vicuna-13b": "aaa"
}

# 加载插件
CFG= Config()

DB_SETTINGS = {
    "user": CFG.LOCAL_DB_USER,
    "password":  CFG.LOCAL_DB_PASSWORD,
    "host": CFG.LOCAL_DB_HOST,
    "port": CFG.LOCAL_DB_PORT
}
def get_simlar(q):
    docsearch = knownledge_tovec_st(os.path.join(DATASETS_DIR, "plan.md"))
    docs = docsearch.similarity_search_with_score(q, k=1)

    contents = [dc.page_content for dc, _ in docs]
    return "\n".join(contents)


def gen_sqlgen_conversation(dbname):
    mo = MySQLOperator(
        **DB_SETTINGS
    )

    message = ""

    schemas = mo.get_schema(dbname)
    for s in schemas:
        message += s["schema_info"] + ";"
    return f"数据库{dbname}的Schema信息如下: {message}\n"


def get_database_list():
    mo = MySQLOperator(**DB_SETTINGS)
    return mo.get_db_list()


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
    return (state,
            dropdown_update,
            gr.Chatbot.update(visible=True),
            gr.Textbox.update(visible=True),
            gr.Button.update(visible=True),
            gr.Row.update(visible=True),
            gr.Accordion.update(visible=True))


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


def http_bot(state, mode, sql_mode, db_selector, temperature, max_new_tokens, request: gr.Request):
    if sql_mode == conversation_sql_mode["auto_execute_ai_response"]:
        print("AUTO DB-GPT模式.")
    if sql_mode == conversation_sql_mode["dont_execute_ai_response"]:
        print("标准DB-GPT模式.")
    print("是否是AUTO-GPT模式.", autogpt)

    start_tstamp = time.time()
    model_name = CFG.LLM_MODEL

    dbname = db_selector
    # TODO 这里的请求需要拼接现有知识库, 使得其根据现有知识库作答, 所以prompt需要继续优化
    if state.skip_next:
        # This generate call is skipped due to invalid inputs
        yield (state, state.to_gradio_chatbot()) + (no_change_btn,) * 5
        return

    cfg = Config()
    auto_prompt = AutoModePrompt()
    auto_prompt.command_registry = cfg.command_registry

    # TODO when tab mode is AUTO_GPT, Prompt need to rebuild.
    if len(state.messages) == state.offset + 2:
        query = state.messages[-2][1]
        # 第一轮对话需要加入提示Prompt
        if sql_mode == conversation_sql_mode["auto_execute_ai_response"]:
            # autogpt模式的第一轮对话需要 构建专属prompt
            system_prompt = auto_prompt.construct_first_prompt(fisrt_message=[query],
                                                               db_schemes=gen_sqlgen_conversation(dbname))
            logger.info("[TEST]:" + system_prompt)
            template_name = "auto_dbgpt_one_shot"
            new_state = conv_templates[template_name].copy()
            new_state.append_message(role='USER', message=system_prompt)
            # new_state.append_message(new_state.roles[0], query)
            new_state.append_message(new_state.roles[1], None)
        else:
            template_name = "conv_one_shot"
            new_state = conv_templates[template_name].copy()
            # prompt 中添加上下文提示, 根据已有知识对话, 上下文提示是否也应该放在第一轮, 还是每一轮都添加上下文?
            # 如果用户侧的问题跨度很大, 应该每一轮都加提示。
            if db_selector:
                new_state.append_message(new_state.roles[0], gen_sqlgen_conversation(dbname) + query)
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
                new_state.append_message(new_state.roles[0], gen_sqlgen_conversation(dbname) + query)
                new_state.append_message(new_state.roles[1], None)
            else:
                new_state.append_message(new_state.roles[0], query)
                new_state.append_message(new_state.roles[1], None)
            state = new_state
        elif sql_mode == conversation_sql_mode["auto_execute_ai_response"]:
            ## 获取最后一次插件的返回
            follow_up_prompt = auto_prompt.construct_follow_up_prompt([query])
            state.messages[0][0] = ""
            state.messages[0][1] = ""
            state.messages[-2][1] = follow_up_prompt
    prompt = state.get_prompt()
    skip_echo_len = len(prompt.replace("</s>", " ")) + 1
    if mode == conversation_types["default_knownledge"] and not db_selector:
        query = state.messages[-2][1]
        knqa = KnownLedgeBaseQA()
        state.messages[-2][1] = knqa.get_similar_answer(query)
        prompt = state.get_prompt()
        state.messages[-2][1] = query
        skip_echo_len = len(prompt.replace("</s>", " ")) + 1

    if mode == conversation_types["custome"] and not db_selector:
        print("vector store name: ", vector_store_name["vs_name"])
        vector_store_config = {"vector_store_name": vector_store_name["vs_name"], "text_field": "content",
                               "vector_store_path": KNOWLEDGE_UPLOAD_ROOT_PATH}
        knowledge_embedding_client = KnowledgeEmbedding(file_path="", model_name=LLM_MODEL_CONFIG["text2vec"],
                                                        local_persist=False,
                                                        vector_store_config=vector_store_config)
        query = state.messages[-2][1]
        docs = knowledge_embedding_client.similar_search(query, VECTOR_SEARCH_TOP_K)
        context = [d.page_content for d in docs]
        prompt_template = PromptTemplate(
            template=conv_qa_prompt_template,
            input_variables=["context", "question"]
        )
        result = prompt_template.format(context="\n".join(context), question=query)
        state.messages[-2][1] = result
        prompt = state.get_prompt()
        print("prompt length:" + str(len(prompt)))

        if len(prompt) > 4000:
            logger.info("prompt length greater than 4000, rebuild")
            context = context[:2000]
            prompt_template = PromptTemplate(
                template=conv_qa_prompt_template,
                input_variables=["context", "question"]
            )
            result = prompt_template.format(context="\n".join(context), question=query)
            state.messages[-2][1] = result
            prompt = state.get_prompt()
            print("new prompt length:" + str(len(prompt)))

        state.messages[-2][1] = query
        skip_echo_len = len(prompt.replace("</s>", " ")) + 1

    # Make requests
    payload = {
        "model": model_name,
        "prompt": prompt,
        "temperature": float(temperature),
        "max_new_tokens": int(max_new_tokens),
        "stop": state.sep if state.sep_style == SeparatorStyle.SINGLE else state.sep2,
    }
    logger.info(f"Requert: \n{payload}")

    if sql_mode == conversation_sql_mode["auto_execute_ai_response"]:
        response = requests.post(urljoin(CFG.MODEL_SERVER, "generate"),
                                 headers=headers, json=payload, timeout=120)

        print(response.json())
        print(str(response))
        try:
            text = response.text.strip()
            text = text.rstrip()
            respObj = json.loads(text)

            xx = respObj['response']
            xx = xx.strip(b'\x00'.decode())
            respObj_ex = json.loads(xx)
            if respObj_ex['error_code'] == 0:
                ai_response = None
                all_text = respObj_ex['text']
                ### 解析返回文本，获取AI回复部分
                tmpResp = all_text.split(state.sep)
                last_index = -1
                for i in range(len(tmpResp)):
                    if tmpResp[i].find('ASSISTANT:') != -1:
                        last_index = i
                ai_response = tmpResp[last_index]
                ai_response = ai_response.replace("ASSISTANT:", "")
                ai_response = ai_response.replace("\n", "")
                ai_response = ai_response.replace("\_", "_")

                print(ai_response)
                if ai_response == None:
                    state.messages[-1][-1] = "ASSISTANT未能正确回复，回复结果为:\n" + all_text
                    yield (state, state.to_gradio_chatbot()) + (no_change_btn,) * 5
                else:
                    plugin_resp = execute_ai_response_json(auto_prompt.prompt_generator, ai_response)
                    cfg.set_last_plugin_return(plugin_resp)
                    print(plugin_resp)
                    state.messages[-1][-1] = "Model推理信息:\n" + ai_response + "\n\nDB-GPT执行结果:\n" + plugin_resp
                    yield (state, state.to_gradio_chatbot()) + (no_change_btn,) * 5
        except NotCommands as e:
            print("命令执行:" + e.message)
            state.messages[-1][-1] = "命令执行:" + e.message + "\n模型输出:\n" + str(ai_response)
            yield (state, state.to_gradio_chatbot()) + (no_change_btn,) * 5
    else:
        # 流式输出
        state.messages[-1][-1] = "▌"
        yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5

        try:
            # Stream output
            response = requests.post(urljoin(CFG.MODEL_SERVER, "generate_stream"),
                                     headers=headers, json=payload, stream=True, timeout=20)
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
                        yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5
                    else:
                        output = data["text"] + f" (error_code: {data['error_code']})"
                        state.messages[-1][-1] = output
                        yield (state, state.to_gradio_chatbot()) + (
                            disable_btn, disable_btn, disable_btn, enable_btn, enable_btn)
                        return

        except requests.exceptions.RequestException as e:
            state.messages[-1][-1] = server_error_msg + f" (error_code: 4)"
            yield (state, state.to_gradio_chatbot()) + (disable_btn, disable_btn, disable_btn, enable_btn, enable_btn)
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
    if sql_mode in ["直接执行结果"]:
        return gr.update(visible=True)
    else:
        return gr.update(visible=False)


def change_mode(mode):
    if mode in ["默认知识库对话", "LLM原生对话"]:
        return gr.update(visible=False)
    else:
        return gr.update(visible=True)


def change_tab():
    autogpt = True


def build_single_model_ui():
    notice_markdown = """
    # DB-GPT
    
    [DB-GPT](https://github.com/csunny/DB-GPT) 是一个开源的以数据库为基础的GPT实验项目，使用本地化的GPT大模型与您的数据和环境进行交互，无数据泄露风险，100% 私密，100% 安全。 
    """
    learn_more_markdown = """ 
        ### Licence
        The service is a research preview intended for non-commercial use only. subject to the model [License](https://github.com/facebookresearch/llama/blob/main/MODEL_CARD.md) of Vicuna-13B 
    """

    state = gr.State()
    gr.Markdown(notice_markdown, elem_id="notice_markdown")

    with gr.Accordion("参数", open=False, visible=False) as parameter_row:
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
            label="最大输出Token数",
        )
    tabs = gr.Tabs()
    with tabs:
        tab_sql = gr.TabItem("SQL生成与诊断", elem_id="SQL")
        with tab_sql:
            # TODO A selector to choose database
            with gr.Row(elem_id="db_selector"):
                db_selector = gr.Dropdown(
                    label="请选择数据库",
                    choices=dbs,
                    value=dbs[0] if len(models) > 0 else "",
                    interactive=True,
                    show_label=True).style(container=False)

            sql_mode = gr.Radio(["直接执行结果", "不执行结果"], show_label=False, value="不执行结果")
            sql_vs_setting = gr.Markdown("自动执行模式下, DB-GPT可以具备执行SQL、从网络读取知识自动化存储学习的能力")
            sql_mode.change(fn=change_sql_mode, inputs=sql_mode, outputs=sql_vs_setting)

        tab_qa = gr.TabItem("知识问答", elem_id="QA")
        with tab_qa:
            mode = gr.Radio(["LLM原生对话", "默认知识库对话", "新增知识库对话"], show_label=False, value="LLM原生对话")
            vs_setting = gr.Accordion("配置知识库", open=False)
            mode.change(fn=change_mode, inputs=mode, outputs=vs_setting)
            with vs_setting:
                vs_name = gr.Textbox(label="新知识库名称", lines=1, interactive=True)
                vs_add = gr.Button("添加为新知识库")
                with gr.Column() as doc2vec:
                    gr.Markdown("向知识库中添加文件")
                    with gr.Tab("上传文件"):
                        files = gr.File(label="添加文件",
                                        file_types=[".txt", ".md", ".docx", ".pdf"],
                                        file_count="multiple",
                                        allow_flagged_uploads=True,
                                        show_label=False
                                        )

                        load_file_button = gr.Button("上传并加载到知识库")
                    with gr.Tab("上传文件夹"):
                        folder_files = gr.File(label="添加文件夹",
                                               accept_multiple_files=True,
                                               file_count="directory",
                                            show_label=False)
                        load_folder_button = gr.Button("上传并加载到知识库")

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
                send_btn = gr.Button(value="发送", visible=False)

    with gr.Row(visible=False) as button_row:
        regenerate_btn = gr.Button(value="重新生成", interactive=False)
        clear_btn = gr.Button(value="清理", interactive=False)

    gr.Markdown(learn_more_markdown)
    btn_list = [regenerate_btn, clear_btn]
    regenerate_btn.click(regenerate, state, [state, chatbot, textbox] + btn_list).then(
        http_bot,
        [state, mode, sql_mode, db_selector, temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )
    clear_btn.click(clear_history, None, [state, chatbot, textbox] + btn_list)

    textbox.submit(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, mode, sql_mode, db_selector, temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )

    send_btn.click(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, mode, sql_mode, db_selector, temperature, max_output_tokens],
        [state, chatbot] + btn_list
    )
    vs_add.click(fn=save_vs_name, show_progress=True,
                           inputs=[vs_name],
                           outputs=[vs_name])
    load_file_button.click(fn=knowledge_embedding_store,
                           show_progress=True,
                           inputs=[vs_name, files],
                           outputs=[vs_name])
    load_folder_button.click(fn=knowledge_embedding_store,
                             show_progress=True,
                             inputs=[vs_name, folder_files],
                             outputs=[vs_name])
    return state, chatbot, textbox, send_btn, button_row, parameter_row


def build_webdemo():
    with gr.Blocks(
            title="数据库智能助手",
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
        shutil.move(file.name, os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, vs_id, filename))
        knowledge_embedding_client = KnowledgeEmbedding(
            file_path=os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, vs_id, filename),
            model_name=LLM_MODEL_CONFIG["text2vec"],
            local_persist=False,
            vector_store_config={
                "vector_store_name": vector_store_name["vs_name"],
                "vector_store_path": KNOWLEDGE_UPLOAD_ROOT_PATH})
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

    # dbs = get_database_list()
    cfg.set_plugins(scan_plugins(cfg, cfg.debug_mode))

    # 加载插件可执行命令
    command_categories = [
        "pilot.commands.audio_text",
        "pilot.commands.image_gen",
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
        server_name=args.host, server_port=args.port, share=args.share, max_threads=200,
    )
