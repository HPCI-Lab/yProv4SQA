# yprov4sqa/models/quality_check.py  (final enriched version)
"""
QualityCheck activity node — fully enriched W3C PROV-DM model.

New ex: attributes added to every QualityCheck activity:
  From subcriterion level:
    ex:required_for_next_level_badge  — does this block badge upgrade?
  From evidence level:
    ex:standard_title/version/url     — SQA baseline standard reference
    ex:plugin_name/version            — reporting plugin used
  From tool level:
    ex:tool_level                     — REQUIRED / RECOMMENDED
    ex:build_repo                     — GitHub Actions repo URL
  From ci level:
    ex:ci_url                         — Jenkins build URL
    ex:ci_stdout_command              — exact command run
    ex:ci_stdout_text                 — actual tool output (truncated 500 chars)
  Aggregated:
    ex:tools_failed / ex:tools_passed
    ex:failure_messages
    ex:fix_hints (JSON)
    ex:subcriteria_summary (JSON)
    ex:requirement_level
"""
import json


class QualityCheck:
    def __init__(
        self,
        id:                  str,
        description:         str,
        is_output:           bool,
        percentage:          str,
        total_subcriteria:   int,
        success_subcriteria: int,
        # ── enriched fields ─────────────────────────────────────
        tools_failed:        list = None,
        tools_passed:        list = None,
        failure_messages:    list = None,
        fix_hints:           list = None,
        subcriteria_summary: list = None,
        requirement_level:   str  = 'MUST',
        # NEW: standard traceability
        standard_title:      str  = '',
        standard_version:    str  = '',
        standard_url:        str  = '',
        # NEW: plugin info
        plugin_name:         str  = '',
        plugin_version:      str  = '',
        # NEW: tool metadata
        tool_level:          str  = '',
        build_repo:          str  = '',
        # NEW: CI execution details
        ci_url:              str  = '',
        ci_stdout_command:   str  = '',
        ci_stdout_text:      str  = '',
        # NEW: badge gate
        required_for_next_level_badge: bool = None,
    ):
        self.id                  = id
        self.description         = description
        self.is_output           = is_output
        self.percentage          = percentage
        self.total_subcriteria   = total_subcriteria
        self.success_subcriteria = success_subcriteria
        self.tools_failed        = tools_failed        or []
        self.tools_passed        = tools_passed        or []
        self.failure_messages    = failure_messages    or []
        self.fix_hints           = fix_hints           or []
        self.subcriteria_summary = subcriteria_summary or []
        self.requirement_level   = requirement_level
        self.standard_title      = standard_title
        self.standard_version    = standard_version
        self.standard_url        = standard_url
        self.plugin_name         = plugin_name
        self.plugin_version      = plugin_version
        self.tool_level          = tool_level
        self.build_repo          = build_repo
        self.ci_url              = ci_url
        self.ci_stdout_command   = ci_stdout_command
        self.ci_stdout_text      = ci_stdout_text
        self.required_for_next_level_badge = required_for_next_level_badge

    def to_dict(self) -> dict:
        activity = {
            "prov:type":              "activity",
            "ex:description":         self.description,
            "ex:output":              self.is_output,
            "ex:percentage":          self.percentage,
            "ex:total_subcriteria":   self.total_subcriteria,
            "ex:success_subcriteria": self.success_subcriteria,
            "ex:requirement_level":   self.requirement_level,
        }

        # Aggregated tool results
        if self.tools_failed:
            activity["ex:tools_failed"]     = self.tools_failed
        if self.tools_passed:
            activity["ex:tools_passed"]     = self.tools_passed
        if self.failure_messages:
            activity["ex:failure_messages"] = self.failure_messages
        if self.fix_hints:
            activity["ex:fix_hints"]        = json.dumps(self.fix_hints)
        if self.subcriteria_summary:
            activity["ex:subcriteria_summary"] = json.dumps(self.subcriteria_summary)

        # Standard traceability (W3C PROV link to SQA baseline)
        if self.standard_title:
            activity["ex:standard_title"]   = self.standard_title
        if self.standard_version:
            activity["ex:standard_version"] = self.standard_version
        if self.standard_url:
            activity["ex:standard_url"]     = self.standard_url

        # Plugin provenance
        if self.plugin_name:
            activity["ex:plugin_name"]      = self.plugin_name
        if self.plugin_version:
            activity["ex:plugin_version"]   = self.plugin_version

        # Tool metadata
        if self.tool_level:
            activity["ex:tool_level"]       = self.tool_level
        if self.build_repo:
            activity["ex:build_repo"]       = self.build_repo

        # CI execution details
        if self.ci_url:
            activity["ex:ci_url"]           = self.ci_url
        if self.ci_stdout_command:
            activity["ex:ci_stdout_command"] = self.ci_stdout_command
        if self.ci_stdout_text:
            activity["ex:ci_stdout_text"]   = self.ci_stdout_text[:500]

        # Badge gate
        if self.required_for_next_level_badge is not None:
            activity["ex:required_for_next_level_badge"] = \
                self.required_for_next_level_badge

        return {f"ex:{self.id}": activity}
