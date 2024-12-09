"""
This module contains functions to generate URDF components from Onshape assembly data.

"""

import asyncio
import os
import random
from typing import Optional, Union

import numpy as np
from networkx import DiGraph

from onshape_api.connect import Client, DownloadableLink
from onshape_api.log import LOGGER
from onshape_api.models.assembly import (
    Assembly,
    MateFeatureData,
    MateRelationFeatureData,
    MateType,
    Part,
)
from onshape_api.models.document import WorkspaceType
from onshape_api.models.geometry import MeshGeometry
from onshape_api.models.joint import (
    BaseJoint,
    DummyJoint,
    FixedJoint,
    JointDynamics,
    JointLimits,
    JointMimic,
    PrismaticJoint,
    RevoluteJoint,
)
from onshape_api.models.link import (
    Axis,
    CollisionLink,
    Colors,
    Inertia,
    InertialLink,
    Link,
    Material,
    Origin,
    VisualLink,
)
from onshape_api.parse import MATE_JOINER, PARENT, RELATION_PARENT
from onshape_api.utilities.helpers import get_sanitized_name

SCRIPT_DIR = os.path.dirname(__file__)


def get_joint_name(mate_id: str, mates: dict[str, MateFeatureData]) -> str:
    reverse_mates = {mate.id: key for key, mate in mates.items()}
    return reverse_mates.get(mate_id)


async def get_robot_link(
    name: str,
    part: Part,
    wid: str,
    client: Client,
    mate: Optional[Union[MateFeatureData, None]] = None,
) -> tuple[Link, np.matrix, DownloadableLink]:
    """
    Generate a URDF link from an Onshape part.
    """
    _link_to_stl_tf = np.eye(4)

    if mate is None:
        _link_to_stl_tf[:3, 3] = np.array(part.MassProperty.center_of_mass).reshape(3)
    else:
        _link_to_stl_tf = mate.matedEntities[0].matedCS.part_to_mate_tf

    _stl_to_link_tf = np.linalg.inv(_link_to_stl_tf)
    _mass = part.MassProperty.mass[0]
    _com = part.MassProperty.center_of_mass_wrt(_stl_to_link_tf)
    _inertia = part.MassProperty.inertia_wrt(_stl_to_link_tf[:3, :3])

    wtype = WorkspaceType.V.value if part.documentVersion else WorkspaceType.W.value
    mvwid = part.documentVersion if part.documentVersion else part.rigidAssemblyWorkspaceId or wid

    _downloadable_link = await asyncio.to_thread(
        DownloadableLink,
        did=part.documentId,
        wtype=wtype,
        wid=mvwid,
        eid=part.elementId,
        partID=part.partId,
        client=client,
        transform=_stl_to_link_tf,
        is_rigid_assembly=part.isRigidAssembly,
        file_name=f"{name}.stl",
    )

    _mesh_path = _downloadable_link.relative_path

    _link = Link(
        name=name,
        visual=VisualLink(
            name=f"{name}-visual",
            origin=Origin.zero_origin(),
            geometry=MeshGeometry(_mesh_path),
            material=Material.from_color(
                name=f"{name}-material",
                color=random.SystemRandom().choice(list(Colors)),
            ),
        ),
        inertial=InertialLink(
            origin=Origin(
                xyz=_com,
                rpy=(0.0, 0.0, 0.0),
            ),
            mass=_mass,
            inertia=Inertia(
                ixx=_inertia[0, 0],
                ixy=_inertia[0, 1],
                ixz=_inertia[0, 2],
                iyy=_inertia[1, 1],
                iyz=_inertia[1, 2],
                izz=_inertia[2, 2],
            ),
        ),
        collision=CollisionLink(
            name=f"{name}-collision",
            origin=Origin.zero_origin(),
            geometry=MeshGeometry(_mesh_path),
        ),
    )

    return _link, _stl_to_link_tf, _downloadable_link


