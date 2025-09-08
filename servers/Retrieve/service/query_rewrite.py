import time
from bio_agent.rewrite_agent import RewriteAgent
from utils.bio_logger import bio_logger as logger
from datetime import datetime

# Instruct
INSTRUCTIONS_rewrite = f"""
    You are a research expert with strong skills in question categorization and optimizing PubMed searches.
    
    Frist, classify the research question into exactly one of the following categories:
    - Review: Queries that summarize existing knowledge or literature on a topic.
    - Question_Answer: Queries that seek specific answers to scientific questions.
    
    
    Secondly, extract the 3-6 key words of the research question. The key words should be the most important terms or phrases that capture the essence of the research question. These key words should be relevant to the topic and can be used to generate search queries. These key words should be relavant to medicine, biology, health, disease.
    
    Thirdly,using the given keywords, please identify at least 60 leading authoritative journals in this field, including their names and EISSNs. It would be ok to include journals that are not strictly in the field of medicine, biology, health, or disease, but are relevant to the topic and the journals should be well-known and respected in their respective fields. The EISSN is the electronic International Standard Serial Number for the journal.
    
    Next, break down this research question into specific search queries for PubMed that comprehensively cover all important aspects of the topic. Generate as many search queries as necessary to ensure thorough coverage - don't limit yourself to a fixed number.

    Each query should:
    1. Be concise (3-6 words maximum)
    2. Focus on a specific aspect of the research question
    3. Use appropriate scientific terminology
    4. Be suitable for a scientific database search
    5. Collectively cover the full breadth of the research topic
    
    If the query's type is review, generate additional queries (10-20) to ensure thorough coverage. If the query's type is question-answer, fewer queries (5-10) may be sufficient.

    Avoid long phrases, questions, or full sentences, as these are not effective for database searches.

    Examples of good queries:
    - "CRISPR cancer therapy"
    - "tau protein Alzheimer's"
    - "microbiome obesity metabolism"
    
    Then, construct the final PubMed search query based on the following filters:
    - "date_range": {{"start": "YYYY/MM/DD", "end": "YYYY/MM/DD",}}, only populate this field if the query contains phrases like "the past x years" or "the last x years"; otherwise, leave blank as default.
    - "article_types": [],array of publication types, only if user specify some publication types, otherwise leave blank as default.
    - "languages": [],array of language filters,if user do not specify, use English as default.
    - "subjects": [],if user do not specify, use human as default.
    - "journals": [], if user do not specify, use [] as default.
    - "author": [{{"name": string, "first_author": boolean, "last_author": boolean}}], if user do not specify, use {{}} as default.
    
    
    IMPORTANT: Your output MUST be a valid JSON object with a "queries" field containing an array of strings. For example:
    ```
    {{ "category": "Review", 
       "key_words":["CRISPR", "cancer", "therapy"], 
       "key_journals":[{{"name":"Nature","EISSN":"1476-4687"}}],
       "queries": [
        "CRISPR cancer therapy",
        "tau protein Alzheimer's",
        "microbiome obesity metabolism"
       ],
       "filters": {{"date_range": {{"start": "2019/01/01", "end": "2024/01/01"}},
                   "article_types": [],
                   "languages": ["English"],
                   "subjects": ["human"],
                   "journals": [],
                   "author": {{"name": "", "first_author": false, "last_author": false}}
       }}
    }}

    Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only.If you are not sure about the output, output an empty array.
    
"""

SIMPLE_INSTRUCTIONS_rewrite = f"""
    You are a research expert with strong skills in question categorization and optimizing PubMed searches.
    Extract the 3-6 key words of the research question. The key words should be the most important terms or phrases that capture the essence of the research question. These key words should be relevant to the topic and can be used to generate search queries. These key words should be relavant to medicine, biology, health, disease.
    IMPORTANT: Your output MUST be a valid JSON object. For example:
    ```
    {{ 
       "key_words":["CRISPR", "cancer", "therapy"], 
    }}

    Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only.If you are not sure about the output, output an empty array.
    """
    

