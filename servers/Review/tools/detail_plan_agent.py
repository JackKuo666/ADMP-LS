
from utils.llm_client import (
    model_supports_structured_output,
    qianwen_plus_model,
)
from utils.parse_output import create_type_parser
from utils.baseclass import ResearchAgent
from tools.search_tool import article_simple_search
from pydantic import BaseModel, Field

from typing import List




# Step 2: Core Outline Models (simple structure)
class CoreSection(BaseModel):
    title: str = Field(description="Main section title (e.g., Introduction)")
    description: str = Field(
        description="Core focus and what this section should cover"
    )


class CoreOutline(BaseModel):
    report_title: str = Field(description="Title of the literature review")
    background: str = Field(description="Background context and rationale")
    sections: List[CoreSection] = Field(description="sections of the review")


# Step 3: Detailed Hierarchical Models (1 → 1.1 → 1.1.1)
class SubSubSection(BaseModel):
    title: str = Field(description="Sub-subsection title (1.1.1)")
    content_to_fill: str = Field(description="Context/content that needs to be filled")


class SubSection(BaseModel):
    title: str = Field(description="Subsection title (1.1)")
    content_to_fill: str = Field(
        description="Context that needs to be filled if necessary"
    )
    sub_sub_sections: List[SubSubSection] = Field(
        description="Sub-subsections (1.1.1, 1.1.2, etc.)", default=[]
    )


class DetailedSection(BaseModel):
    title: str = Field(description="Main section title (1.)")
    subsections: List[SubSection] = Field(description="Subsections (1.1, 1.2, etc.)")


class DetailedOutline(BaseModel):
    report_title: str = Field(description="Title of the literature review")
    background: str = Field(description="Background context")
    sections: List[DetailedSection] = Field(
        description="Detailed hierarchical sections"
    )


# Step 1: Query Enrichment Agent
QUERY_ENRICHMENT_INSTRUCTION = """
You are a Literature Review Query Enhancement Specialist.

Your task: Transform a research topic into a comprehensive literature review specification.

Given a research topic, enrich it by adding:

1. **Research Context**: 
   - Scientific field and current state of knowledge
   - Key research gaps and controversies

2. **Review Scope**:
   - Specific aspects to be covered
   - Methodological considerations
   - Target audience level

3. **Expected Outcomes**:
   - Knowledge synthesis opportunities
   - Future research directions

Provide an enriched query (200-250 words) that gives clear direction for literature review outline generation.
"""
selected_model = qianwen_plus_model
query_enrichment_agent = ResearchAgent(
    name="query_enrichment_agent",
    model=qianwen_plus_model,
    instructions=QUERY_ENRICHMENT_INSTRUCTION,
)

# Step 2: Core Outline Generation Agent
CORE_OUTLINE_INSTRUCTION = f"""
You are a Literature Review Core Outline Generator.

Your task: Create a core outline structure for a scientific literature review.
Dont generate more than 6 section
Given an enriched research query, generate:

1. **Review Title**: Clear, specific title for the literature review
2. **Background**: Concise rationale and context (2-3 sentences)
3. **Core Sections**: Main sections with clear focus, typically including:
   - Introduction/Background
   - Methods/Search Strategy
   - Results/Current State of Research
   - Discussion/Analysis
   - Future Directions/Conclusions

For each section, provide:
- Clear title
- Description of core focus and what it should cover

Keep this as a high-level structure - details will be added later.

Only output JSON and follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{CoreOutline.model_json_schema()}
"""

core_outline_agent = ResearchAgent(
    name="core_outline_agent",
    model=qianwen_plus_model,
    instructions=CORE_OUTLINE_INSTRUCTION,
    # tools = [article_simple_search],
    output_type=CoreOutline
    if model_supports_structured_output(qianwen_plus_model)
    else None,
    output_parser=create_type_parser(CoreOutline)
    if not model_supports_structured_output(qianwen_plus_model)
    else None,
)

# Step 3: Detailed Outline Generation Agent
DETAILED_OUTLINE_INSTRUCTION = f"""
You are a Literature Review Detailed Outline Generator.

Your task: Expand a core outline into a detailed hierarchical structure.
Dont generate more than 6 section
Given a core outline, create a detailed structure with:

**For each main section, generate hierarchical subsections,MOST have 3 level:**
- Use numbered hierarchy: 1.1, 1.2, 1.3 (subsections)
- Use sub-numbered hierarchy: 1.1.1, 1.1.2, 1.1.3 (sub-subsections)
- Include "Context/content to fill" descriptions for each subsection
- Include " instruction" specific requirement including generate table or workflow format
**Structure Format (put in description field):**
For each section, put the hierarchical structure in the description field like this:

1.1 [Subsection Title]
Context/content to fill: [Detailed description of what content should go here]
instruction: [specific user requirement to generateor none]

1.1.1 [Sub-subsection Title]  
Context/content to fill: [Specific content guidance and specific user needs]
instruction: [specific user requirement to generateor none]

1.1.2 [Sub-subsection Title]
Context/content to fill: [Specific content guidance and specific user needs]]
instruction: [specific user requirement to generateor none]
1.2 [Next Subsection Title]
Context/content to fill: [Detailed description]
instruction: [specific user requirement to generateor none]
**Content Guidelines:**
- Each main section should have 2-4 subsections (1.1, 1.2, etc.)
- Include sub-subsections where needed (1.1.1, 1.1.2, etc.) 
- Provide specific "Context/content to fill" for each subsection
- Ensure logical flow and comprehensive coverage
- Make titles clear and specific


**Important:** 
- Put the entire hierarchical structure in the description field of each section.
- can call the tool to search the article abstract to help , DO NOT do more than 2 tool calls


Only output JSON and follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{CoreOutline.model_json_schema()}

"""

detailed_outline_agent = ResearchAgent(
    name="detailed_outline_agent",
    model=qianwen_plus_model,
    instructions=DETAILED_OUTLINE_INSTRUCTION,
    tools=[article_simple_search],
    output_type=CoreOutline
    if model_supports_structured_output(qianwen_plus_model)
    else None,
    output_parser=create_type_parser(CoreOutline)
    if not model_supports_structured_output(qianwen_plus_model)
    else None,
)


# Quality Evaluation
class OutlineEvaluation(BaseModel):
    core_complete: bool = Field(description="Whether core structure is complete")
    hierarchy_appropriate: bool = Field(
        description="Whether hierarchical structure is appropriate"
    )
    missing_elements: List[str] = Field(
        description="Missing elements that need to be added"
    )
    suggestions: str = Field(description="Suggestions for improvement")
    ready_for_writing: bool = Field(
        description="Whether outline is ready for content writing"
    )


EVALUATION_INSTRUCTION = f"""
You are a Literature Review Outline Quality Evaluator.

Evaluate the outline for:

**Completeness:**
- All essential sections present
- Appropriate hierarchical depth
- Clear content specifications

**Structure:**
- Logical flow from introduction to conclusion
- Appropriate subsection breakdown
- Clear writing guidance

**Literature Review Standards:**
- Methodology sections included
- Synthesis opportunities identified
- Publication-ready structure

Provide specific feedback for improvement.

Output JSON only:
{OutlineEvaluation.model_json_schema()}
"""

evaluation_agent = ResearchAgent(
    name="evaluation_agent",
    model=qianwen_plus_model,
    instructions=EVALUATION_INSTRUCTION,
    output_type=OutlineEvaluation
    if model_supports_structured_output(qianwen_plus_model)
    else None,
    output_parser=create_type_parser(OutlineEvaluation)
    if not model_supports_structured_output(qianwen_plus_model)
    else None,
)
