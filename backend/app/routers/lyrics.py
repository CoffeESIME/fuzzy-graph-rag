"""
API router for LRCLIB lyrics search.

Proxies requests to the LRCLIB API (https://lrclib.net/docs)
so the frontend can search for song lyrics and inject them
into the text ingestion pipeline.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Any
import requests

router = APIRouter(
    prefix="/lyrics",
    tags=["lyrics"]
)

LRCLIB_BASE_URL = "https://lrclib.net/api"
LRCLIB_USER_AGENT = "GraphRAG Multimodal v2 (https://github.com/graphrag)"


@router.get("/search")
def search_lyrics(
    track_name: str = Query(..., description="Track name to search for"),
    artist_name: Optional[str] = Query(None, description="Artist name (optional)"),
    album_name: Optional[str] = Query(None, description="Album name (optional)"),
) -> List[Any]:
    """
    Search for song lyrics via the LRCLIB API.

    Proxies to https://lrclib.net/api/search with the given parameters.
    Returns up to 20 results from LRCLIB, each containing:
    - id, trackName, artistName, albumName, duration
    - plainLyrics, syncedLyrics, instrumental

    **Example:**
    ```
    GET /lyrics/search?track_name=Creep&artist_name=Radiohead
    ```
    """
    params = {"track_name": track_name}
    if artist_name:
        params["artist_name"] = artist_name
    if album_name:
        params["album_name"] = album_name

    try:
        response = requests.get(
            f"{LRCLIB_BASE_URL}/search",
            params=params,
            headers={"User-Agent": LRCLIB_USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="LRCLIB API timed out. Please try again.",
        )
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to LRCLIB API.",
        )
    except requests.exceptions.HTTPError as e:
        raise HTTPException(
            status_code=e.response.status_code if e.response else 500,
            detail=f"LRCLIB API error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error searching lyrics: {str(e)}",
        )
