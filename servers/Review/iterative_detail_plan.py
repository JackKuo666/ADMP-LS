from typing import Optional, Callable, Any, Tuple
import time
from openai.types.responses import ResponseTextDeltaEvent

from iterative_research import Conversation
from utils.baseclass import ResearchRunner
from tools.detail_plan_agent import (
    query_enrichment_agent,
    core_outline_agent,
    detailed_outline_agent,
    evaluation_agent,
    CoreOutline,
    OutlineEvaluation,
)
from utils.parse_output import create_type_parser
from config_logger import logger
# from biodeepdiscovery.config.logging_config import configure_logging
# logger = logging.getLogger(__name__)


# logger = configure_logging()
class IterativeDetailPlan:
    """
    3-Step Literature Review Outline Generator.

    Workflow:
    1. Enrich user query
    2. Generate core outline (title, background, core sections)
    3. Generate enhanced detailed outline (more comprehensive sections with detailed descriptions)
    """

    def __init__(
        self,
        max_iterations: int = 3,
        max_time_minutes: int = 8,
        thoughts_callback: Optional[Callable[[str], Any]] = None,
    ):
        self.max_iterations = max_iterations
        self.max_time_minutes = max_time_minutes
        self.start_time: float = None
        self.conversation: Conversation = Conversation()
        self.iteration: int = 0
        self.should_continue: bool = True
        self.thoughts_callback = thoughts_callback

        # Workflow state variables
        self.enriched_query: str = ""
        self.core_outline: Optional[CoreOutline] = None
        self.final_detailed_outline: Optional[CoreOutline] = None
        self.evaluation_feedback: str = ""

    async def run(self, query: str) -> Tuple[CoreOutline, str]:
        """
        Run the 3-step iterative literature review outline generation process.

        :param query: The initial research query.
        :return: A CoreOutline with enhanced detailed structure.
        """
        self.start_time = time.time()

        if self.thoughts_callback:
            await self.thoughts_callback(
                "Starting literature review outline generation... \n"
            )

        # Step 1: Enrich the user query (done once at the beginning)
        logger.info(f"Step 1: Enriching user query... \n")
        await self._step1_enrich_query(query)

        # Steps 2 & 3: Iterative core and detailed outline generation
        logger.info(f"Step 2 & 3: Iterative core and detailed outline generation... \n")
        while self.should_continue and self._check_constraints():
            self.iteration += 1
            self.conversation.add_iteration()

            if self.thoughts_callback:
                await self.thoughts_callback(
                    f" Iteration {self.iteration}: Generating outlines...\n"
                )

            # Step 2: Generate core outline (with evaluation feedback from previous iteration)
            logger.info(f"Step 2: Generating core outline... \n")
            await self._step2_generate_core_outline(self.evaluation_feedback)

            # Step 3: Generate detailed outline (with evaluation feedback from previous iteration)
            logger.info(f"Step 3: Generating detailed outline... \n")
            await self._step3_generate_detailed_outline(self.evaluation_feedback)

            # Evaluate quality
            logger.info(f"Step 4: Evaluating outlines... \n")
            evaluation = await self._evaluate_outlines()

            if evaluation.ready_for_writing and evaluation.core_complete:
                if self.thoughts_callback:
                    await self.thoughts_callback(
                        "Literature review outline completed and ready for writing!"
                    )
                break
            else:
                if self.thoughts_callback:
                    missing = (
                        ", ".join(evaluation.missing_elements)
                        if evaluation.missing_elements
                        else "structure improvements"
                    )
                    await self.thoughts_callback(
                        f"Refining outline - addressing: {missing}"
                    )

                # Prepare evaluation feedback for next iteration
                self.evaluation_feedback = self._format_evaluation_feedback(evaluation)

        if self.thoughts_callback:
            await self.thoughts_callback(
                "Literature review outline generation completed!\n"
            )
            await self.thoughts_callback(f"{self.get_core_outline_summary()}\n")
        return self.final_detailed_outline, self.enriched_query

    def _check_constraints(self) -> bool:
        """Check if the constraints for the iterative process are met."""
        elapsed_time = time.time() - self.start_time
        if elapsed_time > self.max_time_minutes * 60:
            return False

        if self.iteration >= self.max_iterations:
            return False

        return True

    async def _step1_enrich_query(self, query: str):
        """Step 1: Enrich the user query with literature review context."""
        if self.thoughts_callback:
            await self.thoughts_callback("Step 1: Enriching user query...\n")

        # Use stream_result for consistency (returns string, not a structured object)
        result = ResearchRunner.run_streamed(query_enrichment_agent, query)
        full_response = ""

        try:
            async for event in result.stream_events():
                try:
                    if event.type == "raw_response_event" and isinstance(
                        event.data, ResponseTextDeltaEvent
                    ):
                        token = event.data.delta
                        full_response += token
                        # if self.thoughts_callback:
                        #     await self.thoughts_callback(token)
                except Exception as e:
                    logger.error(f"Error processing stream event: {e}")
                    continue
        except Exception as e:
            if "ResponseUsage" in str(e):
                logger.error(f"ResponseUsage validation error (continuing): {e}")
            else:
                logger.error(f"Stream processing error: {e}")
                raise

        # Query enrichment returns a string, not a structured object
        self.enriched_query = result.final_output or full_response

        if self.thoughts_callback:
            await self.thoughts_callback("\n Query enrichment completed \n")

    async def _step2_generate_core_outline(self, evaluation_feedback: str = ""):
        """Step 2: Generate core outline (title, background, main sections)."""
        if self.thoughts_callback:
            await self.thoughts_callback("Step 2: Generating core outline...\n")

        if evaluation_feedback:
            query = f"""
            ENRICHED QUERY: {self.enriched_query}
            
            EVALUATION FEEDBACK FOR IMPROVEMENT:
            {evaluation_feedback}
            
            Please generate an improved core outline based on the feedback above.
            """
        else:
            query = self.enriched_query

        # Use stream_result for streaming output
        self.core_outline = await self._stream_result(
            core_outline_agent, query, CoreOutline
        )

        if self.thoughts_callback:
            await self.thoughts_callback("Core outline generated\n")

    async def _step3_generate_detailed_outline(self, evaluation_feedback: str = ""):
        """Step 3: Generate enhanced detailed outline with comprehensive descriptions."""
        if self.thoughts_callback:
            await self.thoughts_callback(
                "Step 3: Generating enhanced detailed outline...\n"
            )

        # Convert core outline to input for detailed generation
        core_outline_text = self._format_core_outline_for_detailed_generation()

        if evaluation_feedback:
            query = f"""
            {core_outline_text}
            
            EVALUATION FEEDBACK FOR IMPROVEMENT:
            {evaluation_feedback}
            
            Please generate an improved detailed outline based on the feedback above.
            """
        else:
            query = core_outline_text

        # Use stream_result for streaming output
        self.final_detailed_outline = await self._stream_result(
            detailed_outline_agent, query, CoreOutline
        )

        if self.thoughts_callback:
            await self.thoughts_callback("Final outline generated \n")

    def _format_core_outline_for_detailed_generation(self) -> str:
        """Format the core outline as input for detailed outline generation."""
        print(f"######self.core_outline: {self.core_outline}")
        formatted_text = f"""
        CORE OUTLINE TO EXPAND:
        
        Title: {self.core_outline.report_title}
        Background: {self.core_outline.background}
        
        Core Sections:
        """

        for i, section in enumerate(self.core_outline.sections, 1):
            formatted_text += f"\n{i}. {section.title}"
            formatted_text += f"\n   Focus: {section.description}"

        formatted_text += f"\n\nENRICHED RESEARCH CONTEXT:\n{self.enriched_query}"

        return formatted_text

    async def _evaluate_outlines(self) -> OutlineEvaluation:
        """Evaluate the quality of both core and detailed outlines."""
        evaluation_input = f"""
        ENRICHED QUERY:
        {self.enriched_query}
        
        CORE OUTLINE:
        Title: {self.core_outline.report_title}
        Background: {self.core_outline.background}
        
        Core Sections:
        """

        for i, section in enumerate(self.core_outline.sections, 1):
            evaluation_input += f"\n{i}. {section.title}: {section.description}"

        evaluation_input += "\n\nDETAILED ENHANCED OUTLINE:\n"
        evaluation_input += f"Title: {self.final_detailed_outline.report_title}\n"
        evaluation_input += f"Background: {self.final_detailed_outline.background}\n\n"

        evaluation_input += "Detailed Sections:\n"
        for i, section in enumerate(self.final_detailed_outline.sections, 1):
            evaluation_input += f"{i}. {section.title}\n"
            evaluation_input += f"   Description: {section.description}\n"

        # result = await ResearchRunner.run(evaluation_agent, evaluation_input)

        result = await self._stream_result(
            evaluation_agent, evaluation_input, OutlineEvaluation
        )
        return result

    def _format_evaluation_feedback(self, evaluation: OutlineEvaluation) -> str:
        """Format evaluation feedback for next iteration."""
        feedback_parts = []

        if evaluation.missing_elements:
            missing_text = ", ".join(evaluation.missing_elements)
            feedback_parts.append(f"Missing Elements: {missing_text}")

        if evaluation.suggestions:
            feedback_parts.append(f"Suggestions: {evaluation.suggestions}")

        if not evaluation.core_complete:
            feedback_parts.append("Core structure needs improvement")

        if not evaluation.hierarchy_appropriate:
            feedback_parts.append("Hierarchical structure needs adjustment")

        return "\n".join(feedback_parts) if feedback_parts else ""

    def get_core_outline_summary(self) -> str:
        """Get a comprehensive summary of the generated outline."""
        if not self.core_outline:
            return "No outline generated yet."

        summary = "LITERATURE REVIEW OUTLINE\n"

        # summary += f"Title: {self.core_outline.report_title}\n"
        summary += f"Background: {self.core_outline.background}\n\n"

        summary += "DETAILED SECTIONS:\n"

        for i, section in enumerate(self.core_outline.sections, 1):
            summary += f"\n{i}. {section.title}\n"
            summary += f"Description: {section.description}\n"

        return summary

    def get_final_outline_summary(self) -> str:
        """Get a comprehensive summary of the generated outline."""
        if not self.final_detailed_outline:
            return "No outline generated yet."

        summary = "LITERATURE REVIEW OUTLINE\n"

        summary += f"Title: {self.final_detailed_outline.report_title}\n"
        summary += f"Background: {self.final_detailed_outline.background}\n\n"

        summary += "DETAILED SECTIONS:\n"

        for i, section in enumerate(self.final_detailed_outline.sections, 1):
            summary += f"\n{i}. {section.title}\n"
            summary += f"Description: {section.description}\n"

        return summary

    def get_workflow_status(self) -> str:
        """Get the current status of the 3-step workflow."""
        status = "🔄 WORKFLOW STATUS:\n"
        status += f"Step 1 - Query Enrichment: {'✅ Complete' if self.enriched_query else '⏳ Pending'}\n"
        status += f"Step 2 - Core Outline: {'✅ Complete' if self.core_outline else '⏳ Pending'}\n"
        status += f"Step 3 - Enhanced Detailed Outline: {'✅ Complete' if self.final_detailed_outline else '⏳ Pending'}\n"
        status += f"Current Iteration: {self.iteration}/{self.max_iterations}\n"

        if self.start_time:
            elapsed = time.time() - self.start_time
            status += f"Elapsed Time: {elapsed:.1f}s / {self.max_time_minutes * 60}s\n"

        return status

    async def _stream_result(self, agent, query, output_format=None):
        """Stream agent result with proper error handling and format conversion."""

        try_num = 0
        max_try_num = 3
        while try_num < max_try_num:
            result = ResearchRunner.run_streamed(agent, query)
            full_response = ""

            try:
                async for event in result.stream_events():
                    try:
                        if event.type == "raw_response_event" and isinstance(
                            event.data, ResponseTextDeltaEvent
                        ):
                            token = event.data.delta
                            full_response += token
                            # Stream token to callback if available (without newlines to avoid mixing with status)
                            # if self.thoughts_callback:
                            #     await self.thoughts_callback(token)
                    except Exception as e:
                        logger.error(f"Error processing stream event: {e}")
                        continue

            except Exception as e:
                if "ResponseUsage" in str(e):
                    # Handle ResponseUsage validation error, continue with collected response
                    logger.error(f"ResponseUsage validation error (continuing): {e}")
                else:
                    logger.error(f"Stream processing error: {e}")
                    raise  # Re-raise other exceptions

            # Get final result and convert to specified format
            try:
                final_result = result.final_output
                if output_format and hasattr(final_result, "final_output_as"):
                    final_result = final_result.final_output_as(output_format)
                elif output_format:
                    resf = create_type_parser(output_format)
                    final_result = resf(full_response)
                return final_result
            except Exception as e:
                logger.error(
                    f"Error converting final result to format in {try_num} times: {output_format}: {e}"
                )
                try_num += 1
                continue
        return None


