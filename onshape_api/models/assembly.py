"""
This module defines data models for Assembly entities retrieved from Onshape REST API responses.

The data models are implemented as Pydantic BaseModel classes, which are used to

    1. Parse JSON responses from the API into Python objects.
    2. Validate the structure and types of the JSON responses.
    3. Provide type hints for better code clarity and autocompletion.

These models ensure that the data received from the API adheres to the expected format and types, facilitating easier
and safer manipulation of the data within the application.

Models:
    - **Occurrence**: Represents an occurrence of a part or sub-assembly within an assembly.
    - **Part**: Represents a part within an assembly, including its properties and configuration.
    - **PartInstance**: Represents an instance of a part within an assembly.
    - **AssemblyInstance**: Represents an instance of an assembly within another assembly.
    - **AssemblyFeature**: Represents a feature within an assembly, such as a mate or pattern.
    - **Pattern**: Represents a pattern feature within an assembly, defining repeated instances of
      parts or sub-assemblies.
    - **SubAssembly**: Represents a sub-assembly within a larger assembly.
    - **RootAssembly**: Represents the root assembly, which is the top-level assembly containing all parts
      and sub-assemblies.
    - **Assembly**: Represents the overall assembly, including all parts, sub-assemblies, and features.

Supplementary models:
    - **IDBase**: Base model providing common attributes for Part, SubAssembly, and AssemblyInstance models.
    - **MatedCS**: Represents a coordinate system used for mating parts within an assembly.
    - **MatedEntity**: Represents an entity that is mated within an assembly, including its coordinate system.
    - **MateRelationMate**: Represents a mate relation within an assembly, defining how parts or sub-assemblies
      are connected.
    - **MateGroupFeatureOccurrence**: Represents an occurrence of a mate group feature within an assembly.
    - **MateGroupFeatureData**: Represents data for a mate group feature within an assembly.
    - **MateConnectorFeatureData**: Represents data for a mate connector feature within an assembly.
    - **MateRelationFeatureData**: Represents data for a mate relation feature within an assembly.
    - **MateFeatureData**: Represents data for a mate feature within an assembly.

Enums:
    - **INSTANCE_TYPE**: Enumerates the types of instances in an assembly, e.g. PART, ASSEMBLY.
    - **MATE_TYPE**: Enumerates the type of mate between two parts or assemblies, e.g. SLIDER,
      CYLINDRICAL, REVOLUTE, etc.
    - **RELATION_TYPE**: Enumerates the type of mate relation between two parts or assemblies, e.g. LINEAR,
      GEAR, SCREW, etc.
    - **ASSEMBLY_FEATURE_TYPE**: Enumerates the type of assembly feature, e.g. mate, mateRelation,
      mateGroup, mateConnector

"""

from enum import Enum
from typing import Union

import numpy as np
from pydantic import BaseModel, Field, field_validator

from onshape_api.models.document import Document
from onshape_api.models.mass import MassProperties
from onshape_api.utilities.helpers import generate_uid


class INSTANCE_TYPE(str, Enum):
    """
    Enumerates the types of instances in an assembly, e.g. PART, ASSEMBLY.

    Attributes:
        PART (str): Represents a part instance.
        ASSEMBLY (str): Represents an assembly instance.
    """

    PART = "Part"
    ASSEMBLY = "Assembly"


class MATE_TYPE(str, Enum):
    """
    Enumerates the type of mate between two parts or assemblies, e.g. SLIDER, CYLINDRICAL, REVOLUTE, etc.

    Attributes:
        SLIDER (str): Represents a slider mate.
        CYLINDRICAL (str): Represents a cylindrical mate.
        REVOLUTE (str): Represents a revolute mate.
        PIN_SLOT (str): Represents a pin-slot mate.
        PLANAR (str): Represents a planar mate.
        BALL (str): Represents a ball mate.
        FASTENED (str): Represents a fastened mate.
        PARALLEL (str): Represents a parallel mate.
    """

    SLIDER = "SLIDER"
    CYLINDRICAL = "CYLINDRICAL"
    REVOLUTE = "REVOLUTE"
    PIN_SLOT = "PIN_SLOT"
    PLANAR = "PLANAR"
    BALL = "BALL"
    FASTENED = "FASTENED"
    PARALLEL = "PARALLEL"


