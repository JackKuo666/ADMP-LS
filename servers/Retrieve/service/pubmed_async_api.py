import asyncio
import time
from typing import Dict, List
import aiohttp

from config.global_storage import get_model_config
from dto.bio_document import PubMedDocument
from service.pubmed_xml_parse import PubmedXmlParse
from utils.bio_logger import bio_logger as logger

PUBMED_ACCOUNT = [
    {"email": "email1@gmail.com", "api_key": "60eb67add17f39aa588a43e30bb7fce98809"},
    {"email": "email2@gmail.com", "api_key": "fd9bb5b827c95086b9c2d579df20beca2708"},
    {"email": "email3@gmail.com", "api_key": "026586b79437a2b21d1e27d8c3f339230208"},
    {"email": "email4@gmail.com", "api_key": "bca0489d8fe314bfdbb1f7bfe63fb5d76e09"},
]


class PubMedAsyncApi:
    def __init__(self):
        self.pubmed_xml_parse = PubmedXmlParse()
        self.model_config = get_model_config()

    async def pubmed_search_function(
        self, query: str, top_k: int, search_type: str
    ) -> List[PubMedDocument]:

        try:
            start_time = time.time()
            logger.info(
                f'Trying to search PubMed for "{query}", top_k={top_k}, search_type={search_type}'
            )
            id_list = await self.search_database(
                query, db="pubmed", retmax=top_k, search_type=search_type
            )
            articles = await self.fetch_details(
                id_list, db="pubmed", rettype="abstract"
            )

            end_search_pubmed_time = time.time()
            logger.info(
                f'Finished searching PubMed for "{query}", took {end_search_pubmed_time - start_time:.2f} seconds, found {len(articles)} results'
            )

            return [
                PubMedDocument(
                    title=result["title"],
                    abstract=result["abstract"],
                    authors=self.process_authors(result["authors"]),
                    doi=result["doi"],
                    source="pubmed",
                    source_id=result["pmid"],
                    pub_date=result["pub_date"],
                    journal=result["journal"],
                )
                for result in articles
            ]
        except Exception as e:
            logger.error(f"Error searching PubMed query: {query} error: {e}")
            raise e

    def process_authors(self, author_list: List[Dict]) -> str:

        return ", ".join(
            [f"{author['forename']} {author['lastname']}" for author in author_list]
        )

    # 搜索数据库（ESearch）
    async def search_database(
        self, query: str, db: str, retmax: int, search_type: str = "keyword"
    ) -> List[Dict]:
        if search_type not in ["keyword", "advanced"]:
            raise ValueError("search_type must be one of 'keyword' or 'advanced'")

        if search_type == "keyword":
            art_type_list = [
                "Address",
                "Bibliography",
                "Biography",
                "Books and Documents",
                "Clinical Conference",
                "Clinical Study",
                "Collected Works",
                "Comment",
                "Congress",
                "Consensus Development Conference",
                "Consensus Development Conference, NIH",
                "Dictionary",
                "Directory",
                "Duplicate Publication",
                "Editorial",
                "Festschrift",
                "Government Document",
                "Guideline",
                "Interactive Tutorial",
                "Interview",
                "Lecture",
                "Legal Case",
                "Legislation",
                "Letter",
                "News",
                "Newspaper Article",
                "Patient Education Handout",
                "Periodical Index",
                "Personal Narrative",
                "Practice Guideline",
                "Published Erratum",
                "Technical Report",
                "Video-Audio Media",
                "Webcast",
            ]
            art_type = "(" + " OR ".join(f'"{j}"[Filter]' for j in art_type_list) + ")"
            query = "( " + query + ")"
            query += " AND (fha[Filter]) NOT " + art_type

        id_list = await self.esearch(query=query, retmax=retmax)

        if len(id_list) == 0:
            return []

        return id_list

    async def esearch(self, query=None, retmax=10):
        start_time = time.time()
        db = "pubmed"
        server = "esearch"
        random_index = int((time.time() * 1000) % len(PUBMED_ACCOUNT))
        random_pubmed_account = PUBMED_ACCOUNT[random_index]

        api_key = random_pubmed_account["api_key"]
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{server}.fcgi?db={db}&term={query}&retmode=json&api_key={api_key}&sort=relevance&retmax={retmax}"
        response = await self.async_http_get(url=url)

        id_list = response["esearchresult"]["idlist"]
        logger.info(
            f"pubmed_async_http get id_list, search Time taken: {time.time() - start_time}s"
        )

        return id_list

    async def async_http_get(self, url: str):
        async with aiohttp.ClientSession() as session:
            try_time = 1
            while try_time < 4:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(
                            f"{url},try_time:{try_time},Error: {response.status}"
                        )
                        try_time += 1
                        # 睡眠0.5秒后重试
                        await asyncio.sleep(0.5)
        raise Exception(f"Failed to fetch data from {url} after 3 attempts")

    async def async_http_get_text(self, url: str, params=None):
        async with aiohttp.ClientSession() as session:
            try_time = 1
            while try_time < 4:
                async with session.get(url, params=params) as response:
                    if response.status == 200:

                        return await response.text()
                    else:
                        logger.error(
                            f"{url},try_time:{try_time},Error: {response.status}"
                        )
                        try_time += 1
                        # 睡眠0.5秒后重试
                        await asyncio.sleep(0.5)
        raise Exception(f"Failed to fetch data from {url} after 3 attempts")

    # 获取详细信息（EFetch）
    async def fetch_details(self, id_list, db="pubmed", rettype="abstract"):
        start_time = time.time()
        try:
            ids = ",".join(id_list)
            server = "efetch"

            random_index = int((time.time() * 1000) % len(PUBMED_ACCOUNT))
            random_pubmed_account = PUBMED_ACCOUNT[random_index]
            api_key = random_pubmed_account["api_key"]
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{server}.fcgi?db={db}&id={ids}&retmode=xml&api_key={api_key}&rettype={rettype}"
            response = await self.async_http_get_text(url=url)
            articles = self.pubmed_xml_parse.parse_pubmed_xml(response)
            logger.info(
                f"pubmed_async_http fetch detail, Time taken: {time.time() - start_time}"
            )
            return articles
        except Exception as e:
            logger.error(f"Error fetching details for id_list: {id_list}, error: {e}")
            # pmid 精准匹配

        return []
