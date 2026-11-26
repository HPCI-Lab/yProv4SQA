# Level-1 Generation Timing

## Machine Details

| Property | Value |
|---|---|
| OS | Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.39 |
| Python | 3.13.11 |
| CPU | Intel(R) Core(TM) i5-6300U CPU @ 2.40GHz |
| CPU cores | 4 |
| RAM | 5.8 GB |

## Level-1 Generation Time (3 runs, median)

| Repository | Reports (raw) | Retained | Median (s) | Min (s) | Max (s) | Doc size (KB) |
|---|---|---|---|---|---|---|
| interTwin-eu/itwinai | 380 | see note | 3.568 | 3.198 | 4.116 | 6005.9 |
| indigo-dc/udocker | 42 | see note | 0.237 | 0.234 | 0.274 | 855.0 |
| grycap/im | 36 | see note | 1.152 | 0.763 | 1.232 | 807.9 |
| EOSC-synergy/sqaaas-assessment-action | 39 | see note | 0.187 | 0.187 | 0.217 | 783.9 |
| SeisSol/SeisSol | 8 | see note | 0.053 | 0.052 | 0.055 | 180.6 |
| grycap/oscar | 7 | see note | 0.042 | 0.04 | 0.043 | 157.4 |
| EOSC-synergy/FAIR_eva | 3 | see note | 0.017 | 0.017 | 0.017 | 68.4 |
| galaxyproject/galaxy | 1 | see note | 0.058 | 0.057 | 0.058 | 24.9 |
| EOSC-synergy/o3api | 1 | see note | 0.005 | 0.005 | 0.007 | 19.2 |
| indigo-dc/orchestrator | 1 | see note | 0.003 | 0.002 | 0.004 | 20.6 |

Note: 'Retained' = raw reports minus duplicate commit SHAs.
For itwinai: 380 raw → 279 retained (see accuracy check).

## Upload Time

Not measured: yProv service was not available during testing.

## Neo4j Query Latency

Not measured: Neo4j instance was not available during testing.

## Level-2 Generation Time

Not timed automatically: Level-2 generation requires live GitHub API calls
to compare file trees between two commits.  Run the compare CLI manually:

```
time python -m yprov4sqa compare \
  Provenance_documents/interTwin-eu_itwinai_prov_output.json \
  <gindex_1> <gindex_2>
```

The fc45...fd9c → 4086...54f4 Level-2 document contains:
  - 2 commit entities
  - 282 file-change activities
  - 2 agents (GitHub users)
  - 282 wasDerivedFrom relations