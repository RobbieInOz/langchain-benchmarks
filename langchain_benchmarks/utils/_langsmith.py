"""Copy the public dataset to your own langsmith tenant."""
import json
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple, Union
from uuid import UUID

from langsmith import Client
from langsmith.utils import LangSmithNotFoundError
from tqdm import auto

WEB_API_URL = "https://web.smith.langchain.com/"


def _parse_token_or_url(url_or_token: str, api_url: str) -> Tuple[str, Optional[str]]:
    """Parse a public dataset URL or share token."""
    try:
        UUID(url_or_token)
        return api_url, url_or_token
    except ValueError:
        pass

    # Then it's a URL
    parsed_url = urllib.parse.urlparse(url_or_token)
    # Extract the UUID from the path
    path_parts = parsed_url.path.split("/")
    uuid = path_parts[-2] if len(path_parts) >= 2 else None
    return WEB_API_URL, uuid


# PUBLIC API


def clone_public_dataset(
    token_or_url: str,
    *,
    dataset_name: Optional[str] = None,
    source_api_url: str = WEB_API_URL,
) -> None:
    """Clone a public dataset to your own langsmith tenant.

    This operation is idempotent. If you already have a dataset with the given name,
    this function will do nothing.

    Args:
        token_or_url (str): The token of the public dataset to clone.
        dataset_name (str): The name of the dataset to create in your tenant.
        source_api_url: The URL of the langsmith server where the data is hosted:w
    """
    if dataset_name is None:
        raise NotImplementedError(
            "Automatic dataset name generation is not implemented yet"
        )
    client = Client()  # Client used to write to langsmith
    try:
        dataset = client.read_dataset(dataset_name=dataset_name)

        if dataset:
            print(f"Dataset {dataset_name} already exists. Skipping.")
            print(f"You can access the dataset at {dataset.url}.")
            return
    except LangSmithNotFoundError:
        pass

    source_api_url, uuid = _parse_token_or_url(token_or_url, source_api_url)
    source_client = Client(api_url=source_api_url, api_key="placeholder")
    try:
        # Fetch examples first
        examples = auto.tqdm(list(source_client.list_shared_examples(uuid)))
        print("Finished fetching examples. Creating dataset...")
        dataset = client.create_dataset(dataset_name=dataset_name)
        print(f"New dataset created you can access it at {dataset.url}.")
        try:
            client.create_examples(
                inputs=[e.inputs for e in examples],
                outputs=[e.outputs for e in examples],
                dataset_id=dataset.id,
            )
        except BaseException as e:
            # Let's not do automatic clean up for now in case there might be
            # some other reasons why create_examples fails (i.e., not network issue or
            # keyboard interrupt).
            # The risk is that this is an existing dataset that has valid examples
            # populated from another source so we don't want to delete it.
            print(
                f"An error occurred while creating dataset {dataset_name}. "
                "You should delete it manually."
            )
            raise e

        print("Done creating dataset.")
    finally:
        del source_client
        del client


def download_public_dataset(
    token_or_url: str,
    *,
    path: Optional[Union[str, Path]] = None,
    api_url: str = WEB_API_URL,
) -> None:
    """Download a public dataset."""
    api_url, uuid = _parse_token_or_url(token_or_url, api_url)
    _path = str(path) if path else f"{uuid}.json"
    if not _path.endswith(".json"):
        raise ValueError(f"Path must end with .json got: {_path}")

    # This the client where the source data lives
    # The destination for the dataset is the local filesystem
    source_client = Client(api_url=api_url, api_key="placeholder")

    try:
        # Fetch examples first
        print("Fetching examples...")
        examples = auto.tqdm(list(source_client.list_shared_examples(uuid)))
        with open(str(_path), mode="w", encoding="utf-8") as f:
            jsonifable_examples = [json.loads(example.json()) for example in examples]
            json.dump(jsonifable_examples, f, indent=2)
        print("Done fetching examples.")
    finally:
        del source_client
