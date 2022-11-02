from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from db.dao.holder import HolderDao
from shvatka.models import dto
from shvatka.models.enums import GameStatus
from shvatka.services.player import get_my_team
from shvatka.services.waiver import add_vote, approve_waivers
from shvatka.utils.exceptions import PlayerNotInTeam, AnotherGameIsActive
from tgbot import keyboards as kb
from tgbot.filters.game_status import GameStatusFilter
from tgbot.services.waiver import swap_saved_message, get_saved_message
from tgbot.views.commands import START_WAIVERS_COMMAND, APPROVE_WAIVERS_COMMAND
from tgbot.views.utils import total_remove_msg
from tgbot.views.waiver import get_waiver_poll_text, start_approve_waivers, get_waiver_final_text


async def start_waivers(m: Message, team: dto.Team, game: dto.Game, dao: HolderDao, bot: Bot):
    msg = await m.answer(
        text=await get_waiver_poll_text(team, game, dao),
        reply_markup=kb.get_kb_waivers(team),
        disable_web_page_preview=True,
    )
    old_msg_id = await swap_saved_message(game, msg, dao.poll)
    await total_remove_msg(bot, m.chat.id, old_msg_id)


async def add_vote_handler(
    c: CallbackQuery,
    callback_data: kb.WaiverVoteCD,
    player: dto.Player,
    team: dto.Team,
    game: dto.Game,
    dao: HolderDao,
):
    if team.id != callback_data.team_id:
        raise PlayerNotInTeam(player=player, team=team)
    await add_vote(
        game=game, team=team, player=player, vote=callback_data.vote, dao=dao.waiver_vote_adder,
    )
    await c.answer()
    await c.message.edit_text(
        text=await get_waiver_poll_text(team, game, dao),
        reply_markup=kb.get_kb_waivers(team),
        disable_web_page_preview=True,
    )


async def start_approve_waivers_handler(
    m: Message,
    player: dto.Player,
    game: dto.Game,
    dao: HolderDao,
    bot: Bot
):
    team = await get_my_team(player, dao.player_in_team)
    await total_remove_msg(
        bot=bot,
        chat_id=team.chat.tg_id,
        msg_id=await get_saved_message(game, team, dao.poll)
    )
    await bot.send_message(**await start_approve_waivers(game, team, player, dao))
    await m.delete()


async def confirm_approve_waivers_handler(
    c: CallbackQuery,
    callback_data: kb.WaiverConfirmCD,
    player: dto.Player,
    game: dto.Game,
    dao: HolderDao,
    bot: Bot,
):
    if game.id != callback_data.game_id:
        raise AnotherGameIsActive(game=game, player=player)
    team = await get_my_team(player, dao.player_in_team)
    if team.id != callback_data.team_id:
        raise PlayerNotInTeam(
            player=player, team=team,
            notify_user="Ты не состоишь в команде, за которую подаёшь вейверы!",
        )
    await approve_waivers(game=game, team=team, approver=player, dao=dao.waiver_approver)
    await bot.send_message(
        chat_id=team.chat.tg_id,
        text=await get_waiver_final_text(team, game, dao),
        disable_web_page_preview=True,
    )
    await c.answer("Вейверы успешно опубликованы!")


async def TODO(c: CallbackQuery):
    await c.answer("UNDERCONSTRUCTION", show_alert=True)


def setup() -> Router:
    router = Router(name=__name__)
    # TODO добавить обработку событий ниже, сработавших не в тот статус
    router.message.filter(
        GameStatusFilter(status=GameStatus.getting_waivers),
    )
    router.callback_query.filter(
        GameStatusFilter(status=GameStatus.getting_waivers),
    )
    # TODO is_team=True, can_manage_waivers=True
    router.message.register(start_waivers, Command(START_WAIVERS_COMMAND))
    # TODO is_team_player
    router.callback_query.register(add_vote_handler, kb.WaiverVoteCD.filter())
    #  TODO can_manage_waivers=True
    router.message.register(start_approve_waivers_handler, Command(APPROVE_WAIVERS_COMMAND))
    router.callback_query.register(confirm_approve_waivers_handler, kb.WaiverConfirmCD.filter())
    router.callback_query.filter(TODO, kb.WaiverManagePlayerCD.filter())
    router.callback_query.filter(TODO, kb.WaiverAddForceMenuCD.filter())
    return router