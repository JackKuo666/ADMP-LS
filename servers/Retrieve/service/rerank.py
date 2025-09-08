from typing import List
from bio_requests.rag_request import RagRequest
from dto.bio_document import BaseBioDocument
from utils.bio_logger import bio_logger as logger

import pandas as pd

# Load the Excel file
df = pd.read_excel("config/2023JCR（完整）.xlsx")

# Select only the 'ISSN' and '5年IF' columns
df = df[["ISSN", "5年IF", "EISSN"]]

# Convert '5年IF' to float, setting invalid values to 0.01
df["5年IF"] = pd.to_numeric(df["5年IF"], errors="coerce").fillna(0.01)


class RerankService:
    def __init__(self):

        # Select only the 'ISSN' and '5年IF' columns
        self.df = df

    async def rerank(
        self, rag_request: RagRequest, documents: List[BaseBioDocument] = []
    ) -> List[BaseBioDocument]:
        if not rag_request.data_source or "pubmed" not in rag_request.data_source:
            logger.info("RerankService: data_source is not pubmed, skip rerank")
            return documents
        logger.info("RerankService: start rerank")
        # Now sorted_documents contains the documents sorted by "5-year IF" from high to low

        # Step 1: Extract ISSN and query the DataFrame for "5-year IF"

        for document in documents:
            issn = document.journal["issn"]

            # Check if ISSN exists in the 'ISSN' column
            if_5_year = self.df.loc[self.df["ISSN"] == issn, "5年IF"].values
            if if_5_year.size > 0:
                document.if_score = if_5_year[0]
            else:
                # If not found in 'ISSN', check the 'EISSN' column
                if_5_year = self.df.loc[self.df["EISSN"] == issn, "5年IF"].values
                if if_5_year.size > 0:
                    document.if_score = if_5_year[0]
                else:
                    document.if_score = None

        # Step 2: De-duplicate the ID of each document in the documents list
        documents = list({doc.bio_id: doc for doc in documents}.values())

        # Step 3: Sort documents by "5-year IF" in descending order
        sorted_documents = sorted(
            documents,
            key=lambda x: x.if_score if x.if_score is not None else 0.01,
            reverse=True,
        )

        return sorted_documents
