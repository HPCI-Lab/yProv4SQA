# Tools Reference

The chat agent has 7 tools. The LLM decides which tool(s) to call based on your question. Each tool queries the loaded provenance document directly.

---

## Tool overview

| Tool | Input | What it returns |
|------|-------|-----------------|
| `get_summary` | — | totals, badge counts, QC averages, latest assessment |
| `get_assessment` | number | full details of one assessment + deltas vs previous |
| `get_regressions` | — | all badge drops + which QC criteria caused them |
| `get_badge_history` | `gold` / `silver` / `bronze` / `no_badge` | all matching assessments |
| `get_qc_trend` | `"QC.Uni"` or `"QC.Uni,30"` | avg, min, max, trend over last N assessments |
| `compare_assessments` | `"246,247"` | side-by-side diff of any two assessments |
| `find_best_period` | — | longest gold streak, best scores per criterion |

---

## get_summary

Returns an overview of the entire provenance document.

**Example question:** *"Give me a summary of the quality history."*

**Returns:**
- Total number of assessments
- Badge distribution (gold / silver / bronze / no_badge counts)
- Average QC scores across all criteria
- Latest assessment details

---

## get_assessment

Returns the full details of a single assessment.

**Example question:** *"Show me assessment #87."*

**Input:** assessment number (integer)

**Returns:**
- Date, commit, branch, badge
- All QC criterion scores
- Delta compared to the previous assessment

---

## get_regressions

Finds all assessments where the badge dropped compared to the previous one.

**Example question:** *"When did we lose the gold badge?"*

**Returns:**
- Total number of regressions
- For each regression: assessment number, date, from/to badge, which QC criteria dropped

---

## get_badge_history

Returns all assessments that achieved a specific badge level.

**Example question:** *"List all gold badge assessments."*

**Input:** `gold`, `silver`, `bronze`, or `no_badge`

**Returns:** list of matching assessments with date, commit, and QC scores

---

## get_qc_trend

Analyzes the trend of a specific QC criterion over the last N assessments.

**Example question:** *"How has QC.Uni been trending over the last 30 assessments?"*

**Input:** criterion name, optionally with window size — e.g. `"QC.Uni,30"`

**QC criteria:**

| Code | Criterion |
|------|-----------|
| `QC.Sty` | Code style |
| `QC.Uni` | Unit testing |
| `QC.Fun` | Functional testing |
| `QC.Sec` | Security |
| `QC.Doc` | Documentation |
| `QC.Lic` | Licensing |
| `QC.Del` | Delivery (CI/CD) |

**Returns:** average, min, max, and trend direction (improving / stable / declining)

---

## compare_assessments

Side-by-side comparison of any two assessments.

**Example question:** *"Compare assessments 59 and 87."*

**Input:** two assessment numbers as a string — `"59,87"`

**Returns:**
- Badge change
- QC score changes per criterion
- Which criteria improved and which degraded

---

## find_best_period

Finds the best quality periods in the history.

**Example question:** *"When was our quality at its best?"*

**Returns:**
- Longest consecutive gold streak (start/end assessment + dates)
- Best score ever achieved per QC criterion
