"""
This module defines data models for Onshape document, workspace, element, and other related entities
retrieved from Onshape REST API responses.

The data models are implemented as Pydantic BaseModel classes, which are used to:
    Parse JSON responses from the API into Python objects.
    Validate the structure and types of the JSON responses.
    Provide type hints for better code clarity and autocompletion.

These models ensure that the data received from the API adheres to the expected format and types, facilitating easier
and safer manipulation of the data within the application.

Models:
    Document: Represents an Onshape document, containing the document ID, workspace type, workspace ID, and element ID.
    DocumentMetaData: Represents metadata of an Onshape document, containing the default workspace information and name.

Supplementary models:
    DefaultWorkspace: Represents the default workspace of an Onshape document, containing the workspace ID and type.

Functions:
    parse_url: Parses an Onshape URL and returns the document ID, workspace type, workspace ID, and element ID.
    generate_url: Generates an Onshape URL from the document ID, workspace type, workspace ID, and element ID.

Enums:
    WORKSPACE_TYPE: Enumerates the possible workspace types in Onshape (w, v, m).
    META_WORKSPACE_TYPE: Enumerates the possible meta workspace types in Onshape (workspace, version, microversion).
"""

from enum import Enum
from typing import Union, cast

import regex as re
from pydantic import BaseModel, Field, field_validator

__all__ = ["WORKSPACE_TYPE", "Document", "parse_url"]


class WORKSPACE_TYPE(str, Enum):
    """
    Enumerates the possible workspace types in Onshape

    Attributes:
        W: Workspace
        V: Version
        M: Microversion
    """

    W = "w"
    V = "v"
    M = "m"


class META_WORKSPACE_TYPE(str, Enum):
    """
    Enumerates the possible meta workspace types in Onshape

    Attributes:
        WORKSPACE: Workspace
        VERSION: Version
        MICROVERSION: Microversion

    Properties:
        shorthand: Shorthand representation of the meta workspace type (first letter)
    """

    WORKSPACE = "workspace"
    VERSION = "version"
    MICROVERSION = "microversion"

    @property
    def shorthand(self) -> str:
        return self.value[0]


# Pattern for matching Onshape document URLs
DOCUMENT_PATTERN = r"https://cad.onshape.com/documents/([\w\d]+)/(w|v|m)/([\w\d]+)/e/([\w\d]+)"


def generate_url(did: str, wtype: str, wid: str, eid: str) -> str:
    """
    Generate Onshape URL from document ID, workspace type, workspace ID, and element ID

    Args:
        did: The unique identifier of the document
        wtype: The type of workspace (w, v, m)
        wid: The unique identifier of the workspace
        eid: The unique identifier of the element

    Returns:
        url: URL to the Onshape document element

    Examples:
        >>> generate_url("a1c1addf75444f54b504f25c", "w", "0d17b8ebb2a4c76be9fff3c7", "a86aaf34d2f4353288df8812")
        "https://cad.onshape.com/documents/a1c1addf75444f54b504f25c/w/0d17b8ebb2a4c76be9fff3c7/e/a86aaf34d2f4353288df8812"
    """
    return f"https://cad.onshape.com/documents/{did}/{wtype}/{wid}/e/{eid}"


def parse_url(url: str) -> str:
    """
    Parse Onshape URL and return document ID, workspace type, workspace ID, and element ID

    Args:
        url: URL to an Onshape document element

    Returns:
        did: The unique identifier of the document
        wtype: The type of workspace (w, v, m)
        wid: The unique identifier of the workspace
        eid: The unique identifier of the element

    Raises:
        ValueError: If the URL does not match the expected pattern

    Examples:
        >>> parse_url("https://cad.onshape.com/documents/a1c1addf75444f54b504f25c/w/0d17b8ebb2a4c76be9fff3c7/e/a86aaf34d2f4353288df8812")
        ("a1c1addf75444f54b504f25c", "w", "0d17b8ebb2a4c76be9fff3c7", "a86aaf34d2f4353288df8812")
    """
    pattern = re.match(
        DOCUMENT_PATTERN,
        url,
    )

    if not pattern:
        raise ValueError("Invalid Onshape URL")

    did = pattern.group(1)
    wtype = cast(WORKSPACE_TYPE, pattern.group(2))
    wid = pattern.group(3)
    eid = pattern.group(4)

    return did, wtype, wid, eid


