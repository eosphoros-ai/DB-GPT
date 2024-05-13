"""Search tools for the agent."""

import re

from typing_extensions import Annotated, Doc

from ...resource.tool.base import tool


@tool(
    description="Baidu search and return the results as a markdown string. Please set "
    "number of results not less than 8 for rich search results.",
)
def baidu_search(
    query: Annotated[str, Doc("The search query.")],
    num_results: Annotated[int, Doc("The number of search results to return.")] = 8,
) -> str:
    """Baidu search and return the results as a markdown string.

    Please set number of results not less than 8 for rich search results.
    """
    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) "
        "Gecko/20100101 Firefox/112.0"
    }
    url = f"https://www.baidu.com/s?wd={query}&rn={num_results}"
    response = requests.get(url, headers=headers)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    search_results = []
    for result in soup.find_all("div", class_=re.compile("^result c-container ")):
        title = result.find("h3", class_="t").get_text()
        link = result.find("a", href=True)["href"]
        snippet = result.find("span", class_=re.compile("^content-right_"))
        if snippet:
            snippet = snippet.get_text()
        else:
            snippet = ""
        search_results.append({"title": title, "href": link, "snippet": snippet})

    return _search_to_view(search_results)


def _search_to_view(results) -> str:
    view_results = []
    for item in results:
        view_results.append(
            f"### [{item['title']}]({item['href']})\n{item['snippet']}\n"
        )
    return "\n".join(view_results)
