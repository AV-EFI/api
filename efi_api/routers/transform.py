from fastapi import APIRouter, HTTPException
from ..schemas.transform import TransformedRecord,InputData
from typing import List

router = APIRouter()

@router.post("/transform", response_model=List[TransformedRecord])
async def transform_data(input_data: InputData):
    try:
        # Create the first record (KIP)
        kip_record = TransformedRecord(
            type="KIP",
            parsed_data="http://typeapi.lab.pidconsortium.net/v1/types/schema/21.T11969/873d5c9f6ebbffecf1df",
            idx=1
        )

        # Create the second record (has_record)
        # Add the described_by field that wasn't in the input
        input_dict = input_data.dict()
        input_dict["described_by"] = {
            "has_issuer_id": "https://w3id.org/isil/DE-MUS-432511",
            "has_issuer_name": "Filmmuseum der Landeshauptstadt Düsseldorf"
        }

        has_record = TransformedRecord(
            type="has_record",
            parsed_data=input_dict,
            idx=2
        )

        return [kip_record, has_record]

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))