"""
Agent used to synthesize a final report by iteratively writing each section of the report.
Used to produce long reports given drafts of each section. Broadly aligned with the methodology described here:


The LongWriterAgent takes as input a string in the following format:
===========================================================
ORIGINAL QUERY: <original user query>

CURRENT REPORT DRAFT: <current working draft of the report, all sections up to the current one being written>

TITLE OF NEXT SECTION TO WRITE: <title of the next section of the report to be written>

DRAFT OF NEXT SECTION: <draft of the next section of the report>
===========================================================

The Agent then:
1. Reads the current draft and the draft of the next section
2. Writes the next section of the report
3. Produces an updated draft of the new section to fit the flow of the report
4. Returns the updated draft of the new section along with references/citations
"""

# 处理相对导入
try:
    from ..utils.llm_client import (
        long_model,
        qianwen_plus_model,
    )
    from ..utils.baseclass import ResearchAgent, ResearchRunner
    from ..utils.parse_output import create_type_parser
    from ..utils.schemas import ReportDraft
    from ..config_logger import logger
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from utils.llm_client import (
        long_model,
        qianwen_plus_model,
    )
    from utils.baseclass import ResearchAgent, ResearchRunner
    from utils.parse_output import create_type_parser
    from utils.schemas import ReportDraft
    from config_logger import logger

import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from openai.types.responses import ResponseTextDeltaEvent
from pydantic import BaseModel, Field, ValidationError






class LongWriterOutput(BaseModel):
    next_section_markdown: str = Field(
        description="The final draft of the next section in markdown format"
    )
    references: List[str] = Field(
        description="A list of references and their corresponding reference hash id for the section"
    )


