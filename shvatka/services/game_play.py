import asyncio
import logging
from datetime import timedelta, datetime

from shvatka.interfaces.dal.game_play import GamePreparer, GamePlayerDao
from shvatka.interfaces.dal.level_times import GameStarter, LevelTimeChecker
from shvatka.interfaces.scheduler import Scheduler
from shvatka.models import dto
from shvatka.models.dto import scn
from shvatka.services.organizers import get_orgs, get_spying_orgs
from shvatka.utils.datetime_utils import tz_utc
from shvatka.utils.exceptions import InvalidKey
from shvatka.utils.input_validation import is_key_valid
from shvatka.utils.key_checker_lock import KeyCheckerFactory
from shvatka.views.game import GameViewPreparer, GameLogWriter, GameView, OrgNotifier, LevelUp

logger = logging.getLogger(__name__)


async def prepare_game(
    game: dto.Game,
    game_preparer: GamePreparer,
    view_preparer: GameViewPreparer,
):
    if not need_prepare_now(game):
        logger.warning(
            "waked up too early or too late planned %s, now %s",
            game.start_at,
            datetime.now(tz=tz_utc),
        )
        return
    await view_preparer.prepare_game_view(
        game=game,
        teams=await game_preparer.get_agree_teams(game),
        orgs=await get_orgs(game, game_preparer),
        dao=game_preparer,
    )
    await game_preparer.delete_poll_data()


async def start_game(
    game: dto.FullGame,
    dao: GameStarter,
    game_log: GameLogWriter,
    view: GameView,
    scheduler: Scheduler,
):
    """
    Для начала игры нужно сделать несколько вещей:
    * пометить игру как начатую
    * поставить команды на первый уровень
    * отправить загадку первого уровня
    * запланировать подсказку первого уровня
    * записать в лог игры, что игра началась
    """
    now = datetime.now(tz=tz_utc)
    if not need_start_now(game):
        logger.warning("waked up too early or too late planned %s, now %s", game.start_at, now)
        return
    await dao.set_game_started(game)
    logger.info("game %s started", game.id)
    teams = await dao.get_played_teams(game)

    await dao.set_teams_to_first_level(game, teams)
    await dao.commit()

    await asyncio.gather(*[view.send_puzzle(team, game.levels[0]) for team in teams])

    await asyncio.gather(
        *[schedule_first_hint(scheduler, team, game.levels[0], now) for team in teams]
    )

    await game_log.log("Game started")


async def check_key(
    key: str,
    player: dto.Player,
    team: dto.Team,
    game: dto.FullGame,
    dao: GamePlayerDao,
    view: GameView,
    game_log: GameLogWriter,
    org_notifier: OrgNotifier,
    locker: KeyCheckerFactory,
    scheduler: Scheduler,
):
    """
    Проверяет введённый игроком ключ. Может случиться несколько исходов:
    - ключ неверный - просто записываем его в лог и уведомляем команду
    - ключ верный, но уже был введён ранее - записываем в лог и уведомляем команду
    - ключ верный, но ещё не все ключи найдены - записываем в лог, уведомляем команду
    - ключ верный и больше на уровне не осталось ненайденных ключей:
      * уровень не последний - переводим команду на следующий уровень, уведомляем оргов,
        присылаем команде новую загадку, планируем отправку подсказки
      * уровень последний - поздравляем команду с завершением игры
      * уровень последний и все команды финишировали - помечаем игру законченной,
        пишем в лог игры уведомление о финале, уведомляем команды

    :param key: Введённый ключ.
    :param player: Игрок, который ввёл ключ.
    :param team: Команда, в которой ввели ключ.
    :param game: Текущая игра.
    :param dao: Слой доступа к бд.
    :param view: Слой отображения данных.
    :param game_log: Логгер игры (публичные уведомления о статусе игры).
    :param org_notifier: Для уведомления оргов о важных событиях.
    :param locker: Локи для обеспечения последовательного исполнения определённых операций.
    :param scheduler: Планировщик подсказок.
    """
    if not is_key_valid(key):
        raise InvalidKey(key=key, team=team, player=player, game=game)
    new_key = await submit_key(
        key=key, player=player, team=team, game=game, dao=dao, locker=locker
    )
    if new_key.is_duplicate:
        await view.duplicate_key(key=new_key)
        return
    elif new_key.is_correct:
        await view.correct_key(key=new_key)
        if new_key.is_level_up:
            async with locker.lock_globally():
                if await dao.is_team_finished(team, game):
                    await finish_team(team, game, view, game_log, dao, locker)
                    return
            next_level = await dao.get_current_level(team, game)

            await view.send_puzzle(team=team, level=next_level)
            await schedule_first_hint(scheduler, team, next_level)
            level_up_event = LevelUp(
                team=team, new_level=next_level, orgs_list=await get_spying_orgs(game, dao)
            )
            await org_notifier.notify(level_up_event)
    else:
        await view.wrong_key(key=new_key)