async def get_robot_joint(
    parent: str,
    child: str,
    mate: MateFeatureData,
    stl_to_parent_tf: np.matrix,
    mimic: Optional[JointMimic] = None,
    is_rigid_assembly: bool = False,
) -> tuple[list[BaseJoint], Optional[list[Link]]]:
    """
    Generate a URDF joint from an Onshape mate feature.
    """
    links = []

    # Calculate parent-to-mate transformation
    parent_to_mate_tf = (
        mate.matedEntities[PARENT].parentCS.part_tf @ mate.matedEntities[PARENT].matedCS.part_to_mate_tf
        if is_rigid_assembly
        else mate.matedEntities[PARENT].matedCS.part_to_mate_tf
    )

    # Compute the STL-to-mate transformation
    stl_to_mate_tf = stl_to_parent_tf @ parent_to_mate_tf
    origin = Origin.from_matrix(stl_to_mate_tf)
    sanitized_name = get_sanitized_name(mate.name)

    LOGGER.info(f"Creating robot joint from {parent} to {child}")

    # Joint type handling
    if mate.mateType == MateType.REVOLUTE:
        return [
            RevoluteJoint(
                name=sanitized_name,
                parent=parent,
                child=child,
                origin=origin,
                limits=JointLimits(
                    effort=1.0,
                    velocity=1.0,
                    lower=-np.pi,
                    upper=np.pi,
                ),
                axis=Axis((0.0, 0.0, -1.0)),
                dynamics=JointDynamics(damping=0.1, friction=0.1),
                mimic=mimic,
            )
        ], links

    elif mate.mateType == MateType.FASTENED:
        return [FixedJoint(name=sanitized_name, parent=parent, child=child, origin=origin)], links

    elif mate.mateType in {MateType.SLIDER, MateType.CYLINDRICAL}:
        return [
            PrismaticJoint(
                name=sanitized_name,
                parent=parent,
                child=child,
                origin=origin,
                limits=JointLimits(
                    effort=1.0,
                    velocity=1.0,
                    lower=-0.1,
                    upper=0.1,
                ),
                axis=Axis((0.0, 0.0, -1.0)),
                dynamics=JointDynamics(damping=0.1, friction=0.1),
                mimic=mimic,
            )
        ], links

    elif mate.mateType == MateType.BALL:
        # Handle ball joint by creating intermediate links for X, Y, Z axes
        dummy_x = Link(name=f"{parent}-dummy-x")
        dummy_y = Link(name=f"{parent}-dummy-y")
        links = [dummy_x, dummy_y]

        return [
            RevoluteJoint(
                name=sanitized_name + "-x",
                parent=parent,
                child=dummy_x.name,
                origin=origin,
                limits=JointLimits(
                    effort=1.0,
                    velocity=1.0,
                    lower=-np.pi,
                    upper=np.pi,
                ),
                axis=Axis((1.0, 0.0, 0.0)),
                dynamics=JointDynamics(damping=0.1, friction=0.1),
                mimic=mimic,
            ),
            RevoluteJoint(
                name=sanitized_name + "-y",
                parent=dummy_x.name,
                child=dummy_y.name,
                origin=Origin.zero_origin(),
                limits=JointLimits(
                    effort=1.0,
                    velocity=1.0,
                    lower=-np.pi,
                    upper=np.pi,
                ),
                axis=Axis((0.0, 1.0, 0.0)),
                dynamics=JointDynamics(damping=0.1, friction=0.1),
                mimic=mimic,
            ),
            RevoluteJoint(
                name=sanitized_name + "-z",
                parent=dummy_y.name,
                child=child,
                origin=Origin.zero_origin(),
                limits=JointLimits(
                    effort=1.0,
                    velocity=1.0,
                    lower=-np.pi,
                    upper=np.pi,
                ),
                axis=Axis((0.0, 0.0, -1.0)),
                dynamics=JointDynamics(damping=0.1, friction=0.1),
                mimic=mimic,
            ),
        ], links

    else:
        LOGGER.warning(f"Unsupported joint type: {mate.mateType}")
        return [DummyJoint(name=sanitized_name, parent=parent, child=child, origin=origin)], links


