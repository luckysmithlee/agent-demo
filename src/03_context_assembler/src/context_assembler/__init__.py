"""在字符预算内组装上下文。"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ContextFragment:
    """为可选片段设置字符上限，超限时给省略号留一个字符。"""

    content: str
    max_chars: int

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise ValueError("fragment content must be a string")
        if (
            isinstance(self.max_chars, bool)
            or not isinstance(self.max_chars, int)
            or self.max_chars <= 0
        ):
            raise ValueError("fragment max_chars must be a positive integer")


@dataclass(frozen=True)
class AssembledContext:
    """保存组装结果。

    fragments 只包含选中的片段。skipped_indices 和 truncated_indices
    分别记录跳过的片段、因超限而截断并保留的片段在原输入中的索引。
    """

    instructions: str
    request: str
    fragments: tuple[str, ...]
    skipped_indices: tuple[int, ...]
    used_chars: int
    max_chars: int
    truncated_indices: tuple[int, ...] = ()


def assemble_context(
    instructions: str,
    request: str,
    fragments: Sequence[str | ContextFragment],
    max_chars: int,
) -> AssembledContext:
    """保留必需文本，应用单段限额后按输入顺序选入可选片段。

    指令和请求必须非空且不能超出预算，原有空白会保留。普通字符串没有
    单段限额。剩余预算放不下的片段会整段跳过。预算是字符串字符数之和，不含
    后续拼接的分隔符，也不是模型的 Token 数。输入无效时抛出 ValueError。
    """
    for name, value in (("instructions", instructions), ("request", request)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    # bool 是 int 的子类，但不能作为字符预算。
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars <= 0:
        raise ValueError("max_chars must be a positive integer")
    # 字符串也是 Sequence，但这里需要的是片段序列，而非单个字符串。
    if isinstance(fragments, (str, bytes)) or not isinstance(fragments, Sequence):
        raise ValueError("fragments must be a sequence of strings or ContextFragment")

    used_chars = len(instructions) + len(request)
    if used_chars > max_chars:
        raise ValueError("instructions and request exceed max_chars")

    included = []
    skipped = []
    truncated = []
    for index, fragment in enumerate(fragments):
        was_truncated = False
        if isinstance(fragment, ContextFragment):
            text = fragment.content
            if len(text) > fragment.max_chars:
                text = text[: fragment.max_chars - 1] + "…"
                was_truncated = True
        elif isinstance(fragment, str):
            text = fragment
        else:
            raise ValueError("fragments must be a sequence of strings or ContextFragment")

        if used_chars + len(text) > max_chars:
            skipped.append(index)
            continue
        included.append(text)
        used_chars += len(text)
        if was_truncated:
            truncated.append(index)

    return AssembledContext(
        instructions=instructions,
        request=request,
        fragments=tuple(included),
        skipped_indices=tuple(skipped),
        used_chars=used_chars,
        max_chars=max_chars,
        truncated_indices=tuple(truncated),
    )
