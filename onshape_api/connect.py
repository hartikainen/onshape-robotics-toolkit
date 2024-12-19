"""
This module provides a client class and other utilities to interact with the Onshape API.

Class:
    - **Client**: Provides access to the Onshape REST API.
    - **Part**: Represents a part within an assembly, including its properties and configuration.
    - **PartInstance**: Represents an instance of a part within an assembly.

Enum:
    - **HTTP**: Enumerates the possible HTTP methods (GET, POST, DELETE).

"""

import asyncio
import base64
import datetime
import hashlib
import hmac
import io
import os
import secrets
import string
import time
from enum import Enum
from typing import Any, BinaryIO, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import lxml.etree as ET
import numpy as np
import requests
import stl
from dotenv import load_dotenv

from onshape_api.log import LOGGER
from onshape_api.mesh import transform_mesh
from onshape_api.models.assembly import Assembly, RootAssembly
from onshape_api.models.document import BASE_URL, Document, DocumentMetaData, generate_url
from onshape_api.models.element import Element
from onshape_api.models.mass import MassProperties
from onshape_api.models.variable import Variable
from onshape_api.utilities.helpers import get_sanitized_name

CURRENT_DIR = os.getcwd()
MESHES_DIR = "meshes"

__all__ = ["HTTP", "Client"]

# TODO: Add asyncio support for async requests


class HTTP(str, Enum):
    """
    Enumerates the possible HTTP methods.

    Attributes:
        GET (str): HTTP GET method
        POST (str): HTTP POST method
        DELETE (str): HTTP DELETE method

    Examples:
        >>> HTTP.GET
        'get'
        >>> HTTP.POST
        'post'
    """

    GET = "get"
    POST = "post"
    DELETE = "delete"


def load_env_variables(env: str) -> tuple[str, str]:
    """
    Load access and secret keys required for Onshape API requests from a .env file.

    Args:
        env: Path to the environment file containing the access and secret keys

    Returns:
        tuple[str, str]: Access and secret keys

    Raises:
        FileNotFoundError: If the environment file is not found
        ValueError: If the required environment variables are missing

    Examples:
        >>> load_env_variables(".env")
        ('asdagflkdfjsdlfkdfjlsdf', 'asdkkjdnknsdgkjsdguoiuosdg')
    """

    if not os.path.isfile(env):
        raise FileNotFoundError(f"{env} file not found")

    load_dotenv(env)

    access_key = os.getenv("ACCESS_KEY")
    secret_key = os.getenv("SECRET_KEY")

    if not access_key or not secret_key:
        missing_vars = [var for var in ["ACCESS_KEY", "SECRET_KEY"] if not os.getenv(var)]
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    return access_key, secret_key


def make_nonce() -> str:
    """
    Generate a unique ID for the request, 25 chars in length

    Returns:
        Cryptographic nonce string for the API request

    Examples:
        >>> make_nonce()
        'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p'
    """

    chars = string.digits + string.ascii_letters
    nonce = "".join(secrets.choice(chars) for i in range(25))
    LOGGER.debug(f"nonce created: {nonce}")

    return nonce


