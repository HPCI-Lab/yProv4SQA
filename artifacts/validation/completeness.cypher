// ============================================================================
// Completeness validation — Cypher queries for Neo4j
//
// Target document : interTwin-eu/itwinai Level-1 provenance (itwinai_prov_output.json)
// Expected counts : 559 entities · 2 111 activities · 1 agent
//                   2 111 wasGeneratedBy · 558 wasDerivedFrom · 1 wasAttributedTo
//                   9 partial-run assessments
//
// Schema assumed  : standard W3C PROV–Neo4j import (e.g. prov2neo).
//   Node labels   — Entity | Activity | Agent
//   Node property — id  : prefixed IRI  (e.g. "ex:assessment1")
//   Relationship  — wasGeneratedBy | wasDerivedFrom | wasAttributedTo
//   Attribute key — stored as "ex:<name>" (namespace kept as prefix)
// ============================================================================

// ----------------------------------------------------------------------------
// 1. Total counts per PROV type
// ----------------------------------------------------------------------------

MATCH (n:Entity)   RETURN count(n) AS total_entities;      // expected: 559
MATCH (n:Activity) RETURN count(n) AS total_activities;    // expected: 2111
MATCH (n:Agent)    RETURN count(n) AS total_agents;        // expected: 1

// ----------------------------------------------------------------------------
// 2. Entity sub-types
// ----------------------------------------------------------------------------

MATCH (n:Entity) WHERE n.id STARTS WITH 'ex:assessment'
RETURN count(n) AS assessment_entities;        // expected: 279

MATCH (n:Entity) WHERE n.id STARTS WITH 'ex:output'
RETURN count(n) AS output_entities;            // expected: 279

MATCH (n:Entity) WHERE n.id STARTS WITH 'ex:repository'
RETURN count(n) AS repository_entities;        // expected: 1

// ----------------------------------------------------------------------------
// 3. Relationship counts
// ----------------------------------------------------------------------------

MATCH ()-[r:wasGeneratedBy]->()
RETURN count(r) AS total_wasGeneratedBy;       // expected: 2111

MATCH ()-[r:wasDerivedFrom]->()
RETURN count(r) AS total_wasDerivedFrom;       // expected: 558

MATCH ()-[r:wasAttributedTo]->()
RETURN count(r) AS total_wasAttributedTo;      // expected: 1

// ----------------------------------------------------------------------------
// 4. Partial-run assessments
// ----------------------------------------------------------------------------

MATCH (n:Entity)
WHERE n.id STARTS WITH 'ex:assessment'
  AND n.`ex:is_partial_run` = true
RETURN count(n) AS partial_run_assessments;    // expected: 9

// ----------------------------------------------------------------------------
// 5. QualityCheck activities by criterion
// ----------------------------------------------------------------------------

MATCH (n:Activity)
WHERE n.id STARTS WITH 'ex:qc_QC.Acc_'
RETURN count(n) AS activities_QC_Acc;          // expected: 270

MATCH (n:Activity)
WHERE n.id STARTS WITH 'ex:qc_QC.Doc_'
RETURN count(n) AS activities_QC_Doc;          // expected: 270

MATCH (n:Activity)
WHERE n.id STARTS WITH 'ex:qc_QC.Lic_'
RETURN count(n) AS activities_QC_Lic;          // expected: 270

MATCH (n:Activity)
WHERE n.id STARTS WITH 'ex:qc_QC.Met_'
RETURN count(n) AS activities_QC_Met;          // expected: 278

MATCH (n:Activity)
WHERE n.id STARTS WITH 'ex:qc_QC.Sec_'
RETURN count(n) AS activities_QC_Sec;          // expected: 270

MATCH (n:Activity)
WHERE n.id STARTS WITH 'ex:qc_QC.Sty_'
RETURN count(n) AS activities_QC_Sty;          // expected: 271

MATCH (n:Activity)
WHERE n.id STARTS WITH 'ex:qc_QC.Uni_'
RETURN count(n) AS activities_QC_Uni;          // expected: 212

MATCH (n:Activity)
WHERE n.id STARTS WITH 'ex:qc_QC.Ver_'
RETURN count(n) AS activities_QC_Ver;          // expected: 270

// ----------------------------------------------------------------------------
// 6. Structural integrity checks
// ----------------------------------------------------------------------------

// Every assessment must be derived from exactly one repository
MATCH (a:Entity)
WHERE a.id STARTS WITH 'ex:assessment'
  AND NOT (a)<-[:wasDerivedFrom]-(:Entity)
RETURN count(a) AS assessments_without_repository;  // expected: 0

// Every output must be derived from exactly one assessment
MATCH (o:Entity)
WHERE o.id STARTS WITH 'ex:output'
  AND NOT (o)<-[:wasDerivedFrom]-(:Entity)
RETURN count(o) AS outputs_without_assessment;      // expected: 0

// Every QC activity must generate exactly one assessment
MATCH (n:Activity)
WHERE NOT (n)-[:wasGeneratedBy]->(:Entity)
RETURN count(n) AS activities_without_assessment;   // expected: 0

// ----------------------------------------------------------------------------
// 7. Badge distribution (output entities)
// ----------------------------------------------------------------------------

MATCH (n:Entity)
WHERE n.id STARTS WITH 'ex:output'
RETURN n.`ex:badge_won` AS badge_level, count(n) AS count
ORDER BY count DESC;
