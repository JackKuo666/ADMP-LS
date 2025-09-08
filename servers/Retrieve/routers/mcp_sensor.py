from asgi_correlation_id import correlation_id
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse

from utils.bio_logger import bio_logger as logger
from utils.i18n_util import (
    get_language,
    create_error_response,
)
from utils.i18n_context import with_language

from bio_requests.chat_request import ChatRequest

from service.chat import ChatService

router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.post("/bio_qa", response_model=None, operation_id="bio_qa_stream_chat")
async def bio_qa(query: str, lang: str = "en"):
    """
    Biomedical Q&A with Evidence-Based RAG System
    
    This MCP tool provides comprehensive, research-backed answers to biological and medical questions
    using a sophisticated Retrieval-Augmented Generation (RAG) system. The tool performs multi-source
    research and evidence-based synthesis to deliver accurate, well-cited responses.
    
    **Process Overview:**
    1. **Query Analysis & Rewriting** (30-45 seconds)
       - Analyzes the user's question and identifies key biomedical concepts
       - Performs intelligent query rewriting to improve search effectiveness
       - Generates multiple search variations to capture different aspects of the question
       - Optimizes search terms for both PubMed and web search engines
    
    2. **Multi-Source Literature Search** (60-90 seconds)
       - **PubMed Database Search**: Searches scientific literature database for peer-reviewed papers
       - **Web Search**: Conducts web searches for recent developments, clinical guidelines, and additional context
       - **Concurrent Processing**: Performs both searches simultaneously for efficiency
       - **Content Extraction**: Extracts and processes relevant content from search results
    
    3. **Intelligent Reranking** (30-45 seconds)
       - Ranks search results by relevance to the specific question
       - Filters out low-quality or irrelevant content
       - Prioritizes recent, authoritative, and highly relevant sources
       - Ensures diversity in source types (papers, guidelines, reviews, etc.)
    
    4. **Evidence-Based Answer Generation** (60-90 seconds)
       - Synthesizes information from multiple high-quality sources
       - Generates comprehensive, well-structured answers
       - Includes proper citations and references
       - Provides evidence-based explanations with source attribution
    
    **Input:**
    - query (string): A biological or medical question
      Examples: "What causes Alzheimer's disease?", "How do mRNA vaccines work?", 
                "What are the latest treatments for diabetes?", "Explain CRISPR gene editing"
    - lang (string, optional): Language preference ("en" for English, "zh" for Chinese)
    - is_pubmed (boolean, optional): Enable PubMed scientific literature search (default: True)
      - When True: Searches peer-reviewed scientific papers for authoritative evidence
      - When False: Skips PubMed search to reduce processing time
    - is_web (boolean, optional): Enable web search for additional context (default: True)
      - When True: Searches web for recent developments, clinical guidelines, and additional context
      - When False: Skips web search to reduce processing time
    
    **Output:**
    - A comprehensive answer with the following components:
      * **Main Answer**: Evidence-based response to the question
      * **Citations**: Properly formatted references to source materials
      * **Source Links**: Direct links to PubMed papers and web sources
      * **Evidence Summary**: Overview of the evidence supporting the answer
    
    **Key Features:**
    - **Real-time Streaming**: Provides progress updates via Server-Sent Events (SSE)
    - **Multi-Source Research**: Combines PubMed scientific literature with web-based information
    - **Intelligent Query Processing**: Uses advanced query rewriting for better search results
    - **Quality Control**: Reranks results to ensure relevance and authority
    - **Evidence-Based Answers**: All claims are supported by cited sources
    - **Comprehensive Coverage**: Covers genetics, molecular biology, diseases, treatments, and more
    
    **Expected Duration:** 3 minutes (may vary based on query complexity and search configuration)
    
    **Performance Notes:**
    - Full search (is_pubmed=True, is_web=True): ~3 minutes with comprehensive coverage
    - PubMed only (is_pubmed=True, is_web=False): ~2 minutes, focused on scientific literature
    - Web only (is_pubmed=False, is_web=True): ~2 minutes, focused on recent developments
    - Minimal search (is_pubmed=False, is_web=False): ~1 minute, basic query processing only
    
    **Use Cases:**
    - Medical education and learning
    - Clinical decision support
    - Research background information
    - Patient education content
    - Healthcare professional training
    - Scientific literature exploration
    
    **Evidence Quality:**
    - Primary sources from peer-reviewed scientific journals
    - Recent clinical guidelines and recommendations
    - Authoritative medical websites and databases
    - Multiple source verification for key claims
    
    **Note:** This tool is specifically optimized for biomedical and healthcare questions.
    For best results, provide specific, well-defined questions about biological or medical topics.
    """

    logger.info(f"{correlation_id.get()} Bio QA for {query}")
    chat_request = ChatRequest(query=query, language=lang, is_pubmed=True, is_web=True)
    # 解析语言设置
    language = get_language(chat_request.language)

    # 使用上下文管理器设置语言
    with with_language(language):
        try:
            chat_service = ChatService()
            return StreamingResponse(
                chat_service.generate_stream(chat_request),
                media_type="text/event-stream",
                headers={
                    "Connection": "keep-alive",
                    "Cache-Control": "no-cache",
                },
            )
        except Exception as e:
            logger.error(f"{correlation_id.get()} Stream chat error: {e}")
            error_response = create_error_response(
                error_key="service_unavailable",
                details=str(e),
                error_code=500,
            )
            return JSONResponse(content=error_response, status_code=500)