def build_pubmed_filter_query(data):
    
    # 基础查询部分（queries的组合）
    base_query = ""
    
    # 构建过滤器部分
    filters = []
    
    # 日期范围过滤
    date_range = data["filters"].get("date_range", {})
    if date_range.get("start") or date_range.get("end"):
        start_date = date_range.get("start", "1000/01/01")  # 很早的日期作为默认
        end_date = date_range.get("end", datetime.now().strftime("%Y/%m/%d"))  # 当前日期作为默认
        date_filter = f'("{start_date}"[Date - Publication] : "{end_date}"[Date - Publication])'
        filters.append(date_filter)
    
    # 文章类型过滤
    article_types = data["filters"].get("article_types", [])
    if article_types:
        type_filter = " OR ".join([f'"{at}"[Publication Type]' for at in article_types])
        filters.append(f"({type_filter})")
    
    # 语言过滤
    languages = data["filters"].get("languages", [])
    if languages:
        lang_filter = " OR ".join([f'"{lang}"[Language]' for lang in languages])
        filters.append(f"({lang_filter})")
    
    # 主题过滤
    # subjects = data["filters"].get("subjects", [])
    # if subjects:
    #     subj_filter = " OR ".join([f'"{subj}"[MeSH Terms]' for subj in subjects])
    #     filters.append(f"({subj_filter})")
    
    # 期刊过滤
    journal_names = data["filters"].get("journals", [])
    if journal_names:
        journal_filter = " OR ".join([f'"{journal}"[Journal]' for journal in journal_names])
        filters.append(f"({journal_filter})")
    
    # 作者过滤
    author = data["filters"].get("author", {})
    if author and author.get("name"):
        author_query = []
        if author.get("first_author", False):
            author_query.append(f'"{author["name"]}"[Author - First]')
        if author.get("last_author", False):
            author_query.append(f'"{author["name"]}"[Author - Last]')
        if not author.get("first_author", False) and not author.get("last_author", False):
            author_query.append(f'"{author["name"]}"[Author]')
        if author_query:
            filters.append(f"({' OR '.join(author_query)})")
    
    # 组合所有过滤器
    if filters:
        full_query = " AND ".join(filters)
    else:
        full_query = base_query
    
    return full_query