if __name__ == "__main__":
    import asyncio

    async def main():
        """Demo function to test the IterativeDetailPlan."""

        # Sample research topic
        research_topic = """PleasewriteacomprehensivereviewonrecentadvancesinCAR-Tcelltherapy,
focusingoninnovativetargetminingstrategiestoaddresscorechallengesinsolid
tumortreatment.Thereviewshould:(1)analyzekeyobstacleshinderingCAR-T
efficacyinsolidtumors,includingtumorheterogeneity,lackoftumor-specific
antigens,andimmunosuppressivemicroenvironments;(2)explorecutting-edge
technologiessuchassingle-cellRNAsequencing,spatialtranscriptomics,and
machinelearning/AIindrivingnoveltargetdiscovery,emphasizingtheirrolesin
decipheringclonalevolution,predictingantigenimmunogenicity,andintegrating
multi-omicsdata;(3)discussengineeringstrategies(e.g.,logic-gatedCARdesigns,
affinityoptimization)thatlinktargetselectiontotoxicitycontrol,aswellas
target-informedcombinationtherapies(e.g.,withimmunecheckpointinhibitors);
(4)Linktargetprofilestocombinationapproaches:Immunecheckpointinhibitors,
Microenvironmentmodulators;(5)FutureDirections:AI,Personalization,and
ScalablePlatformsoutlinefuturedirections,includingAI-poweredtarget
prediction,personalizedneoantigenscreening,andscalablemanufacturing
platforms.Maintainacohesivenarrativecenteredontargetmining,incorporate
tableswhereappropriatetocomparetechnologiesorsummarizecriticaltargets,
andensureacademicrigorwithlogicalprogressionfromchallengestosolutions
andfutureperspectives."""

        # Progress callback function
        async def progress_callback(message: str):
            import time

            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
            await asyncio.sleep(0.1)

        # Initialize the outline generator
        generator = IterativeDetailPlan(
            max_iterations=3, max_time_minutes=10, thoughts_callback=progress_callback
        )

        try:
            # Generate the outline
            print("\n🚀 Starting outline generation...")
            outline = await generator.run(query=research_topic)

            if outline:
                print("\n" + "=" * 80)
                print(" OUTLINE GENERATION COMPLETED!")
                print("=" * 80)

                # Display the summary
                print(generator.get_outline_summary())

                print("\n" + "=" * 80)
                print(" WORKFLOW STATUS:")
                print("=" * 80)
                print(generator.get_workflow_status())

                print("\n" + "=" * 80)
                print("🔍 DETAILED STRUCTURE:")
                print("=" * 80)
                print(f"📋 Title: {outline.report_title}")
                print(f"📄 Background: {outline.background}")
                print(f" Total Sections: {len(outline.sections)}")

                # Show first section as example
                if outline.sections:
                    print("\n Example Section:")
                    first_section = outline.sections[0]
                    print(f"Title: {first_section.title}")
                    print(f"Description: {first_section.description[:300]}...")

                print("\n🎉 Demo completed successfully!")

            else:
                print("\n❌ Failed to generate outline")

        except Exception as e:
            print(f"\n❌ Error during outline generation: {str(e)}")
            import traceback

            traceback.print_exc()

    # Run the demo
    asyncio.run(main())
