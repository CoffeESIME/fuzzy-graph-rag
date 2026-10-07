# Pathfinder similarity diagnostics — inspection milestone

2026-10-06. **Diagnostic use only.** All candidate records and their native order remain intact. Serendipity, Home, graph data, weights and candidate generation are unchanged. No route families, selection score, MMR, thresholds, representative selection or search pruning have been added.

## Evidence and reproduction

The evaluation uses the existing audited corpus snapshot captured at **2026-10-06T16:06:48.910081+00:00**, the audit's 22 canonical simple routes of at most six hops, and its retained native query records. This is a new analysis of existing evidence, not a fresh database run. The audit enumerator previously retained one qualifying relationship per node pair; its 22 routes cannot test parallel relationships. Native records supply those cases separately.

- Generated local output `pathfinder-diagnostics.json` (excluded from Git; regenerate with the command below): 231 canonical snapshot comparisons plus comparisons within each successful native candidate set; input SHA-256 hashes, capture date, route labels, ordered node/relationship identities, shared and differing sets, coverage, and errors.
- Run `node search-app/tests/evaluate-pathfinder-diagnostics.mjs` from the repository root. It uses the same TypeScript diagnostic implementation as the UI and writes only the diagnostic JSON.
- Run `node --test search-app/tests/pathfinder-diagnostics.test.mjs search-app/tests/pathfinder.test.mjs` for the regression checks.

The 24 retained native probes include 11 completed queries and 13 audit timeouts/errors. Missing results remain missing; they do not mean that paths do not exist. No native costs are compared across modes. The snapshot list's C-1…C-22 indices indicate enumeration order, **not native ranking**.

## Representation verification

The current Pathfinder contract retains ordered nodes, ordered edges, relationship IDs, stored and traversal directions, numeric and original weights, mode, hop count, native cost when returned, parameters and traversed DigitalAsset metadata. Its signature identifies equal ordered node sequences; relationship identities distinguish parallel alternatives. Existing exact-sequence presentation groups remain unchanged and retain selectable original records.

Source coverage here means assets actually traversed, not every document supporting a concept. Relation provenance is available for inspection, but `provenance.source` often names a process rather than a DigitalAsset; it is not treated as an asset identity. Legacy saved unions cannot support this analysis and are not reconstructed into hypothetical paths.

No stable per-node community partition is included in the contract or audit evidence. The current analysis endpoint runs `gds.louvain.stream` and returns aggregate/truncated membership, rather than a retained complete partition. Therefore community overlap is **unavailable**, not zero. The diagnostic function can accept an explicit existing partition and reports assignment coverage; it does not run Louvain. No backend/community lifecycle change is necessary for this milestone.

## Definitions and inspection surface

Expand **“Diagnóstico experimental de similitud”** in Pathfinder's routes panel. Its table compares every pair of original records, including parallel variants. The nested evidence panel exposes shared identities, identities unique to each side, union/intersection counts, ordered sequences and repeated-node counts. Existing sequence and relationship inspection supplies names, weights and provenance.

Each available metric is `|A ∩ B| / |A ∪ B|`:

| Signal | Identity and convention |
|---|---|
| Internal nodes | Distinct node IDs, excluding source/target identities even if revisited inside a cycle. Includes internal assets and other node types. |
| Normalized edges | Unordered endpoint-ID pair **plus relationship type**. This mirrors undirected traversal; stored direction and parallel relationship IDs are ignored only for this metric. |
| Relationship IDs | Additional overlap of actual IDs, unavailable if either route has any missing relationship ID. |
| Source assets | Distinct internal DigitalAsset node IDs. Fixed asset endpoints are excluded too, avoiding mandatory shared-source inflation. Different node IDs remain different even if content/hashes match. |
| Communities | Distinct assigned communities of internal Concepts from one explicit partition. Unavailable if assignments are missing for any internal Concept. Coverage remains inspectable. |

An empty union yields `null` (no evidence); one empty side and a nonempty side yield zero. Metrics are separate: no weighted combination or calibrated semantic score exists. An exact relationship route requires matching ordered node and relationship-ID sequences; an ordered node match with different relationship IDs is flagged as an edge variant. Missing IDs yield unknown identity, not a false exact match. These flags do not certify equal weights or provenance across snapshots.

“Near duplicate” has no automatic cutoff. High overlap, exact-sequence flags and explicit differences support human judgment without making semantic equivalence claims. Set metrics intentionally lose order and multiplicity; sequence identity and repeated-node counts expose that limitation.

## Canonical findings

Labels below refer to previously reviewed routes, not production rules or semantic ground truth. Every one of the 22 candidates remains in the evidence.

