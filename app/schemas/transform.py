from typing import Annotated

from pydantic import BaseModel, Field

from .efi_schema import efi

InputData = Annotated[
        efi.WorkVariant | efi.Manifestation | efi.Item,
        Field(discriminator='category')]

# Output models
class TransformedRecord(BaseModel):
    type: str
    parsed_data: str
    idx: int