INSTRUCTIONS = f"""
You are an expert report writer tasked with iteratively writing each section of a report. 
Today's date is {datetime.now().strftime("%Y-%m-%d")}.
You will be provided with:
1. The original research query
3. A final draft of the report containing the table of contents and all sections written up until this point (in the first iteration there will be no sections written yet)
3. A first draft of the next section of the report to be written

OBJECTIVE:
1. Write a final draft of the next section of the report with numbered citations in square brackets in the body of the report
2. Produce a list of references to be appended to the end of the report
3. Content Depth: The review should comprehensively cover the provided articles, ensuring detailed analysis and discussion of each study, including methodologies, key findings, and contributions. Feel free to include supplementary information, explanations, and insights that may enhance the depth and breadth of your review, even if it seems verbose. The goal is to produce a comprehensive and thorough output that fulfills the length requirement.

CITATIONS/REFERENCES:
The citations should be in numerical order, written in numbered square brackets in the body of the report.
Separately, a list of all references and their corresponding reference numbers will be included at the end of the report.


For the References :
1. Use ONLY information that is explicitly provided in the articles
2. DO NOT invent or fabricate any information, dates, journal names, or other details
3. For missing information, use "N/A" or omit the field entirely, but NEVER invent data
4. Use this format: Author(s et al), (Year). Title. 
5. If any piece of information is missing, simply exclude it rather than making it up
For example, if author, year and title are available but not journal details:
- Smith J, Johnson K. (2020). Advances in gene therapy for cancer treatment.

If only author and title are available:
- Smith J. Advances in gene therapy for cancer treatment.
Follow the example below for fomartting.

DO NOT create fictional references or invent missing data.
GUIDELINES:
- You can reformat and reorganize the flow of the content and headings within a section to flow logically, but DO NOT remove details that were included in the first draft
- Only remove text from the first draft if it is already mentioned earlier in the report, or if it should be covered in a later section per the table of contents
- Ensure the heading for the section matches the table of contents
- Format the final output and references section as markdown
- Do not include a title for the reference section, just a list of numbered references

Important:
-Ensure that the output body of your output review contains 3,000-3,500 words. 

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{LongWriterOutput.model_json_schema()}
"""
INSTRUCTIONS_TEST = f"""
You are an expert academic writer specializing in writing each section of comprehensive literature reviews. 
Today's date is {datetime.now().strftime("%Y-%m-%d")}.

INPUT PROVIDED:
1. Original research query
2. A final draft of the report containing the table of contents and all sections written up until this point (in the first iteration there will be no sections written yet)
3. A first draft of the next section of the report to be written
4. Language preference

OBJECTIVE:
Write a a final draft comprehensive, well-structured literature next review section with <hash string> in the body of the report.
ATTENTION: The <hash string> is the hash string provided by the user to the reference. DON'T change the <hash string> to other string.
CRITICAL FORMATTING REQUIREMENTS (MUST FOLLOW EXACTLY):

## Section Structure:
- Main section title: ## [Section Title]
- Primary subsections: ### [Subsection Title] 
- Secondary subsections: #### [Sub-subsection Title]
- Never use numbered headings (e.g., avoid "2.1", "2.2")

## Writing Style:
- Use flowing narrative paragraphs, NOT bullet points or lists
- Each paragraph should be 4-8 sentences with clear topic sentences
- Integrate citations naturally within sentences using <hash string> format
- Maintain academic tone with sophisticated vocabulary
- Use transitional phrases between paragraphs for smooth flow

## Content Organization:
- Start each subsection with a clear introductory paragraph
- Present findings in a logical sequence
- Compare and contrast studies within the same paragraph when relevant
- Synthesize information across multiple sources
- End subsections with brief summary or transition to next topic

## Citation Requirements:
- Use ONLY the seperated <hash string> format provided (e.g., <a1b2c3d4> <a3b4c5d6>)
- NEVER change or modify the hash strings
- Integrate citations naturally: "Recent studies have shown <a1b2c3d4> that..."
- for multiple citations format,DONOT use "<a1b2c3d4,a3b4c5d6>",use the "<a1b2c3d4> <a3b4c5d6> that..." in the text,and the <hash string> is the hash string provided by the user to the reference.
- Avoid citation clustering at paragraph ends

## Language Requirements:
- If language is "CH": Write in Chinese but keep <hash string> unchanged
- If language is "EN": Write in English
- Maintain consistent language throughout

## Content Requirements:
- Comprehensively cover ALL provided articles
- Include methodology discussion when relevant
- Discuss key findings, limitations, and implications
- Maintain 800-1000 words for the section
- Do NOT remove details from the original draft unless clearly redundant,do not change the <hash string> 

## Prohibited Formats:
- No bullet points (•) or numbered lists (1., 2., 3.)

- No excessive short paragraphs (under 3 sentences)
- No standalone citation sentences

REFERENCES FORMAT:
Collect all <hash string> citations and their corresponding sources exactly as provided by the user.

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{LongWriterOutput.model_json_schema()}
"""


selected_model = long_model

long_writer_agent = ResearchAgent(
    name="LongWriterAgent",
    instructions=INSTRUCTIONS_TEST,
    model=selected_model,
    # output_type=LongWriterOutput if model_supports_structured_output(selected_model) else None,
    # output_parser=create_type_parser(LongWriterOutput) if not model_supports_structured_output(selected_model) else None
)

INSTRUCTIONS_Translation = """
You are an expert translator tasked with translating a text from English to Chinese.

INPUT PROVIDED:
1. A text in English

OBJECTIVE:
Translate the text from English to Chinese

"""

translation_agent = ResearchAgent(
    name="TranslationAgent",
    instructions=INSTRUCTIONS_Translation,
    model=selected_model,
    # output_type=LongWriterOutput if model_supports_structured_output(selected_model) else None,
    # output_parser=create_type_parser(LongWriterOutput) if not model_supports_structured_output(selected_model) else None
)


