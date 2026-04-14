# Data Sources

Pointers to data used for ontology extraction. Data lives in its original location — this file just documents where to find it.

## GitHub Issues (Primary)

- **Local copy**: `../../pt2-issues/` (being built — see that directory's README)
- **Filter**: label `oncall: pt2` on pytorch/pytorch
- **Content**: Issue title, body, comments, labels, assignees, state
- **Status**: Fetch scripts ready, pending web-proxy startup

## PyTorch Compile Q&A (Workplace)

- **Group ID**: 1075192433118967
- **Access**: Workplace API via `knowledge_filtered_search`
- **Content**: User questions, team answers, workarounds
- **Status**: Searchable but not bulk-exported yet

## PyTorch Codebase

- **Location**: `~/fbsource/fbcode/caffe2/torch/` (and related paths)
- **What to extract**: Component hierarchy from imports, config flags from `torch._dynamo.config`, op registry
- **Status**: Available, needs targeted extraction scripts