def get_topological_mates(
    graph: DiGraph,
    mates: dict[str, MateFeatureData],
    relations: Optional[dict[str, MateRelationFeatureData]] = None,
) -> tuple[dict[str, MateFeatureData], dict[str, MateRelationFeatureData]]:
    """
    Get the topological mates from the graph. This shuffles the order of the mates to match the directed graph edges.

    Args:
        graph: The graph representation of the assembly.
        mates: The dictionary of mates in the assembly.

    Returns:
        dict[str, MateFeatureData]: The topological mates.

    Examples:
        >>> get_topological_mates(graph, mates)
        {
            'link1-MATE-body': MateFeatureData(...),
            'subassembly1-SUB-link2-MATE-body': MateFeatureData(...),
        }
    """
    topological_mates: dict[str, MateFeatureData] = {}
    topological_relations: dict[str, MateRelationFeatureData] = relations or {}

    mate_keys = {tuple(key.split(MATE_JOINER)) for key in mates}
    graph_edges = set(graph.edges)

    rogue_mates = mate_keys.difference(graph_edges)

    for edge in graph.edges:
        parent, child = edge
        key = f"{parent}{MATE_JOINER}{child}"

        if (child, parent) in rogue_mates:
            # the only way it can be a rogue mate is if the parent and child are swapped
            # LOGGER.info(f"Rogue mate found: {edge}")
            rogue_key = f"{child}{MATE_JOINER}{parent}"
            topological_mates[key] = mates[rogue_key]

            if isinstance(topological_mates[key], MateFeatureData):
                topological_mates[key].matedEntities = topological_mates[key].matedEntities[::-1]

            if relations and rogue_key in topological_relations:
                LOGGER.info(f"Rogue relation found: {rogue_key}")
                topological_relations[key] = topological_relations[rogue_key]
                topological_relations.pop(rogue_key)

        else:
            topological_mates[key] = mates[key]

    return topological_mates, topological_relations


async def _get_urdf_components_async(
    assembly: Assembly,
    graph: DiGraph,
    root_node: str,
    parts: dict[str, Part],
    mates: dict[str, MateFeatureData],
    relations: dict[str, MateRelationFeatureData],
    client: Client,
) -> tuple[dict[str, Link], dict[str, BaseJoint], dict[str, DownloadableLink]]:
    """
    Generate URDF links and joints from an Onshape assembly asynchronously.
    """
    links_map = {}
    joints_map = {}
    assets_map = {}
    stl_to_link_tf_map = {}

    topological_mates, topological_relations = get_topological_mates(graph, mates, relations)

    LOGGER.info(f"Processing root node: {root_node}")

    root_link, stl_to_root_tf, _downloadable_link = await get_robot_link(
        name=root_node, part=parts[root_node], wid=assembly.document.wid, client=client, mate=None
    )

    links_map[root_node] = root_link
    assets_map[root_node] = _downloadable_link
    stl_to_link_tf_map[root_node] = stl_to_root_tf

    async def process_edge(edge):
        parent, child = edge
        mate_key = f"{parent}{MATE_JOINER}{child}"
        LOGGER.info(f"Processing edge: {parent} -> {child}")

        try:
            parent_tf = stl_to_link_tf_map[parent]
        except KeyError:
            LOGGER.warning(f"Parent {parent} not found in stl_to_link_tf_map")
            return

        relation = topological_relations.get(topological_mates[mate_key].id)

        joint_mimic = (
            JointMimic(
                joint=get_joint_name(relation.mates[RELATION_PARENT].featureId, topological_mates),
                multiplier=relation.relationRatio or 1.0,
                offset=0.0,
            )
            if relation
            else None
        )

        joint_list, link_list = await get_robot_joint(
            parent,
            child,
            topological_mates[mate_key],
            parent_tf,
            joint_mimic,
            is_rigid_assembly=parts[parent].isRigidAssembly,
        )

        links_map.update({link.name: link for link in link_list})
        joints_map.update({joint.name: joint for joint in joint_list})

        link, stl_to_link_tf, downloadable_link = await get_robot_link(
            child, parts[child], assembly.document.wid, client, topological_mates[mate_key]
        )
        stl_to_link_tf_map[child] = stl_to_link_tf
        assets_map[child] = downloadable_link

        links_map[child] = link

    await asyncio.gather(*(process_edge(edge) for edge in graph.edges))

    return links_map, joints_map, assets_map


def get_urdf_components(
    assembly: Assembly,
    graph: DiGraph,
    root_node: str,
    parts: dict[str, Part],
    mates: dict[str, MateFeatureData],
    relations: dict[str, MateRelationFeatureData],
    client: Client,
) -> tuple[dict[str, Link], dict[str, BaseJoint], dict[str, DownloadableLink]]:
    """
    Synchronous wrapper for the asynchronous `get_urdf_components`.
    """
    return asyncio.run(
        _get_urdf_components_async(
            assembly=assembly,
            graph=graph,
            root_node=root_node,
            parts=parts,
            mates=mates,
            relations=relations,
            client=client,
        )
    )
