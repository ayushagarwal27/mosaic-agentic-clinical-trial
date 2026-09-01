import json
import asyncio
from typing import Any

from google.cloud import storage

from config.settings import settings
from config.logging_config import setup_logging
from ingestion.document_parser import ParsedStudy, ParsedPaper

logger = setup_logging(__name__)

PREFIX_RAW_STUDIES       = "raw/studies"
PREFIX_RAW_PAPERS        = "raw/papers"
PREFIX_PROCESSED_STUDIES = "processed/studies"
PREFIX_PROCESSED_PAPERS  = "processed/papers"


class GCSStore:
    """
    Handles saving data to and loading data from Google Cloud Storage.

    IMPORTANT — WHY WE USE asyncio.to_thread() THROUGHOUT THIS FILE:

    Google's official storage library is "synchronous" — meaning
    when you ask it to upload a file, your whole program freezes
    and waits until the upload is done before doing anything else.

    But our entire MOSAIC system is built to be "asynchronous" —
    meaning we want our program to be able to do OTHER things
    while waiting for slow operations like uploads to finish.

    asyncio.to_thread() is the bridge between these two worlds.
    It takes a synchronous function (like a GCS upload) and runs
    it in a separate background thread, while letting our main
    program keep working on other tasks in the meantime.
    Think of it like handing a task to an assistant in another
    room, instead of standing there waiting yourself.
    """

    def __init__(self):
        self._client = storage.Client(project=settings.gcp_project_id)
        self._bucket = self._client.bucket(settings.gcs_bucket_name)

        logger.info(
            f"GCSStore initialised | "
            f"bucket={settings.gcs_bucket_name} | "
            f"project={settings.gcp_project_id}"
        )

    async def save_raw_study(
        self,
        nct_id: str,
        data: dict[str, Any],
    ) -> str:
        """
        Saves the EXACT, untouched API response for one study.

        Call this the moment you receive data from the API —
        BEFORE any cleaning or parsing happens. This way, even
        if the parser has a bug, the original is always safe.

        Args:
            nct_id: The study's ID, used as the filename.
            data:   The raw study dictionary to save.

        Returns:
            The path inside GCS where the file was saved.
            Example: "raw/studies/NCT04788680.json"
        """

        gcs_path = f"{PREFIX_RAW_STUDIES}/{nct_id}.json"
        await self._upload_json(path=gcs_path, data=data)

        logger.info(f"Saved raw study | nct_id={nct_id} | path={gcs_path}")
        return gcs_path

    async def save_raw_paper(
        self,
        pmid: str,
        data: dict[str, Any],
    ) -> str:
        """
        Saves the EXACT, untouched data for one PubMed paper.
        Same idea as save_raw_study — but for papers.

        Args:
            pmid: The paper's PubMed ID, used as the filename.
            data: The raw paper dictionary to save.

        Returns:
            The path inside GCS where the file was saved.
        """

        gcs_path = f"{PREFIX_RAW_PAPERS}/{pmid}.json"
        await self._upload_json(path=gcs_path, data=data)

        logger.info(f"Saved raw paper | pmid={pmid} | path={gcs_path}")
        return gcs_path

    async def save_parsed_study(self, study: ParsedStudy) -> str:
        """
        Saves the CLEANED version of a study — after document_parser.py
        has already processed it into a ParsedStudy object.

        Args:
            study: A ParsedStudy object (the clean, typed version).

        Returns:
            The path inside GCS where the file was saved.
        """

        gcs_path = f"{PREFIX_PROCESSED_STUDIES}/{study.nct_id}.json"

        await self._upload_json(
            path=gcs_path,
            data=study.model_dump(),
        )

        logger.info(
            f"Saved parsed study | nct_id={study.nct_id} | path={gcs_path}"
        )
        return gcs_path

    async def save_parsed_paper(self, paper: ParsedPaper) -> str:
        """
        Saves the CLEANED version of a paper.

        Args:
            paper: A ParsedPaper object (the clean, typed version).

        Returns:
            The path inside GCS where the file was saved.
        """

        gcs_path = f"{PREFIX_PROCESSED_PAPERS}/{paper.pmid}.json"

        await self._upload_json(
            path=gcs_path,
            data=paper.model_dump(),
        )

        logger.info(
            f"Saved parsed paper | pmid={paper.pmid} | path={gcs_path}"
        )
        return gcs_path

    async def load_parsed_study(self, nct_id: str) -> ParsedStudy | None:
        """
        Loads a previously saved, cleaned study back from GCS.

        This is the REVERSE of save_parsed_study — we use this
        in the processing layer when we need to read studies
        back in to chunk and embed them.

        Args:
            nct_id: Which study to load, by its NCT ID.

        Returns:
            A ParsedStudy object if found.
            None if no study with that ID exists in GCS.
        """

        gcs_path = f"{PREFIX_PROCESSED_STUDIES}/{nct_id}.json"
        data = await self._download_json(path=gcs_path)

        if not data:
            return None

        return ParsedStudy(**data)

    async def list_processed_studies(self) -> list[str]:
        """
        Returns a list of every study's NCT ID currently saved
        in the "processed" folder of our bucket.

        We use this later in the processing layer to know exactly
        which studies are available to chunk and embed, without
        needing to ask the database first.

        Returns:
            A list of NCT ID strings.
            Example: ["NCT04788680", "NCT03232294", "NCT06796322"]
        """

        blobs = await asyncio.to_thread(
            self._bucket.list_blobs,
            prefix=PREFIX_PROCESSED_STUDIES,
        )

        nct_ids = []
        for blob in blobs:
            filename = blob.name.split("/")[-1]
            nct_id = filename.replace(".json", "")

            if nct_id:
                nct_ids.append(nct_id)

        logger.info(f"Listed processed studies | count={len(nct_ids)}")
        return nct_ids

    async def _upload_json(
        self,
        path: str,
        data: dict[str, Any],
    ) -> None:
        """
        The shared internal method that ACTUALLY does the uploading.
        Every save_* method above eventually calls this one.

        Args:
            path: The destination path inside the GCS bucket.
            data: The dictionary to save as JSON.
        """

        json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")

        blob = self._bucket.blob(path)

        await asyncio.to_thread(
            blob.upload_from_string,
            json_bytes,
            content_type="application/json",
        )

    async def _download_json(
        self,
        path: str,
    ) -> dict[str, Any] | None:
        """
        The shared internal method that downloads a file from GCS
        and converts it back into a Python dictionary.

        Args:
            path: The path inside the GCS bucket to download from.

        Returns:
            A Python dictionary if the file was found.
            None if the file does not exist or something went wrong.
        """

        try:
            blob = self._bucket.blob(path)
            json_bytes = await asyncio.to_thread(blob.download_as_bytes)
            return json.loads(json_bytes.decode("utf-8"))

        except Exception as e:
            if "404" in str(e) or "Not Found" in str(e):
                logger.warning(f"File not found in GCS | path={path}")
            else:
                logger.error(
                    f"Failed to download from GCS | path={path} | error={e}"
                )
            return None