| Pair | Internal nodes | Normalized edges | Assets |
|---|---:|---:|---:|
| Short literary C-4 / philosophical-musical C-11 | 14.29% | 11.11% | 25% |
| Short literary C-4 / mathematical-visual C-12 | 14.29% | 11.11% | 25% |
| Philosophical-musical C-11 / mathematical-visual C-12 | 25% | 20% | 20% |
| Mortality/Haggard C-10 / human-condition/Haggard C-11 | 66.67% | 50% | **100%** |
| Mortality/text C-5 / mortality/Warcry C-6 | 66.67% | 50% | 50% |
| Mortality/nihilism C-14 / mortality/nihilism C-15 | 66.67% | 50% | 50% |
| Fade to Black/despair C-13 / Fade to Black/nihilism C-19 | 66.67% | 50% | **100%** |
| Human-condition/Haggard C-11 / human-condition/nihilism C-22 | 42.86% | 33.33% | 50% |

C-4 traverses Goethe → Autodestrucción → Master of Puppets. C-11 traverses Séneca → Condición Humana → Haggard → Desesperación → Master of Puppets. C-12 traverses the Markov–Nekrasov transcription → Matemáticas → eigenvalue meme → Desesperación → Master of Puppets. The latter pair's shared terminal bridge is visible as overlap without hiding the distinct initial regions.

The native topological probe returned just the short route. Native lateral returned C-11's sequence and two instances of C-12's sequence; the two mathematical variants have **100% node and asset overlap but 71.43% typed-edge overlap**, because one relationship type differs. Native direct's first two records have identical node sequences and 100% normalized-edge overlap, but distinct relationship IDs. Both pairs are explicitly flagged as relationship variants and remain present. Exact copies are covered by synthetic identity regression tests, not claimed as an observed corpus result.

### Mismatches to retain for review

1. **Asset-only similarity collapses a meaningful conceptual substitution.** Mortality versus human condition and despair versus nihilism can each produce 100% asset overlap. Node/edge differences remain visible. A future asset-only selector would lose this distinction.
2. **Necessary bridges inflate overlap.** Philosophical and mathematical routes share more internal nodes than either shares with the literary route. This is convergence on Desesperación and Master of Puppets, not evidence that philosophy and mathematics are semantically closer.
3. **Distinct source assets are not necessarily distinct interpretations.** Mortality variants that swap one song/text show 50% asset overlap while staying near the same reviewed region. Asset identities do not compare their content.
4. **One structural change has different meanings.** A concept substitution and a source substitution can both give 66.67% node / 50% edge overlap; identical metric values do not imply equivalent interpretive changes.
5. **Type-sensitive edges need identity context.** The mathematical parallel variants appear less than identical under typed-edge overlap. Ordered-sequence and relationship-variant flags prevent mistaking this for a different conceptual itinerary.
6. **High node overlap does not assess route quality.** The native direct records contain repeated nodes and author/genre bridges. They remain inspectable; no validity gate or cycle removal was introduced.

## Additional audited endpoint pairs

| Candidate set | Observations |
|---|---|
| Ciclos Temporales y Naturales ↔ Lógica Difusa, native direct (3 records) | Node overlap 55.56–75%; asset overlap 33.33–60%. These remain variants in a related scientific region; the metrics do not label them separate interpretations. |
| Same pair, native lateral (3 records) | Node overlap 0–40%; asset overlap 0–33.33%. Distinct identities are visible, but zero overlap alone does not validate the semantic quality of a route. |
| Inmortalidad ↔ Automatización y Control de Sistemas, native topological (3 records) | First two routes share 100% of assets but only 50% of internal nodes and 33.33% of edges: Opresión e Injusticia versus Rebeldía y Revolución stays visible. Each against the Libertad alternative shares 20% of internal nodes and 33.33% of assets. |
| Aislamiento y Soledad ↔ Crítica a Internet y la Era Digital, native topological (2 records) | Via Bad Religion versus The Motorleague: **0% on nodes, edges and assets**, despite the audit placing them in the same broad thematic region. This is a concrete failure of structural disjointness as semantic diversity. |

The full JSON also includes completed thresholded probes and preserves all unsuccessful probes. Community coverage cannot distinguish any of these cases with the available evidence. A synthetic test demonstrates that a single broad community can itself collapse structurally distinct routes to 100% community overlap; it is not a claim about a computed corpus partition.

## Recommendation and validation

The metrics are useful for human inspection of exact identities and local substitutions. **They are insufficient on their own to establish semantic diversity.** Keep this diagnostic milestone available for review before deciding whether any subsequent selection mechanism is justified. No thresholds were tuned to return three paths, and no candidate was discarded or reranked.

Validation: 17 domain/regression tests passed, covering the canonical numbers, exact copies, real-data parallel-variant patterns, missing IDs, edge direction/type, symmetry, empty sets, incomplete communities, cycles and nonmutation, alongside the existing route/export tests. Production TypeScript compilation and Vite build were run. No live browser visual check or fresh database queries were performed in this stage.
