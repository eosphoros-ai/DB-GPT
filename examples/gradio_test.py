#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import gradio as gr


def change_tab():
    return gr.Tabs.update(selected=1)


with gr.Blocks() as demo:
    with gr.Tabs() as tabs:
        with gr.TabItem("Train", id=0):
            t = gr.Textbox()
        with gr.TabItem("Inference", id=1):
            i = gr.Image()

    btn = gr.Button()
    btn.click(change_tab, None, tabs)

demo.launch()