class RELATION_TYPE(str, Enum):
    """
    Enumerates the type of mate relation between two parts or assemblies, e.g. LINEAR, GEAR, SCREW, etc.

    Attributes:
        LINEAR (str): Represents a linear relation.
        GEAR (str): Represents a gear relation.
        SCREW (str): Represents a screw relation.
        RACK_AND_PINION (str): Represents a rack and pinion relation.
    """

    LINEAR = "LINEAR"
    GEAR = "GEAR"
    SCREW = "SCREW"
    RACK_AND_PINION = "RACK_AND_PINION"


class ASSEMBLY_FEATURE_TYPE(str, Enum):
    """
    Enumerates the type of assembly feature, e.g. mate, mateRelation, mateGroup, mateConnector

    Attributes:
        MATE (str): Represents a mate feature.
        MATERELATION (str): Represents a mate relation feature.
        MATEGROUP (str): Represents a mate group feature.
        MATECONNECTOR (str): Represents a mate connector feature.
    """

    MATE = "mate"
    MATERELATION = "mateRelation"
    MATEGROUP = "mateGroup"
    MATECONNECTOR = "mateConnector"


class Occurrence(BaseModel):
    """
    Represents an occurrence of a part or sub-assembly within an assembly.

    JSON:
        ```json
            {
                "fixed": false,
                "transform": [
                    0.8660254037844396, 0.0, 0.5000000000000004, 0.09583333333333346,
                    0.0, 1.0, 0.0, -1.53080849893419E-19,
                    -0.5000000000000004, 0.0, 0.8660254037844396, 0.16598820239201767,
                    0.0, 0.0, 0.0, 1.0
                ],
                "hidden": false,
                "path": ["M0Cyvy+yIq8Rd7En0"]
            }
        ```

    Attributes:
        fixed (bool): Indicates if the occurrence is fixed in space.
        transform (list[float]): A 4x4 transformation matrix represented as a list of 16 floats.
        hidden (bool): Indicates if the occurrence is hidden.
        path (list[str]): A list of strings representing the path to the instance.
    """

    fixed: bool = Field(..., description="Indicates if the occurrence is fixed in space.")
    transform: list[float] = Field(..., description="A 4x4 transformation matrix represented as a list of 16 floats.")
    hidden: bool = Field(..., description="Indicates if the occurrence is hidden.")
    path: list[str] = Field(..., description="A list of strings representing the path to the instance.")

    @field_validator("transform")
    def check_transform(cls, v: list[float]) -> list[float]:
        """
        Validates that the transform list has exactly 16 values.

        Args:
            v (list[float]): The transform list to validate.

        Returns:
            list[float]: The validated transform list.

        Raises:
            ValueError: If the transform list does not contain exactly 16 values.
        """
        if len(v) != 16:
            raise ValueError("Transform must have 16 values")

        return v


class IDBase(BaseModel):
    """
    Base model providing common attributes for Part, SubAssembly, and AssemblyInstance models.

    JSON:
        ```json
            {
                "fullConfiguration" : "default",
                "configuration" : "default",
                "documentId" : "a1c1addf75444f54b504f25c",
                "elementId" : "0b0c209535554345432581fe",
                "documentMicroversion" : "12fabf866bef5a9114d8c4d2"
            }
        ```

    Attributes:
        fullConfiguration (str): The full configuration of the entity.
        configuration (str): The configuration of the entity.
        documentId (str): The unique identifier of the entity.
        elementId (str): The unique identifier of the entity.
        documentMicroversion (str): The microversion of the document.
    """

    fullConfiguration: str = Field(..., description="The full configuration of the entity.")
    configuration: str = Field(..., description="The configuration of the entity.")
    documentId: str = Field(..., description="The unique identifier of the entity.")
    elementId: str = Field(..., description="The unique identifier of the entity.")
    documentMicroversion: str = Field(..., description="The microversion of the document.")

    @field_validator("documentId", "elementId", "documentMicroversion")
    def check_ids(cls, v: str) -> str:
        """
        Validates that the ID fields have exactly 24 characters.

        Args:
            v (str): The ID field to validate.

        Returns:
            str: The validated ID field.

        Raises:
            ValueError: If the ID field does not contain exactly 24 characters.
        """
        if len(v) != 24:
            raise ValueError("DocumentId must have 24 characters")

        return v

    @property
    def uid(self) -> str:
        """
        Generates a unique identifier for the part.

        Returns:
            str: The unique identifier generated from documentId, documentMicroversion,
                elementId, and fullConfiguration.
        """
        return generate_uid([self.documentId, self.documentMicroversion, self.elementId, self.fullConfiguration])


