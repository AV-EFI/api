from avefi_schema import model_pydantic_v2 as efi
from pydantic import BaseModel, Field

EFIRequest = efi.WorkVariant

class EFIResponse(BaseModel):
    message: str = Field(
        ..., description="A message indicating the result of the operation")
    data: EFIRequest = Field(..., description="The processed EFI data")

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error details")
