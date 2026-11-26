import pytest

from context_assembler import AssembledContext, ContextFragment, assemble_context


def test_assembles_exact_budget_and_preserves_text():
    result = assemble_context(" 指令 ", " 请求 ", ["甲", " b ", ""], 12)

    assert result == AssembledContext(
        instructions=" 指令 ",
        request=" 请求 ",
        fragments=("甲", " b ", ""),
        skipped_indices=(),
        used_chars=12,
        max_chars=12,
    )


def test_skips_large_fragments_and_tries_following_ones():
    result = assemble_context("i", "r", ["abc", "x", "abc", "y"], 4)

    assert result.fragments == ("x", "y")
    assert result.skipped_indices == (0, 2)
    assert result.used_chars == 4


def test_applies_fragment_caps_before_the_total_budget():
    result = assemble_context(
        " 规 ",
        " 问 ",
        [
            "未设置长度限制的背景信息",
            ContextFragment("错误细节", max_chars=3),
            ContextFragment("补充", max_chars=2),
            ContextFragment("配置", max_chars=1),
        ],
        max_chars=12,
    )

    assert (result.instructions, result.request) == (" 规 ", " 问 ")
    assert result.fragments == ("错误…", "补充", "…")
    assert result.skipped_indices == (0,)
    assert result.truncated_indices == (1, 3)
    assert result.used_chars == result.max_chars == 12


def test_skips_a_capped_fragment_if_it_still_exceeds_remaining_budget():
    result = assemble_context("i", "r", [ContextFragment("长资料", 2), "短"], 3)

    assert result.fragments == ("短",)
    assert result.skipped_indices == (0,)
    assert result.truncated_indices == ()
    assert result.used_chars == 3


@pytest.mark.parametrize(
    ("content", "max_chars"),
    [(None, 1), ("资料", 0), ("资料", -1), ("资料", True), ("资料", 1.5)],
)
def test_rejects_invalid_fragment(content, max_chars):
    with pytest.raises(ValueError):
        ContextFragment(content, max_chars)


@pytest.mark.parametrize(
    ("instructions", "request_text", "fragments", "max_chars"),
    [
        ("", "r", [], 10),
        ("i", "  ", [], 10),
        (None, "r", [], 10),
        ("i", "r", [], 0),
        ("i", "r", [], True),
        ("i", "r", [], 1.5),
        ("i", "r", [], 1),
        ("i", "r", "text", 10),
        ("i", "r", ["valid", 1], 10),
    ],
)
def test_rejects_invalid_input(instructions, request_text, fragments, max_chars):
    with pytest.raises(ValueError):
        assemble_context(instructions, request_text, fragments, max_chars)