class Part(IDBase):
    """
    Represents a part within an assembly, including its properties and configuration.

    JSON:
        ```json
            {
                "isStandardContent": false,
                "partId": "RDBD",
                "bodyType": "solid",
                "fullConfiguration": "default",
                "configuration": "default",
                "documentId": "a1c1addf75444f54b504f25c",
                "elementId": "0b0c209535554345432581fe",
                "documentMicroversion": "349f6413cafefe8fb4ab3b07"
            }
        ```

    Attributes:
        isStandardContent (bool): Indicates if the part is standard content.
        partId (str): The unique identifier of the part.
        bodyType (str): The type of the body (e.g., solid, surface).
        MassProperty (Union[MassProperties, None]): The mass properties of the part, if available.
    """

    isStandardContent: bool = Field(..., description="Indicates if the part is standard content.")
    partId: str = Field(..., description="The unique identifier of the part.")
    bodyType: str = Field(..., description="The type of the body (e.g., solid, surface).")
    MassProperty: Union[MassProperties, None] = Field(
        None, description="The mass properties of the part, if available."
    )

    @property
    def uid(self) -> str:
        """
        Generates a unique identifier for the part.

        Returns:
            str: The unique identifier generated from documentId, documentMicroversion,
                elementId, partId, and fullConfiguration.
        """
        return generate_uid([
            self.documentId,
            self.documentMicroversion,
            self.elementId,
            self.partId,
            self.fullConfiguration,
        ])


class PartInstance(IDBase):
    """
    Represents an instance of a part within an assembly.

    JSON:
        ```json
            {
                "isStandardContent": false,
                "type": "Part",
                "id": "M0Cyvy+yIq8Rd7En0",
                "name": "Part 1 <2>",
                "suppressed": false,
                "partId": "JHD",
                "fullConfiguration": "default",
                "configuration": "default",
                "documentId": "a1c1addf75444f54b504f25c",
                "elementId": "a86aaf34d2f4353288df8812",
                "documentMicroversion": "12fabf866bef5a9114d8c4d2"
            }
        ```

    Attributes:
        isStandardContent (bool): Indicates if the part is standard content.
        type (INSTANCE_TYPE): The type of the instance, must be 'Part'.
        id (str): The unique identifier for the part instance.
        name (str): The name of the part instance.
        suppressed (bool): Indicates if the part instance is suppressed.
        partId (str): The identifier for the part.
        fullConfiguration (str): The full configuration of the part instance.
        configuration (str): The configuration of the part instance.
        documentId (str): The unique identifier of the document containing the part.
        elementId (str): The unique identifier of the element containing the part.
        documentMicroversion (str): The microversion of the document containing the part.
    """

    isStandardContent: bool = Field(..., description="Indicates if the part is standard content.")
    type: INSTANCE_TYPE = Field(..., description="The type of the instance, must be 'Part'.")
    id: str = Field(..., description="The unique identifier for the part instance.")
    name: str = Field(..., description="The name of the part instance.")
    suppressed: bool = Field(..., description="Indicates if the part instance is suppressed.")
    partId: str = Field(..., description="The identifier for the part.")

    @field_validator("type")
    def check_type(cls, v: INSTANCE_TYPE) -> INSTANCE_TYPE:
        """
        Validates that the type is 'Part'. Raises a ValueError if not.

        Args:
            v (INSTANCE_TYPE): The type to validate.

        Returns:
            INSTANCE_TYPE: The validated type.
        """
        if v != INSTANCE_TYPE.PART:
            raise ValueError("Type must be Part")

        return v

    @property
    def uid(self) -> str:
        """
        Generates a unique identifier for the part instance based on its attributes.

        Returns:
            str: The unique identifier for the part instance.
        """
        return generate_uid([
            self.documentId,
            self.documentMicroversion,
            self.elementId,
            self.partId,
            self.fullConfiguration,
        ])


