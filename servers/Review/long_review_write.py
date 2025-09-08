import asyncio
import traceback
from typing import Any, Callable, List, Optional

from agents import function_tool
from openai.types.responses import ResponseTextDeltaEvent
from pydantic import ValidationError

from iterative_detail_plan import IterativeDetailPlan
from iterative_research import IterativeResearcher
from utils.baseclass import ResearchAgent, ResearchRunner
from tools.long_writer_agent import LongWriterOutput, write_report_from_section_drafts
from utils.schemas import ReportDraft, ReportDraftSection


from tools.detail_plan_agent import CoreOutline, CoreSection
from tools.writer_agent import (
    checkout_section_agent,
    section_summary_agent,
    abstract_agent,
    translate_title_chinese_agent,
)
from config_logger import logger
# logger = logging.getLogger(__name__)


class LiteratureReviewTool:
    """
    文献研究工具类，用于自动查询文章并生成研究报告。
    """

    def __init__(
        self,
        verbose: bool = True,
        thoughts_callback: Optional[Callable[[str], Any]] = None,
        results_callback: Optional[Callable[[str], Any]] = None,
        stop_event: Optional[asyncio.Event] = None,
        hooks=None,
        u_id: Optional[str] = None,
        is_web: Optional[bool] = False,
        is_pkb: Optional[bool] = False,
        language: str = "EN",  # EN or CH
    ):
        self.verbose = verbose
        self.thoughts_callback = thoughts_callback
        self.results_callback = results_callback
        self.stop_event = stop_event
        self.hooks = hooks
        self.u_id = u_id
        self.is_web = is_web
        self.is_pkb = is_pkb
        self.language = language
        self.enrichquery = ""
        if thoughts_callback is None:

            async def noop(x):
                pass

            self.thoughts_callback = noop
        if results_callback is None:
            self.results_callback = thoughts_callback

    async def run(
        self,
        query: str,
    ) -> str:
        """
        运行文献研究工具，生成研究报告。

        Args:
            query: 研究主题或问题
            thoughts_callback: 用于报告进度和思考的异步回调函数
            results_callback: 用于流式返回结果的异步回调函数
            stop_event: 用于检查取消操作的异步事件

        Returns:
            生成的文献研究报告（Markdown格式）
        """
        try:
            # 1. 构建报告计划
            report_plan = await self._build_detail_report_plan(query)
            # await self.results_callback(f"########## report_plan{report_plan}")
            # 2. 为每个章节执行文献研究
            research_results, found_references = await self._run_research_loops(
                report_plan,
            )
            await self._log_message("Research_results loop down")

            # 3. 创建最终报告
            logger.info(f"Creating final report... \n")
            final_report = await self._create_final_report(
                query,
                report_plan,
                research_results,
                found_references,
                self.thoughts_callback,
                self.language,
            )
            logger.info(f"Final report created... \n")
            await self.results_callback("Final_report\n")
            # await self.results_callback(final_report)
            await self.stream_text(final_report)
            return final_report

        except Exception as e:
            error_msg = f"Research error: {str(e)}\n{traceback.format_exc()}"
            if self.thoughts_callback:
                await self.thoughts_callback(error_msg)
            return f"Research error: {str(e)}"

    async def stream_text(self, res: str, chunk_size: int = 100):
        for i in range(0, len(res), chunk_size):
            chunk = res[i : i + chunk_size]
            await asyncio.sleep(0.05)
            await self.results_callback(chunk)

    async def _build_detail_report_plan(
        self,
        query: str,
    ) -> CoreOutline:
        """构建详细报告计划，使用planner_agent_test生成报告计划"""
        await self._log_message("\n=== Building Detail Report Plan ===\n")
        # user_raw_query = query
        # 构建多个agent的循环输入
        generator = IterativeDetailPlan(
            max_iterations=3,
            max_time_minutes=10,
            thoughts_callback=self.results_callback,
        )
        logger.info(f"Building detail report plan... \n")
        detail_outline, enrichquery = await generator.run(query=query)
        self.enrichquery = enrichquery
        await self._log_message("\n=== Report Plan Built ===\n")

        return detail_outline

    async def _run_research_loops(
        self,
        report_plan: CoreOutline,
    ) -> tuple[Any, List[Any]]:
        """为每个章节执行文献研究并收集结果"""
        research_results = []
        found_ref = []
        await self._log_message("\n **Reasoning about Sections** \n")

        async def run_research_for_section(section: CoreSection):
            if self.stop_event and self.stop_event.is_set():
                await self._log_message(
                    f"\n **Study section {section.title} canceled** \n"
                )
                return "Study canceled", []

            await self._log_message(
                f"\n===Initializing  Section: {section.title} Research Loops Study===\n"
            )

            # 创建IterativeResearcher实例
            iterative_researcher = IterativeResearcher(
                max_iterations=1, #2,  # 可以根据需要调整
                max_time_minutes=12,  # 可以根据需要调整
                verbose=True,
                thoughts_callback=self.thoughts_callback,
                hooks=self.hooks,
                u_id=self.u_id,
            )
            # 准备IterativeResearcher的参数
            args = {
                "query": self.enrichquery,
                "output_length": " 800",
                "output_instructions": section,
                "background_context": report_plan.background,
            }

            try:
                section_result, section_references = await iterative_researcher.run(
                    **args
                )
                await self._log_message(
                    f"\nSection: {section.title} Research Loops Study completed\n"
                )

            except Exception as e:
                error_msg = f"Section {section.title} error: {str(e)}"
                logger.error(error_msg)
                section_result = None
                section_references = None

                # return f"Error: {str(e)}", []
            return section_result, section_references

        # await self._log_message("=== Initializing Research Loops ===")
        # 并发执行所有章节的研究
        is_loop_iter = False
        if is_loop_iter:
            # 单次跑
            # for section in report_plan.report_outline:
            #     result = await run_research_for_section(section)
            #     research_results.append(result)
            #
            max_tasks = 2
            for i in range(0, len(report_plan.sections), max_tasks):
                bach_sections = report_plan.sections[i : i + max_tasks]
                batch_tasks = [
                    run_research_for_section(section) for section in bach_sections
                ]
                batch_results = await asyncio.gather(*batch_tasks)
                for section_result, section_references in batch_results:
                    research_results.append(section_result)
                    found_ref.extend(section_references)

        else:
            # 使用asyncio.gather并发执行所有章节的研究
            batch_results = await asyncio.gather(
                *(run_research_for_section(section) for section in report_plan.sections)
            )
            research_results = []
            found_ref = []
            for section_result, section_references in batch_results:
                # print(f"########## section_references {section_references},length {len(section_references)}.\n ########## section_result {section_result}")
                # print(f"########################################################")
                research_results.append(section_result)
                if section_references:
                    found_ref.extend(section_references)
        return research_results, found_ref

    async def _create_final_report(
        self,
        query: str,
        report_plan: CoreOutline,
        section_drafts: List[LongWriterOutput],
        ref: List[Any],
        thoughts_callback: Optional[Callable[[str], Any]] = None,
        language: str = "EN",  # EN or CH
    ) -> str:
        """从报告计划和章节草稿创建最终报告"""
        # 构建ReportDraft对象
        logger.info(
            f"########## found_references length {len(ref)},\n research_results length {len(section_drafts)}"
        )
        report_draft = ReportDraft(sections=[])

        async def check_section(section_draft: LongWriterOutput, ins_query: str, section_title: str):
            logger.info(f"Checking section {section_title}... \n")
            await self.results_callback(f"Checking section {section_title}... \n")
            if not section_draft.next_section_markdown:
                return None, None
            else:
                logger.info(f"Checking section {section_title}... \n")
                check_result = await self._check_section(
                    section_draft, ins_query, language
                )
                logger.info(f"Checking section {section_title} completed... \n")
                summary = await self._generate_summary(
                    check_result.next_section_markdown
                )
                logger.info(f"Generating summary for section {section_title} completed... \n")
                return check_result, summary

        # 过滤出非空的section_drafts并记录它们的原始索引
        non_empty_sections = []
        for i, section_draft in enumerate(section_drafts):

            if section_draft and section_draft.next_section_markdown:
                non_empty_sections.append((i, section_draft))

        checkouts_results = await asyncio.gather(
            *(
                check_section(
                    section_draft,
                    f" u are modifing the section num {j + 1}",
                    report_plan.sections[i].title,
                )
                for j, (i, section_draft) in enumerate(non_empty_sections)
            )
        )
        logger.info(f"Checkouts completed... \n")

        section_summaries = []
        for j, (section_result, summary) in enumerate(checkouts_results):
            if section_result:
                # 使用原始索引来获取正确的section title
                original_index = non_empty_sections[j][0]
                report_draft.sections.append(
                    ReportDraftSection(
                        section_title=report_plan.sections[original_index].title,
                        section_content=section_result.next_section_markdown,
                    )
                )
            if summary:
                section_summaries.append(summary)
        if thoughts_callback:
            await thoughts_callback("\n **Generating final report...** \n")
        logger.info(f"Generating abstract... \n")
        await self.results_callback(f"Generating abstract... \n")
        abstract = await self._genrate_abstract(section_summaries, language)
        if language == "CH":
            report_plan.report_title = await self._translate_title_chinese(
                report_plan.report_title
            )
        logger.info(f"Writing report from section drafts... \n")    
        final_output = await write_report_from_section_drafts(
            query,
            abstract,
            report_plan.report_title,
            report_draft,
            ref,
            self.thoughts_callback,
        )

        return final_output

    async def _generate_summary(self, sections: str) -> str:
        full_response = ""
        result = ResearchRunner.run_streamed(
            starting_agent=section_summary_agent, input=sections
        )
        try:
            async for event in result.stream_events():
                try:
                    if event.type == "raw_response_event" and isinstance(
                        event.data, ResponseTextDeltaEvent
                    ):
                        full_response += event.data.delta
                except Exception as e:
                    logger.error(f"Error processing event: {e}")
                    continue

        except ValidationError:
            pass
        except Exception as e:
            logger.error(f"Error processing generate summary event: {e}")
            pass

        final_result = result.final_output
        return final_result

    async def _translate_title_chinese(self, title: str) -> str:
        """Translate English title to Chinese"""
        input_str = f"LANGUAGE: Chinese\n\nTITLE: {title}"
        try:
            result = ResearchRunner.run(
                starting_agent=translate_title_chinese_agent,
                input=input_str,
            )
            return result.final_output
        except ValidationError as e:
            logger.warning(f"Translation validation error: {e}")
            return title  # Return original title if translation fails
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return title  # Return original title if translation fails

    async def _genrate_abstract(self, summarys: List[str], language: str = "EN") -> str:
        full_response = ""

        if language == "CH":
            language_str = "Chinese"
        else:
            language_str = "English"
        input_str = f"LANGUAGE: {language_str}\n\nSUMMARY: {str(summarys)}"
        result = ResearchRunner.run_streamed(
            starting_agent=abstract_agent,
            input=input_str,
        )
        try:
            async for event in result.stream_events():
                try:
                    if event.type == "raw_response_event" and isinstance(
                        event.data, ResponseTextDeltaEvent
                    ):
                        full_response += event.data.delta
                except Exception as e:
                    logger.error(f"Error processing event: {e}")
                    continue

        except ValidationError:
            pass

        final_result = result.final_output
        return final_result

    async def _log_message(self, message: str) -> None:
        """Log a message if verbose is True"""
        if self.verbose:
            await self.thoughts_callback(message)
        else:
            print(message)

    async def _check_section(
        self, section: LongWriterOutput, query: str = "", language: str = "EN"
    ) -> LongWriterOutput:
        if language == "CH":
            language_str = "Chinese"
        else:
            language_str = "English"

        section_str = section.next_section_markdown
        ins = f"""
        LANGUAGE:
        {language_str}
        
        PROCESS_REQUIRMENT:
        {query}

        SECTION:
        {section.next_section_markdown}
        """
        try_num = 0
        max_try_num = 3
        full_response = ""
        if not section_str:
            return section
        while try_num < max_try_num:
            result = ResearchRunner.run_streamed(
                starting_agent=checkout_section_agent, input=ins
            )
            try:
                async for event in result.stream_events():
                    try:
                        if event.type == "raw_response_event" and isinstance(
                            event.data, ResponseTextDeltaEvent
                        ):
                            full_response += event.data.delta
                    except Exception as e:
                        logger.error(f"Error processing event: {e}")
                        continue
                final_result = result.final_output
                break
            except ValidationError:
                final_result = full_response
                break
            except Exception as e:
                logger.error(f"Error processing event in {try_num} times: {e}")
                try_num += 1

        if try_num == max_try_num:
            return section
        section.next_section_markdown = final_result
        return section


