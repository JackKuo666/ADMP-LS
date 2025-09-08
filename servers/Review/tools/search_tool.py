import hashlib
import aiohttp
from typing import List, Optional
from pydantic import BaseModel, Field
from agents import RunContextWrapper, function_tool

# 处理相对导入
try:
    from ..util import formate_message
    from ..setting_config import settings
    from ..config_logger import logger
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from util import formate_message
    from setting_config import settings
    from config_logger import logger
ARTICLE_SEARCH_URL = f"{settings.SEARCH_URL}/retrieve"


class Article(BaseModel):
    """Represents a scientific article from PubMed"""

    title: str | None = Field(description="The title of the article")
    authors: str | None = Field(description="The authors of the article")
    journal: str | None = Field(
        description="The journal where the article was published"
    )
    year: str | None = Field(description="Publication year")
    # abstract: str = Field(description="Abstract of the article")
    url: str | None = Field(description="url if web search", default="")
    source_query: str | None = Field(
        description="The query used to find this article", default=""
    )
    text: str | None = Field(
        description="text of the article by vector search",
    )
    volume: str | None = Field(description="The volume of the article")
    page: str | None = Field(description="The page of the article")


class SimpleArticle(BaseModel):
    """Represents a scientific article from search"""

    hash_id: str = Field(description="The hash id of the article")
    source: str = Field(
        description="The detail source of the article ,use the return of tool"
    )
    text: str = Field(description="The text of the article")


async def get_literature_articles(
    query: str,
    user_id: str = "",
    # thoughts_callback,
    num_to_show: int = 5,
    search_source: str = "pubmed",
    url: str = ARTICLE_SEARCH_URL,
):
    
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    # if is_pubmed:
    #     data_s = 'pubmed'
    # else:
    #     data_s = 'vector'
    data_s = search_source
    payload = {
        "query": query,
        "top_k": num_to_show,
        "search_type": "keyword",
        "data_source": [data_s],
        "user_id": user_id,
        "is_rerank": False,
    }
    timeout = aiohttp.ClientTimeout(total=600)
    try:
        async with aiohttp.ClientSession(timeout=timeout,trust_env = True) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_msg = (
                        f"literature articles API returned status {response.status}"
                    )
                    logger.error(
                        f"user_id :{user_id}, query :{query}, literature articles API returned error : {error_msg}"
                    )
                    return None

                search_response = await response.json()
                stautus = search_response.get("success")
                logger.info(
                    f"user_id :{user_id}, query :{query}, literature articles API returned sutaus {stautus}, response is {str(await response.json())[:50]}"
                )
                response_data = search_response.get("data", [])
                return response_data
    except Exception as e:
        logger.error(
            f"user_id :{user_id}, query :{query}, literature articles API returned error : {e}"
        )
        return None


async def pubmed_search_function(
    query: str, user_id: str = "", num_to_show: int = 20, search_source: str = "pubmed"
) -> List[Article]:
    """
    Search PubMed for scientific articles related to the query.

    Args:
        query: The search query for PubMed
        num_to_show: the number of search results
    Returns:
        A list of articles from PubMed with title, authors, journal, year, and abstract
    """
    results = []

    try:
        articles = await get_literature_articles(
            query, user_id=user_id, num_to_show=num_to_show, search_source=search_source
        )
    except Exception as e:
        # print(f"literature articles API returned error : {e}")
        logger.error(
            f"user_id :{user_id}, query :{query}, literature articles API returned error : {e}"
        )
        articles = []
        # results= await pubmed_retrivers(query=query, num_to_show=num_to_show)
        pass
    if articles:
        for article in articles:
            if article is None:
                logger.warning(
                    f"user_id :{user_id}, query :{query}, literature articles API returned None"
                )
                continue
            try:
                journal_info = article.get("journal", "")
                if isinstance(journal_info, dict):
                    journal = journal_info.get("abbreviation", "")
                    start_page = journal_info.get("startPage", "")
                    end_page = journal_info.get("endPage", "")
                    volume = journal_info.get("volume", "")
                    if start_page and end_page:
                        page = f"{start_page}-{end_page}"
                    elif start_page:
                        page = start_page
                    elif end_page:
                        page = end_page
                    else:
                        page = ""
                else:
                    journal = ""
                    page = ""
                    volume = ""
                results.append(
                    Article(
                        title=article.get("title", ""),
                        authors=article.get("authors", ""),
                        journal=journal,
                        year=(
                            article.get("pub_date", {}).get("year", "")
                            if isinstance(article.get("pub_date"), dict)
                            else ""
                        ),
                        url=article.get("url", ""),
                        text=article.get("text", ""),
                        source_query=query,
                        volume=volume,
                        page=page,
                    )
                )
            except Exception as e:
                logger.error(
                    f"user_id :{user_id}, query :{query}, literature articles append error: {e}"
                )
                pass
    return results


def format_author_name(full_name: str) -> str:
    """
    Format author name to extract first name and last name initial.

    Args:
        full_name: Full author name string

    Returns:
        Formatted name as "FirstName LastInitial."
    """
    try:
        # Remove extra spaces and split by space
        name_parts = full_name.strip().split()

        if len(name_parts) == 0:
            return full_name
        elif len(name_parts) == 1:
            # Only one name, return as is
            return name_parts[0]
        else:
            # Get first name and last name initial
            last_name = name_parts[0:-1]
            first_name = name_parts[-1]
            # Extract the initials of all parts of the last name and concatenate them
            last_initial = "".join([n[0].upper() for n in last_name if n])

            return f"{first_name} {last_initial}." if last_initial else first_name
    except Exception:
        return full_name