async def write_next_section(
    original_query: str,
    report_draft: str,
    next_section_title: str,
    next_section_draft: str,
    thoughts_callback,
    language: str = "EN",  # EN or CH
):
    """Write the next section of the report"""

    user_message = f"""
    <ORIGINAL QUERY>
    {original_query}
    </ORIGINAL QUERY>

    <CURRENT REPORT DRAFT>
    {report_draft or "No draft yet"}
    </CURRENT REPORT DRAFT>

    <TITLE OF NEXT SECTION TO WRITE>
    {next_section_title}
    </TITLE OF NEXT SECTION TO WRITE>

    <DRAFT OF NEXT SECTION>
    {next_section_draft}
    </DRAFT OF NEXT SECTION>

    <LANGUAGE>
    {language}
    </LANGUAGE>
    """
    # await thoughts_callback(user_message)

    # result = await ResearchRunner.run(
    #     long_writer_agent,
    #     user_message,
    # )
    # return result.final_output_as(LongWriterOutput)
    max_iter = 3
    iter_num = 0
    temp_agent_type = ""

    while iter_num < max_iter:
        full_response = ""
        try:
            result = ResearchRunner.run_streamed(
                long_writer_agent,
                user_message,
            )

            async for event in result.stream_events():
                # Process different event types
                if event.type == "raw_response_event" and isinstance(
                    event.data, ResponseTextDeltaEvent
                ):
                    full_response += event.data.delta
                elif event.type == "agent_updated_stream_event":
                    if event.new_agent.name != temp_agent_type:
                        temp_agent_type = event.new_agent.name
                        # await thoughts_callback(
                        #     f"Agent updated: {event.new_agent.name}"
                        # )

            # Try to parse as JSON first, if that fails, treat as markdown
            try:
                # print(f"Full response length: {len(full_response)}")
                # Clean and prepare the response for JSON parsing
                cleaned_response = clean_json_response(full_response)

                resf = create_type_parser(LongWriterOutput)
                res = resf(cleaned_response)
                return res
            except Exception as parse_error:
                # If JSON parsing fails, try manual extraction
                logger.warning(
                    f"Failed to parse output as JSON in write_next_section ,try extract from failed json: {str(parse_error)[:200]}"
                )
                try:
                    manual_result = extract_from_failed_json(full_response)
                    if manual_result:
                        return manual_result
                except Exception as manual_error:
                    logger.error(
                        f"Manual extraction also failed: {str(manual_error)[:100]}"
                    )

                # Increment iteration counter and continue the loop instead of returning empty references
                iter_num += 1
                logger.error(
                    f"Parse error occurred: {parse_error}. Retrying {iter_num}/{max_iter}..."
                )
                continue

        except ValidationError:
            # print(f"#############ValidationError: {e}")
            resf = create_type_parser(LongWriterOutput)
            res = resf(full_response)
            return res
        except Exception as e:
            logger.error(f"Write next section error: {e}")
            iter_num += 1
            logger.error(f"Error occurred: {e}. Retrying {iter_num}/{max_iter}...")
    # If all retries fail, return an error output
    return LongWriterOutput(
        next_section_markdown="The section generate error", references=[]
    )


def clean_json_response(response: str) -> str:
    """Clean and prepare JSON response for parsing"""
    import json

    # Remove any leading/trailing whitespace
    response = response.strip()

    # If response doesn't start with {, try to find the JSON part
    if not response.startswith("{"):
        json_start = response.find("{")
        if json_start != -1:
            response = response[json_start:]

    # If response doesn't end with }, try to find the end
    if not response.endswith("}"):
        json_end = response.rfind("}")
        if json_end != -1:
            response = response[: json_end + 1]

    # Fix common JSON issues
    # 1. Replace curly quotes with regular quotes
    response = response.replace('"', '"').replace('"', '"')
    response = response.replace(""", "'").replace(""", "'")

    # 2. Fix common issues with hash strings in references
    # Ensure proper escaping of < and > characters if they cause issues
    response = response.replace("\\<", "<").replace("\\>", ">")

    # 3. Try to fix trailing commas in arrays/objects
    response = re.sub(r",(\s*[}\]])", r"\1", response)

    # 4. Ensure proper closing of strings and arrays
    try:
        json.loads(response)
        return response
    except json.JSONDecodeError as e:
        logger.warning(
            f"JSON decode error at position {e.pos}: {str(e)},try to fix it "
        )
        # If still failing, try to truncate at the error position
        if hasattr(e, "pos") and e.pos > 0:
            # Try to find a safe truncation point before the error
            truncate_pos = e.pos
            while truncate_pos > 0 and response[truncate_pos - 1] not in [
                '"',
                "}",
                "]",
            ]:
                truncate_pos -= 1
            if truncate_pos > 0:
                truncated = response[:truncate_pos]
                # Try to close the JSON properly
                if truncated.count('"') % 2 == 1:  # Odd number of quotes
                    truncated += '"'
                if truncated.count("{") > truncated.count("}"):
                    truncated += "}"
                if truncated.count("[") > truncated.count("]"):
                    truncated += "]"
                try:
                    json.loads(truncated)
                    return truncated
                except:
                    pass

    return response