# 使用示例
async def example_usage():
    """
    展示如何使用LiteratureResearchTool的示例
    """
    # 创建工具实例

    # 定义回调函数
    async def progress_callback(message):
        print(f"Progress: {message}")

    async def results_callback(token):
        print(token, end="", flush=True)

    #
    user_message = str(
        """Please write a comprehensive review on recent advances in CAR-T cell therapy, focusing on innovative target mining strategies to address core challenges in solid tumor treatment. The review should: (1) analyze key obstacles hindering CAR-T efficacy in solid tumors, including tumor heterogeneity, lack of tumor-specific antigens, and immunosuppressive microenvironments; (2) explore cutting-edge technologies such as single-cell RNA sequencing, spatial transcriptomics, and machine learning/AI in driving novel target discovery, emphasizing their roles in deciphering clonal evolution, predicting antigen immunogenicity, and integrating multi-omics data; (3) discuss engineering strategies (e.g., logic-gated CAR designs, affinity optimization) that link target selection to toxicity control, as well as target-informed combination therapies (e.g., with immune checkpoint inhibitors); (4) Link target profiles to combination approaches: Immune checkpoint inhibitors, Microenvironment modulators; (5) Future Directions: AI, Personalization, and Scalable Platforms outline future directions, including AI-powered target prediction, personalized neoantigen screening, and scalable manufacturing platforms. Maintain a cohesive narrative centered on target mining, incorporate tables where appropriate to compare technologies or summarize critical targets, and ensure academic rigor with logical progression from challenges to solutions and future perspectives."""
    )

    tool = LiteratureReviewTool(
        thoughts_callback=progress_callback,
        results_callback=results_callback,
        verbose=True,
    )
    # 运行研究
    report_plan = await tool.run(
        query=user_message,
    )
    print(report_plan)

    # 运行研究 分段


