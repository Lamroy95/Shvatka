from dataclass_factory import Factory

from shvatka.models.dto.scn.game import GameScenario


def load_game(scn: dict, dcf: Factory) -> GameScenario:
    return dcf.load(scn, GameScenario)