class AssemblyInstance(IDBase):
    """
    Represents an instance of an assembly within another assembly.

    JSON:
        ```json
            {
                "id": "Mon18P7LPP8A9STk+",
                "type": "Assembly",
                "name": "subAssembly",
                "suppressed": false,
                "fullConfiguration": "default",
                "configuration": "default",
                "documentId": "a1c1addf75444f54b504f25c",
                "elementId": "f0b3a4afab120f778a4037df",
                "documentMicroversion": "349f6413cafefe8fb4ab3b07"
            }
        ```

    Attributes:
        id (str): The unique identifier for the assembly instance.
        type (INSTANCE_TYPE): The type of the instance, must be 'Assembly'.
        name (str): The name of the assembly instance.
        suppressed (bool): Indicates if the assembly instance is suppressed.
        fullConfiguration (str): The full configuration of the assembly instance.
        configuration (str): The configuration of the assembly instance.
        documentId (str): The unique identifier of the document containing the assembly.
        elementId (str): The unique identifier of the element containing the assembly.
        documentMicroversion (str): The microversion of the document containing the assembly.
    """

    id: str = Field(..., description="The unique identifier for the assembly instance.")
    type: INSTANCE_TYPE = Field(..., description="The type of the instance, must be 'Assembly'.")
    name: str = Field(..., description="The name of the assembly instance.")
    suppressed: bool = Field(..., description="Indicates if the assembly instance is suppressed.")

    @field_validator("type")
    def check_type(cls, v: INSTANCE_TYPE) -> INSTANCE_TYPE:
        """
        Validates that the type is 'Assembly'. Raises a ValueError if not.

        Args:
            v (INSTANCE_TYPE): The type to validate.

        Returns:
            INSTANCE_TYPE: The validated type.
        """
        if v != INSTANCE_TYPE.ASSEMBLY:
            raise ValueError("Type must be Assembly")

        return v


class MatedCS(BaseModel):
    """
    Represents a coordinate system used for mating parts within an assembly.

    JSON:
        ```json
            {
                "xAxis" : [ 1.0, 0.0, 0.0 ],
                "yAxis" : [ 0.0, 0.0, -1.0 ],
                "zAxis" : [ 0.0, 1.0, 0.0 ],
                "origin" : [ 0.0, -0.0505, 0.0 ]
            }
        ```

    Attributes:
        xAxis (list[float]): The x-axis vector of the coordinate system.
        yAxis (list[float]): The y-axis vector of the coordinate system.
        zAxis (list[float]): The z-axis vector of the coordinate system.
        origin (list[float]): The origin point of the coordinate system.
    """

    xAxis: list[float] = Field(..., description="The x-axis vector of the coordinate system.")
    yAxis: list[float] = Field(..., description="The y-axis vector of the coordinate system.")
    zAxis: list[float] = Field(..., description="The z-axis vector of the coordinate system.")
    origin: list[float] = Field(..., description="The origin point of the coordinate system.")

    @field_validator("xAxis", "yAxis", "zAxis", "origin")
    def check_vectors(cls, v: list[float]) -> list[float]:
        """
        Validates that the vectors have exactly 3 values.

        Args:
            v (list[float]): The vector to validate.

        Returns:
            list[float]: The validated vector.

        Raises:
            ValueError: If the vector does not have exactly 3 values.
        """
        if len(v) != 3:
            raise ValueError("Vectors must have 3 values")

        return v

    @property
    def part_to_mate_tf(self) -> np.matrix:
        """
        Generates a transformation matrix from the part coordinate system to the mate coordinate system.

        Returns:
            np.matrix: The 4x4 transformation matrix.
        """
        rotation_matrix = np.array([self.xAxis, self.yAxis, self.zAxis]).T
        translation_vector = np.array(self.origin)
        part_to_mate_tf = np.eye(4)
        part_to_mate_tf[:3, :3] = rotation_matrix
        part_to_mate_tf[:3, 3] = translation_vector
        return np.matrix(part_to_mate_tf)


