"""根据本地证据生成活动草案，在需要外部操作前停下。"""

from collections.abc import Sequence
from dataclasses import dataclass

ATTENDEES = 100
BUDGET_YUAN = 2500
OTHER_COSTS_YUAN = {"茶歇": 600, "物料": 200, "应急预留": 300}


@dataclass(frozen=True)
class Venue:
    """同一活动时段下的场地证据。None 表示该项待确认。"""

    name: str
    capacity: int | None
    fee_yuan: int | None
    available: bool | None
    source: str


def plan_meetup(event_time: str, venues: Sequence[Venue]) -> dict:
    """为 100 人、2500 元的固定案例生成策划草案，按输入顺序选首个合格场地。"""
    other_total = sum(OTHER_COSTS_YUAN.values())
    candidates = []
    selected = None
    for venue in venues:
        total = None if venue.fee_yuan is None else venue.fee_yuan + other_total
        if venue.capacity is None or total is None or venue.available is None:
            status = "待确认"
        elif not venue.available:
            status = "档期不可用"
        elif venue.capacity < ATTENDEES:
            status = "容量不足"
        elif total > BUDGET_YUAN:
            status = "超出预算"
        else:
            status = "符合约束"
            if selected is None:
                selected = venue

        candidates.append(
            {
                "场地": venue.name,
                "容量": venue.capacity,
                "场地费（元）": venue.fee_yuan,
                "预计总额（元）": total,
                "档期可用": venue.available,
                "依据": venue.source,
                "判断": status,
            }
        )

    return {
        "主题": "AI Agent 实战交流会",
        "时间": event_time,
        "预计人数": ATTENDEES,
        "预算上限（元）": BUDGET_YUAN,
        "预算明细（元）": {
            **OTHER_COSTS_YUAN,
            "场地": selected.fee_yuan if selected else None,
        },
        "场地候选": candidates,
        "拟选场地": selected.name if selected else "待确认",
        "议程": ["20 分钟签到与开场", "70 分钟案例分享", "60 分钟分组讨论", "30 分钟总结交流"],
        "分工": {"主持人": "控场", "场务": "确认场地和设备", "运营": "报名和签到"},
        "风险": ["待确认的场地需补齐容量、报价和档期依据", "报名人数超过容量时暂停报名"],
        "发布审批": "待审批" if selected else "暂不提交",
        "拟提交审批的操作": (
            ["预订场地", "创建日历", "发布活动", "发送通知"] if selected else []
        ),
    }