class QueryRewriteService:
    def __init__(self):
        self.rewrite_agent = RewriteAgent()
        # self.aclient = OPENAI_CLIENT
        # self.pd_data= pd.read_excel('config/2023JCR（完整）.xlsx')
        # self.pd_data = self.pd_data[["名字", "EISSN"]]
        

    async def query_split(self, query: str):
        start_time = time.time()
        query_list = []
        queries = []
        key_journals = {"name": "", "EISSN": ""}
        category = "Review"
        try_count = 0
        while try_count < 3:
            try:
                query_dict = await self.rewrite_agent.rewrite_query(
                    query, INSTRUCTIONS_rewrite + ' Please note: Today is ' + datetime.now().strftime("%Y/%m/%d") + '.'
                )
                logger.info(f"query_dict: {query_dict}")
                # logger.info(f"query_dict filter: {query_dict['filters']}")
                if (
                    "queries" not in query_dict
                    or "key_journals" not in query_dict
                    or "category" not in query_dict
                ):
                    logger.error(f"Invalid JSON structure, {query_dict}")
                    
                    raise ValueError("Invalid JSON structure")
                queries = query_dict.get("queries")
                key_journals = query_dict.get("key_journals")
                category = query_dict.get("category")
                key_words = query_dict.get("key_words")
                journal_list =[]
                for journal in key_journals:
                    journal_list.append(journal.get("EISSN", ""))
                journal_list = [
                    f"""("{journal_EISSN}"[Journal])"""
                    for journal_EISSN in journal_list
                ]
                journal_list += [
                    "(Nature[Journal])",
                    "(Science[Journal])",
                    "(Nature Reviews Methods Primers[Journal])",
                    "(Innovation[Journal])",
                    "(National Science Review[Journal])",
                    "(Nature Communications[Journal])",
                    "(Science Bulletin[Journal])",
                    "(Science Advances[Journal])",
                    "(BMJ[Journal])",
                ]
                if category == "Review":
                    for sub_query in queries:
                        query_list.append(
                            {
                                "query_item": "( "
                                # + sub_query.strip()
                                + ' '.join(key_words)
                                # + " ) AND ("
                                # + " OR ".join(journal_list)
                                + ") AND (fha[Filter]) AND "
                                + build_pubmed_filter_query(query_dict),
                                "search_type": "advanced",
                            }
                        )
                        query_list.append(
                            {
                                "query_item": "( "
                                + sub_query.strip()
                                + " ) AND ("
                                + " OR ".join(journal_list)
                                + ") AND (fha[Filter]) AND "
                                + build_pubmed_filter_query(query_dict),
                                "search_type": "advanced",
                            }
                            )
                        
                else:
                        # query_list.append(
                        #     {
                        #         "query_item": "( "
                        #         + sub_query.strip()
                        #         + " ) AND ("
                        #         + " OR ".join(journal_list)
                        #         + ") AND (fha[Filter]) AND "
                        #         + build_pubmed_filter_query(query_dict),
                        #         "search_type": "advanced",
                        #     }
                        # )
                    query_list.append(
                            {
                                "query_item": "( "
                                # + sub_query.strip()
                                + ' '.join(key_words)
                                # + " ) AND ("
                                # + " OR ".join(journal_list)
                                + ") AND (fha[Filter]) AND "
                                + build_pubmed_filter_query(query_dict),
                                "search_type": "advanced",
                            }
                        )
                query_list = query_list[:30]
                logger.info(
                    f"Original query: {query}, count: {len(query_list)}, wait time: {time.time() - start_time:.2f}s, rewrite result: {query_list}"
                )
                return query_list
            except Exception as e:
                logger.error(f"Error in query rewrite: {e},trying again...",exc_info=e)
                try_count += 1
                time.sleep(0.1)
        new_try_count = 0
        logger.info(f"Error in query rewrite,trying a simple version again...")
        while new_try_count < 3:
            try:
                query_dict = await self.rewrite_agent.rewrite_query(
                    query,
                    SIMPLE_INSTRUCTIONS_rewrite + ' Please note: Today is ' + datetime.now().strftime("%Y/%m/%d") + '.',
                    simple_version=True,
                )
                logger.info(f"query_dict: {query_dict}")
                if "key_words" not in query_dict:
                    logger.error(f"SIMPLE_version:Invalid JSON structure, {query_dict}")
                    raise ValueError("SIMPLE_version:Invalid JSON structure")
                key_words = query_dict.get("key_words")
                query_list.append(
                    {
                        "query_item": "( "
                        + ' '.join(key_words)
                        + " ) AND (fha[Filter]) AND "
                        + build_pubmed_filter_query(query_dict),
                        "search_type": "advanced",
                    }
                )
                query_list = query_list[:30]
                logger.info(
                    f"SIMPLE_version: Original query: {query}, count: {len(query_list)}, wait time: {time.time() - start_time:.2f}s, rewrite result: {query_list}"
                )
                return query_list
            except Exception as e:
                logger.error(f"SIMPLE_version: Error in query rewrite: {e}")
                new_try_count += 1
                time.sleep(0.1)
        return []
    async def query_split_for_web(self,query: str):
        """
        For web use, only return the key words.
        """
        start_time = time.time()
        query_list = []
        try_count = 0
        while try_count < 3:
            try:
                query_dict = await self.rewrite_agent.rewrite_query(
                    query, INSTRUCTIONS_rewrite + ' Please note: Today is ' + datetime.now().strftime("%Y/%m/%d") + '.',True
                )
                logger.info(f"query_dict: {query_dict}")
                if "key_words" not in query_dict:
                    logger.error(f"SIMPLE_version for web:Invalid JSON structure, {query_dict}")
                    raise ValueError("SIMPLE_version for web:Invalid JSON structure")
                key_words = query_dict.get("key_words")
                query_list.append(
                    {
                        "query_item": 
                        ' '.join(key_words)
                        # + " ) AND (fha[Filter]) AND "
                        # + build_pubmed_filter_query(query_dict),
                        # "search_type": "advanced",
                    }
                )
                query_list = query_list[:30]
                logger.info(
                    f"SIMPLE_version for web: Original query: {query}, count: {len(query_list)}, wait time: {time.time() - start_time:.2f}s, rewrite result: {query_list}"
                )
                return query_list
            except Exception as e:
                logger.error(f"SIMPLE_version: Error in query rewrite: {e}")
                try_count += 1
                time.sleep(0.1)
        return [{"query_item": ""}]
    
    async def query_split_for_simple(self,query: str):
        """
        For simple use, only return the key words.
        """
        start_time = time.time()
        query_list = []
        try_count = 0
        while try_count < 3:
            try:
                query_dict = await self.rewrite_agent.rewrite_query(
                    query, SIMPLE_INSTRUCTIONS_rewrite + ' Please note: Today is ' + datetime.now().strftime("%Y/%m/%d") + '.',True
                )
                logger.info(f"query_dict: {query_dict}")
                if "key_words" not in query_dict:
                    logger.error(f"SIMPLE_version for simple:Invalid JSON structure, {query_dict}")
                    raise ValueError("SIMPLE_version for simple:Invalid JSON structure")
                key_words = query_dict.get("key_words")
                query_list.append(
                    {
                        "query_item": 
                        ' '.join(key_words),
                        # + " ) AND (fha[Filter]) AND "
                        # + build_pubmed_filter_query(query_dict),
                        "search_type": "keyword",
                    }
                )
                query_list = query_list[:30]
                logger.info(
                    f"SIMPLE_version for simple: Original query: {query}, count: {len(query_list)}, wait time: {time.time() - start_time:.2f}s, rewrite result: {query_list}"
                )
                return query_list
            except Exception as e:
                logger.error(f"SIMPLE_version for simple: Error in query rewrite: {e}")
                try_count += 1
                time.sleep(0.1)
        return [{"query_item": ""}]
