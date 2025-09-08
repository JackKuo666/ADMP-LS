# 处理相对导入
try:
    from ..tools.pubmed_search_agent import (
        article_search_agent,
    )
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from tools.pubmed_search_agent import (
        article_search_agent,
    )

from typing import List, Optional, Any, Callable
from dataclasses import dataclass
from pydantic import BaseModel, Field


class ToolAgentOutput(BaseModel):
    """Standard output for all tool agents"""

    output: str
    sources: list[str] = Field(default_factory=list)


class TaskManagerToolAgentstatus(BaseModel):
    # output: str = Field(description="return tool run result directly as final output")
    status_code: int = Field(
        description="201 if the tool ran successfully, 501 if there was an error or it returned None or Error"
    )


class TaskData(BaseModel):
    code: int = Field(
        description="HTTP-like status code: 200 if the tool ran successfully, 501 if there was an error or it returned None or Error"
    )
    message: str = Field(required=False)
    thinking: str = Field(required=False, description="thinking of the tool")


class TaskManagerToolAgentOutput(TaskManagerToolAgentstatus):
    # output: str = Field(description="return tool run result directly as final output")
    # status_code: int = Field(description="HTTP-like status code: 200 if the tool ran successfully, 400 if there was an error or it returned None or Error")
    data: TaskData = Field(
        description="HTTP-like status code: 200 if the tool ran successfully, 501 if there was an error or it returned None or Error"
    )


class ReportDraftSection(BaseModel):
    """A section of the report that needs to be written"""

    section_title: str = Field(description="The title of the section")
    section_content: str = Field(description="The content of the section")


class ReportDraft(BaseModel):
    """Output from the Report Planner Agent"""

    sections: List[ReportDraftSection] = Field(
        description="List of sections that are in the report"
    )
class QaRequest(BaseModel):
    """Request model for QA"""

    query: str = Field(description="The query string for the QA")
    is_web: bool = Field(default=False, description="Whether the query is for web search")


TOOL_AGENTS = {
    "ArticleSearchAgent": article_search_agent,
}


@dataclass
class InputCallbackTool:
    thoughts_callback: Optional[Callable[[str], Any]] = None
    """callback of thinking ."""
    results_callback: Optional[Callable[[str], Any]] = None
    """callback of results"""
    u_id: Optional[str] = ""
    """user_id"""
    c_id: Optional[str] = None
    """chat_id"""
    is_pkb: Optional[bool] = False
    """whether to search personal knowledge base"""

    @property
    def name(self):
        return "callback"
