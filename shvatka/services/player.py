import logging

from shvatka.interfaces.dal.player import (
    PlayerUpserter,
    PlayerTeamChecker,
    PlayerPromoter,
    TeamJoiner,
    TeamLeaver,
    TeamPlayersGetter,
    TeamPlayerGetter,
    PlayerByIdGetter,
    TeamPlayerPermissionFlipper,
)
from shvatka.interfaces.dal.secure_invite import InviteSaver, InviteRemover, InviterDao
from shvatka.models import dto, enums
from shvatka.models.enums.invite_type import InviteType
from shvatka.utils import exceptions
from shvatka.utils.defaults_constants import DEFAULT_ROLE, EMOJI_BY_ROLE, DEFAULT_EMOJI
from shvatka.utils.exceptions import (
    PlayerRestoredInTeam,
    CantBeAuthor,
    PromoteError,
    PlayerNotInTeam,
    PermissionsError,
    SaltError,
)

logger = logging.getLogger(__name__)


async def upsert_player(user: dto.User, dao: PlayerUpserter) -> dto.Player:
    player_user = await dao.upsert_player(user)
    await dao.commit()
    return player_user


async def have_team(player: dto.Player, dao: PlayerTeamChecker) -> bool:
    return await dao.have_team(player)


async def get_my_team(player: dto.Player, dao: PlayerTeamChecker) -> dto.Team | None:
    return await dao.get_team(player)


async def get_player_by_id(id_: int, dao: PlayerByIdGetter) -> dto.Player:
    return await dao.get_by_id(id_)


async def get_team_player_by_player(player: dto.Player, dao: PlayerTeamChecker) -> dto.TeamPlayer:
    return await dao.get_team_player(player)


async def get_my_role(player: dto.Player, dao: PlayerTeamChecker) -> str:
    return (await get_team_player_by_player(player, dao)).role


async def get_my_emoji(player: dto.Player, dao: PlayerTeamChecker) -> str:
    team_player = await get_team_player_by_player(player, dao)
    return team_player.emoji or EMOJI_BY_ROLE.get(team_player.role, DEFAULT_EMOJI)


async def promote(actor: dto.Player, target: dto.Player, dao: PlayerPromoter):
    if not actor.can_be_author:
        raise CantBeAuthor(
            notify_user="Чтобы повысить другого пользователя - "
            "нужно самому обладать такими правами",
            player=actor,
        )
    if target.can_be_author:
        raise PromoteError(
            text="user already have author rights",
            player=actor,
        )
    await dao.promote(actor, target)
    await dao.commit()
    logger.info("player %s promoted for target %s", actor.id, target.id)


async def join_team(
    player: dto.Player,
    team: dto.Team,
    manager: dto.Player,
    dao: TeamJoiner,
    role: str = DEFAULT_ROLE,
):
    await dao.check_player_free(player)
    check_can_add_players(await get_full_team_player(manager, team, dao))
    try:
        await dao.join_team(player, team, role=role)
    except PlayerRestoredInTeam:
        await dao.commit()
        raise
    await dao.commit()


async def check_player_on_team(player: dto.Player, team: dto.Team, dao: TeamPlayerGetter):
    pit = await dao.get_team_player(player)
    if pit.team_id != team.id:
        raise PlayerNotInTeam(player=player, team=team)


async def leave(player: dto.Player, remover: dto.Player, dao: TeamLeaver):
    team = await dao.get_team(player)
    if not team:
        raise PlayerNotInTeam(player=player)
    if player.id != remover.id:  # player itself always can leave
        team_player = await get_full_team_player(
            remover, team, dao
        )  # team of remover must be the same as player
        check_can_remove_player(team_player)  # and remover must have permission for remove
    if game := await dao.get_active_game():
        await dao.delete(
            dto.Waiver(
                player=player,
                game=game,
                team=team,
            )
        )
        await dao.del_player_vote(team_id=team.id, player_id=player.id)
    await dao.leave_team(player)
    await dao.commit()