async def example_tool():
    async def collect_thoughts(thought):
        print(f"THOUGHT: {thought}")

    async def collect_results(result):
        # Only store first 100 chars to avoid overwhelming memory

        print(f"PARTIAL RESULT: {result[:100]}...")

    from dataclasses import dataclass
    from typing import Any, Callable, Optional

    from agents import RunContextWrapper

    @dataclass
    class InputCallbackTool:
        query: str
        thoughts_callback: Optional[Callable[[str], Any]] = None
        """callback of thinking ."""
        results_callback: Optional[Callable[[str], Any]] = None
        """callback of results"""

        @property
        def name(self):
            return "callback"

    @function_tool
    async def test_tool(wrapper: RunContextWrapper[InputCallbackTool]):
        """
        a tool to generate a literature review
        """

        tool = LiteratureReviewTool(
            verbose=True,
            thoughts_callback=wrapper.context.thoughts_callback,
            results_callback=wrapper.context.results_callback,
        )
        response = await tool.run(wrapper.context.query)
        return response

    # 处理最后的相对导入
    try:
        from .utils.llm_client import qianwen_plus_model
    except ImportError:
        from utils.llm_client import qianwen_plus_model

    INSTRUCTIONS = """
    You are a research manager, managing a team of research agents.
    Given a research query, your job is to produce an initial outline of the report (section titles and key questions),
    as well as some background context. Each section will be assigned to a different researcher in your team who will then
    carry out research on the section.
    You will be given:
    - An initial research query
    Your task is to:
    use once of this tool to generate the review report return the full result of tool
    """

    selected_model = qianwen_plus_model
    test_agent = ResearchAgent(
        name="testtool",
        instructions=INSTRUCTIONS,
        tools=[test_tool],
        model=selected_model,
    )

    user_message = str(
        """Please write a comprehensive review on recent advances in CAR-T cell therapy, focusing on innovative target mining strategies to address core challenges in solid tumor treatment. The review should: (1) analyze key obstacles hindering CAR-T efficacy in solid tumors, including tumor heterogeneity, lack of tumor-specific antigens, and immunosuppressive microenvironments; (2) explore cutting-edge technologies such as single-cell RNA sequencing, spatial transcriptomics, and machine learning/AI in driving novel target discovery, emphasizing their roles in deciphering clonal evolution, predicting antigen immunogenicity, and integrating multi-omics data; (3) discuss engineering strategies (e.g., logic-gated CAR designs, affinity optimization) that link target selection to toxicity control, as well as target-informed combination therapies (e.g., with immune checkpoint inhibitors); (4) Link target profiles to combination approaches: Immune checkpoint inhibitors, Microenvironment modulators; (5) Future Directions: AI, Personalization, and Scalable Platforms outline future directions, including AI-powered target prediction, personalized neoantigen screening, and scalable manufacturing platforms. Maintain a cohesive narrative centered on target mining, incorporate tables where appropriate to compare technologies or summarize critical targets, and ensure academic rigor with logical progression from challenges to solutions and future perspectives."""
    )

    input = InputCallbackTool(
        query=user_message,
        thoughts_callback=collect_thoughts,
        results_callback=collect_results,
    )
    result = await ResearchRunner.run(test_agent, user_message, context=input)
    # print(result)


if __name__ == "__main__":
    asyncio.run(example_usage())
