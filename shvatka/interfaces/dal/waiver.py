from typing import Iterable, Protocol

from shvatka.interfaces.dal.base import Committer
from shvatka.interfaces.dal.player import TeamPlayerGetter, TeamPlayersGetter
from shvatka.models import dto
from shvatka.models.enums.played import Played


class WaiverVoteAdder(TeamPlayerGetter, Protocol):
    async def add_player_vote(self, team_id: int, player_id: int, vote_var: str) -> None:
        raise NotImplementedError

    async def is_excluded(
        self,
        game: dto.Game,
        player: dto.Player,
        team: dto.Team,
    ) -> bool:
        raise NotImplementedError

    async def get_team_player(self, player: dto.Player) -> dto.TeamPlayer:
        raise NotImplementedError


class PollGetWaivers(Protocol):
    async def get_dict_player_vote(self, team_id: int) -> dict[int, Played]:
        raise NotImplementedError


class WaiverVoteGetter(PollGetWaivers, Protocol):
    async def get_by_ids_with_user_and_pit(self, ids: Iterable[int]) -> list[dto.VotedPlayer]:
        raise NotImplementedError


class WaiverApprover(Committer, TeamPlayerGetter, WaiverVoteGetter, TeamPlayersGetter, Protocol):
    async def upsert(self, waiver: dto.Waiver):
        raise NotImplementedError

    async def del_player_vote(self, team_id: int, player_id: int) -> None:
        raise NotImplementedError


class GameWaiversGetter(Protocol):
    async def get_played_teams(self, game: dto.Game) -> Iterable[dto.Team]:
        raise NotImplementedError

    async def get_played(self, game: dto.Game, team: dto.Team) -> Iterable[dto.VotedPlayer]:
        raise NotImplementedError