def check_allow_be_author(player: dto.Player):
    if not player.can_be_author:
        raise CantBeAuthor(player=player)


def check_can_manage_players(team_player: dto.FullTeamPlayer):
    if not team_player.can_manage_players:
        raise PermissionsError(
            permission_name=enums.TeamPlayerPermission.can_manage_players.name,
            team=team_player.team,
            player=team_player.player,
        )


def check_can_remove_player(team_player: dto.FullTeamPlayer):
    if not team_player.can_remove_players:
        raise PermissionsError(
            permission_name=enums.TeamPlayerPermission.can_remove_players.name,
            team=team_player.team,
            player=team_player.player,
        )


def check_can_add_players(team_player: dto.FullTeamPlayer):
    if not team_player.can_add_players:
        raise PermissionsError(
            permission_name=enums.TeamPlayerPermission.can_add_players.name,
            team=team_player.team,
            player=team_player.player,
        )


async def get_full_team_player(
    player: dto.Player, team: dto.Team | None, dao: TeamPlayerGetter
) -> dto.FullTeamPlayer:
    team_player = dto.FullTeamPlayer.from_simple(
        team_player=await dao.get_team_player(player),
        team=team,
        player=player,
    )
    if team is None or team_player.team_id != team.id:
        raise PlayerNotInTeam(player=player, team=team)
    return team_player


async def get_team_players(team: dto.Team, dao: TeamPlayersGetter) -> list[dto.FullTeamPlayer]:
    return await dao.get_players(team)


async def save_promotion_invite(inviter: dto.Player, dao: InviteSaver) -> str:
    return await dao.save_new_invite(
        dct=dict(inviter_id=inviter.id, type_=InviteType.promote_author.name)
    )


async def check_promotion_invite(inviter: dto.Player, token: str, dao: InviterDao):
    data = await dao.get_invite(token)
    if data["type_"] != InviteType.promote_author.name:
        raise SaltError(
            text="Ошибка нарушения данных. Токен в зашифрованной и открытой части не совпал",
            alarm=True,
        )
    if data["inviter_id"] != inviter.id:
        raise SaltError(
            text="Ошибка нарушения данных. Токен в зашифрованной и открытой части не совпал",
            alarm=True,
        )


async def save_promotion_confirm_invite(inviter: dto.Player, dao: InviteSaver) -> str:
    return await dao.save_new_invite(
        dct=dict(inviter_id=inviter.id, type_=InviteType.promotion_confirm.name),
        token_len=16,
    )


async def dismiss_promotion(token: str, dao: InviteRemover):
    await dao.remove_invite(token)


async def agree_promotion(
    token: str,
    inviter_id: int,
    target: dto.Player,
    dao: PlayerPromoter,
):
    data = await dao.get_invite(token)
    if data["type_"] != InviteType.promotion_confirm.name:
        raise SaltError(
            text="Ошибка нарушения данных. Токен в зашифрованной и открытой части не совпал",
            alarm=True,
        )
    if data["inviter_id"] != inviter_id:
        raise SaltError(
            text="Ошибка нарушения данных. Токен в зашифрованной и открытой части не совпал",
            alarm=True,
        )
    inviter = await dao.get_by_id(inviter_id)
    await promote(inviter, target, dao)


async def flip_permission(
    actor: dto.FullTeamPlayer,
    team_player: dto.TeamPlayer,
    permission: enums.TeamPlayerPermission,
    dao: TeamPlayerPermissionFlipper,
):
    check_can_manage_players(actor)
    if actor.player_id == team_player.player_id:
        raise exceptions.PermissionsError(
            permission_name=enums.TeamPlayerPermission.can_manage_players.name,
            notify_user="can't edit yourself",
            player=actor.player,
            team=actor.team,
        )
    await dao.flip_permission(team_player, permission)
    await dao.commit()
