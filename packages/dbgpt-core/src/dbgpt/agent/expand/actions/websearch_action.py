import json
import logging
import random
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import charset_normalizer
import pandas as pd
import requests
from bs4 import BeautifulSoup

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict
from dbgpt.vis.tags.vis_chart import VisChart

# from dbgpt.agent.core.action.base import Action, ActionOutput
# from dbgpt.agent.resource.base import AgentResource, ResourceType
from ...core.action.base import Action, ActionOutput
from ...resource.base import AgentResource

logger = logging.getLogger(__name__)

# -------------------------- 基础配置（修复+优化） --------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bing_search.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
    "like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
]

# 2. 全局Session（复用连接+默认头）
session = requests.Session()
session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/113.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
)


def clean_text(text):
    """清洗文本：移除控制字符、非打印字符，保留纯文本"""
    if not isinstance(text, str):
        return ""
    cleaned = re.sub(r"[\x00-\x1F\x7F]", "", text)
    cleaned = re.sub(r"\n+", "\n\n", cleaned).strip()
    cleaned = re.sub(r" +", " ", cleaned)
    cleaned = re.sub(
        r'[^\u4e00-\u9fa5a-zA-Z0-9\s,.，。；;！!？?：:""' "（）()【】[\]{}、/\\-]",
        "",
        cleaned,
    )
    return cleaned


def get_page_content(url, worker=None):
    """
    获取指定URL页面的所有文本内容，处理编码并过滤非HTML内容，同时尽量保留原网页的文本格式。
    支持中断功能：使用流式下载数据，并在每个块读取时检测 worker 的中断标志。
    """
    if worker and not worker.is_running:
        logging.info(f"中断获取页面内容：{url}")
        return "任务已中断，无法获取内容"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/113.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        logging.info(f"请求页面内容: {url}")
        # 使用 stream=True 以便分块读取数据
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            logging.warning(f"非HTML内容，跳过: {url}，Content-Type: {content_type}")
            return "非HTML内容，无法提取"

        chunks = []
        # 以 1KB 为单位读取响应数据，并在每个块时检查中断标志
        for chunk in response.iter_content(chunk_size=1024):
            if worker and not worker.is_running:
                logging.info(f"中断获取页面内容：{url}")
                response.close()
                return "任务已中断，无法获取内容"
            chunks.append(chunk)
        content_bytes = b"".join(chunks)

        detected = charset_normalizer.from_bytes(content_bytes).best()
        encoding = detected.encoding if detected and detected.encoding else "utf-8"
        text = content_bytes.decode(encoding, errors="replace")
    except requests.RequestException as e:
        logging.error(f"获取页面内容失败 ({url}): {e}")
        return "无法获取内容"
    except Exception as e:
        logging.error(f"解码页面内容失败 ({url}): {e}")
        return "无法提取内容"

    soup = BeautifulSoup(text, "html.parser")

    article = soup.find("article")
    if article:
        extracted_text = "\n\n".join(
            [
                p.get_text(separator="\n", strip=True)
                for p in article.find_all(
                    ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]
                )
            ]
        )
    else:
        paragraphs = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"])
        extracted_text = "\n\n".join(
            [p.get_text(separator="\n", strip=True) for p in paragraphs]
        )

    extracted_text = clean_text(extracted_text)
    if len(extracted_text) < 200:
        logging.debug(f"提取内容过短 ({len(extracted_text)} 字符), 使用备用方法。")
        extracted_text = "\n\n".join(
            [
                p.get_text(separator="\n", strip=True)
                for p in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"])
            ]
        )
        extracted_text = clean_text(extracted_text)

    return extracted_text if extracted_text else "无法提取内容"


