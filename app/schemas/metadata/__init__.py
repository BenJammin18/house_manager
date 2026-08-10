from app.models.item import Domain
from app.schemas.metadata.baby import BabyMetadata
from app.schemas.metadata.bill import BillMetadata
from app.schemas.metadata.chore import ChoreMetadata
from app.schemas.metadata.pet import PetMetadata
from app.schemas.metadata.prescription import PrescriptionMetadata
from app.schemas.metadata.social import SocialMetadata

METADATA_MODELS = {
    Domain.chore: ChoreMetadata,
    Domain.maintenance: ChoreMetadata,
    Domain.pet: PetMetadata,
    Domain.baby: BabyMetadata,
    Domain.bill: BillMetadata,
    Domain.social: SocialMetadata,
    Domain.prescription: PrescriptionMetadata,
}


def validate_metadata(domain: Domain, metadata: dict) -> dict:
    model = METADATA_MODELS[domain]
    return model.model_validate(metadata).model_dump(exclude_none=True)
