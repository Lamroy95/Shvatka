import enum
import typing

HintLiteral = typing.Literal[
    "text",
    "gps",
    "venue",
    "photo",
    "audio",
    "video",
    "document",
    "animation",
    "voice",
    "video_note",
    "contact",
    "sticker",
]


# noinspection PyArgumentList
class HintType(enum.Enum):
    text = "text"
    gps = "gps"
    venue = "venue"
    photo = "photo"
    audio = "audio"
    video = "video"
    document = "document"
    animation = "animation"
    voice = "voice"
    video_note = "video_note"
    contact = "contact"
    sticker = "sticker"


HINTS_EMOJI: dict[HintType: str] = {
    HintType.text: "📃",
    HintType.gps: "📡",
    HintType.venue: "🧭",
    HintType.photo: "🪪",
    HintType.audio: "📷",
    HintType.video: "🎼",
    HintType.document: "🎬",
    HintType.animation: "📎",
    HintType.voice: "🌀",
    HintType.video_note: "🎤",
    HintType.contact: "🤳",
    HintType.sticker: "🏷",
}
