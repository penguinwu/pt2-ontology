# PT2 Domain Ontology — Overview

**Version:** 0.6.1 | **Entities:** 272 | **Relationships:** 310 | **Entity Types:** 13

## Entity Types

| Type | Count | Description |
|------|-------|-------------|
| cause | 110 | Root cause (21 categories + 89 leaf subcauses from 9,277 issues) |
| component | 39 | Software component or subsystem |
| config | 28 | Configuration flag or setting |
| failure_mode | 17 | Category of things that can go wrong |
| resolution | 14 | Fix or workaround |
| symptom | 13 | Observable signal |
| user_journey | 9 | User-facing problem scenario |
| op | 9 | PyTorch operator or function |
| ecosystem | 8 | Ecosystem project or framework |
| backend | 6 | Compilation backend |
| optimization | 5 | Optimization technique or pass |
| platform | 10 | Hardware accelerator or OS (7 hardware + 3 OS) |
| deprecated_component | 4 | Deprecated components |

## User Journeys

| ID | Name | Tier | Issues | Question |
|----|------|------|--------|----------|
| j1 | First Compile | symptom | 193 | How do I get torch.compile to work? |
| j2 | Performance Diagnosis | symptom | 800 | My compiled model is slower than eager |
| j3 | Correctness & Debugging | symptom | 686 | Compiled model gives different results |
| j4 | Graph Breaks | root_cause | 495 | Parts of my model fall back to eager |
| j5 | Dynamic Shapes | root_cause | 1061 | My model recompiles on shape changes |
| j6 | Compile-Time Performance | root_cause | 347 | Compilation takes too long |
| j7 | Performance Optimization | root_cause | 1800 | I want more speedup |
| j8 | Custom & Higher-Order Ops | root_cause | 533 | My custom op doesn't work |
| j9 | Export & Serialization | deployment | 907 | I want to save my compiled model |

## Relationship Types

| Type | Count | Description |
|------|-------|-------------|
| is_subcause_of | 97 | X is a sub-cause of Y (cause tree) |
| is_component_of | 41 | X is a sub-component of Y |
| affects | 35 | X affects Y |
| causes | 27 | X leads to Y (failure_mode) |
| fixed_by | 20 | X can be resolved by Y |
| enters_via | 19 | Journey entered via symptom/failure |
| involves | 15 | Journey involves component/config |
| diagnosed_by | 15 | Diagnosed using tool/config |
| is_symptom_of | 13 | X indicates Y |
| depends_on | 10 | X depends on Y |
| resolved_by | 10 | Specific cause → resolution with fix_type |
| routes_to | 8 | Journey routes to journey |

## Data Sources

- PyTorch GitHub issues (9,277 analyzed by Beaver)
- PyTorch source code and documentation
- Internal Compile Q&A discussions
- torch.compile documentation audit project