class Client:
    """
    Represents a client for the Onshape REST API with methods to interact with the API.

    Args:
        env (str, default='./.env'): Path to the environment file containing the access and secret keys
        base_url (str, default='https://cad.onshape.com'): Base URL for the Onshape API

    Methods:
        get_document_metadata: Get details for a specified document.
        get_elements: Get list of elements in a document.
        get_variables: Get list of variables in a variable studio.
        set_variables: Set variables in a variable studio.
        get_assembly: Get assembly data for a specified document / workspace / assembly.
        download_part_stl: Download an STL file from a part studio.
        get_mass_property: Get mass properties for a part in a part studio.
        request: Issue a request to the Onshape API.

    Examples:
        >>> client = Client(
        ...     env=".env",
        ... )
        >>> document_meta_data = client.get_document_metadata("document_id")
    """

    def __init__(self, env: str = "./.env", base_url: str = BASE_URL):
        """
        Initialize the Onshape API client.

        Args:
            env: Path to the environment file containing the access and secret keys
            base_url: Base URL for the Onshape API

        Examples:
            >>> client = Client(
            ...     env=".env",
            ... )
        """

        self._url = base_url
        self._access_key, self._secret_key = load_env_variables(env)
        LOGGER.info(f"Onshape API initialized with env file: {env}")

    def set_base_url(self, base_url: str):
        """
        Set the base URL for the Onshape API.

        Args:
            base_url: Base URL for the Onshape API

        Examples:
            >>> client.set_base_url("https://cad.onshape.com")
        """
        self._url = base_url

    def get_document_metadata(self, did: str) -> DocumentMetaData:
        """
        Get meta data for a specified document.

        Args:
            did: The unique identifier of the document.

        Returns:
            Meta data for the specified document as a DocumentMetaData object or None if the document is not found

        Examples:
            >>> document_meta_data = client.get_document_metadata("document_id
            >>> print(document_meta_data)
            DocumentMetaData(
                defaultWorkspace=DefaultWorkspace(id="739221fb10c88c2bebb456e8", type="workspace"),
                name="Document Name",
                id="a1c1addf75444f54b504f25c"
            )
        """
        if len(did) != 24:
            raise ValueError(f"Invalid document ID: {did}")

        res = self.request(HTTP.GET, "/api/documents/" + did)

        if res.status_code == 404:
            """
            404: Document not found
                {
                    "message": "Not found.",
                    "code": 0,
                    "status": 404,
                    "moreInfoUrl": ""
                }
            """
            raise ValueError(f"Document does not exist: {did}")
        elif res.status_code == 403:
            """
            403: Forbidden
                {
                    "message": "Forbidden",
                    "code": 0,
                    "status": 403,
                    "moreInfoUrl": ""
                }
            """
            raise ValueError(f"Access forbidden for document: {did}")

        document = DocumentMetaData.model_validate(res.json())
        document.name = get_sanitized_name(document.name)

        return document

    def get_elements(self, did: str, wtype: str, wid: str) -> dict[str, Element]:
        """
        Get a list of all elements in a document.

        Args:
            did: The unique identifier of the document.
            wtype: The type of workspace.
            wid: The unique identifier of the workspace.

        Returns:
            A dictionary of element name and Element object pairs.

        Examples:
            >>> elements = client.get_elements(
            ...     did="a1c1addf75444f54b504f25c",
            ...     wtype="w",
            ...     wid="0d17b8ebb2a4c76be9fff3c7"
            ... )
            >>> print(elements)
            {
                "wheelAndFork": Element(id='0b0c209535554345432581fe', name='wheelAndFork', elementType='PARTSTUDIO',
                                         microversionId='9b3be6165c7a2b1f6dd61305'),
                "frame": Element(id='0b0c209535554345432581fe', name='frame', elementType='PARTSTUDIO',
                                 microversionId='9b3be6165c7a2b1f6dd61305')
            }
        """

        # /documents/d/{did}/{wvm}/{wvmid}/elements
        request_path = "/api/documents/d/" + did + "/" + wtype + "/" + wid + "/elements"
        _elements_json = self.request(
            HTTP.GET,
            request_path,
        ).json()

        return {element["name"]: Element.model_validate(element) for element in _elements_json}

    def get_variables(self, did: str, wid: str, eid: str) -> dict[str, Variable]:
        """
        Get a list of variables in a variable studio within a document.

        Args:
            did: The unique identifier of the document.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the variable studio.

        Returns:
            A dictionary of variable name and Variable object pairs.

        Examples:
            >>> variables = client.get_variables(
            ...     did="a1c1addf75444f54b504f25c",
            ...     wid="0d17b8ebb2a4c76be9fff3c7",
            ...     eid="cba5e3ca026547f34f8d9f0f"
            ... )
            >>> print(variables)
            {
                "forkAngle": Variable(
                    type='ANGLE',
                    name='forkAngle',
                    value=None,
                    description='Fork angle for front wheel assembly in deg',
                    expression='15 deg'
                )
            }
        """
        request_path = "/api/variables/d/" + did + "/w/" + wid + "/e/" + eid + "/variables"

        _variables_json = self.request(
            HTTP.GET,
            request_path,
        ).json()

        return {variable["name"]: Variable.model_validate(variable) for variable in _variables_json[0]["variables"]}

    def set_variables(self, did: str, wid: str, eid: str, variables: dict[str, str]) -> requests.Response:
        """
        Set values for variables of a variable studio in a document.

        Args:
            did: The unique identifier of the document.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the variable studio.
            variables: A dictionary of variable name and expression pairs.

        Returns:
            requests.Response: Response from Onshape API after setting the variables.

        Examples:
            >>> variables = {
            ...     "forkAngle": "15 deg",
            ...     "wheelRadius": "0.5 m"
            ... }
            >>> client.set_variables(
            ...     did="a1c1addf75444f54b504f25c",
            ...     wid="0d17b8ebb2a4c76be9fff3c7",
            ...     eid="cba5e3ca026547f34f8d9f0f",
            ...     variables=variables
            ... )
            <Response [200]>
        """

        payload = [variable.model_dump() for variable in variables.values()]

        # api/v9/variables/d/a1c1addf75444f54b504f25c/w/0d17b8ebb2a4c76be9fff3c7/e/cba5e3ca026547f34f8d9f0f/variables
        request_path = "/api/variables/d/" + did + "/w/" + wid + "/e/" + eid + "/variables"

        return self.request(
            HTTP.POST,
            request_path,
            body=payload,
        )

    def get_assembly_name(
        self,
        did: str,
        wtype: str,
        wid: str,
        eid: str,
        configuration: str = "default",
    ) -> str:
        """
        Get assembly name for a specified document / workspace / assembly.

        Args:
            did: The unique identifier of the document.
            wtype: The type of workspace.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the assembly.

        Returns:
            str: Assembly name

        Examples:
            >>> assembly_name = client.get_assembly_name(
            ...     did="a1c1addf75444f54b504f25c",
            ...     wtype="w",
            ...     wid="0d17b8ebb2a4c76be9fff3c7",
            ...     eid="a86aaf34d2f4353288df8812"
            ... )
            >>> print(assembly_name)
            "Assembly Name"
        """
        request_path = "/api/metadata/d/" + did + "/" + wtype + "/" + wid + "/e/" + eid
        result_json = self.request(
            HTTP.GET,
            request_path,
            query={
                "inferMetadataOwner": "false",
                "includeComputedProperties": "false",
                "includeComputedAssemblyProperties": "false",
                "thumbnail": "false",
                "configuration": configuration,
            },
            log_response=False,
        ).json()

        name = None
        try:
            name = result_json["properties"][0]["value"]
            name = get_sanitized_name(name)

        except KeyError:
            LOGGER.warning(f"Assembly name not found for document: {did}")

        return name

    def get_root_assembly(
        self,
        did: str,
        wtype: str,
        wid: str,
        eid: str,
        configuration: str = "default",
        with_mass_properties: bool = False,
        log_response: bool = True,
        with_meta_data: bool = True,
    ) -> RootAssembly:
        """
        Get root assembly data for a specified document / workspace / element.

        Args:
            did: The unique identifier of the document.
            wtype: The type of workspace.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the element.
            configuration: The configuration of the assembly.
            log_response: Log the response from the API request.

        Returns:
            RootAssembly: RootAssembly object containing the root assembly data

        Examples:
            >>> root_assembly = client.get_root_assembly(
            ...     did="a1c1addf75444f54b504f25c",
            ...     wtype="w",
            ...     wid="0d17b8ebb2a4c76be9fff3c7",
            ...     eid="a86aaf34d2f4353288df8812"
            ... )
            >>> print(root_assembly)
            RootAssembly(
                instances=[...],
                patterns=[...],
                features=[...],
                occurrences=[...],
                fullConfiguration="default",
                configuration="default",
                documentId="a1c1addf75444f54b504f25c",
                elementId="0b0c209535554345432581fe",
                documentMicroversion="349f6413cafefe8fb4ab3b07",
            )
        """
        request_path = "/api/assemblies/d/" + did + "/" + wtype + "/" + wid + "/e/" + eid
        res = self.request(
            HTTP.GET,
            request_path,
            query={
                "includeMateFeatures": "true",
                "includeMateConnectors": "true",
                "includeNonSolids": "false",
                "configuration": configuration,
            },
            log_response=log_response,
        )

        if res.status_code == 401:
            LOGGER.warning(f"Unauthorized access to document: {did}")
            LOGGER.warning("Please check the API keys in your env file.")
            exit(1)

        if res.status_code == 404:
            LOGGER.error(f"Assembly not found: {did}")
            LOGGER.error(
                generate_url(
                    base_url=self._url,
                    did=did,
                    wtype=wtype,
                    wid=wid,
                    eid=eid,
                )
            )
            exit(1)

        assembly_json = res.json()
        assembly = RootAssembly.model_validate(assembly_json["rootAssembly"])

        if with_mass_properties:
            assembly.MassProperty = self.get_assembly_mass_properties(
                did=did,
                wid=wid,
                eid=eid,
                wtype=wtype,
            )

        if with_meta_data:
            assembly.documentMetaData = self.get_document_metadata(did)

        return assembly

    def get_assembly(
        self,
        did: str,
        wtype: str,
        wid: str,
        eid: str,
        configuration: str = "default",
        log_response: bool = True,
        with_meta_data: bool = True,
    ) -> Assembly:
        """
        Get assembly data for a specified document / workspace / assembly.

        Args:
            did: The unique identifier of the document.
            wtype: The type of workspace.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the assembly.
            configuration: The configuration of the assembly.
            log_response: Log the response from the API request.
            with_meta_data: Include meta data in the assembly data.

        Returns:
            Assembly: Assembly object containing the assembly data

        Examples:
            >>> assembly = client.get_assembly(
            ...     did="a1c1addf75444f54b504f25c",
            ...     wtype="w",
            ...     wid="0d17b8ebb2a4c76be9fff3c7",
            ...     eid="a86aaf34d2f4353288df8812"
            ... )
            >>> print(assembly)
            Assembly(
                rootAssembly=RootAssembly(
                    instances=[...],
                    patterns=[...],
                    features=[...],
                    occurrences=[...],
                    fullConfiguration="default",
                    configuration="default",
                    documentId="a1c1addf75444f54b504f25c",
                    elementId="0b0c209535554345432581fe",
                    documentMicroversion="349f6413cafefe8fb4ab3b07",
                ),
                subAssemblies=[...],
                parts=[...],
                partStudioFeatures=[...],
                document=Document(
                    url="https://cad.onshape.com/documents/a1c1addf75444f54b504f25c/w/0d17b8ebb2a4c76be9fff3c7/e/a86aaf34d2f4353288df8812",
                    did="a1c1addf75444f54b504f25c",
                    wtype="w",
                    wid="0d17b8ebb2a4c76be9fff3c7",
                    eid="a86aaf34d2f4353288df8812"
                )
            )
        """
        request_path = "/api/assemblies/d/" + did + "/" + wtype + "/" + wid + "/e/" + eid
        res = self.request(
            HTTP.GET,
            request_path,
            query={
                "includeMateFeatures": "true",
                "includeMateConnectors": "true",
                "includeNonSolids": "false",
                "configuration": configuration,
            },
            log_response=log_response,
        )

        if res.status_code == 401 or res.status_code == 403:
            LOGGER.warning(f"Unauthorized access to document: {did}")
            LOGGER.warning("Please check the API keys in your env file.")
            exit(1)

        if res.status_code == 404:
            LOGGER.error(f"Assembly not found: {did}")
            LOGGER.error(
                generate_url(
                    base_url=self._url,
                    did=did,
                    wtype=wtype,
                    wid=wid,
                    eid=eid,
                )
            )
            exit(1)

        assembly = Assembly.model_validate(res.json())
        document = Document(did=did, wtype=wtype, wid=wid, eid=eid)
        assembly.document = document

        if with_meta_data:
            assembly.name = self.get_assembly_name(did, wtype, wid, eid, configuration)
            document_meta_data = self.get_document_metadata(did)
            assembly.document.name = document_meta_data.name

        return assembly

    def download_assembly_stl(
        self,
        did: str,
        wtype: str,
        wid: str,
        eid: str,
        buffer: BinaryIO,
        configuration: str = "default",
    ):
        """
        Download an STL file from an assembly. The file is written to the buffer.

        Args:
            did: The unique identifier of the document.
            wtype: The type of workspace.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the element.
            configuration: The configuration of the assembly.

        """
        req_headers = {"Accept": "application/vnd.onshape.v1+octet-stream"}
        request_path = f"/api/assemblies/d/{did}/{wtype}/{wid}/e/{eid}/translations"

        # Initiate the translation
        payload = {
            "formatName": "STL",
            "storeInDocument": "false",
        }
        response = self.request(
            HTTP.POST,
            path=request_path,
            body=payload,
            log_response=False,
        )

        if response.status_code == 200:
            job_info = response.json()
            translation_id = job_info.get("id")
            if not translation_id:
                LOGGER.error("Translation job ID not found in response.")
                return None

            status_path = f"/api/translations/{translation_id}"
            while True:
                status_response = self.request(HTTP.GET, path=status_path)
                if status_response.status_code != 200:
                    LOGGER.error(f"Failed to get translation status: {status_response.text}")
                    return None

                status_info = status_response.json()
                request_state = status_info.get("requestState")
                LOGGER.info(f"Current status: {request_state}")
                if request_state == "DONE":
                    LOGGER.info("Translation job completed.")
                    break
                elif request_state == "FAILED":
                    LOGGER.error("Translation job failed.")
                    return None
                time.sleep(1)

            fid = status_info.get("resultExternalDataIds")[0]
            data_path = f"/api/documents/d/{did}/externaldata/{fid}"

            download_response = self.request(
                HTTP.GET,
                path=data_path,
                headers=req_headers,
                log_response=False,
            )
            if download_response.status_code == 200:
                buffer.write(download_response.content)
                LOGGER.info("STL file downloaded successfully.")
                return buffer
            else:
                LOGGER.error(f"Failed to download STL file: {download_response.text}")
                return None

        else:
            LOGGER.info(f"Failed to download assembly: {response.status_code} - {response.text}")
            LOGGER.info(
                generate_url(
                    base_url=self._url,
                    did=did,
                    wtype=wtype,
                    wid=wid,
                    eid=eid,
                )
            )

        return buffer

    def download_part_stl(
        self,
        did: str,
        wtype: str,
        wid: str,
        eid: str,
        partID: str,
        buffer: BinaryIO,
    ) -> BinaryIO:
        """
        Download an STL file from a part studio. The file is written to the buffer.

        Args:
            did: The unique identifier of the document.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the element.
            partID: The unique identifier of the part.
            buffer: BinaryIO object to write the STL file to.
            wtype: The type of workspace.

        Returns:
            BinaryIO: BinaryIO object containing the STL file

        Examples:
            >>> with io.BytesIO() as buffer:
            ...     client.download_part_stl(
            ...         "a1c1addf75444f54b504f25c",
            ...         "0d17b8ebb2a4c76be9fff3c7",
            ...         "a86aaf34d2f4353288df8812",
            ...         "0b0c209535554345432581fe",
            ...         buffer,
            ...         "w",
            ...         "0d17b8ebb2a4c76be9fff3c7"
            ...     )
            >>> buffer.seek(0)
            >>> raw_mesh = stl.mesh.Mesh.from_file(None, fh=buffer)
            >>> raw_mesh.save("mesh.stl")
        """
        # TODO: version id seems to always work, should this default behavior be changed?
        req_headers = {"Accept": "application/vnd.onshape.v1+octet-stream"}
        request_path = f"/api/parts/d/{did}/{wtype}/{wid}/e/{eid}/partid/{partID}/stl"
        _query = {
            "mode": "binary",
            "grouping": True,
            "units": "meter",
        }
        response = self.request(
            HTTP.GET,
            path=request_path,
            headers=req_headers,
            query=_query,
            log_response=False,
        )
        if response.status_code == 200:
            buffer.write(response.content)
        else:
            url = generate_url(
                base_url=self._url,
                did=did,
                wtype=wtype,
                wid=wid,
                eid=eid,
            )
            LOGGER.info(f"{url}")
            LOGGER.info(f"Failed to download STL file: {response.status_code} - {response.text}")

        return buffer

    def get_assembly_mass_properties(
        self,
        did: str,
        wtype: str,
        wid: str,
        eid: str,
    ) -> MassProperties:
        """
        Get mass properties of a rigid assembly in a document.

        Args:
            did: The unique identifier of the document.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the rigid assembly.
            wtype: The type of workspace.

        Returns:
            MassProperties object containing the mass properties of the assembly.

        Examples:
            >>> mass_properties = client.get_assembly_mass_properties(
            ...     did="a1c1addf75444f54b504f25c",
            ...     wid="0d17b8ebb2a4c76be9fff3c7",
            ...     eid="a86aaf34d2f4353288df8812",
            ...     wtype="w"
            ... )
            >>> print(mass_properties)
            MassProperties(
                volume=[0.003411385108378978, 0.003410724395374695, 0.0034120458213832646],
                mass=[9.585992154544929, 9.584199206938452, 9.587785102151415],
                centroid=[...],
                inertia=[...],
                principalInertia=[0.09944605933465941, 0.09944605954654827, 0.19238058837442526],
                principalAxes=[...]
            )
        """
        request_path = f"/api/assemblies/d/{did}/{wtype}/{wid}/e/{eid}/massproperties"
        res = self.request(HTTP.GET, request_path, log_response=False)

        if res.status_code == 404:
            url = generate_url(
                base_url=self._url,
                did=did,
                wtype="w",
                wid=wid,
                eid=eid,
            )
            raise ValueError(f"Assembly: {url} does not have a mass property")

        return MassProperties.model_validate(res.json())

    def get_mass_property(
        self,
        did: str,
        wtype: str,
        wid: str,
        eid: str,
        partID: str,
    ) -> MassProperties:
        """
        Get mass properties of a part in a part studio.

        Args:
            did: The unique identifier of the document.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the element.
            partID: The identifier of the part.
            wtype: The type of workspace.

        Returns:
            MassProperties object containing the mass properties of the part.

        Examples:
            >>> mass_properties = client.get_mass_property(
            ...     did="a1c1addf75444f54b504f25c",
            ...     wid="0d17b8ebb2a4c76be9fff3c7",
            ...     eid="a86aaf34d2f4353288df8812",
            ...     partID="0b0c209535554345432581fe"
            ...     wtype="w"
            ... )
            >>> print(mass_properties)
            MassProperties(
                volume=[0.003411385108378978, 0.003410724395374695, 0.0034120458213832646],
                mass=[9.585992154544929, 9.584199206938452, 9.587785102151415],
                centroid=[...],
                inertia=[...],
                principalInertia=[0.09944605933465941, 0.09944605954654827, 0.19238058837442526],
                principalAxes=[...]
            )
        """
        # TODO: version id seems to always work, should this default behavior be changed?
        request_path = f"/api/parts/d/{did}/{wtype}/{wid}/e/{eid}/partid/{partID}/massproperties"
        res = self.request(HTTP.GET, request_path, {"useMassPropertiesOverrides": True}, log_response=False)

        if res.status_code == 404:
            # TODO: There doesn't seem to be a way to assign material to a part currently
            # It is possible that the workspace got deleted
            url = generate_url(
                base_url=self._url,
                did=did,
                wtype=wtype,
                wid=wid,
                eid=eid,
            )
            raise ValueError(f"Part: {url} does not have a material assigned or the part is not found")

        elif res.status_code == 429:
            raise ValueError(f"Too many requests, please retry after {res.headers['Retry-After']} seconds")

        resonse_json = res.json()

        if "bodies" not in resonse_json:
            raise KeyError(f"Bodies not found in response, broken part? {partID}")

        return MassProperties.model_validate(resonse_json["bodies"][partID])

    def request(
        self,
        method: HTTP,
        path: str,
        query: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        base_url: Optional[str] = None,
        log_response: bool = True,
        timeout: int = 50,
    ) -> requests.Response:
        """
        Send a request to the Onshape API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            path: URL path for the request
            query: Query string in key-value pairs
            headers: Additional headers for the request
            body: Body of the request
            base_url: Base URL for the request
            log_response: Log the response from the API request

        Returns:
            requests.Response: Response from the Onshape API request
        """
        if query is None:
            query = {}
        if headers is None:
            headers = {}
        if base_url is None:
            base_url = self._url

        req_headers = self._make_headers(method, path, query, headers)
        url = self._build_url(base_url, path, query)

        LOGGER.debug(f"Request body: {body}")
        LOGGER.debug(f"Request headers: {req_headers}")
        LOGGER.debug(f"Request URL: {url}")

        res = self._send_request(method, url, req_headers, body, timeout)

        if res.status_code == 307:
            return self._handle_redirect(res, method, headers, log_response)
        else:
            if log_response:
                self._log_response(res)

        return res

    def _build_url(self, base_url, path, query):
        return base_url + path + "?" + urlencode(query)

    def _send_request(self, method, url, headers, body, timeout):
        return requests.request(
            method,
            url,
            headers=headers,
            json=body,
            allow_redirects=False,
            stream=True,
            timeout=timeout,  # Specify an appropriate timeout value in seconds
        )

    def _handle_redirect(self, res, method, headers, log_response=True):
        location = urlparse(res.headers["Location"])
        querystring = parse_qs(location.query)

        LOGGER.debug(f"Request redirected to: {location.geturl()}")

        new_query = {key: querystring[key][0] for key in querystring}
        new_base_url = location.scheme + "://" + location.netloc

        return self.request(
            method, location.path, query=new_query, headers=headers, base_url=new_base_url, log_response=log_response
        )

    def _log_response(self, res):
        try:
            if not 200 <= res.status_code <= 206:
                LOGGER.debug(f"Request failed, details: {res.text}")
            else:
                LOGGER.debug(f"Request succeeded, details: {res.text}")
        except UnicodeEncodeError as e:
            LOGGER.error(f"UnicodeEncodeError: {e}")

    def _make_auth(self, method, date, nonce, path, query=None, ctype="application/json"):
        if query is None:
            query = {}
        query = urlencode(query)

        hmac_str = (
            str(method + "\n" + nonce + "\n" + date + "\n" + ctype + "\n" + path + "\n" + query + "\n")
            .lower()
            .encode("utf-8")
        )

        signature = base64.b64encode(
            hmac.new(self._secret_key.encode("utf-8"), hmac_str, digestmod=hashlib.sha256).digest()
        )
        auth = "On " + self._access_key + ":HmacSHA256:" + signature.decode("utf-8")

        LOGGER.debug(f"query: {query}, hmac_str: {hmac_str}, signature: {signature}, auth: {auth}")

        return auth

    def _make_headers(self, method, path, query=None, headers=None):
        if headers is None:
            headers = {}
        if query is None:
            query = {}
        date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        nonce = make_nonce()
        ctype = headers.get("Content-Type") if headers.get("Content-Type") else "application/json"

        auth = self._make_auth(method, date, nonce, path, query=query, ctype=ctype)

        req_headers = {
            "Content-Type": "application/json",
            "Date": date,
            "On-Nonce": nonce,
            "Authorization": auth,
            "User-Agent": "Onshape Python Sample App",
            "Accept": "application/json",
        }

        # add in user-defined headers
        for h in headers:
            req_headers[h] = headers[h]

        return req_headers

    @property
    def base_url(self):
        return self._url


