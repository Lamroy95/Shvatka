from aiogram.utils.markdown import html_decoration as hd

from shvatka.models import dto
from tgbot.views.player import get_emoji
from tgbot.views.user import get_small_card_no_link, get_small_card


def render_team_card(team: dto.Team) -> str:
    cap = team.captain
    cap_card = get_small_card_no_link(cap.user) if cap else "отсутствует"
    rez = f"🚩Команда: {hd.bold(hd.quote(team.name))}\n"
    rez += f"🔢ID{team.id}\n"
    rez += f"👑Капитан: {cap_card}\n"
    if team.description is not None:
        rez += f"📃Девиз: {hd.quote(team.description)}"
    return rez


def render_team_players(
    team: dto.Team, players: list[dto.FullTeamPlayer], notification=False
) -> str:
    rez = f"Список игроков команды {hd.bold(hd.quote(team.name))}:\n"
    for team_player in players:
        rez += (
            f"{hd.quote(get_emoji(team_player))} "
            f"{get_small_card(team_player.player.user, notification)}, "
            f"{hd.quote(team_player.role)}\n"
        )
    return rez
