from sqlalchemy import Column, Integer, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import relationship

from db.models import Base
from shvatka.models import dto


class KeyTime(Base):
    __tablename__ = "log_keys"
    __mapper_args__ = {"eager_defaults": True}
    id = Column(Integer, primary_key=True)
    player_id = Column(ForeignKey("players.id"), nullable=False)
    player = relationship(
        "Player",
        foreign_keys=player_id,
        back_populates="typed_keys",
    )
    team_id = Column(ForeignKey("teams.id"), nullable=False)
    team = relationship(
        "Team",
        foreign_keys=team_id,
        back_populates="typed_keys",
    )
    game_id = Column(ForeignKey("games.id"), nullable=False)
    game = relationship(
        "Game",
        foreign_keys=game_id,
        back_populates="log_keys",
    )
    level_number = Column(Integer)
    enter_time = Column(DateTime)
    key_text = Column(Text)
    is_correct: bool | None = Column(Boolean, nullable=True)

    def to_dto(self, player: dto.Player) -> dto.KeyTime:
        return dto.KeyTime(
            text=self.key_text,
            is_correct=self.is_correct is not False,
            is_duplicate=self.is_correct is None,
            at=self.enter_time,
            level_number=self.level_number,
            player=player,
        )