class Document(BaseModel):
    """
    Represents an Onshape document, containing the document ID, workspace type, workspace ID, and element ID.

    Attributes:
        url: URL to the document element
        did: The unique identifier of the document
        wtype: The type of workspace (w, v, m)
        wid: The unique identifier of the workspace
        eid: The unique identifier of the element

    Methods:
        from_url: Create a Document instance from an Onshape URL
    """

    url: Union[str, None] = Field(None, description="URL to the document element")
    did: str = Field(..., description="The unique identifier of the document")
    wtype: str = Field(..., description="The type of workspace (w, v, m)")
    wid: str = Field(..., description="The unique identifier of the workspace")
    eid: str = Field(..., description="The unique identifier of the element")

    def __init__(self, **data):
        super().__init__(**data)
        if self.url is None:
            self.url = generate_url(self.did, self.wtype, self.wid, self.eid)

    @field_validator("did", "wid", "eid")
    def check_ids(cls, value: str) -> str:
        """
        Validate the document, workspace, and element IDs

        Args:
            value: The ID to validate

        Returns:
            value: The validated ID

        Raises:
            ValueError: If the ID is empty or not 24 characters long
        """
        if not value:
            raise ValueError("ID cannot be empty, please check the URL")
        if not len(value) == 24:
            raise ValueError("ID must be 24 characters long, please check the URL")
        return value

    @field_validator("wtype")
    def check_wtype(cls, value: str) -> str:
        """
        Validate the workspace type

        Args:
            value: The workspace type to validate

        Returns:
            value: The validated workspace type

        Raises:
            ValueError: If the workspace type is empty or not one of the valid values
        """
        if not value:
            raise ValueError("Workspace type cannot be empty, please check the URL")

        if value not in WORKSPACE_TYPE.__members__.values():
            raise ValueError(
                f"Invalid workspace type. Must be one of {WORKSPACE_TYPE.__members__.values()}, please check the URL"
            )

        return value

    @classmethod
    def from_url(cls, url: str) -> "Document":
        """
        Create a Document instance from an Onshape URL

        Args:
            url: URL to the document element

        Returns:
            Document: The Document instance created from the URL

        Raises:
            ValueError: If the URL does not match the expected pattern

        Examples:
            >>> Document.from_url(
            ...     "https://cad.onshape.com/documents/a1c1addf75444f54b504f25c/w/0d17b8ebb2a4c76be9fff3c7/e/a86aaf34d2f4353288df8812"
            ... )
            Document(
                url="https://cad.onshape.com/documents/a1c1addf75444f54b504f25c/w/0d17b8ebb2a4c76be9fff3c7/e/a86aaf34d2f4353288df8812",
                did="a1c1addf75444f54b504f25c",
                wtype="w",
                wid="0d17b8ebb2a4c76be9fff3c7",
                eid="a86aaf34d2f4353288df8812"
            )
        """
        did, wtype, wid, eid = parse_url(url)
        return cls(url=url, did=did, wtype=wtype, wid=wid, eid=eid)


class DefaultWorkspace(BaseModel):
    """
    Represents the default workspace of an Onshape document, containing the workspace ID and type.

    Attributes:
        id: The unique identifier of the workspace
        type: The type of workspace (workspace, version, microversion)
    """

    id: str = Field(..., description="The unique identifier of the workspace")
    type: META_WORKSPACE_TYPE = Field(..., description="The type of workspace (workspace, version, microversion)")


class DocumentMetaData(BaseModel):
    """
    Represents metadata of an Onshape document, containing the default workspace information and name.

    Attributes:
        defaultWorkspace: Default workspace information
        name: The name of the document
        id: The unique identifier of the document
    """

    defaultWorkspace: DefaultWorkspace = Field(..., description="Default workspace information")
    name: str = Field(..., description="The name of the document")
    id: str = Field(..., description="The unique identifier of the document")