def get_bing_search_results(query, num_results=5, worker=None):
    query_encoded = urllib.parse.quote_plus(query)
    url = f"https://www.bing.com/search?q={query_encoded}"
    logging.info(f"发送请求到Bing URL: {url}")
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.bing.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            # You can set cookies and other request headers here
            # "cookie": "your_cookie_here",
        }

        # user headers in request
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            logging.error(
                f"搜索结果页面非HTML内容: {url}，Content-Type: {content_type}"
            )
            raise Exception("搜索结果页面非HTML内容")

        detected = charset_normalizer.from_bytes(response.content).best()
        encoding = detected.encoding if detected and detected.encoding else "utf-8"

        text = response.content.decode(encoding, errors="replace")
        logging.info(f"检测到编码: {encoding}，Bing搜索结果页面URL: {url}")
    except Exception as e:
        logging.error(f"请求或解码Bing搜索结果失败：{e}")
        raise Exception(f"请求或解码Bing搜索结果失败：{e}")

    soup = BeautifulSoup(text, "html.parser")
    processed_count = 0

    # 更鲁棒的查找：处理多类型结果容器
    # 常见容器包括 li.b_algo, li.b_ans, div.b_vlist, div.b_mhdr (等)
    candidates = soup.select("li.b_algo, li.b_ans, div.b_vlist > li, div.b_mhdr")
    links = []

    for el in candidates:
        processed_count += 1
        # 提取链接
        a = el.select_one("h2 a") or el.select_one("a")
        link = a["href"] if a and a.has_attr("href") else None

        # 提取标题（即使暂时不用也保留，方便后续使用）
        title = a.get_text(strip=True) if a else el.get_text(strip=True)[:80]

        # 提取摘要
        snippet_tag = el.select_one("p") or el.select_one(".b_caption p")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        # 过滤无效链接和不需要的域名
        if not link:
            continue  # 跳过无链接的结果
        if link.startswith("https://www.zhihu.com"):
            continue  # 过滤知乎链接

        print(f"候选结果: {title} - {link}")
        # 只保存必要的基础信息，不包含内容字段
        links.append({"title": title, "link": link, "snippet": snippet})

        # 达到所需结果数量则停止收集
        if len(links) >= num_results:
            break

    logging.info(f"处理候选数: {processed_count}, 收集链接数: {len(links)}")

    # 后续需要时，再从链接获取内容
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_link = {}
        for link_info in links:
            if worker and not worker.is_running:
                logging.info("抓取内容任务被中断。")
                break
            # 提交任务获取内容
            future = executor.submit(get_page_content, link_info["link"], worker)
            future_to_link[future] = link_info

        for future in as_completed(future_to_link):
            if worker and not worker.is_running:
                logging.info("抓取内容任务被中断，取消剩余任务。")
                for fut in future_to_link:
                    if not fut.done():
                        fut.cancel()
                break

            link_info = future_to_link[future]
            try:
                # 补充内容信息
                content = future.result()
                results.append(
                    {
                        **link_info,  # 扩展已有的标题、链接、摘要
                        "content": content,  # 新增内容字段
                    }
                )
            except Exception as e:
                logging.error(f"抓取内容时出错 ({link_info['link']}): {e}")
                results.append({**link_info, "content": "无法获取内容"})

    return results


# if __name__ == "__main__":
#     test_query = "2025年中秋节日期？"
#     try:
#         search_results = get_bing_search_results(test_query, num_results=3)
#         for idx, res in enumerate(search_results):
#             print(f"结果 {idx+1}:")
#             print(f"标题: {res['title']}")
#             print(f"链接: {res['link']}")
#             print(f"摘要: {res['snippet']}")
#             print(f"内容预览: {res['content'][:200]}...")  # 只显示前200字符
#             print("-" * 80)
#     except Exception as e:
#         print(f"搜索失败: {e}")


class SqlInput(BaseModel):
    """SQL input model."""

    is_need: str = Field(
        ...,
        description="Whether you need to use web search to answer user questions, "
        "must be strictly 'yes' or 'no' (lowercase), no other values allowed",
    )

    keywords: str = Field(
        ...,
        description="Keywords that need to be retrieved through search engines to "
        "answer users' questions.If is_need is 'no', keywords must be an empty "
        "string ('')",
    )

    thought: str = Field(..., description="Summary of thoughts to the user")


class WebSearchAction(Action[SqlInput]):
    """Chart action class."""

    def __init__(self, **kwargs):
        """Chart action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisChart()

    @property
    def out_model_type(self):
        """Return the output model type."""
        return SqlInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action."""
        try:
            param: SqlInput = self._input_convert(ai_message, SqlInput)
        except Exception as e:
            logger.exception(f"{str(e)}! \n {ai_message}")
            return ActionOutput(
                is_exe_success=False,
                content="Error:The answer is not output in the required format.",
            )
        try:
            is_need = param.is_need.lower()
            keywords = param.keywords
            if is_need not in ["yes", "no"]:
                return ActionOutput(
                    is_exe_success=False,
                    content="Error:The value of 'is_need' must be strictly "
                    "'yes' or 'no'(lowercase), no other values allowed.",
                )
            if is_need == "no" or (is_need == "yes" and not keywords.strip()):
                ActionOutput(is_exe_success=True, content="No web search needed.")
            data_df = pd.DataFrame()
            if is_need == "yes":
                results = get_bing_search_results(keywords, num_results=3)
                data_df = pd.DataFrame(results)

            param_dict = model_to_dict(param)
            if not data_df.empty:
                param_dict["data"] = json.loads(
                    data_df.to_json(orient="records", date_format="iso", date_unit="s")
                )
            else:
                return ActionOutput(
                    is_exe_success=False,
                    content="Error:No data retrieved from web search in this keywords.",
                )
            content = (
                "Through online search, we retrieved the following content："
                + json.dumps(param_dict)
            )

            return ActionOutput(is_exe_success=True, content=content)
        except Exception:
            logger.exception("Check your questions,the websearch run failed!")
            return ActionOutput(
                is_exe_success=False,
                content="Error:Check your questions,the websearch run failed!"
                "Reason:{str(e)}",
            )
