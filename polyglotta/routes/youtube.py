from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from ..services.youtube import MetadataUnavailable, video_metadata

router = APIRouter(prefix="/api/youtube", tags=["YouTube"])


@router.get("/{video_id}")
def metadata(video_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{11}$")]):
    try:
        return video_metadata(video_id)
    except MetadataUnavailable as error:
        raise HTTPException(502, "Video details unavailable.") from error