def extract_from_failed_json(response: str) -> Optional[LongWriterOutput]:
    """Attempt to extract data from malformed JSON response"""
    try:
        import re

        # More flexible approach to extract markdown content
        # Look for the pattern with various possible endings
        markdown_patterns = [
            r'"next_section_markdown":\s*"(.*?)"(?=,\s*"references")',
            r'"next_section_markdown":\s*"(.*?)"(?=,?\s*"references")',
            r'"next_section_markdown":\s*"(.*?)"\s*,',
            r'"next_section_markdown":\s*"(.*?)"(?=\s*[,}])',
        ]

        markdown_content = None
        for pattern in markdown_patterns:
            markdown_match = re.search(pattern, response, re.DOTALL)
            if markdown_match:
                markdown_content = markdown_match.group(1)
                break

        if not markdown_content:
            # Try to extract everything between first quote after next_section_markdown
            start_match = re.search(r'"next_section_markdown":\s*"', response)
            if start_match:
                start_pos = start_match.end()
                # Find the closing quote, handling escaped quotes
                quote_count = 0
                end_pos = start_pos
                while end_pos < len(response):
                    if response[end_pos] == '"' and (
                        end_pos == 0 or response[end_pos - 1] != "\\"
                    ):
                        break
                    end_pos += 1
                if end_pos < len(response):
                    markdown_content = response[start_pos:end_pos]

        # Extract references
        references = []
        refs_patterns = [
            r'"references":\s*\[(.*?)\]',
            r'"references":\s*\[(.*?)(?=\s*})',
        ]

        for pattern in refs_patterns:
            refs_match = re.search(pattern, response, re.DOTALL)
            if refs_match:
                refs_content = refs_match.group(1)
                # Extract individual reference strings, looking for hash patterns
                ref_items = re.findall(r'"([^"]*<[a-f0-9]{8}>[^"]*)"', refs_content)
                references = ref_items
                break

        if markdown_content:
            # Clean up the markdown content
            markdown_content = (
                markdown_content.replace('\\"', '"')
                .replace("\\n", "\n")
                .replace("\\/", "/")
            )

            return LongWriterOutput(
                next_section_markdown=markdown_content, references=references
            )
    except Exception as e:
        logger.error(f"Manual extraction error: {e}")
        return None

    return None


def extract_hash_strings_from_text(text: str) -> List[str]:
    """Extract all <hash_string> patterns from text, preserving order and removing duplicates"""
    pattern = r"<([a-f0-9]{8})>"
    matches = re.findall(pattern, text)

    # 保持顺序的去重：使用dict.fromkeys()保持插入顺序
    return list(dict.fromkeys(matches))


