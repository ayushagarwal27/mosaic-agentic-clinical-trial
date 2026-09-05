import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from graph.state import MosaicState, SignalOutput
from memory.procedural_store import ProceduralStore
from memory.episodic_store import EpisodicStore
from memory.semantic_store import SemanticStore
from tools.search_tools import (
    search_studies_by_meaning,
    search_past_episodes,
    save_episode,
    get_sponsor_profile,
    update_sponsor_profile,
)
from tools.clinical_tools import check_results_posted, fetch_study_details
from config.settings import settings
from config.logging_config import setup_logging
from pydantic import SecretStr

logger = setup_logging(__name__)


AGENT_NAME = "missing_results_agent"
SIGNAL_TYPE = "missing_results"
AGENT_TOOLS = [
    search_studies_by_meaning,
    search_past_episodes,
    save_episode,
    get_sponsor_profile,
    update_sponsor_profile,
    check_results_posted,
    fetch_study_details,
]


_procedural = ProceduralStore()
_episodic   = EpisodicStore()
_semantic   = SemanticStore()

_llm = ChatOpenAI(
    model=settings.openai_chat_model,
    temperature=0.1,
    api_key=settings.openai_api_key # type: ignore
).bind_tools(AGENT_TOOLS)


async def missing_results_node(state: MosaicState) -> dict:
    """
    The Missing Results Agent node — called by LangGraph during graph execution.

    Finds completed clinical trials that never posted results.
    Returns updated state with any signals found and this agent's name
    added to agents_activated.

    Args:
        state: The current MosaicState from LangGraph.
               Contains the task, nct_ids to analyse, and prior signals.

    Returns:
        Dict with updated signals list and agents_activated list.
    """

    logger.info(f"{AGENT_NAME} | Starting analysis")

    try:
        procedures = await _procedural.get_procedures(AGENT_NAME)

        procedures_text = "\n".join(f"- {r}" for r in procedures)

        system_prompt = f"""You are the Missing Results Agent for MOSAIC —
                    a clinical trial research integrity intelligence system.

                    YOUR MISSION:
                    Find completed clinical trials that have never posted their results
                    to ClinicalTrials.gov, violating federal law (FDAAA 801).
                    By law, results must be posted within 12 months of primary completion.

                    YOUR REASONING RULES (follow these exactly):
                    {procedures_text}

                    YOUR WORKFLOW:
                    1. Search past episodes to see if you have investigated similar cases
                    2. Search the database for completed studies with missing results
                    3. For each suspicious study, verify the current status with a live API call
                    4. Check the sponsor's track record using get_sponsor_profile
                    5. Generate a signal with confidence score based on evidence strength
                    6. Update the sponsor profile with your findings
                    7. Save this session as an episode before finishing

                    CONFIDENCE SCORING GUIDE:
                    - 0.9+ : Completed 5+ years ago, zero results, repeat offender sponsor
                    - 0.8  : Completed 2-5 years ago, zero results, known non-compliant sponsor
                    - 0.7  : Completed 1-2 years ago, zero results, average sponsor
                    - 0.6  : Completed 1 year ago exactly, borderline timing
                    - Below 0.6: Uncertain — send to human review

                    OUTPUT FORMAT for each signal found:
                    Return a JSON block exactly like this:
                    {{
                    "nct_id": "NCT_ID_HERE",
                    "signal_type": "missing_results",
                    "summary": "Plain English description of what you found",
                    "evidence": ["key fact 1", "key fact 2", "key fact 3"],
                    "confidence": 0.85
                    }}

                    If you find no signals, say "NO_SIGNALS_FOUND" clearly.
                    """

        task = state.get("task", "Find completed trials with missing results")

        nct_ids = state.get("nct_ids", [])

        human_message = f"""
            ANALYSIS TASK: {task}

            SPECIFIC STUDIES TO CHECK: {nct_ids if nct_ids else "Search broadly — no specific studies provided"}

            Begin your investigation now. Use your tools to search for completed
            studies with missing results. Generate signals for every violation you find.
        """

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message),
        ]

        signals_found = []

        max_iterations = 10

        for iteration in range(max_iterations):
            response = await _llm.ainvoke(messages)

            messages.append(AIMessage(content=response.content or ""))

            if not response.tool_calls:
                logger.info(
                    f"{AGENT_NAME} | Analysis complete | iteration={iteration+1}"
                )
                signals_found = _parse_signals(response.content, AGENT_NAME) # type: ignore
                break

            for tool_call in response.tool_calls:
                tool_result = await _execute_tool(tool_call, AGENT_TOOLS) # type: ignore

                messages.append(
                    HumanMessage(
                        content=f"Tool result for {tool_call['name']}:\n{tool_result}"
                    )
                )

        episode_content = (
            f"Task: {task}. "
            f"Found {len(signals_found)} missing results signals. "
            f"Signals: {[s.get('nct_id') for s in signals_found]}"
        )

        await _episodic.save_episode(
            agent_name=AGENT_NAME,
            content=episode_content,
            outcome="signal_generated" if signals_found else "no_signal",
        )

        logger.info(
            f"{AGENT_NAME} | Complete | signals_found={len(signals_found)}"
        )

        current_signals   = state.get("signals", [])
        current_activated = state.get("agents_activated", [])

        return {
            "signals":          current_signals + signals_found,
            "agents_activated": current_activated + [AGENT_NAME],
        }

    except Exception as e:
        logger.error(f"{AGENT_NAME} | Error | {e}")
        error_log = state.get("error_log", [])
        return {
            "error_log":        error_log + [f"{AGENT_NAME}: {str(e)}"],
            "agents_activated": state.get("agents_activated", []) + [AGENT_NAME],
        }