def reorganize_pubmed_article(article: Article) -> Optional[SimpleArticle]:
    """
    Reorganize a PubMed article into a SimpleArticle format.

    Args:
        article: The original Article object

    Returns:
        SimpleArticle with properly formatted source citation, or None if invalid
    """
    try:
        # Skip articles with no meaningful text content
        if not article.text or article.text == "Unknown" or article.text.strip() == "":
            return None

        authors = ""
        if article.authors and article.authors != "Unknown":
            authors_list = article.authors.split(",")
            if len(authors_list) == 2:
                authors = (
                    format_author_name(authors_list[0])
                    + " & "
                    + format_author_name(authors_list[1])
                )
            elif len(authors_list) > 2:
                # Format the first author name
                formatted_first_author = format_author_name(authors_list[0])
                authors = formatted_first_author + " et al."
            else:
                # Format the single author name
                authors = format_author_name(authors_list[0])
        # print(f"authors_list: {authors_list}, authors: {authors}")
        # Format: Author(s) (Year). Title. Journal, Volume(Issue), Pages.
        year = f"({article.year or ''})"
        title = f"{article.title or ''}"
        journal = f"{article.journal or ''}"
        volume = f"{article.volume or ''},"
        page = f"{article.page or ''}"
        if authors.strip():
            source = " ".join([authors, title, journal, volume, page, year])
        else:
            source = " ".join([title, journal, volume, page, year])
        # Remove trailing spaces and commas from the source string
        source = source.strip().rstrip(",")

        # Generate hash from source string
        source_hash = hashlib.md5(source.encode("utf-8")).hexdigest()[:8]

        # Add hash to source if it exists
        # if source.strip():
        #     source = f"{source} [ID: {source_hash}]"
        return SimpleArticle(
            hash_id=source_hash,
            source=source,
            text=article.text,
        )
    except Exception as e:
        logger.error(f"reorganize_pubmed_article error: {e}")
        return None


def reorganize_personal_article(article: Article) -> Optional[SimpleArticle]:
    """
    Reorganize a personal/vector article into a SimpleArticle format.

    Args:
        article: The original Article object

    Returns:
        SimpleArticle with title as source, or None if invalid
    """
    try:
        # Skip articles with no meaningful text content
        if not article.text or article.text == "Unknown" or article.text.strip() == "":
            return None

        return SimpleArticle(
            source=article.title + "[From Personal Vector]",
            text=article.text,
        )
    except Exception as e:
        logger.error(f"reorganize_personal_article error: {e}")
        return None


async def get_article_simple_source(
    query: str, user_id: str = "", number_to_show: int = 20, is_pkb: bool = False
) -> List[SimpleArticle]:
    """
    Search for articles from both PubMed and personal vector sources and return them as SimpleArticle objects.

    Args:
        query: Search query string
        user_id: User identifier
        number_to_show: Number of articles to retrieve from each source

    Returns:
        List of SimpleArticle objects from both sources
    """
    results = []
    if is_pkb:
        # Search pubmed and personal vector sources
        personal_articles = await pubmed_search_function(
            query, user_id=user_id, num_to_show=10, search_source="personal_vector"
        )
        results.extend(
            reorganize_personal_article(article)
            for article in personal_articles
            if reorganize_personal_article(article)
        )
    else:
        personal_articles = []
        results.extend(
            reorganize_personal_article(article)
            for article in personal_articles
            if reorganize_personal_article(article)
        )
    num_pubmed = number_to_show - len(results)
    # print(f"num_pubmed: {num_pubmed}, number_to_show: {number_to_show}, len(personal_articles): {len(results)}")
    if num_pubmed > 0:
        pubmed_articles = await pubmed_search_function(
            query, user_id=user_id, num_to_show=num_pubmed, search_source="pubmed"
        )
    else:
        pubmed_articles = []

    # Process PubMed articles
    results.extend(
        reorganize_pubmed_article(article)
        for article in pubmed_articles
        if reorganize_pubmed_article(article)
    )
    # Process personal articles

    return results


@function_tool
async def article_simple_search(
    ctx: RunContextWrapper,
    query: str,
) -> List[SimpleArticle]:
    """
    Search for information and return them as SimpleArticle objects.

    Args:
        query: The search query string

    Returns:
        List of SimpleArticle objects with formatted source citations
    """

    is_pkb = ctx.context.is_pkb or False
    query = query[:50]
    if is_pkb:
        user_id = ctx.context.u_id or ""
    else:
        user_id = ""
    logger.info(f"article_simple_search, input is {query},is_pkb#########:{is_pkb}")

    reformated = formate_message(
        type="search", message=f"Searching articles by Articles_search_tool ...{query}"
    )
    if ctx.context.results_callback:
        await ctx.context.results_callback(reformated)

    results = await get_article_simple_source(
        query, user_id=user_id, number_to_show=10, is_pkb=is_pkb
    )
    logger.info(
        f"find {len(results)} research results,is_pkb:{is_pkb},user_id:{user_id},results:{str(results)[:100]}"
    )
    return results
