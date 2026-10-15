> ARCHIVED: accuracy evaluation and review are stopped by user instruction. Current demonstration graphs are manually curated. See scene-workspace.md.

# Scene reference audit

Historical pre-pruning baseline only. The current graph has confidence/size/duplicate/reflection filtering and sparse relations. Current precision/recall await the user's labels in [the five-photo review pack](scene-review/README.md).

Assistant visual reference annotations from source photographs. Approximate 2D boxes; 36 selected instances, not exhaustive labels. These are NOT independent human ground truth or 3D ground truth. Relation references are qualitative visible evidence. Match category aliases and IoU >= 0.30 one-to-one. Report anchored correspondence recall and end-to-end relation recovery; never call this full precision/accuracy.

| Photograph | Nodes generated | Reference matches | Relations recovered |
|---|---:|---:|---:|
| dav2-01 | 77 | 3/3 | 2/2 |
| dav2-02 | 49 | 2/2 | 1/1 |
| dav2-04 | 3 | 2/2 | 0/1 |
| dav2-06 | 11 | 2/3 | 0/1 |
| dav2-07 | 4 | 2/2 | 0/0 |
| dav2-08 | 27 | 1/2 | 0/1 |
| dav2-10 | 20 | 3/3 | 2/2 |
| dav2-11 | 22 | 2/2 | 1/1 |
| dav2-12 | 27 | 2/2 | 0/1 |
| dav2-13 | 26 | 3/3 | 1/1 |
| dav2-14 | 63 | 2/2 | 1/1 |
| dav2-15 | 42 | 2/3 | 1/1 |
| dav2-16 | 33 | 2/2 | 1/1 |
| sam3-truck | 27 | 2/2 | 0/1 |
| sam3-groceries | 23 | 3/3 | 1/1 |

Selected object correspondence: 33/36. Selected relation recovery: 11/16.

Previous user-reported values: object correspondence 14/36 (38.9%), relation accuracy 9/10 (90%). Different photos, annotations and possibly definitions: no valid improvement claim.

Unmatched and extra predicted nodes are retained in raw graph JSON. Full node precision/recall, complete relation precision, and metric 3D accuracy remain unmeasured. Reference audit is provisional until independently reviewed.