def _parse_signals(response_text: str, agent_name: str) -> list[SignalOutput]:
    """
    Extracts signal JSON blocks from the agent's text response.

    GPT-4o writes signals as JSON blocks in its response text.
    This function finds and parses every JSON block.

    WHY PARSE FROM TEXT?
    We could ask GPT-4o to return structured JSON directly.
    But agents need to explain their reasoning in plain text TOO —
    the text before and after the JSON contains valuable context
    for debugging and audit trails.
    Parsing JSON from mixed text gives us both.

    Args:
        response_text: The full text response from GPT-4o.
        agent_name:    Used to tag each signal with its source agent.

    Returns:
        List of SignalOutput dicts ready to add to state.
    """

    signals = []

    if not response_text or "NO_SIGNALS_FOUND" in response_text:
        return signals

    import re

    json_pattern = re.compile(r'\{[^{}]*"signal_type"[^{}]*\}', re.DOTALL)

    matches = json_pattern.findall(response_text)

    for match in matches:
        try:
            signal_data = json.loads(match)

            signal: SignalOutput = {
                "agent":       agent_name,
                "signal_type": signal_data.get("signal_type", SIGNAL_TYPE),
                "nct_id":      signal_data.get("nct_id", ""),
                "summary":     signal_data.get("summary", ""),
                "evidence":    signal_data.get("evidence", []),
                "confidence":  float(signal_data.get("confidence", 0.5)),
            }
            signals.append(signal)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Could not parse signal JSON | error={e}")
            continue

    return signals


async def _execute_tool(tool_call: dict, available_tools: list) -> str:
    """
    Finds and executes the tool that GPT-4o requested.

    LangGraph agents emit tool_calls in their responses — these
    contain the tool name and arguments GPT-4o wants to use.
    This function looks up the right tool by name and calls it.

    Args:
        tool_call:       The tool call from GPT-4o response.
                         Contains: name (string) and args (dict).
        available_tools: List of tool functions available to this agent.

    Returns:
        The tool's output as a string — fed back to the agent.
    """

    tool_name = tool_call.get("name", "")
    tool_args = tool_call.get("args", {})

    tool_func = None
    for t in available_tools:
        if t.name == tool_name:
            tool_func = t
            break

    if tool_func is None:
        return f"Error: Tool '{tool_name}' not found in agent's toolset."

    try:
        result = tool_func.invoke(tool_args)

        return str(result)

    except Exception as e:
        logger.error(f"Tool execution failed | tool={tool_name} | error={e}")
        return f"Error executing tool '{tool_name}': {str(e)}"