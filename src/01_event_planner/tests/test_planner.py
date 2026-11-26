from event_planner import Venue, plan_meetup


def test_selects_a_venue_at_the_capacity_and_budget_limits():
    plan = plan_meetup("周六下午", [
        Venue("小场地", 99, 500, True, "本地样例"),
        Venue("贵场地", 100, 1401, True, "本地样例"),
        Venue("合格场地", 100, 1400, True, "本地样例"),
    ])

    assert [venue["判断"] for venue in plan["场地候选"]] == ["容量不足", "超出预算", "符合约束"]
    assert plan["拟选场地"] == "合格场地"
    assert sum(plan["预算明细（元）"].values()) == 2500
    assert plan["发布审批"] == "待审批"
    assert plan["拟提交审批的操作"] == ["预订场地", "创建日历", "发布活动", "发送通知"]


def test_stops_before_approval_when_venue_evidence_is_incomplete():
    plan = plan_meetup("周六下午", [
        Venue("档期未回复", 120, 800, None, "本地样例：缺少档期回复"),
        Venue("档期已占用", 120, 800, False, "本地样例：场地已约满"),
    ])

    assert [venue["判断"] for venue in plan["场地候选"]] == ["待确认", "档期不可用"]
    assert plan["场地候选"][0]["依据"] == "本地样例：缺少档期回复"
    assert plan["拟选场地"] == "待确认"
    assert plan["预算明细（元）"]["场地"] is None
    assert plan["发布审批"] == "暂不提交"
    assert plan["拟提交审批的操作"] == []
