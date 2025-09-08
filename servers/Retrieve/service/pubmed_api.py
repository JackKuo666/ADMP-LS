import time
from typing import Dict, List
from Bio import Entrez
import requests
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


class PubMedApi:
    def __init__(self):
        self.pubmed_xml_parse = PubmedXmlParse()
        self.model_config = get_model_config()

    def pubmed_search_function(
        self, query: str, top_k: int, search_type: str
    ) -> List[PubMedDocument]:

        try:
            start_time = time.time()
            logger.info(
                f'Trying to search PubMed for "{query}", top_k={top_k}, search_type={search_type}'
            )
            id_list = self.search_database(query, retmax=top_k, search_type=search_type)
            records = self.fetch_details(id_list, db="pubmed", rettype="abstract")

            end_search_pubmed_time = time.time()
            logger.info(
                f'Finished searching PubMed for "{query}", took {end_search_pubmed_time - start_time:.2f} seconds, found {len(records)} results'
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
                    text=result["abstract"],
                )
                for result in records
            ]
        except Exception as e:
            logger.error(f"Error searching PubMed query: {query} error: {e}")
            raise e

    def process_authors(self, author_list: List[Dict]) -> str:

        return ", ".join(
            [f"{author['forename']} {author['lastname']}" for author in author_list]
        )

    # 搜索数据库（ESearch）
    def search_database(
        self, query: str, retmax: int, search_type: str = "keyword"
    ) -> List[str]:
        """
        获取pubmed数据库中的记录id列表
        :param search_type: 搜索类型，keyword或advanced
        :param query: 查询字符串
        :param retmax: 返回的最大结果数
        """
        start_time = time.time()
        db = "pubmed"
        handle = None
        try:
            # 随机从pubmed账号池中选择一个
            random_index = int((time.time() * 1000) % len(PUBMED_ACCOUNT))
            random_pubmed_account = PUBMED_ACCOUNT[random_index]
            Entrez.email = random_pubmed_account["email"]
            Entrez.api_key = random_pubmed_account["api_key"]
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
                handle = Entrez.esearch(
                    db=db, term=query, usehistory="y", sort="relevance", retmax=retmax
                )
            elif search_type == "advanced":
                handle = Entrez.esearch(
                    db=db, term=query, usehistory="y", sort="relevance", retmax=retmax
                )
            else:
                raise ValueError("search_type must be either 'keyword' or 'advanced'")

            results = Entrez.read(handle)
            id_list = results["IdList"]
            logger.info(
                f"Finished searching PubMed id, took {time.time() - start_time:.2f} seconds, found {len(id_list)} results,query: {query}"
            )
            logger.info(
                f"Search type:{search_type} PubMed search query: {query}, id_list: {id_list}"
            )
            if len(id_list) == 0:
                return []
            return id_list
        except Exception as e:
            logger.error(f"Error in search_database: {e}")
            raise e
        finally:
            # 确保handle被正确关闭，防止内存泄漏
            if handle is not None:
                try:
                    handle.close()
                except Exception as e:
                    logger.error(f"Error closing Entrez handle: {e}")

    def fetch_details(self, id_list, db="pubmed", rettype="abstract"):
        start_time = time.time()
        try:
            ids = ",".join(id_list)
            server = "efetch"

            random_index = int((time.time() * 1000) % len(PUBMED_ACCOUNT))
            random_pubmed_account = PUBMED_ACCOUNT[random_index]
            api_key = random_pubmed_account["api_key"]
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{server}.fcgi?db={db}&id={ids}&retmode=xml&api_key={api_key}&rettype={rettype}"
            response = requests.get(url)
            articles = self.pubmed_xml_parse.parse_pubmed_xml(response.text)
            logger.info(
                f"pubmed_async_http fetch detail, Time taken: {time.time() - start_time}"
            )
            return articles
        except Exception as e:
            logger.error(f"Error fetching details for id_list: {id_list}, error: {e}")
            # pmid 精准匹配

        return []
