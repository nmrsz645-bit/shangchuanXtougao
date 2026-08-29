from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectRef:
    advertiser_id: str
    advertiser_name: str
    project_id: str
    project_name: str


@dataclass(frozen=True)
class PlanEntry:
    id: int | None
    plan_id: int
    project: ProjectRef
    sort_order: int
    daily_limit: int
    enabled: bool = True


@dataclass(frozen=True)
class PostingPlan:
    id: int | None
    name: str
