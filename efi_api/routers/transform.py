from fastapi import APIRouter, HTTPException
from ..schemas.efi_schema import efi
from ..schemas.transform import TransformedRecord,InputData
from typing import List

router = APIRouter()

@router.post("/transform")
async def transform_data(input_data: InputData) -> list[TransformedRecord]:
    try:
        # Create the first record (KIP)
        kip_record = TransformedRecord(
            type="KIP",
            parsed_data="http://typeapi.lab.pidconsortium.net/v1/types/schema/21.T11969/873d5c9f6ebbffecf1df",
            idx=1
        )

        # Create the second record (has_record)
        # Add the described_by field that wasn't in the input
        described_by = efi.DescriptionResource(
            has_issuer_id="https://w3id.org/isil/DE-MUS-432511",
            has_issuer_name="Filmmuseum der Landeshauptstadt Düsseldorf")
        if isinstance(input_data, efi.WorkVariant):
            if not input_data.described_by:
                input_data.described_by = [described_by]
            elif described_by.has_issuer_id not in [
                    d.has_issuer_id for d in input_data.described_by]:
                input_data.described_by.append(described_by)
        else:
            input_data.described_by = described_by

        has_record = TransformedRecord(
            type="has_record",
            parsed_data=input_data.model_dump_json(exclude_none=True),
            idx=2
        )

        return [kip_record, has_record]

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
