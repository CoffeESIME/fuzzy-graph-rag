"""Pathfinder serialization, independent of database clients and path ranking."""
import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field

ALGORITHM_VERSION = 'pathfinder-cypher-v1'


class PathfinderRequest(BaseModel):
    source_element_id: str
    target_element_id: str
    mode: str = 'direct'
    threshold: float = 0.85
    topo_threshold: float = 0.0
    k_paths: int = 3


class PathfinderNodeData(BaseModel):
    id: str
    label: str
    node_type: str
    weight_to_next: Optional[float] = None
    file_hash: Optional[str] = None
    mime_type: Optional[str] = None
    download_url: Optional[str] = None
    minio_path: Optional[str] = None


class PathfinderEdgeData(BaseModel):
    id: Optional[str] = None
    source: str
    target: str
    rel_type: str
    weight: Optional[float] = None
    raw_weight: Any = None
    traversal_source: Optional[str] = None
    traversal_target: Optional[str] = None
    reasoning: Optional[str] = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class PathfinderParameters(BaseModel):
    k_paths: int
    requested_k_paths: int
    max_hops: int = 8
    lateral_threshold: Optional[float] = None
    topological_threshold: Optional[float] = None


class PathfinderMetrics(BaseModel):
    cost: Optional[float] = None
    min_weight: Optional[float] = None
    missing_weight_count: int = 0


class PathfinderPath(BaseModel):
    id: str
    rank: int
    mode: str
    signature: str
    duplicate_of: Optional[str] = None
    nodes: list[PathfinderNodeData]
    edges: list[PathfinderEdgeData]
    hop_count: int
    metrics: PathfinderMetrics
    parameters: PathfinderParameters


class PathfinderResponse(BaseModel):
    status: str
    message: str
    nodes: list[PathfinderNodeData]
    edges: list[PathfinderEdgeData]
    path_length: int
    mode: str
    paths: list[PathfinderPath] = Field(default_factory=list)
    raw_result_count: int = 0
    unique_route_count: int = 0
    generated_at: Optional[str] = None
    algorithm_version: str = ALGORITHM_VERSION
    parameters: Optional[PathfinderParameters] = None
    source: Optional[PathfinderNodeData] = None
    target: Optional[PathfinderNodeData] = None


def finite_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def json_value(value):
    """Keep Neo4j temporal values as ISO-like strings; never drop provenance."""
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def build_pathfinder_response(records, request: PathfinderRequest, resolve_asset=None):
    mode = request.mode if request.mode in ('direct', 'lateral', 'topological') else 'direct'
    params = PathfinderParameters(
        k_paths=max(1, min(10, request.k_paths)), requested_k_paths=request.k_paths,
        lateral_threshold=request.threshold if mode == 'lateral' else None,
        topological_threshold=request.topo_threshold if mode == 'topological' else None,
    )
    combined_nodes, combined_edges, signatures = {}, {}, {}
    paths = []
    for rank, record in enumerate(records, 1):
        ordered_nodes = []
        for n in record['path_nodes']:
            nid = str(n.element_id)
            if nid not in combined_nodes:
                node_type = next((lbl for lbl in ('DigitalAsset', 'Person', 'Location', 'Organization', 'Event', 'Project') if lbl in n.labels), 'Concept')
                file_hash = n.get('file_hash') or n.get('neo4j_hash') or n.get('hash')
                media = resolve_asset(file_hash, n.get('mime_type')) if resolve_asset and node_type == 'DigitalAsset' and file_hash else {}
                combined_nodes[nid] = PathfinderNodeData(id=nid, label=n.get('name') or n.get('filename') or n.get('title') or '?', node_type=node_type, file_hash=file_hash, mime_type=n.get('mime_type'), **media)
            ordered_nodes.append(combined_nodes[nid])
        ordered_edges = []
        for index, rel in enumerate(record['path_rels']):
            properties = dict(rel)
            edge = PathfinderEdgeData(
                id=str(rel.element_id) if getattr(rel, 'element_id', None) is not None else None,
                source=str(rel.start_node.element_id), target=str(rel.end_node.element_id),
                traversal_source=ordered_nodes[index].id, traversal_target=ordered_nodes[index + 1].id,
                rel_type=rel.type, weight=finite_number(properties.get('weight')),
                raw_weight=json_value(properties.get('weight')),
                reasoning=str(properties['reasoning']) if properties.get('reasoning') is not None else None,
                provenance=json_value({k: v for k, v in properties.items() if k not in ('weight', 'reasoning')}),
            )
            ordered_edges.append(edge)
            # All relationships remain distinguishable, including parallel edges.
            key = edge.id or (edge.source, edge.target, edge.rel_type, json.dumps(properties, default=str, sort_keys=True))
            combined_edges.setdefault(key, edge)
        sequence = json.dumps([n.id for n in ordered_nodes], ensure_ascii=False, separators=(',', ':'))
        signature = hashlib.sha256(sequence.encode()).hexdigest()
        route_id = f'route-{rank}-{signature[:12]}'
        valid_weights = [e.weight for e in ordered_edges if e.weight is not None]
        paths.append(PathfinderPath(
            id=route_id, rank=rank, mode=mode, signature=signature, duplicate_of=signatures.get(signature),
            nodes=ordered_nodes, edges=ordered_edges, hop_count=len(ordered_edges), parameters=params,
            metrics=PathfinderMetrics(cost=finite_number(record['totalCost']), min_weight=min(valid_weights) if valid_weights else None, missing_weight_count=len(ordered_edges)-len(valid_weights)),
        ))
        signatures.setdefault(signature, route_id)
    return PathfinderResponse(
        status='success' if paths else 'not_found',
        message=f'{len(paths)} resultado(s), {len(signatures)} secuencia(s) de nodos distinta(s).',
        nodes=list(combined_nodes.values()), edges=list(combined_edges.values()),
        path_length=max((p.hop_count for p in paths), default=0), mode=mode,
        paths=paths, raw_result_count=len(paths), unique_route_count=len(signatures),
        generated_at=datetime.now(timezone.utc).isoformat(), parameters=params,
        source=paths[0].nodes[0] if paths else None, target=paths[0].nodes[-1] if paths else None,
    )