class MatedEntity(BaseModel):
    """
    Represents an entity that is mated within an assembly, including its coordinate system.

    JSON:
        ```json
            {
                "matedOccurrence": ["MDUJyqGNo7JJll+/h"],
                "matedCS": {
                    "xAxis": [1.0, 0.0, 0.0],
                    "yAxis": [0.0, 0.0, -1.0],
                    "zAxis": [0.0, 1.0, 0.0],
                    "origin": [0.0, -0.0505, 0.0]
                }
            }
        ```

    Attributes:
        matedOccurrence (list[str]): A list of identifiers for the occurrences that are mated.
        matedCS (MatedCS): The coordinate system used for mating the parts.
    """

    matedOccurrence: list[str] = Field(..., description="A list of identifiers for the occurrences that are mated.")
    matedCS: MatedCS = Field(..., description="The coordinate system used for mating the parts.")


class MateRelationMate(BaseModel):
    """
    Represents a mate relation within an assembly, defining how parts or sub-assemblies are connected.

    JSON:
        ```json
            {
                "featureId": "S4/TgCRmQt1nIHHp",
                "occurrence": []
            }
        ```

    Attributes:
        featureId (str): The unique identifier of the mate feature.
        occurrence (list[str]): A list of identifiers for the occurrences involved in the mate relation.
    """

    featureId: str = Field(..., description="The unique identifier of the mate feature.")
    occurrence: list[str] = Field(
        ..., description="A list of identifiers for the occurrences involved in the mate relation."
    )


class MateGroupFeatureOccurrence(BaseModel):
    """
    Represents an occurrence of a mate group feature within an assembly.

    JSON:
        ```json
            {
                "occurrence": ["MplKLzV/4d+nqmD18"]
            }
        ```

    Attributes:
        occurrence (list[str]): A list of identifiers for the occurrences in the mate group feature.
    """

    occurrence: list[str] = Field(
        ..., description="A list of identifiers for the occurrences in the mate group feature."
    )


class MateGroupFeatureData(BaseModel):
    """
    Represents data for a mate group feature within an assembly.

    JSON:
        ```json
            {
                "occurrences": [
                    {
                        "occurrence": ["MplKLzV/4d+nqmD18"]
                    }
                ],
                "name": "Mate group 1"
            }
        ```

    Attributes:
        occurrences (list[MateGroupFeatureOccurrence]): A list of occurrences in the mate group feature.
        name (str): The name of the mate group feature.
    """

    occurrences: list[MateGroupFeatureOccurrence] = Field(
        ..., description="A list of occurrences in the mate group feature."
    )
    name: str = Field(..., description="The name of the mate group feature.")


class MateConnectorFeatureData(BaseModel):
    """
    Represents data for a mate connector feature within an assembly.

    JSON:
        ```json
            {
                "mateConnectorCS": {
                    "xAxis": [],
                    "yAxis": [],
                    "zAxis": [],
                    "origin": []
                },
                "occurrence": [
                    "MplKLzV/4d+nqmD18"
                ],
                "name": "Mate connector 1"
            }
        ```

    Attributes:
        mateConnectorCS (MatedCS): The coordinate system used for the mate connector.
        occurrence (list[str]): A list of identifiers for the occurrences involved in the mate connector.
        name (str): The name of the mate connector feature.
    """

    mateConnectorCS: MatedCS
    occurrence: list[str]
    name: str


class MateRelationFeatureData(BaseModel):
    """
    Represents data for a mate relation feature within an assembly.

    JSON:
        ```json
            {
                "relationType": "GEAR",
                "mates": [
                    {
                    "featureId": "S4/TgCRmQt1nIHHp",
                    "occurrence": []
                    },
                    {
                    "featureId": "QwaoOeXYPifsN7CP",
                    "occurrence": []
                    }
                ],
                "reverseDirection": false,
                "relationRatio": 1,
                "name": "Gear 1"
            }
        ```

    Attributes:
        relationType (RELATION_TYPE): The type of mate relation.
        mates (list[MateRelationMate]): A list of mate relations.
        reverseDirection (bool): Indicates if the direction of the mate relation is reversed.
        relationRatio (Union[float, None]): The ratio of the mate relation. Defaults to None.
        name (str): The name of the mate relation feature.
    """

    relationType: RELATION_TYPE = Field(..., description="The type of mate relation.")
    mates: list[MateRelationMate] = Field(..., description="A list of mate relations.")
    reverseDirection: bool = Field(..., description="Indicates if the direction of the mate relation is reversed.")
    relationRatio: Union[float, None] = Field(None, description="The ratio of the mate relation. Defaults to None.")
    name: str = Field(..., description="The name of the mate relation feature.")


