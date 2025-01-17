import dataclass_factory
from dataclass_factory import Factory

from shvatka.models.dto import scn
from shvatka.utils import exceptions


def load_level(dct: dict, dcf: Factory) -> scn.LevelScenario:
    try:
        return dcf.load(dct, scn.LevelScenario)
    except dataclass_factory.PARSER_EXCEPTIONS:
        raise exceptions.ScenarioNotCorrect(notify_user="невалидный уровень")


def check_all_files_saved(level: scn.LevelScenario, guids: set[str]):
    for hints in level.time_hints:
        check_all_files_in_time_hint_saved(hints, guids)


def check_all_files_in_time_hint_saved(hints: scn.TimeHint, guids: set[str]):
    for hint in hints.hint:
        if isinstance(hint, scn.FileMixin):
            if hint.file_guid not in guids:
                raise exceptions.FileNotFound(text=f"not found {hint.file_guid} in files")
