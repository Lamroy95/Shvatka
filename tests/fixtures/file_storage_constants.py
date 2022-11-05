from shvatka.models.dto.scn import FileContent, TgLink, FileContentLink
from shvatka.models.enums.hint_type import HintType
from tests.fixtures.scn_fixtures import GUID

FILE_ID = "98765"
CHAT_ID = 111
FILE_CONTENT = FileContent(
    guid=GUID,
    tg_link=TgLink(file_id=FILE_ID, content_type=HintType.photo),
    extension=".jpg",
    file_content_link=FileContentLink(file_path=GUID),
    original_filename="файло",
)