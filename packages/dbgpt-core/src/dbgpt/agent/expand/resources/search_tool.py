"""Search tools for the agent."""

import os
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
    try:
        import requests
    except ImportError:
        raise ImportError(
            "`requests` is required for baidu_search tool, please run "
            "`pip install requests` to install it."
        )
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError(
            "`beautifulsoup4` is required for baidu_search tool, please run "
            "`pip install beautifulsoup4` to install it."
        )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) "
        "Gecko/20100101 Firefox/112.0"
    }
    if num_results < 8:
        num_results = 8
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


@tool(
    description="Google search through the Serply API and return the results as a "
    "markdown string. Please set number of results not less than 8 for rich "
    "search results.",
)
def serply_search(
    query: Annotated[str, Doc("The search query.")],
    num_results: Annotated[int, Doc("The number of search results to return.")] = 8,
) -> str:
    """Google search through the Serply API and return the results as a markdown string.

    Reads the API key from the `SERPLY_API_KEY` environment variable. Get a key at
    https://serply.io, the API reference is at https://serply.io/docs.
    """
    try:
        import requests
    except ImportError:
        raise ImportError(
            "`requests` is required for serply_search tool, please run "
            "`pip install requests` to install it."
        )

    api_key = os.getenv("SERPLY_API_KEY")
    if not api_key:
        raise ValueError(
            "`SERPLY_API_KEY` environment variable is required for serply_search "
            "tool, get an API key at https://serply.io"
        )
    if num_results < 8:
        num_results = 8
    response = requests.get(
        "https://api.serply.io/v1/search",
        params={"q": query, "num": num_results},
        # Serply sits behind Cloudflare, which rejects the default requests
        # user agent.
        headers={"X-Api-Key": api_key, "User-Agent": "dbgpt"},
        timeout=10,
    )
    response.raise_for_status()

    search_results = []
    for result in response.json().get("results", [])[:num_results]:
        search_results.append(
            {
                "title": result.get("title", ""),
                "href": result.get("link", ""),
                "snippet": result.get("description", ""),
            }
        )

    return _search_to_view(search_results)


def _search_to_view(results) -> str:
    view_results = []
    for item in results:
        view_results.append(
            f"### [{item['title']}]({item['href']})\n{item['snippet']}\n"
        )
    return "\n".join(view_results)
