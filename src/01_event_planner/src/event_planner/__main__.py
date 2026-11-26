"""用一组虚构的场地查询结果演示活动策划。"""

import json

from . import Venue, plan_meetup


if __name__ == "__main__":
    plan = plan_meetup(
        "示例周六 14:00–17:00",
        [
            Venue("社区交流室", 80, 500, True, "本地样例：场地登记与档期记录"),
            Venue("创新中心报告厅", 120, 1800, True, "本地样例：场地报价与档期记录"),
            Venue("联合办公大厅", 110, 900, None, "本地样例：暂未收到档期回复"),
            Venue("园区多功能厅", 100, 1400, True, "本地样例：场地报价与档期记录"),
        ],
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2))
