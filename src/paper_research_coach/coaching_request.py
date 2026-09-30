"""Validated per-turn choices. These are not learner answers or mastery scores."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import Anchor

HelpMode = Literal["guided", "hint", "explain", "challenge"]
HELP_INSTRUCTIONS = {
    "guided": "按当前理解提供最少必要帮助；最多一个思考任务，不把每轮变成考试。",
    "hint": "本轮只给一个可操作的提示或已核实位置，不提前泄露结论。若缺前置知识，说明缺口；用户随后要求解释时直接解释。",
    "explain": "本轮直接回答，连起结论、机制与已核实证据，不用反问或测验拦住答案。不把看过解释记为独立掌握。",
    "challenge": "检验用户已有判断：选择最强的一个替代解释或反例，并指出可区分的证据。证据不足就保留未决，不为了反驳而编造缺陷。",
}


class Send(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str = Field(min_length=1, max_length=120)
    conversation_id: str = ""
    content: str = Field(default="", max_length=30000)
    intent: Literal["follow", "answer", "detour"] = "detour"
    help_mode: HelpMode = "guided"
    anchor: Anchor | None = None
    page_index: int = Field(default=0, ge=0)
    model: str = Field(default="", max_length=160)
    effort: str = Field(default="", max_length=30)
    page_image: str = Field(default="", max_length=4000000)
    source_version: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def image_matches_selection(self):
        # An image is of page_index, not an arbitrary previously selected page.
        if self.page_image and self.anchor and self.anchor.page_index != self.page_index:
            raise ValueError("页面图像与选区不在同一页，请回到选区页后附图。")
        return self

    def fingerprint_data(self):
        # Default requests retain pre-help-mode fingerprints across upgrades,
        # so a durable retry cannot accidentally become a second model turn.
        return self.model_dump(exclude={"help_mode"} if self.help_mode == "guided" else set())

    def context_page_index(self):
        # Old durable requests can carry the viewport page after the reader
        # selected another page. Resolve the source without rewriting their
        # fingerprint, so previously accepted requests remain idempotent.
        if self.anchor and self.anchor.page_index is not None:
            return self.anchor.page_index
        return self.page_index

    def help_instruction(self):
        return (f"本轮意图：{self.intent}。以本轮为准，不沿用上一轮。\n"
                + "本轮帮助方式（用户选择，不是掌握程度）：" + HELP_INSTRUCTIONS[self.help_mode])
