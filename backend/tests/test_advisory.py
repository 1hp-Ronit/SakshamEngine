"""Advisory: deterministic EN/HI/MR plans offline; LLM output passes guardrails or falls back."""
import json

import pytest

from app.adapters.interfaces import LLMClient
from app.services.advisory import AdvisoryService, render_plan_message

NEG = [
    {"feature": "bounce_velocity", "reason_code": "RC002"},
    {"feature": "buffer_ratio", "reason_code": "RC001"},
    {"feature": "recharge_frequency_regularity", "reason_code": "RC015"},
]


class FakeLLM(LLMClient):
    name = "fake"

    def __init__(self, reply=None, error=None, available=True):
        self.reply, self.error, self._available, self.calls = reply, error, available, 0

    @property
    def available(self):
        return self._available

    async def complete_json(self, system_prompt, user_prompt):
        self.calls += 1
        self.last_system, self.last_user = system_prompt, user_prompt
        if self.error:
            raise self.error
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply, ensure_ascii=False)


GOOD_HI = {"greeting": "नमस्ते सुनील जी", "summary": "आपके आवेदन को मज़बूत करने के लिए ये कदम उठाएं।",
           "steps": ["EMI से 2 दिन पहले खाते में पैसे रखें।", "हर महीने एक ही तारीख पर रिचार्ज करें।"], "closing": "कुछ महीनों बाद फिर आवेदन करें।"}


@pytest.mark.parametrize("lang,marker", [("en", "Hello Ravi"), ("hi", "नमस्ते Ravi"), ("mr", "नमस्कार Ravi")])
async def test_fallback_plans_in_all_three_languages(lang, marker):
    plan = await AdvisoryService(llm=FakeLLM(available=False)).generate_plan(NEG, lang, "TWO_WHEELER", "Ravi")
    assert plan.source == "fallback" and plan.language == lang and len(plan.steps) == 3 and marker in plan.greeting
    if lang != "en":
        assert all(any("ऀ" <= c <= "ॿ" for c in step) for step in plan.steps)


async def test_fallback_steps_come_from_reason_code_actions():
    plan = await AdvisoryService(llm=FakeLLM(available=False)).generate_plan(NEG, "en", "TWO_WHEELER", "Ravi")
    assert "reminder" in plan.steps[0].lower() and plan.reason_codes == ["RC002", "RC001", "RC015"]


async def test_no_negative_drivers_still_gives_a_plan():
    plan = await AdvisoryService(llm=FakeLLM(available=False)).generate_plan([], "mr", "TRACTOR", "Mohan")
    assert len(plan.steps) == 1


async def test_valid_llm_output_is_used():
    llm = FakeLLM(GOOD_HI)
    plan = await AdvisoryService(llm=llm).generate_plan(NEG[:2], "hi", "TWO_WHEELER", "सुनील")
    assert plan.source == "llm" and plan.steps == GOOD_HI["steps"]
    assert "Hindi" in llm.last_system and "Never reveal the score" in llm.last_system


@pytest.mark.parametrize("bad,why", [
    ({"greeting": "नमस्ते", "summary": "आपका स्कोर 612 है", "steps": ["क"], "closing": "ख"}, "invented number / score"),
    ({**GOOD_HI, "summary": "आपका लोन ज़रूर मंज़ूर होगा, guaranteed"}, "promise"),
    ({"greeting": "Hello", "summary": "Do these", "steps": ["Do a", "Do b"], "closing": "Bye"}, "wrong language"),
    ({**GOOD_HI, "steps": ["a", "b", "c", "d"]}, "too many steps"),
    ({"greeting": "नमस्ते"}, "missing keys"),
    ("this is not json", "not json"),
])
async def test_guardrails_reject_bad_llm_output(bad, why):
    plan = await AdvisoryService(llm=FakeLLM(bad)).generate_plan(NEG[:2], "hi", "TWO_WHEELER", "सुनील")
    assert plan.source == "fallback", why
    assert plan.fallback_reason


async def test_number_from_the_input_is_allowed():
    ok = {**GOOD_HI, "steps": ["EMI से 2 दिन पहले खाते में पैसे रखें।"]}  # "2" appears in the supplied action template
    plan = await AdvisoryService(llm=FakeLLM(ok)).generate_plan([NEG[0]], "hi", "TWO_WHEELER", "सुनील")
    assert plan.source == "llm"


async def test_llm_error_or_timeout_falls_back():
    for err in (TimeoutError("slow"), RuntimeError("HTTP 429")):
        plan = await AdvisoryService(llm=FakeLLM(error=err)).generate_plan(NEG, "mr", "TRACTOR", "Mohan")
        assert plan.source == "fallback" and len(plan.steps) == 3


async def test_plans_are_cached_per_codes_and_language():
    llm = FakeLLM(GOOD_HI)
    svc = AdvisoryService(llm=llm)
    a = await svc.generate_plan(NEG[:2], "hi", "TWO_WHEELER", "सुनील")
    b = await svc.generate_plan(NEG[:2], "hi", "TWO_WHEELER", "सुनील")
    assert a is b and llm.calls == 1


def test_whatsapp_message_rendering():
    from app.services.advisory import Plan

    msg = render_plan_message(Plan("नमस्ते रमेश जी,", "सारांश", ["कदम 1", "कदम 2"], "समापन", "hi", "fallback"), "https://x/plan/1")
    assert msg.splitlines()[0] == "नमस्ते रमेश जी," and "1. कदम 1" in msg and "https://x/plan/1" in msg
