import re
from typing import List

from langchain.text_splitter import CharacterTextSplitter


class CHNDocumentSplitter(CharacterTextSplitter):
    def __init__(self, pdf: bool = False, sentence_size: int = None, **kwargs):
        super().__init__(**kwargs)
        self.pdf = pdf
        self.sentence_size = sentence_size

    def split_text(self, text: str) -> List[str]:
        if self.pdf:
            text = re.sub(r"\n{3,}", r"\n", text)
            text = re.sub("\s", " ", text)
            text = re.sub("\n\n", "", text)

        text = re.sub(r"([;；.!?。！？\?])([^”’])", r"\1\n\2", text)
        text = re.sub(r'(\.{6})([^"’”」』])', r"\1\n\2", text)
        text = re.sub(r'(\…{2})([^"’”」』])', r"\1\n\2", text)
        text = re.sub(r'([;；!?。！？\?]["’”」』]{0,2})([^;；!?，。！？\?])', r"\1\n\2", text)
        text = text.rstrip()
        ls = [i for i in text.split("\n") if i]
        for ele in ls:
            if len(ele) > self.sentence_size:
                ele1 = re.sub(r'([,，.]["’”」』]{0,2})([^,，.])', r"\1\n\2", ele)
                ele1_ls = ele1.split("\n")
                for ele_ele1 in ele1_ls:
                    if len(ele_ele1) > self.sentence_size:
                        ele_ele2 = re.sub(
                            r'([\n]{1,}| {2,}["’”」』]{0,2})([^\s])', r"\1\n\2", ele_ele1
                        )
                        ele2_ls = ele_ele2.split("\n")
                        for ele_ele2 in ele2_ls:
                            if len(ele_ele2) > self.sentence_size:
                                ele_ele3 = re.sub(
                                    '( ["’”」』]{0,2})([^ ])', r"\1\n\2", ele_ele2
                                )
                                ele2_id = ele2_ls.index(ele_ele2)
                                ele2_ls = (
                                    ele2_ls[:ele2_id]
                                    + [i for i in ele_ele3.split("\n") if i]
                                    + ele2_ls[ele2_id + 1 :]
                                )
                        ele_id = ele1_ls.index(ele_ele1)
                        ele1_ls = (
                            ele1_ls[:ele_id]
                            + [i for i in ele2_ls if i]
                            + ele1_ls[ele_id + 1 :]
                        )

                id = ls.index(ele)
                ls = ls[:id] + [i for i in ele1_ls if i] + ls[id + 1 :]
        return ls
