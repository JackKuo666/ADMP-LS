import xml.etree.ElementTree as ET
import re
from utils.bio_logger import bio_logger as logger


class PubmedXmlParse:
    def __init__(self):
        pass

    def remove_xml_tags(self, text):
        """移除XML标签，返回纯文本"""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)


    # 解析 XML 数据
    def parse_pubmed_xml(self, xml_data):
        try:
            tree = ET.ElementTree(ET.fromstring(xml_data))
            root = tree.getroot()

            articles = []

            # 遍历每个 PubmedArticle 元素
            for article in root.findall(".//PubmedArticle"):
                try:
                    # 提取文章信息
                    article_title_elem = article.find(".//ArticleTitle")
                    article_title = ""
                    if article_title_elem is not None:
                        # Convert element to string and decode to handle tags
                        title_text = ET.tostring(article_title_elem, encoding='unicode', method='xml')
                        # Remove the ArticleTitle tags but keep inner content and tags
                        title_text = title_text.replace('<ArticleTitle>', '').replace('</ArticleTitle>', '')
                        # Remove all XML tags to get plain text
                        article_title = self.remove_xml_tags(title_text).strip()

                    pmid = (
                        article.find(".//ArticleId[@IdType='pubmed']").text
                        if article.find(".//ArticleId[@IdType='pubmed']") is not None
                        else ""
                    )
                    abstract_texts = article.findall(".//AbstractText")
                    abstract_text = (
                        " ".join(
                            [
                                abstract.text if abstract.text is not None else ""
                                for abstract in abstract_texts
                            ]
                        )
                        if abstract_texts
                        else ""
                    )

                    # 提取作者信息
                    authors = []
                    for author in article.findall(".//Author"):
                        try:
                            authors.append(
                                {
                                    "lastname": (
                                        author.find(".//LastName").text
                                        if author.find(".//LastName") is not None
                                        else ""
                                    ),
                                    "forename": (
                                        author.find(".//ForeName").text
                                        if author.find(".//ForeName") is not None
                                        else ""
                                    ),
                                    "initials": (
                                        author.find(".//Initials").text
                                        if author.find(".//Initials") is not None
                                        else ""
                                    ),
                                    "affiliation": (
                                        author.find(".//AffiliationInfo/Affiliation").text
                                        if author.find(".//AffiliationInfo/Affiliation") is not None
                                        else ""
                                    ),
                                }
                            )
                        except Exception as e:
                            logger.error(f"Error parsing author: {e}")
                            continue

                    journal = {
                        "issn": (
                            article.find(".//Journal/ISSN").text
                            if article.find(".//Journal/ISSN") is not None
                            else ""
                        ),
                        "title": (
                            article.find(".//Journal/Title").text
                            if article.find(".//Journal/Title") is not None
                            else ""
                        ),
                        "abbreviation": (
                            article.find(".//Journal/ISOAbbreviation").text
                            if article.find(".//Journal/ISOAbbreviation") is not None
                            else ""
                        ),
                        "startPage": (
                            article.find(".//Pagination/StartPage").text
                            if article.find(".//Pagination/StartPage") is not None
                            else ""
                        ),
                        "endPage": (
                            article.find(".//Pagination/EndPage").text
                            if article.find(".//Pagination/EndPage") is not None
                            else ""
                        ),
                        "volume": (
                            article.find(".//Journal/JournalIssue/Volume").text
                            if article.find(".//Journal/JournalIssue/Volume") is not None
                            else ""
                        ),
                        "issue": (
                            article.find(".//Journal/JournalIssue/Issue").text
                            if article.find(".//Journal/JournalIssue/Issue") is not None
                            else ""
                        ),
                        "year": (
                            article.find(".//Journal/JournalIssue/PubDate/Year").text
                            if article.find(".//Journal/JournalIssue/PubDate/Year") is not None
                            else ""
                        ),
                    }
                    medline = article.find("MedlineCitation")
                    references = article.findall(".//PubmedData/ReferenceList/Reference")
                    # 将每篇文章的信息添加到列表中
                    articles.append(
                        {
                            "pmid": pmid,
                            "pmcid": (
                                article.find(
                                    ".//PubmedData/ArticleIdList/ArticleId[@IdType='pmc']"
                                ).text
                                if article.find(
                                    ".//PubmedData/ArticleIdList/ArticleId[@IdType='pmc']"
                                )
                                is not None
                                else ""
                            ),
                            "title": article_title,
                            "abstract": abstract_text,
                            "journal": journal,
                            "authors": authors,
                            "pub_date": {
                                "year": (
                                    article.find(".//Journal/JournalIssue/PubDate/Year").text
                                    if article.find(".//Journal/JournalIssue/PubDate/Year")
                                    is not None
                                    else ""
                                ),
                                "month": (
                                    article.find(".//Journal/JournalIssue/PubDate/Month").text
                                    if article.find(".//Journal/JournalIssue/PubDate/Month")
                                    is not None
                                    else ""
                                ),
                                "day": (
                                    article.find(".//Journal/JournalIssue/PubDate/Day").text
                                    if article.find(".//Journal/JournalIssue/PubDate/Day")
                                    is not None
                                    else ""
                                ),
                            },
                            "keywords": (
                                [k.text for k in medline.findall(".//KeywordList/Keyword")]
                                if medline.findall(".//KeywordList/Keyword") is not None
                                else ""
                            ),
                            "doi": self.parse_doi(medline.find("Article"), article),
                            "mesh_terms": [
                                self.parse_mesh(m)
                                for m in medline.findall("MeshHeadingList/MeshHeading")
                            ],
                            "references": [self.parse_reference(r) for r in references],
                        }
                    )
                except Exception as e:
                    logger.error(f"Error parsing article: {e}")
                    continue

            return articles
        except Exception as e:
            logger.error(f"Error parsing PubMed XML: {e}")
            return []

    def parse_doi(self, article, article_elem) -> str:
        if article.find(".//ELocationID[@EIdType='doi']") is not None:
            doi = article.find(".//ELocationID[@EIdType='doi']").text
            if doi is not None and doi != "":
                return doi
        elif article_elem.find(".//ArticleIdList/ArticleId[@IdType='doi']") is not None:
            doi = article_elem.find(".//ArticleIdList/ArticleId[@IdType='doi']").text
            if doi is not None and doi != "":
                return doi
        else:
            return ""

    def parse_mesh(self, mesh_elem):
        """解析MeSH主题词"""
        return {
            "descriptor": (
                mesh_elem.find(".//DescriptorName").text
                if mesh_elem.find(".//DescriptorName") is not None
                else ""
            ),
            "qualifiers": [
                (
                    q.find(".//QualifierName").text
                    if q.find(".//QualifierName") is not None
                    else ""
                )
                for q in mesh_elem.findall(".//QualifierName")
            ],
        }

    def parse_reference(self, reference_elem):
        """解析参考文献"""
        return {
            "citation": (
                reference_elem.find("Citation").text
                if reference_elem.find("Citation") is not None
                else ""
            ),
            "doi": (
                reference_elem.find(".//ArticleId[@IdType='doi']").text
                if reference_elem.find(".//ArticleId[@IdType='doi']") is not None
                else ""
            ),
            "pmid": (
                reference_elem.find(".//ArticleId[@IdType='pubmed']").text
                if reference_elem.find(".//ArticleId[@IdType='pubmed']") is not None
                else ""
            ),
            "pmcid": (
                reference_elem.find(".//ArticleId[@IdType='pmcid']").text
                if reference_elem.find(".//ArticleId[@IdType='pmcid']") is not None
                else ""
            ),
        }
