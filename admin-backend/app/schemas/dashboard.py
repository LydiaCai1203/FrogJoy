from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_users: int
    total_books: int
    total_reading_seconds: int
    today_active_users: int
    verified_users: int
    admin_users: int


class GrowthPoint(BaseModel):
    date: str
    count: int


class UserGrowthResponse(BaseModel):
    data: list[GrowthPoint]


class ReadingStatsPoint(BaseModel):
    date: str
    total_seconds: int
    active_users: int


class ReadingStatsResponse(BaseModel):
    data: list[ReadingStatsPoint]


class ActiveUserItem(BaseModel):
    user_id: str
    email: str
    total_reading_seconds: int
    reading_days: int
    last_login_at: str | None = None


class ActiveUsersResponse(BaseModel):
    data: list[ActiveUserItem]
