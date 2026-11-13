# Data flow

```mermaid
flowchart TD
  subgraph Records
    SRC[10 sources] -->|CDC, streams, files| BR[Bronze Iceberg, append-only]
    BR -->|Glue mapping + DQ| SV[Silver canonical model]
    SV -->|EMR + Flink, C1-C9| GR[Gold recon results]
    GR -->|group + prioritize| GX[Gold exceptions + groups]
    GX -->|EventBridge to SQS| AI[AI tier]
    AI -->|pending proposals| CS[Case + provenance]
    CS -->|analyst approval| ADJ[Approved adjustments to S3, S4, S9]
  end
  subgraph Documents
    DOC[Contracts, tariffs, policies] -->|Textract, BDA| COR[Corpora with effective dates]
    COR -->|embed + sync| KB[Knowledge Bases, hybrid + rerank]
  end
  KB -->|retrieve| AI
  GR --> RS[Redshift + QuickSight KPIs]
  subgraph Learning loop
    CS --> VD[Analyst verdicts] -->|labels| GS[Gold set] -->|regression| EG[Eval gate] -->|pass| RM[Release manifest]
  end
  RM -.-> AI
```

Lineage: OpenLineage events from Glue, EMR and Flink to SageMaker Unified Studio / DataZone;
Iceberg snapshot IDs are stored in every provenance record so any decision can be replayed.