async def submit_key(
    key: str,
    player: dto.Player,
    team: dto.Team,
    game: dto.Game,
    dao: GamePlayerDao,
    locker: KeyCheckerFactory,
) -> dto.InsertedKey:
    async with locker(team):  # несколько конкурентных ключей от одной команды - последовательно
        level = await dao.get_current_level(team, game)
        keys = level.get_keys()
        new_key = await dao.save_key(
            key=key,
            team=team,
            level=level,
            game=game,
            player=player,
            is_correct=key in keys,
            is_duplicate=await dao.is_key_duplicate(level, team, key),
        )
        typed_keys = await dao.get_correct_typed_keys(level=level, game=game, team=team)
        is_level_up = False
        if typed_keys == keys:
            await dao.level_up(team=team, level=level, game=game)
            is_level_up = True
        await dao.commit()
    return dto.InsertedKey.from_key_time(new_key, is_level_up)


async def finish_team(
    team: dto.Team,
    game: dto.FullGame,
    view: GameView,
    game_log: GameLogWriter,
    dao: GamePlayerDao,
    locker: KeyCheckerFactory,
):
    """
    два варианта:
    * уровень последний - поздравляем команду с завершением игры
    * уровень последний и все команды финишировали - помечаем игру законченной,
      пишем в лог игры уведомление о финале, уведомляем команды.
    :param team: Команда закончившая игру.
    :param game: Текущая игра.
    :param dao: Слой доступа к бд.
    :param view: Слой отображения данных.
    :param game_log: Логгер игры (публичные уведомления о статусе игры).
    :param locker: Эту штуку мы просто очистим, если игра кончилась.
    """
    await view.game_finished(team)
    if await dao.is_all_team_finished(game):
        await dao.finish(game)
        await dao.commit()
        await game_log.log("Game finished")
        locker.clear()
        for team in await dao.get_played_teams(game):
            await view.game_finished_by_all(team)


async def send_hint(
    level: dto.Level,
    hint_number: int,
    team: dto.Team,
    dao: LevelTimeChecker,
    view: GameView,
    scheduler: Scheduler,
):
    """
    Отправить подсказку (запланированную ранее) и запланировать ещё одну.
    Если команда уже на следующем уровне - отправлять не надо.

    :param level: Подсказка относится к уровню.
    :param hint_number: Номер подсказки, которую надо отправить.
    :param team: Какой команде надо отправить подсказку.
    :param dao: Слой доступа к данным.
    :param view: Слой отображения.
    :param scheduler: Планировщик.
    """
    if not await dao.is_team_on_level(team, level):
        logger.debug(
            "team %s is not on level %s, skip sending hint #%s",
            team.id,
            level.db_id,
            hint_number,
        )
        return
    await view.send_hint(team, hint_number, level)
    next_hint_number = hint_number + 1
    if level.is_last_hint(hint_number):
        logger.debug(
            "sent last hint #%s to team %s on level %s, no new scheduling required",
            hint_number,
            team.id,
            level.db_id,
        )
        return
    next_hint_time = calculate_next_hint_time(
        level.get_hint(hint_number),
        level.get_hint(next_hint_number),
    )
    await scheduler.plain_hint(level, team, next_hint_number, next_hint_time)


async def get_available_hints(
    game: dto.Game, team: dto.Team, dao: GamePlayerDao
) -> list[scn.TimeHint]:
    level_time = await dao.get_current_level_time(team=team, game=game)
    level = await dao.get_current_level(team=team, game=game)
    from_start_level_minutes = (datetime.now(tz=tz_utc) - level_time.start_at).seconds // 60
    return list(filter(lambda th: th.time <= from_start_level_minutes, level.scenario.time_hints))


async def schedule_first_hint(
    scheduler: Scheduler,
    team: dto.Team,
    next_level: dto.Level,
    now: datetime = None,
):
    await scheduler.plain_hint(
        level=next_level,
        team=team,
        hint_number=1,
        run_at=calculate_first_hint_time(next_level, now),
    )


def calculate_first_hint_time(next_level: dto.Level, now: datetime = None) -> datetime:
    return calculate_next_hint_time(next_level.get_hint(0), next_level.get_hint(1), now)


def calculate_next_hint_time(
    current: scn.TimeHint, next_: scn.TimeHint, now: datetime = None
) -> datetime:
    if now is None:
        now = datetime.now(tz=tz_utc)
    return now + calculate_next_hint_timedelta(current, next_)


def calculate_next_hint_timedelta(
    current_hint: scn.TimeHint,
    next_hint: scn.TimeHint,
) -> timedelta:
    return timedelta(minutes=(next_hint.time - current_hint.time))


def need_start_now(game: dto.Game) -> bool:
    if game.start_at is None:
        return False
    utcnow = datetime.now(tz=tz_utc)
    if game.start_at < utcnow:
        if (utcnow - game.start_at) < timedelta(minutes=30):
            return True
        return False
    else:
        if (game.start_at - utcnow) < timedelta(minutes=1):
            return True
        return False


def need_prepare_now(game: dto.Game) -> bool:
    if game.start_at is None:
        return False
    utcnow = datetime.now(tz=tz_utc)
    if game.start_at < utcnow:
        if (utcnow - game.start_at) < timedelta(minutes=35):
            return True
        return False
    else:
        if (game.start_at - utcnow) < timedelta(minutes=6):
            return True
        return False
