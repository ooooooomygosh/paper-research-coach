"""Defaults and migration behaviour the macOS port adds on top of upstream.

These cover rules that only exist in the port: Flash/high as the coach default,
and the fact that threads written by the browser build are not resumable here.
"""

import re

from paper_research_coach.coach import Coach
from paper_research_coach.dsh_bridge import DeepSeekRPC


def test_preferred_effort_uses_declared_high():
    state = {
        "model": "deepseek-flash",
        "effort": "high",
        "models": [
            {
                "model": "deepseek-flash",
                "supportedReasoningEfforts": [
                    {"reasoningEffort": "off"},
                    {"reasoningEffort": "low"},
                    {"reasoningEffort": "high"},
                    {"reasoningEffort": "max"},
                ],
                "defaultReasoningEffort": "high",
            }
        ],
    }
    assert DeepSeekRPC.preferred_effort(state) == "high"


def test_preferred_effort_never_invents_a_level():
    state = {
        "model": "m",
        "effort": "high",
        "models": [
            {
                "model": "m",
                "supportedReasoningEfforts": [{"reasoningEffort": "off"}, {"reasoningEffort": "max"}],
                "defaultReasoningEffort": "max",
            }
        ],
    }
    assert DeepSeekRPC.preferred_effort(state) == "max"


def test_browser_thread_ids_are_not_runtime_thread_ids():
    # The browser build stored Codex CLI ids; the port files threads as 32 hex.
    assert not re.fullmatch(r"[a-f0-9]{32}", "01a0f0ab-71f3-7d40-b0c4-645d14c61db6")
    assert re.fullmatch(r"[a-f0-9]{32}", "e30cf014365f45569d028c248d5b3a10")


def test_failure_message_keeps_the_runtime_reason():
    assert "额度" in Coach.failure_message(ValueError("DeepSeek 账户额度已用完，请在 Harness 中检查账户。"))
    assert "回复未完成" in Coach.failure_message(ValueError(""))
