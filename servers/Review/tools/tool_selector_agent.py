"""
Agent used to determine which specialized agents should be used to address knowledge gaps.

The Agent takes as input a string in the following format:
===========================================================
ORIGINAL QUERY: <original user query>

KNOWLEDGE GAP TO ADDRESS: <knowledge gap that needs to be addressed>
===========================================================

The Agent then:
1. Analyzes the knowledge gap to determine which agents are best suited to address it
2. Returns an AgentSelectionPlan object containing a list of AgentTask objects

The available agents are:
- WebSearchAgent: General web search for broad topics
- SiteCrawlerAgent: Crawl the pages of a specific website to retrieve information about it
"""

# Handle relative imports
try:
    from ..utils.llm_client import model_supports_structured_output, qianwen_plus_model
    from ..utils.baseclass import ResearchAgent
    from ..utils.parse_output import create_type_parser
except ImportError:
    # If relative import fails, try absolute import
    from utils.llm_client import model_supports_structured_output, qianwen_plus_model
    from utils.baseclass import ResearchAgent
    from utils.parse_output import create_type_parser
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field






class AgentTask(BaseModel):
    """A task for a specific agent to address knowledge gaps"""

    gap: Optional[str] = Field(
        description="The knowledge gap being addressed", default=None
    )
    agent: str = Field(description="The name of the agent to use")
    query: str = Field(description="The specific query for the agent,should be str")
    entity_website: Optional[str] = Field(
        description="The citation of the article,include author,publication year,journal name, if known",
        default=None,
    )


class AgentSelectionPlan(BaseModel):
    """Plan for which agents to use for knowledge gaps"""

    tasks: List[AgentTask] = Field(
        description="List of agent tasks to address knowledge gaps"
    )


# INSTRUCTIONS = f"""
# You are an Tool Selector responsible for determining which specialized agents should address a knowledge gap in a research project.
# Today's date is {datetime.now().strftime("%Y-%m-%d")}.
#
# You will be given:
# 1. The original user query
# 2. A knowledge gap identified in the research
# 3. A full history of the tasks, actions, findings and thoughts you've made up until this point in the research process
#
# Your task is to decide:
# 1. Which specialized agents are best suited to address the gap
# 2. What specific queries should be given to the agents (keep this short - 3-6 words)
#
# Available specialized agents:
# - WebSearchAgent: General web search for broad topics (can be called multiple times with different queries)
# - SiteCrawlerAgent: Crawl the pages of a specific website to retrieve information about it - use this if you want to find out something about a particular company, entity or product
#
# Guidelines:
# - Aim to call at most 3 agents at a time in your final output
# - You can list the WebSearchAgent multiple times with different queries if needed to cover the full scope of the knowledge gap
# - Be specific and concise (3-6 words) with the agent queries - they should target exactly what information is needed
# - If you know the website or domain name of an entity being researched, always include it in the query
# - If a gap doesn't clearly match any agent's capability, default to the WebSearchAgent
# - Use the history of actions / tool calls as a guide - try not to repeat yourself if an approach didn't work previously
#
# Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
# {AgentSelectionPlan.model_json_schema()}
# """

INSTRUCTIONS = f"""
You are an Tool Selector responsible for determining which specialized agents should address a knowledge gap in a research project.
Today's date is {datetime.now().strftime("%Y-%m-%d")}.

You will be given:
1. The original user query
2. A knowledge gap identified in the research
3. A full history of the tasks, actions, findings and thoughts you've made up until this point in the research process

Your task is to decide:
1. Which specialized agents are best suited to address the gap
2. What specific queries should be given to the agents (keep most 100 words)

Available specialized agents:
- ArticleSearchAgent: search the web for information relevant to the query - provide a query with most 100 words as , - use this most 3 times if you want to find out something about a the information of query,the refs are in the output of this agent

Guidelines:
- Aim to call at most 2 agents at a time in your final output
- You can list the PubMedSearchAgent at most 1 times with different queries if needed to cover the full scope of the knowledge gap
- Be specific and concise (most 100 words) with the agent queries - they should target exactly what information is needed
- If you know the citation of the article of an entity being researched, always include it in the query
- If a gap doesn't clearly match any agent's capability, default to generate query and search PubMedSearchAgent
- Use the history of actions / tool calls as a guide - try not to repeat yourself if an approach didn't work previously
- For the citation of the article:
1. Use ONLY information that is explicitly provided in the articles
2. DO NOT invent or fabricate any information, dates, journal names, or other details
3. For missing information, use "N/A" or omit the field entirely, but NEVER invent data
4. Use this format: Author(s), (Year). Title. Journal, Volume(Issue), Pages.
5. If any piece of information is missing, simply exclude it rather than making it up

For example, if author, year and title are available but not journal details:
- Smith J, Johnson K. (2020). Advances in gene therapy for cancer treatment.


Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{AgentSelectionPlan.model_json_schema()}
"""

selected_model = qianwen_plus_model

tool_selector_agent = ResearchAgent(
    name="ToolSelectorAgent",
    instructions=INSTRUCTIONS,
    model=selected_model,
    output_type=AgentSelectionPlan
    if model_supports_structured_output(selected_model)
    else None,
    output_parser=(
        create_type_parser(AgentSelectionPlan)
        if not model_supports_structured_output(selected_model)
        else None
    ),
)