class MateFeatureData(BaseModel):
    """
    Represents data for a mate feature within an assembly.

    JSON:
        ```json
            {
                "matedEntities" :
                [
                    {
                        "matedOccurrence" : [ "MDUJyqGNo7JJll+/h" ],
                        "matedCS" :
                        {
                            "xAxis" : [ 1.0, 0.0, 0.0 ],
                            "yAxis" : [ 0.0, 0.0, -1.0 ],
                            "zAxis" : [ 0.0, 1.0, 0.0 ],
                            "origin" : [ 0.0, -0.0505, 0.0 ]
                        }
                    }, {
                        "matedOccurrence" : [ "MwoBIsds8rn1/0QXA" ],
                        "matedCS" :
                        {
                            "xAxis" : [ 0.8660254037844387, 0.0, -0.49999999999999994 ],
                            "yAxis" : [ -0.49999999999999994, 0.0, -0.8660254037844387 ],
                            "zAxis" : [ 0.0, 1.0, 0.0 ],
                            "origin" : [ 0.0, -0.0505, 0.0 ]
                        }
                    }
                ],
                "mateType" : "FASTENED",
                "name" : "Fastened 1"
            }
        ```

    Attributes:
        matedEntities (list[MatedEntity]): A list of mated entities.
        mateType (MATE_TYPE): The type of mate.
        name (str): The name of the mate feature.
    """

    matedEntities: list[MatedEntity] = Field(..., description="A list of mated entities.")
    mateType: MATE_TYPE = Field(..., description="The type of mate.")
    name: str = Field(..., description="The name of the mate feature.")


class AssemblyFeature(BaseModel):
    """
    Represents a feature within an assembly, such as a mate or pattern.

    JSON:
        ```json
            {
            "id": "Mw+URe/Uaxx5gIdlu",
            "suppressed": false,
            "featureType": "mate",
            "featureData": {
                "matedEntities" :
                [
                    {
                        "matedOccurrence" : [ "MDUJyqGNo7JJll+/h" ],
                        "matedCS" :
                        {
                            "xAxis" : [ 1.0, 0.0, 0.0 ],
                            "yAxis" : [ 0.0, 0.0, -1.0 ],
                            "zAxis" : [ 0.0, 1.0, 0.0 ],
                            "origin" : [ 0.0, -0.0505, 0.0 ]
                        }
                    }, {
                        "matedOccurrence" : [ "MwoBIsds8rn1/0QXA" ],
                        "matedCS" :
                        {
                            "xAxis" : [ 0.8660254037844387, 0.0, -0.49999999999999994 ],
                            "yAxis" : [ -0.49999999999999994, 0.0, -0.8660254037844387 ],
                            "zAxis" : [ 0.0, 1.0, 0.0 ],
                            "origin" : [ 0.0, -0.0505, 0.0 ]
                        }
                    }
                ],
                "mateType" : "FASTENED",
                "name" : "Fastened 1"
                }
            }
        ```

    Attributes:
        id (str): The unique identifier of the feature.
        suppressed (bool): Indicates if the feature is suppressed.
        featureType (ASSEMBLY_FEATURE_TYPE): The type of the feature.
        featureData (Union[MateGroupFeatureData, MateConnectorFeatureData, MateRelationFeatureData, MateFeatureData]):
            Data associated with the assembly feature.
    """

    id: str = Field(..., description="The unique identifier of the feature.")
    suppressed: bool = Field(..., description="Indicates if the feature is suppressed.")
    featureType: ASSEMBLY_FEATURE_TYPE = Field(..., description="The type of the feature.")
    featureData: Union[MateGroupFeatureData, MateConnectorFeatureData, MateRelationFeatureData, MateFeatureData] = (
        Field(..., description="Data associated with the assembly feature.")
    )


class Pattern(BaseModel):
    """
    TODO: Represents a pattern feature within an assembly, defining repeated instances of parts or sub-assemblies.
    """

    pass