def replace_hash_strings_with_numbered_refs(
    final_draft: str, all_references: List[str]
) -> Tuple[str, List[str]]:
    """
    在final_draft中搜索所有的<hash str>，然后和all_references对比，
    将不同的hash str逐个替换为[1][2]...
    如果有找不到的hash str，则直接删除这条，正文中也要删除

    Args:
        final_draft: 报告正文
        all_references: 所有引用列表，格式为 ["<hash> source", ...]

    Returns:
        (updated_final_draft, formatted_references)
    """
    # 提取正文中的所有hash字符串
    hash_strings_in_text = extract_hash_strings_from_text(final_draft)

    # 创建hash到引用的映射
    hash_to_source = {}
    for ref in all_references:
        if ref and "<" in ref and ">" in ref:
            # 提取hash和source
            match = re.match(r"<([a-f0-9]{8})>\s*(.*)", ref)
            if match:
                hash_str, source = match.groups()
                hash_to_source[hash_str] = source.strip()

    # 为正文中出现的hash字符串分配编号（仅对找到匹配的hash）
    hash_to_number = {}
    formatted_references = []
    ref_counter = 1

    for hash_str in hash_strings_in_text:
        if hash_str in hash_to_source:
            hash_to_number[hash_str] = ref_counter
            formatted_references.append(f"[{ref_counter}] {hash_to_source[hash_str]}")
            ref_counter += 1

    # 在正文中处理所有hash字符串
    updated_final_draft = final_draft
    for hash_str in hash_strings_in_text:
        pattern = f"<{hash_str}>"
        if hash_str in hash_to_number:
            # 找到对应引用，替换为编号
            replacement = f"[{hash_to_number[hash_str]}]"
            updated_final_draft = updated_final_draft.replace(pattern, replacement)
        else:
            # 找不到对应引用，直接删除
            updated_final_draft = updated_final_draft.replace(pattern, "")

    return updated_final_draft, formatted_references


async def write_report(
    original_query: str,
    report_title: str,
    report_draft: ReportDraft,
    ref: List[str],
    thoughts_callback,
    language: str = "EN",  # EN or CH
) -> str:
    """Write the final report by iteratively writing each section"""

    if thoughts_callback == None:

        async def thoughts_callback(thought):
            pass

    if language == "CH":
        report_title_response = await ResearchRunner.run(
            translation_agent,
            report_title,
        )
        report_title = report_title_response.final_output
        final_draft = f"# {report_title}\n\n" + "\n\n"
    else:
        # Initialize the final draft of the report with the title and table of contents
        final_draft = (
            f"# {report_title}\n\n"
            + "## Table of Contents\n\n"
            + "\n".join(
                [
                    f"{i + 1}. {section.section_title}"
                    for i, section in enumerate(report_draft.sections)
                ]
            )
            + "\n\n"
        )
    all_references = ref
    # print(f"########## all_references {all_references},length {len(all_references)}")
    for section in report_draft.sections:
        # Produce the final draft of each section and add it to the report with corresponding references
        # print(f"Writing section: {section.section_title}, {section.section_content}")
        next_section_draft = await write_next_section(
            original_query,
            final_draft,
            section.section_title,
            section.section_content,
            thoughts_callback,
            language,
        )
        # print(f"####Next section draft references: {len(next_section_draft.references)}")

        # 收集所有引用
        # if next_section_draft.references:
        #     all_references.extend(next_section_draft.references)

        section_markdown = next_section_draft.next_section_markdown
        section_markdown = reformat_section_headings(section_markdown)
        final_draft += section_markdown + "\n\n"

    # 处理引用：将hash字符串替换为编号
    # print(f"####Total references collected: {len(all_references)}")
    # print(f"##############final_draft: {final_draft}")
    final_draft, formatted_references = replace_hash_strings_with_numbered_refs(
        final_draft, all_references
    )
    # print(f"####Formatted references: {len(formatted_references)}")

    # Add the final references to the end of the report
    # final_draft += "## References:\n\n" + "  \n".join(all_references)
    if formatted_references:
        final_draft += "## References\n\n" + "\n".join(formatted_references)
    # else:
    #     fake_info = "NOTICE: THIS ARTICLE is "
    #     final_draft += "## References\n\n" + "\n".join(formatted_references)

    return final_draft


