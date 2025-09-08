from utils.llm_client import qianwen_plus_model
from utils.baseclass import ResearchAgent
from utils.parse_output import create_type_parser
from tools.search_tool import article_simple_search, SimpleArticle
from typing import List
from pydantic import BaseModel, Field





from agents import ModelSettings


class ArticleSearchResult(BaseModel):
    """Output from the Pubmed Simple Agent containing articles for synthesis"""

    articles: List[SimpleArticle] = Field(
        description="The retrieved scientific articles and the source of the article"
    )
    query: str = Field(description="The original research query/topic")


class PubmedSimpleResultOutput(BaseModel):
    output: str = Field(description="all the response of tool")


INSTRUCTIONS = f"""You are an expert researcher analyzing a research question.

Generate queries at most 30 words which MUST be start with "generate review about*" for search topic that comprehensively cover all important aspects of the topic. 
For example, "generate review about the history of rna-seq" is a good query,   
Each query should:
1. Be concise (30 words maximum)
2. Focus on a specific aspect of the research question
3. Be suitable for a scientific database search
4. Collectively cover the full breadth of the research topic

For complex or multifaceted topics, generate proper queries to ensure comprehensive coverage.


Important:
- DO NOT do more than 2 tool calls, and wait for the tool response, as the tool cannot accept too many requests,if the tool return error, you can try again,but do not do more than 5 times
- Use the EXACT source format returned by the tool - DO NOT modify or reformat the source field
- Simply pass through the source field as-is from the tool response
- The tool already formats the source correctly, so preserve it exactly

After generating the search queries, use the tool to retrieve articles for all queries at once. This will be much faster than searching for each query individually.

The tool returns list[SimpleArticle] objects with:
- source: The formatted citation (already properly formatted by the tool)
- text: The article content

DO NOT modify the source field - use it exactly as returned by the tool.

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{ArticleSearchResult.model_json_schema()}
"""

select_model = qianwen_plus_model

article_search_agent = ResearchAgent(
    name="ArticleSearchAgent",
    instructions=INSTRUCTIONS,
    tools=[article_simple_search],
    model=select_model,
    #  output_type = ArticleSearchResult,
    model_settings=ModelSettings(tool_choice="required"),
    output_parser=create_type_parser(ArticleSearchResult),
)


if __name__ == "__main__":
    import asyncio
    from ..utils.schemas import (
        InputCallbackTool,
    )
    from ..utils.baseclass import ResearchRunner
    from openai.types.responses import ResponseTextDeltaEvent

    user_message = "some rna seq history"
    references = []

    async def test_tool():
        u_id = "123"
        input_call = InputCallbackTool(
            # thoughts_callback=self.thoughts_callback,
            u_id=str(u_id),
            is_pkb=False,
            # c_id=str(c_id),
        )
        synthesis_streamed_result = ResearchRunner.run_streamed(
            article_search_agent,
            user_message,
            context=input_call,
            max_turns=20,
        )
        print(synthesis_streamed_result)

        full_response = ""
        # async for event in synthesis_streamed_result.stream_events():
        #     if event.type == "raw_response_event" and isinstance(
        #         event.data, ResponseTextDeltaEvent
        #     ):
        #         token = event.data.delta
        #         full_response += token
        #     elif event.type == "run_item_stream_event":
        #         if event.item.type == "tool_call_output_item":
        #             tool_call_output = event.item.output
        #             references.extend(tool_call_output)

        def get_references(articles: list):
            t_ref = [(f"{article.hash_id} {article.source}") for article in articles]
            references.extend(t_ref)

        async for event in synthesis_streamed_result.stream_events():
            if event.type == "raw_response_event" and isinstance(
                event.data, ResponseTextDeltaEvent
            ):
                token = event.data.delta
                full_response += token
            elif event.type == "run_item_stream_event":
                if event.item.type == "tool_call_output_item":
                    tool_call_output = event.item.output
                    print(f"########## tool_call_output {tool_call_output}")
                    print(
                        f"########## tool_call_output {type(tool_call_output)},isinstance {isinstance(tool_call_output, list)}"
                    )
                    if (
                        isinstance(tool_call_output, list)
                        and len(tool_call_output) > 0
                        and isinstance(tool_call_output[0], SimpleArticle)
                    ):
                        get_references(tool_call_output)
        print(f"########## references {references}")
        tool_output = ""

        # fresult = ArticleSearchResult(
        #     articles=tool_output, query=user_message
        # )
        # print(fresult)

    asyncio.run(test_tool())
