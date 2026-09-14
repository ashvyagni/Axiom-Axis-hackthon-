from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any


class WeatherData(BaseModel):
    temperature: float = 0.0
    condition: str = "clear"
    humidity: float = 0.0


class CityDataProvider(ABC):
    @abstractmethod
    async def get_districts(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_infrastructure(self, district_id: str | None = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_teams(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_weather(self, lat: float, lng: float) -> WeatherData:
        ...


class SimulationProvider(CityDataProvider):
    def __init__(self):
        self._seeded = False

    async def get_districts(self) -> list[dict[str, Any]]:
        from axiom.db.engine import async_session
        from sqlalchemy import select
        from axiom.db.models.domain import District
        async with async_session() as db:
            districts = (await db.execute(select(District))).scalars().all()
            return [{"id": d.id, "name": d.name, "lat": d.latitude, "lon": d.longitude} for d in districts]

    async def get_infrastructure(self, district_id: str | None = None) -> list[dict[str, Any]]:
        from axiom.db.engine import async_session
        from sqlalchemy import select
        from axiom.db.models.domain import Infrastructure
        async with async_session() as db:
            query = select(Infrastructure)
            if district_id:
                query = query.where(Infrastructure.district_id == district_id)
            infra = (await db.execute(query)).scalars().all()
            return [{"id": i.id, "name": i.name, "type": i.type, "status": i.status} for i in infra]

    async def get_teams(self) -> list[dict[str, Any]]:
        from axiom.db.engine import async_session
        from sqlalchemy import select
        from axiom.db.models.domain import Team
        async with async_session() as db:
            teams = (await db.execute(select(Team))).scalars().all()
            return [{"id": t.id, "name": t.name, "status": t.status} for t in teams]

    async def get_weather(self, lat: float, lng: float) -> WeatherData:
        return WeatherData(temperature=22.0, condition="clear", humidity=0.5)


simulation_provider = SimulationProvider()