async def write_report_from_section_drafts(
    original_query: str,
    abstract: str,
    report_title: str,
    report_draft: ReportDraft,
    ref: List[str],
    thoughts_callback,
    language: str = "EN",  # EN or
) -> str:
    """Write the final report by iteratively writing each section"""
    if thoughts_callback == None:

        async def thoughts_callback(thought):
            pass

    if abstract:
        abstract_string = "# Abstract\n\n" + abstract + "\n\n"
    else:
        abstract_string = ""
    final_draft = (
        f"# {report_title}\n\n"
        + "## Table of Contents\n\n"
        + "\n".join(
            [
                f"{i + 1}. {section.section_title}"
                for i, section in enumerate(report_draft.sections)
            ]
        )
        + "\n\n"
        + abstract_string
    )
    all_references = ref
    for section in report_draft.sections:
        section_markdown = section.section_content
        section_markdown = reformat_section_headings(section_markdown)
        final_draft += section_markdown + "\n\n"
    final_draft, formatted_references = replace_hash_strings_with_numbered_refs(
        final_draft, all_references
    )
    if formatted_references:
        final_draft += "## References\n\n" + "\n\n".join(formatted_references)
    return final_draft


def reformat_references(
    section_markdown: str, section_references: List[str], all_references: List[str]
) -> Tuple[str, List[str]]:
    """
    This method gracefully handles the re-numbering, de-duplication and re-formatting of references as new sections are added to the report draft.
    It takes as input:
    1. The markdown content of the new section containing inline references in square brackets, e.g. [1], [2]
    2. The list of references for the new section, e.g. ["[1] Authors, (year). Title", "[2] [1] Authors, (year). Title"]
    3. The list of references covering all prior sections of the report

    It returns:
    1. The updated markdown content of the new section with the references re-numbered and de-duplicated, such that they increment from the previous references
    2. The updated list of references for the full report, to include the new section's references
    """

    def convert_ref_list_to_map(ref_list: List[str]) -> Dict[str, str]:
        ref_map = {}
        for ref in ref_list:
            try:
                ref_num = int(ref.split("]")[0].strip("["))
                url = ref.split("]", 1)[1].strip()
                ref_map[url] = ref_num
            except ValueError:
                print(f"Invalid reference format: {ref}")
                continue
        return ref_map

    section_ref_map = convert_ref_list_to_map(section_references)
    report_ref_map = convert_ref_list_to_map(all_references)
    section_to_report_ref_map = {}

    report_urls = set(report_ref_map.keys())
    ref_count = max(report_ref_map.values() or [0])
    for url, section_ref_num in section_ref_map.items():
        if url in report_urls:
            section_to_report_ref_map[section_ref_num] = report_ref_map[url]
        else:
            # If the reference is not in the report, add it to the report
            ref_count += 1
            section_to_report_ref_map[section_ref_num] = ref_count
            all_references.append(f"[{ref_count}] {url}")

    def replace_reference(match):
        # Extract the reference number from the match
        ref_num = int(match.group(1))
        # Look up the new reference number
        mapped_ref_num = section_to_report_ref_map.get(ref_num)
        if mapped_ref_num:
            return f"[{mapped_ref_num}]"
        return ""

    # Replace all references in a single pass using a replacement function
    section_markdown = re.sub(r"\[(\d+)\]", replace_reference, section_markdown)

    return section_markdown, all_references


def reformat_section_headings(section_markdown: str) -> str:
    """
    Reformat the headings of a section to be consistent with the report, by rebasing the section's heading to be a level-2 heading

    E.g. this:
    # Big Title
    Some content
    ## Subsection

    Becomes this:
    ## Big Title
    Some content
    ### Subsection
    """
    # If the section is empty, return as-is
    if not section_markdown.strip():
        return section_markdown

    # Find the first heading level
    first_heading_match = re.search(r"^(#+)\s", section_markdown, re.MULTILINE)
    if not first_heading_match:
        return section_markdown

    # Calculate the level adjustment needed
    first_heading_level = len(first_heading_match.group(1))
    level_adjustment = 2 - first_heading_level

    def adjust_heading_level(match):
        hashes = match.group(1)
        content = match.group(2)
        new_level = max(2, len(hashes) + level_adjustment)
        return "#" * new_level + " " + content

    # Apply the heading adjustment to all headings in one pass
    return re.sub(
        r"^(#+)\s(.+)$", adjust_heading_level, section_markdown, flags=re.MULTILINE
    )
