from enum import Enum


class TaskType(str, Enum):
    CHAT = "chat"
    RESEARCH = "research"
    CODING = "coding"