class Asset:
    """
    Represents a set of parameters required to download a link from Onshape.
    """

    def __init__(
        self,
        did: str,
        wtype: str,
        wid: str,
        eid: str,
        client: Client,
        transform: np.ndarray,
        file_name: str,
        is_rigid_assembly: bool = False,
        partID: Optional[str] = None,
    ) -> None:
        """
        Initialize the Asset object.

        Args:
            did: The unique identifier of the document.
            wtype: The type of workspace.
            wid: The unique identifier of the workspace.
            eid: The unique identifier of the element.
            client: Onshape API client object.
            transform: Transformation matrix to apply to the mesh.
            file_name: Name of the mesh file.
            is_rigid_assembly: Whether the element is a rigid assembly.
            partID: The unique identifier of the part.
        """
        self.did = did
        self.wtype = wtype
        self.wid = wid
        self.eid = eid
        self.client = client
        self.transform = transform
        self.file_name = file_name
        self.is_rigid_assembly = is_rigid_assembly
        self.partID = partID

    @property
    def absolute_path(self) -> str:
        """
        Returns the file path of the mesh file.
        """
        # if meshes directory does not exist, create it
        if not os.path.exists(os.path.join(CURRENT_DIR, MESHES_DIR)):
            os.makedirs(os.path.join(CURRENT_DIR, MESHES_DIR))

        return os.path.join(CURRENT_DIR, MESHES_DIR, self.file_name)

    @property
    def relative_path(self) -> str:
        """
        Returns the relative path of the mesh file.
        """
        return os.path.relpath(self.absolute_path, CURRENT_DIR)

    async def download(self) -> None:
        """
        Asynchronously download the mesh file from Onshape, transform it, and save it to a file.
        """
        LOGGER.info(f"Starting download for {self.file_name}")
        try:
            with io.BytesIO() as buffer:
                if not self.is_rigid_assembly:
                    await asyncio.to_thread(
                        self.client.download_part_stl,
                        did=self.did,
                        wtype=self.wtype,
                        wid=self.wid,
                        eid=self.eid,
                        partID=self.partID,
                        buffer=buffer,
                    )
                else:
                    await asyncio.to_thread(
                        self.client.download_assembly_stl,
                        did=self.did,
                        wtype=self.wtype,
                        wid=self.wid,
                        eid=self.eid,
                        buffer=buffer,
                    )

                buffer.seek(0)

                raw_mesh = stl.mesh.Mesh.from_file(None, fh=buffer)
                transformed_mesh = transform_mesh(raw_mesh, self.transform)
                transformed_mesh.save(self.absolute_path)

                LOGGER.info(f"Mesh file saved: {self.absolute_path}")
        except Exception as e:
            LOGGER.error(f"Failed to download {self.file_name}: {e}")

    def to_xml(self, root: Optional[ET.Element] = None) -> str:
        """
        Returns the XML representation of the asset, which is a mesh file.

        Examples:
            >>> asset = Asset(
            ...     did="a1c1addf75444f54b504f25c",
            ...     wtype="w",
            ...     wid="0d17b8ebb2a4c76be9fff3c7",
            ...     eid="a86aaf34d2f4353288df8812",
            ...     client=client,
            ...     transform=np.eye(4),
            ...     file_name="mesh.stl",
            ...     is_rigid_assembly=True
            ... )
            >>> asset.to_xml()
            <mesh name="Part-1-1" file="Part-1-1.stl" />
        """
        asset = ET.Element("mesh") if root is None else ET.SubElement(root, "mesh")
        asset.set("mesh", self.file_name)
        asset.set("file", self.relative_path)
        return asset
