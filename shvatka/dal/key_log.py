from shvatka.dal.base import Reader
from shvatka.models import dto


class TypedKeyGetter(Reader):
    async def get_typed_keys(self, game: dto.Game) -> dict[dto.Team, list[dto.KeyTime]]:
        raise NotImplementedError