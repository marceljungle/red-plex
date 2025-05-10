"""Response with the result of the create_collection use case."""
from dataclasses import dataclass, field
from typing import Optional, List

from domain.models import Collection, Album


@dataclass
class CreateCollectionResponse:
    """Response with the result of the create_collection use case
    including the information from the collection_data
    and the list of albums affected."""
    response_status: Optional[bool] = None
    collection_data: Optional[Collection] = None
    albums: List[Album] = field(default_factory=list)
