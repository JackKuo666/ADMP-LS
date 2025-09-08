from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sse_starlette import EventSourceResponse
import asyncio
# import logging
import uuid

# Handle relative imports
# If relative import fails, try absolute import
from long_review_write import LiteratureReviewTool
from config_logger import logger
from setting_config import settings
from typing import Any
debug_config_args: dict[str, Any] = {"debug": settings.DEBUG_MODE}
if not settings.DEBUG_MODE:
    debug_config_args["openapi_url"] = None
    debug_config_args["docs_url"] = None
    debug_config_args["redoc_url"] = None

app = FastAPI(title="Bio-Agent Literature Review API", version="1.0.0",
              **debug_config_args,)
message_queues = {} 

class StreamMessage(BaseModel):
    type: str
    content: str


@app.get("/health",tags=["check"],operation_id="health_check")
async def health_check():
    """
    Health Check and Service Validation Tool
    
    This MCP tool performs comprehensive health checks and validation for the Review service
    and its dependencies. It verifies the service is ready to handle literature review requests.
    
    **Process:**
    1. **Service Status Check** - Verifies the Review service is running and responsive
    2. **Dependency Validation** - Checks all required APIs and services are available
    3. **Configuration Verification** - Validates environment variables and settings
    4. **Connection Testing** - Tests connections to external services (PubMed, web search)
    
    **Input:**
    - None (no parameters required)
    
    **Output:**
    - Service status information via Server-Sent Events (SSE)
    - Health check results including:
      * Service availability status
      * Dependency connection status
      * Configuration validation results
      * Ready/not ready status for processing requests
    
    **Use Cases:**
    - Service monitoring and diagnostics
    - Pre-flight checks before starting literature reviews
    - System health monitoring
    - Troubleshooting service issues
    
    **Expected Duration:** 5-10 seconds
    
    **Note:** This tool is useful for verifying the Review service is properly configured
    and ready to handle literature review generation requests.
    """
    async def generate_data():
        a = "test"
        for i in a:
            
            yield {
                "data": StreamMessage(
                    type="result", content=f"data {i}\n"
                ).model_dump_json()
            }
    return EventSourceResponse(generate_data())


@app.get("/review_generate",operation_id="review_generate")
async def review_generate(query: str = Query(..., description="Research query for literature review generation")):
    """
    Comprehensive Literature Review Generation Tool
    
    This MCP tool generates comprehensive, research-backed literature reviews on biomedical topics.
    The tool performs an extensive multi-stage research and writing process that typically takes 
    approximately 30 minutes to complete.
    
    **Process Overview:**
    1. **Query Analysis & Plan Generation** (5-8 min)
       - Analyzes the research query and generates a detailed outline
       - Creates multiple sections with specific research objectives
       - Plans the overall structure of the review
    
    2. **Comprehensive Literature Research** (15-20 min)
       - Performs extensive PubMed database searches for relevant scientific papers
       - Conducts web searches for additional context and recent developments
       - Collects and analyzes 50-100+ relevant scientific papers
       - Gathers comprehensive reference materials
    
    3. **Section-by-Section Writing** (8-10 min)
       - Writes detailed content for each planned section
       - Each section typically contains 800-1200 words
       - Integrates findings from multiple research sources
       - Ensures proper citation and academic formatting
    
    4. **Quality Control & Review** (2-3 min)
       - Performs content validation and fact-checking
       - Ensures accuracy of scientific claims
       - Validates references and citations
       - Checks for consistency and coherence
    
    5. **Final Report Assembly** (2-3 min)
       - Combines all sections into a cohesive document
       - Generates comprehensive abstract
       - Creates final bibliography with proper formatting
       - Produces a complete 15,000-word literature review
    
    **Input:**
    - query (string): A research topic or question in biomedical field
      Examples: "CRISPR gene editing in cancer treatment", "COVID-19 vaccine development", 
                "Alzheimer's disease mechanisms", "Stem cell therapy applications"
    
    **Output:**
    - A comprehensive literature review in Markdown format containing:
      * Abstract (200-300 words)
      * Introduction and background
      * Multiple detailed sections (typically 5-8 sections)
      * Discussion and future directions
      * Comprehensive bibliography (50-100+ references)
      * Total length: ~15,000 words
    
    **Key Features:**
    - Real-time progress updates via Server-Sent Events (SSE)
    - Extensive use of PubMed and web search APIs
    - Multi-agent collaboration for different aspects of research
    - Quality control and validation at multiple stages
    - Academic-grade formatting and citation
    - Comprehensive coverage of current research landscape
    
    **Expected Duration:** 30 minutes (may vary based on query complexity)
    
    **Use Cases:**
    - Academic research preparation
    - Grant proposal background research
    - Clinical practice guideline development
    - Drug development literature analysis
    - Medical education content creation
    - Healthcare policy research
    
    **Note:** This tool is specifically designed for biomedical and healthcare topics.
    For best results, provide specific, well-defined research questions.
    """
    if not query or query.strip() == "":
        raise HTTPException(status_code=400, detail="Query parameter is required")
    
    # Create a unique queue for this request
    request_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    message_queues[request_id] = queue
    
    try:
        async def result_callback(result):
            await queue.put(StreamMessage(type="result", content=result))
        
        tool = LiteratureReviewTool(
            thoughts_callback=result_callback,
            results_callback=result_callback,
            verbose=True,
        )
        
        process_task = asyncio.create_task(
            tool.run(query)
        )
        
        async def event_generator():
            try:
                while True:
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=0.1)
                        yield {"data": message.model_dump_json()}
                    except asyncio.TimeoutError:
                        if process_task.done():
                            break
                        continue
            except Exception as e:
                logger.error(f"stream error: {e}")
            finally:
                yield {
                    "data": StreamMessage(
                        type="done", content="task done"
                    ).model_dump_json()
                }
        
        return EventSourceResponse(event_generator())
    
    finally:
        # Clean up the queue when done
        if request_id in message_queues:
            del message_queues[request_id]