class SubAssembly(IDBase):
    """
    Represents a sub-assembly within a root assembly.

    JSON:
        ```json
            {
                "instances": [],
                "patterns": [],
                "features": [],
                "fullConfiguration": "default",
                "configuration": "default",
                "documentId": "a1c1addf75444f54b504f25c",
                "elementId": "0b0c209535554345432581fe",
                "documentMicroversion": "349f6413cafefe8fb4ab3b07"
            }
        ```

    Attributes:
        instances (list[Union[PartInstance, AssemblyInstance]]):
            A list of part and assembly instances in the sub-assembly.
        patterns (list[Pattern]): A list of patterns in the sub-assembly.
        features (list[AssemblyFeature]): A list of features in the sub-assembly
        fullConfiguration (str): The full configuration of the sub-assembly.
        configuration (str): The configuration of the sub-assembly.
        documentId (str): The unique identifier of the document containing the sub-assembly.
        elementId (str): The unique identifier of the element containing the sub-assembly.
        documentMicroversion (str): The microversion of the document containing the sub-assembly.
    """

    instances: list[Union[PartInstance, AssemblyInstance]] = Field(
        ..., description="A list of part and assembly instances in the sub-assembly."
    )
    patterns: list[Pattern] = Field(..., description="A list of patterns in the sub-assembly.")
    features: list[AssemblyFeature] = Field(..., description="A list of features in the sub-assembly")

    @property
    def uid(self) -> str:
        """
        Generates a unique identifier for the sub-assembly with documentId, documentMicroversion, elementId, and
        fullConfiguration.

        Returns:
            str: The unique identifier for the sub-assembly.
        """
        return generate_uid([self.documentId, self.documentMicroversion, self.elementId, self.fullConfiguration])


class RootAssembly(SubAssembly):
    """
    Represents the root assembly, which is the top-level assembly containing all parts and sub-assemblies.

    JSON:
        ```json
            {
                "instances": [],
                "patterns": [],
                "features": [],
                "occurrences": [],
                "fullConfiguration": "default",
                "configuration": "default",
                "documentId": "a1c1addf75444f54b504f25c",
                "elementId": "0b0c209535554345432581fe",
                "documentMicroversion": "349f6413cafefe8fb4ab3b07"
            }
        ```

    Attributes:
        instances (list[Union[PartInstance, AssemblyInstance]]):
            A list of part and assembly instances in the root assembly.
        patterns (list[Pattern]): A list of patterns in the root assembly.
        features (list[AssemblyFeature]): A list of features in the root assembly.
        occurrences (list[Occurrence]): A list of occurrences in the root assembly.
        fullConfiguration (str): The full configuration of the root assembly.
        configuration (str): The configuration of the root assembly.
        documentId (str): The unique identifier of the document containing the root assembly.
        elementId (str): The unique identifier of the element containing the root assembly.
        documentMicroversion (str): The microversion of the document containing the root assembly.
    """

    occurrences: list[Occurrence] = Field(..., description="A list of occurrences in the root assembly.")


class Assembly(BaseModel):
    """
    Represents the overall assembly, including all parts, sub-assemblies, and features.

    JSON:
        ```json
            {
                "rootAssembly": {
                    "instances": [],
                    "patterns": [],
                    "features": [],
                    "occurrences": [],
                    "fullConfiguration": "default",
                    "configuration": "default",
                    "documentId": "a1c1addf75444f54b504f25c",
                    "elementId": "0b0c209535554345432581fe",
                    "documentMicroversion": "349f6413cafefe8fb4ab3b07"
                },
                "subAssemblies": [],
                "parts": [],
                "partStudioFeatures": []
            }
        ```

    Attributes:
        rootAssembly (RootAssembly): The root assembly in the document.
        subAssemblies (list[SubAssembly]): A list of sub-assemblies in the document.
        parts (list[Part]): A list of parts in the document.
        partStudioFeatures (list[dict]): A list of part studio features in the document.

    Custom Attributes:
        document (Union[Document, None]): The document object associated with the assembly. Defaults to None.
    """

    rootAssembly: RootAssembly = Field(..., description="The root assembly in the document.")
    subAssemblies: list[SubAssembly] = Field(..., description="A list of sub-assemblies in the document.")
    parts: list[Part] = Field(..., description="A list of parts in the document.")
    partStudioFeatures: list[dict] = Field(..., description="A list of part studio features in the document.")

    document: Union[Document, None] = Field(None, description="The document associated with the assembly.")
