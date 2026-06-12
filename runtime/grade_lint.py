#!/usr/bin/env python3
"""Deterministic lint for bs Grade artifacts."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any
try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None
BLOCKING={"P0","P1"}
SURFACES={"process","background_process","runtime_files","identity_sentinel","network_probe","auth_or_secret","file_modes","concurrency_or_locking","destructive_operation","external_subprocess","string_boundary","input_validation_or_schema"}
OPTIONAL_CURRENT_HINT_PATTERNS=(
    (re.compile(r"\boptional\b", re.I), "optional"),
    (re.compile(r"\bdefer(?:red|ral|s|ring)?\b", re.I), "deferred"),
    (re.compile(r"\bfuture\b", re.I), "future"),
    (re.compile(r"\bnot[-\s]?reachable\b", re.I), "not-reachable"),
    (re.compile(r"\bunreachable\b", re.I), "unreachable"),
    (re.compile(r"\bnot\s+required\b", re.I), "not required"),
    (re.compile(r"\bcan\s+skip\b", re.I), "can skip"),
    (re.compile(r"\bif\s+possible\b", re.I), "if possible"),
    (re.compile(r"\blater\b", re.I), "later"),
    (re.compile(r"\bfollow[-\s]?up\b", re.I), "follow-up"),
)
CONCURRENCY_TERMS=re.compile(r"\bconcurrent(?:ly|cy)?\b|lost\s+update|same[-\s]?revision|\bone\s+2xx\b|\b409\b|if[-\s]?match", re.I)
CONCURRENCY_EVIDENCE={"concurrency_test","atomicity_proof"}
BOUNDARY_TERMS=re.compile(r"<=\s*\d+\s*chars?\b|\b\d+\s*chars?\b|\blength\s+(?:cap|limit|boundary)\b|\bchar[-_\s]?boundary\b|\bstring[-_\s]?boundary\b|\btruncate(?:d|s|ion)?\b|\buser\s+text\b|\bmalformed\s+(?:input|json)\b|\bnon[-_\s]?ascii\b|\bboundary\s+(?:probe|test|risk|case)\b", re.I)
BOUNDARY_SURFACES={"string_boundary","input_validation_or_schema"}
BOUNDARY_EVIDENCE={"non_ascii_boundary_test","malformed_input_test","length_boundary_test","json_boundary_test","schema_validation_test"}
PANIC_TERMS=re.compile(r"\bno[-\s]?panic\b|\bpanic(?:s|ked|king)?\b|\bunwrap\b|\bexpect\b", re.I)
PANIC_EVIDENCE={"panic_audit","implicit_panic_audit"}
SUBPROCESS_LIFECYCLE_STRONG_SCOPE_TERMS=re.compile(r"\bexternal[-_\s]?subprocess\b|\bsubprocess(?:es)?\b|\bvendor\s+(?:child|process|binary|subprocess)\b|\bchild\s+process\b|\bspawn(?:s|ed|ing)?\s+(?:the\s+)?(?:vendor|child|subprocess|process|command|helper|argv|binary|daemon|app[-_\s]?server|call[-_\s]?sites?|failure|path|error)\b|\b(?:vendor|child|subprocess|process|command|helper|argv|binary|daemon|app[-_\s]?server)[^.;,\n]{0,80}\bspawn(?:s|ed|ing)?\b|\bspawn[-_\s]?(?:process|group|command|helper|vendor|child)\b|\b--detach\b|\bdetach(?:ed|es|ing)?\b|\bre[-_\s]?exec\b|\bprocess[-_\s]?group\b|\.process_group\(0\)|\bstart_new_session\b|\bsetsid\b|\bsetpgid\b|SIGTERM|SIGKILL|\bkill\s+(?:-TERM|-9)\b|\bkill\s*\(\s*-?9\s*\)|\bkill\s*\([^)]*\bSIG(?:TERM|KILL)\b[^)]*\)|\bkill(?:ed|s|ing)?\s+(?:the\s+)?(?:child|process|subprocess|daemon|vendor|app[-_\s]?server)\b|\breap(?:ed|s|ing)?\b|\bzombie(?:s)?\b|\borphan(?:ed)?\s+grandchild\b", re.I)
SUBPROCESS_PROBE_SCOPE_TERMS=re.compile(r"\bprobe(?:s|d|ing)?\b|\bcapability[-_\s]?probe\b|\bprobe_capability\b", re.I)
SUBPROCESS_PROBE_VENDOR_CONTEXT=re.compile(r"\b(?:codex|claude|vendor|cli|binary|Command)\b|--version\b|\blogin\s+status\b|\bapp[-_\s]?server\b", re.I)
SUBPROCESS_PROBE_HTTP_CONTEXT=re.compile(r"\bGET\b|(?i:\bendpoint\b|/api/|\bhttp\b|\burl\b|\bAuthorization\b)")
SUBPROCESS_DEPENDENCY_COMPLIANCE_CLAIM_TERMS=re.compile(r"\bno\s+new\s+(?:external\s+)?(?:dep(?:endenc(?:y|ies)|s)?|dependencies|deps)\b|\b(?:all\s+)?deps?\s+in\s+tech[-_\s]?stack(?:\.yaml)?\b|\bdependency\s+review\b|\bcrate\s*/\s*version[-_\s]?pinning\b|\b(?:crate|version|package)[-_\s]?pinning\b|\b(?:pinned|locked)\s+(?:crate|package|version)\b", re.I)
SUBPROCESS_TIMEOUT_FACET=re.compile(r"\btime::timeout\b|\btimeout\b|\bdeadline\b|\bwait[-_\s]?timeout\b|\bbounded\s+(?:wait|deadline)\b|\bwait\s+bounded\b", re.I)
SUBPROCESS_PROCESS_GROUP_FACET=re.compile(r"\.process_group\(0\)|\bprocess[-_\s]?group\b|\bnegative[-_\s]?pgid\b|\bstart_new_session\b|\bsetsid\b|\bsetpgid\b|\bown\s+(?:process[-_\s]?)?group\b|\bnew\s+session\b|\bisolat(?:e|ed|ion)\b", re.I)
SUBPROCESS_REAP_FACET=re.compile(r"\bchild\.wait\b|\.wait\(\)|\btry_wait\b|\bwaitpid\b|\breap(?:ed|s|ing)?\b|\bwait/reap\b|\bwait\s+after\s+(?:SIGTERM|SIGKILL|kill|signal)\b|after\s+(?:SIGTERM|SIGKILL|kill|signal)[^.;,\n]*\bwait\b", re.I)
SUBPROCESS_STREAM_TERMS=re.compile(r"\bstream(?:ing|ed|s)?\b|\bstream[-_\s]?json\b|\bstdio\b|\bstdout\b|\bstderr\b|\breader(?:s)?\b|\braw[-_\s]?vendor[-_\s]?output\b|\bNDJSON\b", re.I)
SUBPROCESS_STREAM_JOIN_FACET=re.compile(r"\bjoin(?:ed|s|ing)?\s+(?:stdout|stderr|reader|stream|task)s?\b|\b(?:stdout|stderr|reader|stream)[^.;,\n]{0,80}\b(?:join(?:ed|s|ing)?|await(?:ed)?|drain(?:ed)?|closed)\b|\bawait(?:ed)?\s+(?:stdout|stderr|reader|stream)[^.;,\n]{0,80}\btask\b|\bdrain(?:ed)?\s+(?:stdout|stderr|reader|stream)s?\b", re.I)
SUBPROCESS_DESCENDANT_CLAIM_TERMS=re.compile(r"\bno[-_\s]?orphan(?:ed)?\b|\borphan(?:ed)?\s+grandchild\b|\bno[-_\s]?hang\b|\bhung\s+process\b|\bbackground(?:ed)?[-_\s]?grandchild\b|\bwhole[-_\s]?process[-_\s]?tree\b|\bprocess[-_\s]?tree\s+(?:containment|reap|kill|audit)\b|\bdescendant(?:s)?\b", re.I)
SUBPROCESS_DESCENDANT_ESCAPE_FIXTURE=re.compile(r"\b(?:detached|new[-_\s]?session|setsid|start_new_session|setpgid|daemonized|background(?:ed)?)\b[^.;\n]{0,160}\b(?:grandchild|descendant|child[-_\s]?of[-_\s]?child|escape|leader\s+exit|parent\s+exit)\b|\b(?:grandchild|descendant|escape)\b[^.;\n]{0,160}\b(?:detached|new[-_\s]?session|setsid|start_new_session|setpgid|daemonized|background(?:ed)?|leader\s+exit|parent\s+exit)\b", re.I)
SUBPROCESS_DESCENDANT_AUDIT_FACET=re.compile(r"\bdescendant[-_\s]?audit\b|\bprocess[-_\s]?tree[-_\s]?containment\b|\bwalk(?:s|ed|ing)?\s+(?:the\s+)?(?:process[-_\s]?)?tree\b|\b(?:pgrep|ps)\b[^.;\n]{0,80}\b(?:P|ppid|parent|child|descendant)\b|\bassert(?:s|ed|ion)?\b[^.;\n]{0,120}\b(?:no\s+descendant|no\s+grandchild|no\s+orphan|process[-_\s]?tree)\b|\b(?:grandchild|descendant)\b[^.;\n]{0,120}\b(?:reaped|killed|gone|absent|not\s+running|does\s+not\s+remain)\b", re.I)
SUBPROCESS_LIFECYCLE_EVIDENCE_KIND="subprocess_lifecycle_test"
RPC_CLEANUP_EVERY_EXIT_CLAIM_TERMS=re.compile(r"\bcleanup\b[^.;,\n]{0,100}\b(?:on|for|across|in|runs?\s+on)\s+(?:every|each|all)\s+(?:exit[-_\s]?)?(?:path|paths|return|returns|outcome|outcomes)\b|\b(?:every|each|all)\s+(?:exit[-_\s]?)?(?:path|paths|return|returns|outcome|outcomes)\b[^.;,\n]{0,100}\bcleanup\b", re.I)
RPC_CLEANUP_CLEAR_TERMS=re.compile(r"\bthread/goal/clear\b|\bgoal/clear\b|\bgoal[-_\s]?clear\b|\bclear(?:s|ed|ing)?\s+(?:the\s+)?(?:goal|thread\s+goal)\b", re.I)
RPC_CLEANUP_ARCHIVE_TERMS=re.compile(r"\bthread/archive\b|\bthread[-_\s]?archive\b|\barchive(?:s|d|ing)?\s+(?:the\s+)?thread\b", re.I)
RPC_CLEANUP_PAIR_TERMS=re.compile(r"(?:\bthread/goal/clear\b|\bgoal/clear\b|\bgoal[-_\s]?clear\b|\bclear(?:s|ed|ing)?\s+(?:the\s+)?(?:goal|thread\s+goal)\b|\bclear(?:s|ed|ing)?\b)[^.;,\n]{0,100}(?:\bthread/archive\b|\bthread[-_\s]?archive\b|\barchive(?:s|d|ing)?\s+(?:the\s+)?thread\b|\barchive(?:s|d|ing)?\b)|(?:\bthread/archive\b|\bthread[-_\s]?archive\b|\barchive(?:s|d|ing)?\s+(?:the\s+)?thread\b|\barchive(?:s|d|ing)?\b)[^.;,\n]{0,100}(?:\bthread/goal/clear\b|\bgoal/clear\b|\bgoal[-_\s]?clear\b|\bclear(?:s|ed|ing)?\s+(?:the\s+)?(?:goal|thread\s+goal)\b|\bclear(?:s|ed|ing)?\b)", re.I)
RPC_CLEANUP_UNCONDITIONAL_TERMS=re.compile(r"\b(?:always|unconditional(?:ly)?)\b|\b(?:every|each|all)\s+(?:exit[-_\s]?)?(?:path|paths|return|returns|outcome|outcomes)\b|\ball\s+paths\b|\bsuccess\b[^.;,\n]{0,80}\bfailure\b[^.;,\n]{0,80}\btimeout\b[^.;,\n]{0,80}\bcancel(?:led|s|lation)?\b|\b(?:any|each|every)\s+failure\b|\bfailure\s*(?:[-=]?>|→|yields?\b|maps?\s+to\b)|\bsuccess\s*(?:[-=]?>|→|yields?\b|maps?\s+to\b)", re.I)
RPC_CLEANUP_NEGATIVE_PATH_TERMS=re.compile(r"\b(?:timeout|error|cancel|cancelled|cancellation|abort|kill|killed|SIGINT|SIGTERM)[-_\s]*(?:path|case|branch)\s*(?:test|fixture|probe)?\b|\b(?:forced?|simulate[sd]?|simulating|induce[sd]?|inducing|inject(?:ed|ion)?|fake|fixture|test)\b[^.;,\n]{0,100}\b(?:timeout|error|cancel|cancelled|cancellation|abort|kill|killed|SIGINT|SIGTERM)\b|\b(?:timeout|error|cancel|cancelled|cancellation|abort|kill|killed|SIGINT|SIGTERM)\b[^.;,\n]{0,100}\b(?:forced?|simulate[sd]?|simulated|induced?|injected|fixture|test)\b|\berror[-_\s]?injection\b|\binduced\s+error\b|\bkills?\s+mid[-_\s]?turn\b|\bouter\s+timeout\s+(?:fires?|fired|expires?|expired)\b", re.I)
RPC_CLEANUP_ASSERTION_TERMS=re.compile(r"\bassert(?:s|ed|ing)?\b[^.;,\n]{0,120}\b(?:cleanup|clear(?:s|ed|ing)?\s*(?:/|\+|and|then|->)\s*archive(?:s|d|ing)?|thread/goal/clear|goal/clear|thread/archive)\b|\b(?:thread/goal/clear|goal/clear|goal[-_\s]?clear)\b[^.;,\n]{0,100}\b(?:thread/archive|thread[-_\s]?archive|archive(?:s|d|ing)?)\b|\bclear(?:s|ed|ing)?\s*(?:/|\+|and|then|->)\s*archive(?:s|d|ing)?\b[^.;,\n]{0,100}\b(?:call(?:ed|s)?|record(?:ed|s)?|happen(?:ed|s)?|still|runs?|ran|emit(?:ted|s)?|sent)\b|\bcleanup\s+(?:calls?\s+)?(?:still\s+)?(?:happen(?:ed|s)?|runs?|ran|record(?:ed|s)?|emit(?:ted|s)?|sent)\b", re.I)
PATH_ROOT_TERMS=re.compile(r"\bpath[-_\s]?traversal\b|\btravers(?:e|al|ing)\b.*\boutside\b|\boutside\b.*\b(?:root|roots|director(?:y|ies)|filesystem|file\s+tree)\b|\bescape\b.*\b(?:root|roots|director(?:y|ies)|filesystem|file\s+tree)\b|\broot[-_\s]?contain(?:ed|ment)?\b", re.I)
PATH_ACCESS_TERMS=re.compile(r"\b(?:read|open|file|filesystem|path|dir|directory|directories|root|roots|skill[-_ ]?id|id)\b", re.I)
STRING_TRAVERSAL_TERMS=re.compile(r"\.\.|slash|backslash|absolute\s+path|%2f|%5c|encoded\s+(?:slash|path)|path[-_\s]?traversal", re.I)
SYMLINK_CONTAINMENT_TERMS=re.compile(r"symlink|canonical(?:ize|ise|ization|isation)?|realpath|starts?_with|starts[-\s]?with|root[-_\s]?contain(?:ed|ment)?|within\s+(?:the\s+)?(?:root|directory)|no[-_\s]?follow|lstat|symlink_metadata|link_metadata", re.I)
REQUEST_TARGET_TERMS=re.compile(r"request[-_\s]?target|request\s+line|raw\s+http|http/1\.1|path\s+segment|percent[-_\s]?encod|url[-_\s]?encod|crlf|control\s+char|request\s+delimiter", re.I)
REQUEST_TARGET_FACET_TERMS=re.compile(r"delimiter|\?|#|\bspaces?\b|control|crlf|\\r|\\n|percent[-_\s]?encod|url[-_\s]?encod", re.I)
SECRET_AUDIT_SCOPE_TERMS=re.compile(r"\b(?:auth|secret|token|credential|password|oauth|bearer|api[-_\s]?key|vendor[-_\s]?stderr|stderr|logs?|logging|traces?|tracing|events?|evidence|debug|display|errors?|serialization)\b", re.I)
NEGATED_SCOPE_PREFIX=re.compile(r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bdoes\s+not\b|\bdo\s+not\b|\bdoesn't\b|\bdon't\b|\bnot_applicable\b)\W+(?:[\w/.-]+\W+){0,8}$", re.I)
SECRET_TOKEN_SHAPE_PATTERNS={
    "bare_token_or_key": re.compile(r"\b(?:bare[-_\s]*(?:whitespace[-_\s]*)?(?:token|key|form|shape)|key[-_\s]?value|token[-_\s]?equals|api[-_\s]?key[-_\s]?equals)\b|\b(?:token|api[-_\s]?key)\s*=", re.I),
    "json_or_quoted_token": re.compile(r"\b(?:json(?:[-_\s]*or[-_\s]*quoted)?|quoted)[-_\s]*(?:token|api[-_\s]?key|form|shape)\b|[\"'](?:api[-_]?key|token)[\"']\s*:", re.I),
    "authorization_bearer": re.compile(r"\bauthorization\s*:\s*bearer\b|\bauthorization[-_\s]*bearer\b|\bhttp[-_\s]*header\b[^.;,\n]*\bbearer\b|\bbearer[-_\s]*header\b", re.I),
}
SECRET_BARE_SK_PATTERN=re.compile(r"(?<![\"':/A-Za-z0-9_-])sk-[A-Za-z0-9][A-Za-z0-9._-]*(?![A-Za-z0-9_-])", re.I)
EVENT_SOURCE_TOKEN=re.compile(r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'|(?<![A-Za-z0-9_-])([A-Za-z][A-Za-z0-9_-]*(?:[/.][A-Za-z0-9_*_-]+)+)(?![A-Za-z0-9_-])")
EVENT_SOURCE_BARE={"result"}
EVENT_SOURCE_PREFIXES={"system","thread","turn","item"}
EVENT_SOURCE_PATHLIKE=re.compile(r"\.(?:md|json|jsonl|rs|py|toml|yaml|yml|txt|log)\b|/\.|^\.|(?:^|/)(?:docs|src|crates|tests|evidence|runtime|lib|prompts|harness|bundle)(?:/|$)", re.I)
EVENT_MAPPING_VERBS=re.compile(r"\b(?:emit(?:s|ted|ting)?|normaliz(?:e|es|ed|ing)|produc(?:e|es|ed|ing)|map(?:s|ped|ping)?|yield(?:s|ed|ing)?|convert(?:s|ed|ing)?|writ(?:e|es|ten|ing)|append(?:s|ed|ing)?|driv(?:e|es|en|ing)|source(?:s)?)\b|[-=]+>|→", re.I)
EVENT_SOURCE_NEGATED_SUFFIX=re.compile(r"^\W*(?:is|are|was|were|be|being)?\W*(?:missing|absent|omitted|raced|unavailable|not\s+present)\b", re.I)
EVENT_PROOF_TERMS=re.compile(r"\b(?:test(?:s)?|fixture(?:s)?|case(?:s)?|assert(?:s|ed|ion)?|probe(?:s)?|regression|parameteri[sz]ed|nextest)\b|::|#\[test\]", re.I)
EVENT_MULTI_SOURCE_PROOF_TERMS=re.compile(r"\b(?:each|per[-_\s]?source|per[-_\s]?event|parameteri[sz]ed|cases?)\b", re.I)
EVENT_AGGREGATE_EVIDENCE_TERMS=re.compile(r"(?:>=|≥)\s*1|\bat least one\b|\bexactly one\b|\bcount(?:s|ed)?\b|\baggregate(?:d|-only)?\b|\bcombined\b|\bassert_exit_condition\b|\be2e\b|\bfake[-_\s]?vendor\b", re.I)
EVENT_OUTPUT_PATTERNS=(
    ("goal_snapshot", re.compile(r"\bgoal[_\s-]?snapshot\b|\bGoalSnapshot\b", re.I)),
    ("plan_snapshot", re.compile(r"\bplan[_\s-]?snapshot\b|\bPlanSnapshot\b", re.I)),
    ("task_end", re.compile(r"\btask[_\s-]?end\b|\bterminal\s+event\b", re.I)),
    ("failure", re.compile(r"\bfailure\b", re.I)),
)
AUTH_STATUS_COMMAND_TERMS=re.compile(r"\b(?:codex\s+login\s+status|claude\s+auth\s+status|login[-_\s]?status|auth[-_\s]?status|login\s+output|auth\s+output|status\s+output|loggedIn|loggedin)\b", re.I)
AUTH_STATUS_LOGGED_OUT_TERMS=re.compile(r"\b(?:not[-_\s]?logged[-_\s]?in|logged[-_\s]?out|not\s+authenticated|unauthenticated)\b", re.I)
AUTH_STATUS_MAPPING_TERMS=re.compile(r"\b(?:maps?|mapped|mapping|yields?|returns?|produces?|classif(?:y|ies|ied|ication)|mis[-_\s]?classif(?:y|ies|ied|ication))\b|[-=]+>|→", re.I)
AUTH_STATUS_DISTINGUISH_TERMS=re.compile(r"\b(?:distinguish(?:es|ed|ing)?|differentiat(?:e|es|ed|ing)?|distinct(?:ly)?|separat(?:e|es|ed|ing)?)\b", re.I)
AUTH_STATUS_ERROR_STATE_TERMS=re.compile(r"\b(?:AdapterError(?:::[A-Za-z][A-Za-z0-9_]*)?|LoginRequired|NotAuthenticated|BinaryNotFound|VersionTooOld|GoalRpcUnavailable|Unsupported|authenticated|unauthenticated|logged[-_\s]?in|logged[-_\s]?out|remediation)\b", re.I)
AUTH_STATUS_DISTINGUISH_FROM_TERMS=re.compile(r"\b(?:distinguish(?:es|ed|ing)?|differentiat(?:e|es|ed|ing)?|separat(?:e|es|ed|ing)?)\b[^.;\n]{0,80}\bfrom\b", re.I)
AUTH_STATUS_JSON_PARSE_EVIDENCE=re.compile(r"\b(?:json[-_\s]?pars(?:e|ed|es|ing)?|pars(?:e|ed|es|ing)\s+(?:the\s+)?(?:codex\s+|claude\s+)?(?:login[-_\s]?status|auth[-_\s]?status|status)\s+(?:as\s+)?json|pars(?:e|ed|es|ing)\s+(?:the\s+)?status\s+as\s+structured\s+data|structured[-_\s]?(?:json|data|status)|serde(?:_json)?(?:\s*::\s*(?:from_str|from_slice))?|deseriali[sz](?:e|ed|es|ing))\b", re.I)
AUTH_STATUS_VARIANT_EVIDENCE=re.compile(r"\b(?:case[-_\s]?insensitive\s+(?:key|field)|key[-_\s]?case|camel[-_\s]?case|lower[-_\s]?case|whitespace[-_\s]?(?:variant|toleran(?:t|ce)|format|fixture)|format[-_\s]?variant|status[-_\s]?format[-_\s]?variant|status[-_\s]?fixture[-_\s]?matrix)\b", re.I)
AUTH_STATUS_MULTI_VARIANT_EVIDENCE=re.compile(r"\b(?:multiple|both|two|several|matrix|parameteri[sz]ed)\b[^.;\n]{0,100}\b(?:login[-_\s]?status|auth[-_\s]?status|status|format|fixture|fixtures|variant|variants|loggedIn|loggedin|whitespace|key[-_\s]?case)\b", re.I)
AUTH_STATUS_LITERAL_VARIANT_EVIDENCE=re.compile(r"(?:loggedIn[^.;\n]{0,100}loggedin|loggedin[^.;\n]{0,100}loggedIn|\"loggedIn\"\s*:\s*false[^.;\n]{0,100}\"loggedin\"\s*:\s*false|\"loggedin\"\s*:\s*false[^.;\n]{0,100}\"loggedIn\"\s*:\s*false)", re.I)
SHAPE_PRIMARY_TASK_TOKENS=re.compile(r"\bsymphony\s+shape\b|\bShape Agent\b|\bcrates/symphony-shape\b|docs/agents/shape/AGENT\.md", re.I)
SHAPE_STRONG_TASK_TOKENS=SHAPE_PRIMARY_TASK_TOKENS
SHAPE_CRATE_TOKEN=re.compile(r"\bsymphony-shape\b", re.I)
SHAPE_CRATE_PLACEHOLDER_CONTEXT=re.compile(r"\bfuture\s+work\b|\bplaceholder\b|\bfuture\b", re.I)
SHAPE_FORBIDDEN_ROOTS=("memory-user","patterns-user","patterns-imported")
SHAPE_FORBIDDEN_SCOPE=re.compile(r"\bR-AGT-6\b|\bmemory-user\b|\bpatterns-user\b|\bpatterns-imported\b", re.I)
SHAPE_FORBIDDEN_SPEC_REF=re.compile(r"docs/agents/shape/AGENT\.md|\bR-AGT-6\b", re.I)
SHAPE_NO_READ_EVIDENCE=re.compile(r"\bno\s+reads?\b|\bdoes\s+not\s+read\b|\bnot\s+read\b|\bread-boundary\b|\bno\s+code\s+path\s+reads\b|\bnever\s+(?:opens?|reads?)\b|\b(?:trees?|roots?)\s+are\s+never\s+opened\b", re.I)
SHAPE_SCHEMA_ASSUMPTION_FIELDS=("id","text","source","confirmed","risk_if_wrong")
SHAPE_SCHEMA_GROUNDING_FIELDS=("id","source_type","fetched_at","why_relevant","supports")
SHAPE_HIGH_RISK_ACTIONS=("deploy","delete","db_write","external_api","payment","merge_pr")
SHAPE_CRITIC_ENVELOPE_FIELDS=("verdict","rejected_reasons","approved_with_notes","incident","incident_class")
GRADE_AGENT_PRIMARY_TASK_TOKENS=re.compile(r"\bM6\s+Grade\s+Agent\b|\bGrade Agent\b|\bcrates/symphony-grade\b|\bsymphony\s+grade\b|docs/agents/grade/AGENT\.md", re.I)
GRADE_AGENT_READ_ONLY_CLAIM=re.compile(r"\bR-AGT-6\b|\bread[-_\s]?only\b|\bforbidden[-_\s]?root\b|\bforbidden\s+(?:dirs?|directories|roots?)\b|\bmemory-user\b|\bpatterns-user\b|\bpatterns-imported\b|\boutcome\.md\b[^.;\n]{0,120}\b(?:byte[-_\s]?identical|unchanged|stable)\b", re.I)
GRADE_AGENT_HOSTILE_TERMS=re.compile(r"\bhostile\b|\bmalicious\b|\badversarial\b|\bnegative\b|\bescape\b|\bcrafted\b|\bfixture\b|\bprobe\b|\battempt(?:s|ed|ing)?\b", re.I)
GRADE_AGENT_COMMAND_TERMS=re.compile(r"\bacceptance\s+command\b|\bcommand(?:-type)?\b|\bshell\b|\bsh\s+-c\b|\bbash\b|\bCommand\b", re.I)
GRADE_AGENT_WRITE_TERMS=re.compile(r"\bwrite(?:s|n|d|ing)?\b|\btouch(?:es|ed|ing)?\b|\bappend(?:s|ed|ing)?\b|\bmodify(?:ies|ied|ing)?\b|\boverwrite(?:s|n|ing)?\b|\bcreate(?:s|d|ing)?\b|fs::write|cat\s*>|>>|sed\s+-i", re.I)
GRADE_AGENT_WRITE_TARGET_TERMS=re.compile(r"\boutcome\.md\b|\bsource\b|\bsrc/|\bcrates/|\bforbidden\b|\bmemory-user\b|\bpatterns-user\b|\bpatterns-imported\b", re.I)
GRADE_AGENT_ARTIFACT_TERMS=re.compile(r"\bartifact(?:_path)?\b|\bartifact\s+path\b", re.I)
GRADE_AGENT_READ_OR_TRAVERSAL_TERMS=re.compile(r"\bread(?:s|ing)?\b|\bopen(?:s|ed|ing)?\b|\b\.\.\b|\bpath[-_\s]?traversal\b|\bforbidden[-_\s]?root\b|\bmemory-user\b|\bpatterns-user\b|\bpatterns-imported\b", re.I)
GRADE_AGENT_CONTAINMENT_TERMS=re.compile(r"\bcanonical(?:ize|ise|ized|ised|ization|isation)?\b|\brealpath\b|\bstarts?_with\b|\broot[-_\s]?contain(?:ed|ment)?\b|\bwithin\s+(?:the\s+)?(?:run|workspace|artifact)?\s*root\b", re.I)
GRADE_AGENT_DENYLIST_TERMS=re.compile(r"\bdeny[-_\s]?list\b|\bforbidden\b|\bmemory-user\b|\bpatterns-user\b|\bpatterns-imported\b|\ballow[-_\s]?list\b", re.I)
GRADE_AGENT_STABILITY_TERMS=re.compile(r"\bpost[-_\s]?run\b|\bbefore\b[^.;\n]{0,80}\bafter\b|\bafter\b[^.;\n]{0,80}\bbefore\b|\brecheck(?:s|ed|ing)?\b", re.I)
GRADE_AGENT_HASH_BYTE_TERMS=re.compile(r"\bsha256\b|\bhash(?:es|ed|ing)?\b|\bbyte[-_\s]?(?:identical|stable|stability)\b|\bunchanged\b|\bno\s+mutation\b", re.I)
GRADE_AGENT_DP13_CLAIM=re.compile(r"\bD-P13\b|\bhigh[-_\s]?risk\b|\bsecond[-_\s]?signal\b|\bhigh_risk_actions?\b|\bllm_judge\b|\bhuman_review\b", re.I)
GRADE_AGENT_HIGH_RISK_ACTIONS_TOP_LEVEL=re.compile(r"\brisk_level\s*[:=]\s*[\"']?high[\"']?\b[\s\S]{0,500}\bhigh_risk_actions\s*:", re.I)
GRADE_AGENT_SECOND_SIGNAL_BRANCH=re.compile(r"\bsecond[-_\s]?signal\b[\s\S]{0,180}\b(?:both_required|llm_judge|deterministic_check|fail|passes?|branch)\b|\b(?:both_required|llm_judge|deterministic_check|fail|passes?|branch)\b[\s\S]{0,180}\bsecond[-_\s]?signal\b", re.I)
GRADE_AGENT_HUMAN_REVIEW_BRANCH=re.compile(r"\bhuman_review\b[\s\S]{0,180}\b(?:needs_human|requires\s+human_review|branch|artifact)\b|\b(?:needs_human|requires\s+human_review|branch|artifact)\b[\s\S]{0,180}\bhuman_review\b", re.I)
GRADE_AGENT_SUBSTRING_UNFORGEABLE=re.compile(r"\b(?:criteria|criterion|text|substring|prose|string)\b[\s\S]{0,180}\bsecond_signal_pass\b[\s\S]{0,180}\b(?:cannot|can't|does\s+not|must\s+not|not\s+set|ignored|rejected)\b[\s\S]{0,120}\bllm_judge_passed\b|\bsecond_signal_pass\b[\s\S]{0,180}\b(?:cannot|can't|does\s+not|must\s+not|not\s+set|ignored|rejected)\b[\s\S]{0,120}\bllm_judge_passed\b", re.I)
GRADE_AGENT_STRUCTURED_SECOND_SIGNAL=re.compile(r"\b(?:structured|JSON|YAML)\b[\s\S]{0,120}\b(?:independent\s+)?judge\s+result\b|\bindependent[-_\s]?judge[-_\s]?result\b|\bllm_judge_result\b|\bhuman_review\b[\s\S]{0,120}\bartifact\b", re.I)
GRADE_AGENT_EMPTY_EVIDENCE_REFS_FAIL=re.compile(r"\b(?:empty|\[\]|zero)\b[\s\S]{0,80}\bevidence_refs?\b[\s\S]{0,120}\b(?:fail|fails|rejected?|invalid|closed)\b|\bevidence_refs?\b[\s\S]{0,80}\b(?:empty|\[\]|zero)\b[\s\S]{0,120}\b(?:fail|fails|rejected?|invalid|closed)\b", re.I)
GRADE_AGENT_MISSING_EVIDENCE_REF_FAIL=re.compile(r"\b(?:missing|null|absent|omitted)\b[\s\S]{0,80}\bevidence_refs?\b[\s\S]{0,120}\b(?:fail|fails|rejected?|invalid|closed)\b|\bevidence_refs?\b[\s\S]{0,80}\b(?:missing|null|absent|omitted)\b[\s\S]{0,120}\b(?:fail|fails|rejected?|invalid|closed)\b", re.I)
GRADE_AGENT_HARD_GATE_DEFAULT_CLOSED=re.compile(r"\bhard[-_\s]?gate\b[\s\S]{0,120}\bdefault(?:s|ed)?\b[\s\S]{0,120}\b(?:false|closed|fail|fails|reject)\b|\bdefault(?:s|ed)?\b[\s\S]{0,120}\bhard[-_\s]?gate\b[\s\S]{0,120}\b(?:false|closed|fail|fails|reject)\b", re.I)
GRADE_AGENT_FABRICATED_TRACE_REF_REJECTED=re.compile(r"\b(?:self[-_\s]?fabricated|fabricated|synthetic|made[-_\s]?up)\b[\s\S]{0,120}\btrace_ref\b[\s\S]{0,160}\b(?:not\s+acceptable|not\s+accepted|rejected?|invalid|cannot|must\s+not)\b|\btrace_ref\b[\s\S]{0,120}\b(?:only|sole)\b[\s\S]{0,80}\bevidence_refs?\b[\s\S]{0,120}\b(?:not\s+acceptable|rejected?|invalid|cannot|must\s+not)\b", re.I)
GRADE_AGENT_REQUIRED_EXIT_NON_DEFAULT=re.compile(r"\brequired_exit_code\s*[:=]\s*(?![\"']?0[\"']?\b)[\"']?-?\d+\b|\bnon[-_\s]?default\b[\s\S]{0,80}\brequired_exit_code\b|\brequired_exit_code\b[\s\S]{0,80}\bnon[-_\s]?default\b", re.I)
GRADE_AGENT_PER_ACCEPTANCE_CWD=re.compile(r"\bper[-_\s]?acceptance\b[\s\S]{0,120}\bcwd\b|\bcwd\s*[:=]\s*[\"'][^\"']+[\"']", re.I)
GRADE_AGENT_MIN_SIZE_BYTES=re.compile(r"\bmin_size_bytes\s*[:=]\s*\d+\b", re.I)
GRADE_AGENT_REJECTED_CRITIC_FIXTURE=re.compile(r"\b(?:seeded[-_\s]?pass|naked[-_\s]?verdict)\b[\s\S]{0,180}\bcritic\b[\s\S]{0,180}\b(?:reject(?:s|ed)?|approved\s*[:=]\s*false|verdict\s*[:=]\s*rejected)\b|\bcritic\b[\s\S]{0,180}\b(?:seeded[-_\s]?pass|naked[-_\s]?verdict)\b[\s\S]{0,180}\b(?:reject(?:s|ed)?|approved\s*[:=]\s*false|verdict\s*[:=]\s*rejected)\b", re.I)
EVOLVE_AGENT_PRIMARY_TASK_TOKENS=re.compile(r"\bM7\s+Evolve\s+Agent\b|\bEvolve\s+Agent\b|\bcrates/symphony-evolve\b|\bsymphony\s+evolve\b|docs/agents/evolve/AGENT\.md", re.I)
EVOLVE_METADATA_CLAIM=re.compile(r"\bD-P21\b|\bmetadata\s+complete(?:ness)?\b|\bcomplete\s+D-P21\s+metadata\b|\bfull\s+metadata\b|\bcommit_hash\b|\brevert_hint\b", re.I)
EVOLVE_REAL_COMMIT_HASH_RE=re.compile(r"\bcommit_hash\s*[:=]\s*[\"']?(?!pending\b)[0-9a-f]{7,40}[\"']?\b|\bcommit_hash\b[\s\S]{0,160}\b(?:patched|updated|replaced|read\s*back|readback)\b[\s\S]{0,160}\bpending\b[\s\S]{0,120}\b[0-9a-f]{7,40}\b|\bpending\b[\s\S]{0,120}(?:->|→|to)\s*[0-9a-f]{7,40}\b", re.I)
EVOLVE_POST_COMMIT_READBACK_RE=re.compile(r"\bpost[-_\s]?commit\b[\s\S]{0,120}\b(?:read[-_\s]?back|readback|re[-_\s]?open(?:ed)?|reload(?:ed)?|verify|verified)\b|\b(?:read[-_\s]?back|readback|re[-_\s]?open(?:ed)?|reload(?:ed)?)\b[\s\S]{0,120}\bafter\b[\s\S]{0,80}\bgit\s+commit\b", re.I)
EVOLVE_REVERT_HINT_REAL_COMMIT_RE=re.compile(r"\brevert_hint\s*[:=][^\n]{0,120}\bgit\s+revert\s+[0-9a-f]{7,40}\b|\bgit\s+revert\s+[0-9a-f]{7,40}\b[\s\S]{0,120}\brevert_hint\b", re.I)
EVOLVE_L2_METADATA_RE=re.compile(r"\b(?:L2|pattern(?:s)?(?:-pending)?|PROPOSAL\.md|skill)\b[\s\S]{0,220}\b(?:D-P21|metadata)\b[\s\S]{0,220}\b(?:commit_hash|revert_hint|source_run_ids?|validation|owner_scope)\b|\b(?:D-P21|metadata)\b[\s\S]{0,220}\b(?:L2|pattern(?:s)?(?:-pending)?|PROPOSAL\.md|skill)\b[\s\S]{0,220}\b(?:commit_hash|revert_hint|source_run_ids?|validation|owner_scope)\b", re.I)
EVOLVE_CRITIC_PREFILTER_CLAIM=re.compile(r"\bevolve[-_\s]?critic\b|\bcritic[_\s-]?review\b|\bmechanical[-_\s]?pre[-_\s]?filter\b|\bpre[-_\s]?filter\b|\bcritic\b[\s\S]{0,80}\b(?:approved|pass|passes|verdict)\b", re.I)
EVOLVE_GRADE_COMPLETED_TRACE_RE=re.compile(r"\bgrade_completed\b[\s\S]{0,180}\b(?:trace(?:ability|_ref)?|source(?:_run)?|run_ids?|grade_result|evidence_refs?|handoff|overall_status|evolve_handoff_status)\b|\b(?:trace(?:ability|_ref)?|source(?:_run)?|run_ids?|grade_result|evidence_refs?|handoff|overall_status|evolve_handoff_status)\b[\s\S]{0,180}\bgrade_completed\b", re.I)
EVOLVE_VALIDATION_ANCHOR_BLACKLIST_RE=re.compile(r"\bvalidation\b[\s\S]{0,160}\b(?:observable[-_\s]?anchor|anchor)\b[\s\S]{0,160}\b(?:blacklist|template[-_\s]?blacklist|generic[-_\s]?template)\b|\b(?:blacklist|template[-_\s]?blacklist|generic[-_\s]?template)\b[\s\S]{0,160}\bvalidation\b[\s\S]{0,160}\b(?:observable[-_\s]?anchor|anchor)\b", re.I)
EVOLVE_GRADE_CONSISTENCY_RE=re.compile(r"\bgrade[-_\s]?consistency\b|\b(?:grade_status|grade_handoff_status|overall_status|grade_pass|grade_fail)\b[\s\S]{0,160}\b(?:consistent|consistency|matches?|aligns?|cross[-_\s]?checks?|rejects?)\b|\b(?:consistent|consistency|matches?|aligns?|cross[-_\s]?checks?|rejects?)\b[\s\S]{0,160}\b(?:grade_status|grade_handoff_status|overall_status|grade_pass|grade_fail)\b", re.I)
EVOLVE_PER_CANDIDATE_VERDICT_RE=re.compile(r"\bper[-_\s]?candidate\b[\s\S]{0,160}\b(?:structured\s+)?verdict\b|\b(?:candidate_id|candidate)\b[\s\S]{0,100}\b(?:structured\s+)?verdict\b|\bevolve_critic_verdict\b", re.I)
EVOLVE_WRITE_GIT_LOG_CLAIM=re.compile(r"\bevolve[-_\s]?log\b|\bmemory[-_\s]?artifact\b|\bnon[-_\s]?git[-_\s]?surfaces?\b|\bD-T1\b|\bwrite[-_\s]?with[-_\s]?git\b|\bgit[-_\s]?commit\b|\bcommit_hash\b", re.I)
EVOLVE_LOG_TERMS=re.compile(r"\bevolve[-_\s]?log\b|\.symphony/evolve-log\b", re.I)
EVOLVE_GIT_COMMIT_TERMS=re.compile(r"\bwrite[-_\s]?with[-_\s]?git\b|\bgit\s+commit\b|\bgit[-_\s]?committed\b|\bcommitted\b|\bcommit_hash\b", re.I)
EVOLVE_MEMORY_ARTIFACT_GIT_RE=re.compile(r"\b(?:every|each|all)\b[\s\S]{0,120}\b(?:memory[-_\s]?artifact|L1|L2|artifact|memory/|patterns/|patterns-pending)\b[\s\S]{0,160}\b(?:write[-_\s]?with[-_\s]?git|git\s+commit|committed|commit_hash)\b|\b(?:memory[-_\s]?artifact|L1|L2|artifact|memory/|patterns/|patterns-pending)\b[\s\S]{0,160}\b(?:every|each|all)\b[\s\S]{0,120}\b(?:write[-_\s]?with[-_\s]?git|git\s+commit|committed|commit_hash)\b", re.I)
EVOLVE_LOG_REAL_COUNTS_RE=re.compile(r"\bcounts?\b[\s\S]{0,160}\b(?:total_candidates|l1_written|l2_written|l1_proposed|l2_proposed)\b[\s\S]{0,180}\b(?:real|actual|candidate\s+writes?|non[-_\s]?zero|[1-9]\d*|invariant|matches?)\b|\b(?:total_candidates|l1_written|l2_written|l1_proposed|l2_proposed)\b[\s\S]{0,160}\b(?:real|actual|candidate\s+writes?|non[-_\s]?zero|[1-9]\d*|invariant|matches?)\b", re.I)
EVOLVE_LIGHTWEIGHT_CLAIM=re.compile(r"\bL0\.?5\b|\blightweight[-_\s]?memory\b|\bRecent\s+Runs\b|\brecent-runs\b|\binline[-_\s]?write\b|\bMEMORY\.md\b", re.I)
EVOLVE_RECENT_RUNS_GIT_COMMIT_RE=re.compile(r"\b(?:Recent\s+Runs|recent-runs|MEMORY\.md)\b[\s\S]{0,160}\b(?:git\s+commit|committed|commit_hash|chore\(memory\):\s*index)\b|\b(?:git\s+commit|committed|commit_hash|chore\(memory\):\s*index)\b[\s\S]{0,160}\b(?:Recent\s+Runs|recent-runs|MEMORY\.md)\b", re.I)
EVOLVE_RECENT_RUNS_IDEMPOTENCE_RE=re.compile(r"\b(?:idempotent|idempotence|replay|re-run|rerun|same\s+digest|duplicate)\b[\s\S]{0,180}\b(?:Recent\s+Runs|recent-runs|MEMORY\.md|line|digest)\b[\s\S]{0,120}\b(?:no\s+duplicate|dedup|does\s+not\s+duplicate|single\s+line|one\s+line|unchanged)\b|\b(?:Recent\s+Runs|recent-runs|MEMORY\.md|line|digest)\b[\s\S]{0,180}\b(?:same\s+digest|replay|rerun|idempotent|idempotence)\b[\s\S]{0,120}\b(?:no\s+duplicate|dedup|does\s+not\s+duplicate|single\s+line|one\s+line|unchanged)\b", re.I)
FRONTEND_PRIMARY_TASK_TOKENS=re.compile(r"\bUI[-_\s]?M0\b|\bfrontend\b|\bwebview\b|\bTauri\b|\bReact\b|\bVite\b|\bTypeScript\b|\bEventSource\b|\buseSyncExternalStore\b|\bZustand\b|apps/[A-Za-z0-9_.-]*-ui(?:/|\b)|(?:^|[^\w.-])package\.json\b|(?:^|[^\w.-])pnpm-lock\.yaml\b|vite\.config\.(?:ts|js|mts|mjs)\b|src/[^\s`'\"|]+\.tsx\b|\.tsx\b", re.I)
FRONTEND_SSE_SCOPE_TERMS=re.compile(r"\bSSE\b|\bEventSource\b|\bheartbeat\b|\bconnected[-_\s]?event\b", re.I)
FRONTEND_SSE_OLD_SOURCE_CLOSE=re.compile(r"\b(?:old|previous|prior|stale|existing)\b[^.;\n]{0,80}\b(?:EventSource|source|connection)\b[^.;\n]{0,80}\b(?:close|dispose|abort|cleanup)|\b(?:close|dispose|abort|cleanup)\b[^.;\n]{0,80}\b(?:old|previous|prior|stale|existing)\b[^.;\n]{0,80}\b(?:EventSource|source|connection)\b|\.close\(\)", re.I)
FRONTEND_SSE_NEW_SOURCE_CREATION=re.compile(r"\b(?:new|second|fresh|recreated?|re-open(?:ed)?|create(?:d)?\s+again|factory\s+(?:called|invoked)\s+again|called\s+(?:twice|2x))\b[^.;\n]{0,100}\b(?:EventSource|source|connection|factory)\b|\b(?:EventSource|source|connection|factory)\b[^.;\n]{0,100}\b(?:new|second|fresh|recreated?|again|called\s+(?:twice|2x))\b", re.I)
FRONTEND_SSE_STALE_OLD_EVENTS_REJECTED=re.compile(r"\b(?:stale|old|previous|prior)\b[^.;\n]{0,80}\b(?:event|message|connected)\b[^.;\n]{0,120}\b(?:ignored|rejected|cannot|can't|must\s+not|not\s+accepted|does\s+not\s+satisfy|cannot\s+satisfy)\b|\b(?:ignored|rejected|not\s+accepted)\b[^.;\n]{0,80}\b(?:stale|old|previous|prior)\b[^.;\n]{0,80}\b(?:event|message|connected)\b", re.I)
FRONTEND_SSE_FULL_GET_REFRESH=re.compile(r"\bGET\s+/api/v1/state\b|\bfull[-_\s]?(?:state[-_\s]?)?refresh\b|\brefresh\(\)\b[^.;\n]{0,120}\b(?:reconnect|new\s+connection|EventSource)\b", re.I)
FRONTEND_SSE_SNAPSHOT_WRITES_DISABLED=re.compile(r"\bsnapshot\b[^.;\n]{0,100}\b(?:retained|preserved|not\s+cleared|never\s+blank(?:ed|s)?|never\s+cleared)\b[^.;\n]{0,120}\b(?:writesDisabled|writes\s+disabled|blocks?\s+writes|write\s+commands?\s+disabled)\b|\b(?:writesDisabled|writes\s+disabled|blocks?\s+writes|write\s+commands?\s+disabled)\b[^.;\n]{0,120}\bsnapshot\b[^.;\n]{0,100}\b(?:retained|preserved|not\s+cleared|never\s+blank(?:ed|s)?|never\s+cleared)\b", re.I)
FRONTEND_IDENTITY_SCOPE_TERMS=re.compile(r"\bidentity\b|\binstance[-_\s]?id\b|\bX-Symphony-Instance-Id\b|\bstale[-_\s]?daemon\b", re.I)
FRONTEND_IDENTITY_MISMATCH_TERMS=re.compile(r"\bmismatch(?:ed|es)?\b|\bdifferent\b|\bchanged\b|\bstale[-_\s]?daemon\b", re.I)
FRONTEND_IDENTITY_RESPONSE_REJECTED=re.compile(r"\b(?:mismatch(?:ed)?|stale[-_\s]?daemon|wrong\s+instance|different\s+instance)\b[^.;\n]{0,100}\b(?:response|HTTP|data|payload)\b[^.;\n]{0,140}\b(?:reject(?:ed|s)?|throw(?:s|n)?|no\s+data\s+acceptance|not\s+accepted|ignored)\b|\b(?:reject(?:ed|s)?|throw(?:s|n)?|no\s+data\s+acceptance|not\s+accepted|ignored)\b[^.;\n]{0,100}\b(?:mismatch(?:ed)?|stale[-_\s]?daemon|wrong\s+instance|different\s+instance)\b[^.;\n]{0,100}\b(?:response|HTTP|data|payload)\b", re.I)
FRONTEND_IDENTITY_CALLBACK_ONLY_INSUFFICIENT=re.compile(r"\bcallback[-_\s]?only\b[^.;\n]{0,120}\b(?:insufficient|not\s+enough|does\s+not\s+prove|cannot\s+prove|not\s+accepted)\b|\b(?:side[-_\s]?effect|callback)\b[^.;\n]{0,80}\b(?:only|alone)\b[^.;\n]{0,120}\b(?:insufficient|not\s+enough|does\s+not\s+prove|cannot\s+prove|not\s+accepted)\b", re.I)
FRONTEND_IDENTITY_MATCH_BEFORE_CONNECTED=re.compile(r"\b(?:connected\(\)|connected|write(?:s)?\s+re[-_\s]?enable|re[-_\s]?enable(?:s|d)?\s+writes|writesDisabled\s*[:=]\s*false)\b[^.;\n]{0,160}\b(?:until|after|only\s+after)\b[^.;\n]{0,120}\b(?:fresh|new)\b[^.;\n]{0,80}\b(?:matching|same|matched)\b[^.;\n]{0,80}\b(?:identity|instance[-_\s]?id)\b|\b(?:no|not)\b[^.;\n]{0,80}\b(?:connected\(\)|connected|write(?:s)?\s+re[-_\s]?enable|re[-_\s]?enable(?:s|d)?\s+writes)\b[^.;\n]{0,160}\b(?:fresh|new)\b[^.;\n]{0,80}\b(?:matching|matched)\b[^.;\n]{0,80}\b(?:identity|instance[-_\s]?id)\b", re.I)
FRONTEND_IDENTITY_SSE_CONNECTED_MISMATCH_REJECTED=re.compile(r"\bSSE\b[^.;\n]{0,80}\bconnected\b[^.;\n]{0,120}\b(?:mismatch(?:ed)?|different|wrong)\b[^.;\n]{0,80}\b(?:identity|instance[-_\s]?id)\b[^.;\n]{0,140}\b(?:not\s+accepted|rejected|ignored|not\s+success|cannot\s+succeed|does\s+not\s+succeed)\b|\bconnected\b[^.;\n]{0,80}\b(?:event)?\b[^.;\n]{0,120}\b(?:mismatch(?:ed)?|different|wrong)\b[^.;\n]{0,80}\b(?:identity|instance[-_\s]?id)\b[^.;\n]{0,140}\b(?:not\s+accepted|rejected|ignored|not\s+success|cannot\s+succeed|does\s+not\s+succeed)\b", re.I)
EXACT_VERSION_RE=re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
class LintError(ValueError): pass

def split_top_level(text, sep=','):
    parts=[]; cur=[]; depth=0; quote=''
    for ch in text:
        if quote:
            cur.append(ch)
            if ch==quote: quote=''
            continue
        if ch in ('"', "'"):
            quote=ch; cur.append(ch); continue
        if ch in '[{(': depth+=1
        elif ch in ']})' and depth>0: depth-=1
        if ch==sep and depth==0:
            parts.append(''.join(cur).strip()); cur=[]
        else:
            cur.append(ch)
    if cur or text.strip(): parts.append(''.join(cur).strip())
    return parts

def parse_scalar(value):
    value=value.strip()
    if value in ('', 'null', 'Null', 'NULL', '~'): return None
    if value in ('true','True','TRUE'): return True
    if value in ('false','False','FALSE'): return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith('{') and value.endswith('}'):
        out={}
        inner=value[1:-1].strip()
        if not inner: return out
        for part in split_top_level(inner):
            if ':' not in part: raise LintError(f'malformed inline mapping item: {part}')
            k,v=part.split(':',1); out[k.strip()]=parse_scalar(v)
        return out
    if value.startswith('[') and value.endswith(']'):
        inner=value[1:-1].strip()
        return [] if not inner else [parse_scalar(part) for part in split_top_level(inner)]
    if re.fullmatch(r'-?\d+', value):
        return int(value)
    return value


def is_block_scalar(value):
    return value in {'>', '>-', '>+', '|', '|-', '|+'}

def parse_block_scalar(lines, start, parent_indent, marker):
    collected=[]; i=start
    while i<len(lines):
        if not lines[i].strip():
            collected.append(''); i+=1; continue
        cur_indent=indent_of(lines[i])
        if cur_indent<=parent_indent: break
        collected.append(lines[i].strip())
        i+=1
    if marker.startswith('>'):
        return ' '.join(part for part in collected if part), i
    return '\n'.join(collected), i

def indent_of(line):
    return len(line)-len(line.lstrip(' '))

def next_content(lines, start):
    i=start
    while i<len(lines) and not lines[i].strip(): i+=1
    return i

def parse_key_value(content):
    if ':' not in content: raise LintError(f'malformed yaml line: {content}')
    key,value=content.split(':',1)
    return key.strip(), value.strip()

def parse_mapping(lines, start, indent):
    out={}; i=start
    while i<len(lines):
        if not lines[i].strip(): i+=1; continue
        cur_indent=indent_of(lines[i])
        if cur_indent<indent: break
        if cur_indent>indent: break
        content=lines[i].strip()
        if content.startswith('- '): break
        key,value=parse_key_value(content)
        if value:
            if is_block_scalar(value):
                out[key], i = parse_block_scalar(lines, i+1, cur_indent, value)
            else:
                out[key]=parse_scalar(value); i+=1
            continue
        j=next_content(lines,i+1)
        if j>=len(lines) or indent_of(lines[j])<=cur_indent:
            out[key]=None; i=i+1; continue
        if lines[j].strip().startswith('- '):
            out[key],i=parse_list(lines,j,indent_of(lines[j]))
        else:
            out[key],i=parse_mapping(lines,j,indent_of(lines[j]))
    return out,i

def parse_list(lines, start, indent):
    out=[]; i=start
    while i<len(lines):
        if not lines[i].strip(): i+=1; continue
        cur_indent=indent_of(lines[i])
        if cur_indent<indent: break
        if cur_indent!=indent or not lines[i].strip().startswith('- '): break
        item=lines[i].strip()[2:].strip()
        if not item:
            parsed,i=parse_mapping(lines,next_content(lines,i+1),indent+2)
            out.append(parsed); continue
        if item.startswith('{') and item.endswith('}'):
            out.append(parse_scalar(item)); i+=1; continue
        if ':' in item:
            key,value=parse_key_value(item)
            if value and is_block_scalar(value):
                parsed_value, next_i = parse_block_scalar(lines, i+1, cur_indent, value)
                out.append({key: parsed_value})
                i = next_i
                continue
            row={key: parse_scalar(value) if value else None}
            j=next_content(lines,i+1)
            if j<len(lines) and indent_of(lines[j])>cur_indent and not lines[j].strip().startswith('- '):
                extra,i=parse_mapping(lines,j,indent_of(lines[j]))
                row.update(extra)
            else:
                i+=1
            out.append(row); continue
        out.append(parse_scalar(item)); i+=1
    return out,i

def parse_yaml_fence(fence_lines):
    if yaml is not None:
        text = '\n'.join(fence_lines)
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            # Backward compatibility: older Grade artifacts sometimes used
            # unquoted prose scalars containing ": ". Prefer PyYAML for valid
            # YAML, but fall back to the legacy permissive parser for those
            # artifacts instead of failing before lint semantics can run.
            pass
    lines=[line.rstrip() for line in fence_lines]
    start=next_content(lines,0)
    if start>=len(lines): return None
    if lines[start].strip().startswith('- '):
        data,_=parse_list(lines,start,indent_of(lines[start]))
        return data
    data,_=parse_mapping(lines,start,indent_of(lines[start]))
    return data

def parse_front_matter(lines):
    if not lines or lines[0].strip()!='---':
        return None, 0
    j=1
    while j<len(lines) and lines[j].strip()!='---':
        j+=1
    if j>=len(lines):
        return None, 0
    data=parse_yaml_fence(lines[1:j])
    return data, j+1

def blocks(path:Path, *, include_front_matter=False)->list[dict[str,Any]]:
    if not path.exists(): raise LintError(f"file missing: {path}")
    out=[]; lines=path.read_text(encoding='utf-8').splitlines(); i=0
    if include_front_matter:
        data,next_i=parse_front_matter(lines)
        if isinstance(data,dict):
            out.append(data)
            i=next_i
    while i<len(lines):
        if lines[i].strip() in {'```yaml','```yml'}:
            j=i+1
            while j<len(lines) and lines[j].strip()!='```': j+=1
            if j>=len(lines): raise LintError(f"unterminated yaml fence in {path}")
            data=parse_yaml_fence(lines[i+1:j])
            if isinstance(data,dict): out.append(data)
            i=j
        i+=1
    return out
def first(bs,key):
    return next((b[key] for b in bs if key in b), None)
def nni(v): return isinstance(v,int) and not isinstance(v,bool) and v>=0
def is_gate(t,r): return t=='code' and r in {'medium','high'}
def strs(v): return [v] if isinstance(v,str) else (v if isinstance(v,list) and all(isinstance(x,str) for x in v) else [])
def sev(row):
    if not isinstance(row,dict): return None
    v=row.get('severity') or row.get('severity_if_fail')
    return v if v in {'P0','P1','P2'} else None
def has_ref(row):
    return any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('evidence_ref','acceptance_id','acceptance_ref','tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref'))
def has_tracked_waiver_or_scope_basis(row):
    return any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref','scope_basis_ref'))
def text_values(value):
    if isinstance(value,str):
        return [value]
    if isinstance(value,dict):
        out=[]
        for k,v in value.items():
            if isinstance(k,str): out.append(k)
            out.extend(text_values(v))
        return out
    if isinstance(value,list):
        out=[]
        for item in value: out.extend(text_values(item))
        return out
    return []
def text_blob(*values):
    return ' '.join(text_values(list(values)))
def row_surfaces(row):
    if not isinstance(row,dict): return set()
    return set(strs(row.get('surface'))+strs(row.get('surfaces')))
def evidence_kind(row):
    return row.get('evidence_kind') if isinstance(row.get('evidence_kind'),str) else ''
def references_any_id(row, ids):
    blob=text_blob(row)
    return any(re.search(rf"(?<![A-Za-z0-9_-]){re.escape(item)}(?![A-Za-z0-9_-])", blob) for item in ids)
def method_is_mere_grep(row):
    for k in ('method','evidence_method','audit_method'):
        v=row.get(k)
        if isinstance(v,str) and re.search(r"^(grep|regex|search)$|\b(mere|only|just)\s+grep\b|\bgrep\s+only\b", v.strip(), re.I):
            return True
    for k in ('evidence_ref','evidence_summary','evidence_note','summary','note'):
        v=row.get(k)
        if isinstance(v,str) and re.search(r"grep\s+(?:-[A-Za-z]*R|-[A-Za-z]+)|\bgrep\b.*\b(?:no hits|found no hits|only|mere)\b|\b(?:no hits|found no hits)\b.*\bgrep\b", v, re.I):
            return True
    return False
def validate_required(summary, acceptance, errors):
    if not isinstance(summary,dict): errors.append('missing or malformed grade_summary block')
    else:
        for k in ('p0_count','p1_count','p2_count'):
            if not nni(summary.get(k)): errors.append(f'grade_summary.{k} must be a non-negative integer')
    if not isinstance(acceptance,list): errors.append('missing or malformed acceptance_status block'); return
    for i,row in enumerate(acceptance):
        if not isinstance(row,dict): errors.append(f'acceptance_status[{i}] must be an object'); continue
        if not isinstance(row.get('id'),str) or not row.get('id'): errors.append(f'acceptance_status[{i}].id is required')
        if row.get('status') not in {'pass','fail'}: errors.append(f'acceptance_status[{i}].status must be pass|fail')
        if row.get('status')=='fail' and row.get('severity') not in {'P0','P1','P2'}: errors.append(f'acceptance_status[{i}].severity is required for fail')
def adversarial_acceptance_metadata(bs):
    meta={}
    adv=first(bs,'adversarial_acceptance')
    if isinstance(adv,list):
        for row in adv:
            if isinstance(row,dict) and isinstance(row.get('id'),str) and row.get('id'):
                meta[row['id']]={'severity':row.get('severity'),'surfaces':row_surfaces(row),'text':text_blob(row),'row':row}
    return meta
def validate_outcome(bs,errors):
    rs=first(bs,'risk_surface'); adv=first(bs,'adversarial_acceptance')
    if not isinstance(rs,dict): errors.append('medium/high code outcome missing parseable risk_surface block'); return
    surfaces=rs.get('surfaces')
    if not isinstance(surfaces,dict): errors.append('risk_surface.surfaces must be a mapping'); return
    present=set()
    for name,detail in surfaces.items():
        if name not in SURFACES: continue
        if detail is True or (isinstance(detail,dict) and detail.get('present') is True): present.add(name)
        if isinstance(detail,dict) and detail.get('not_applicable') is True and not detail.get('reason'): errors.append(f'risk_surface.surfaces.{name} not_applicable requires reason')
    if present and (not isinstance(adv,list) or not adv): errors.append('medium/high code outcome with present risk surfaces requires adversarial_acceptance entries'); return
    covered=set()
    if isinstance(adv,list):
        for i,row in enumerate(adv):
            if not isinstance(row,dict): errors.append(f'adversarial_acceptance[{i}] must be an object'); continue
            row_id=row.get('id')
            row_sev=row.get('severity')
            hint=row.get('verification_hint')
            if not isinstance(row_id,str) or not row_id: errors.append(f'adversarial_acceptance[{i}].id is required')
            if row_sev not in {'P0','P1','P2'}: errors.append(f'adversarial_acceptance[{i}].severity must be P0|P1|P2')
            surfaces_for_row=row_surfaces(row)
            covered.update(surfaces_for_row & present)
            if not isinstance(hint,str) or not hint.strip(): errors.append(f'adversarial_acceptance[{i}].verification_hint is required')
            elif row_sev in BLOCKING:
                for pattern,label in OPTIONAL_CURRENT_HINT_PATTERNS:
                    if pattern.search(hint):
                        errors.append(f'adversarial_acceptance[{i}] {row_id} P0/P1 verification_hint makes current validation optional via {label} wording')
                        break
            row_text=text_blob(row)
            if BOUNDARY_TERMS.search(row_text) and not (surfaces_for_row & BOUNDARY_SURFACES):
                errors.append(f'adversarial_acceptance[{i}] {row_id} boundary/input risk must use string_boundary or input_validation_or_schema surface')
    missing=sorted(present-covered)
    if missing: errors.append('present risk surfaces without adversarial_acceptance coverage: '+','.join(missing))

def adversarial_acceptance_ids(outcome_file: Path) -> set[str]:
    return set(adversarial_acceptance_metadata(blocks(outcome_file)))

def outcome_acceptance_metadata(bs):
    meta={}
    acc=first(bs,'acceptance')
    if isinstance(acc,list):
        for row in acc:
            if isinstance(row,dict) and isinstance(row.get('id'),str) and row.get('id'):
                meta[row['id']]={'severity':row.get('severity'),'text':text_blob(row),'row':row}
    return meta

def strip_markdown_cell(text):
    text=re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text or '')
    return text.replace('**','').replace('__','').replace('<br>',' ').strip()

def split_markdown_row(line):
    if not line.lstrip().startswith('|'): return []
    body=line.strip().strip('|')
    return [strip_markdown_cell(cell) for cell in body.split('|')]

def markdown_acceptance_metadata(path: Path):
    try:
        lines=path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return {}
    meta={}; i=0
    while i<len(lines)-1:
        header=split_markdown_row(lines[i])
        lower=[cell.lower() for cell in header]
        if {'id','acceptance','severity'}.issubset(set(lower)):
            idx_id=lower.index('id'); idx_text=lower.index('acceptance'); idx_sev=lower.index('severity')
            i+=2
            while i<len(lines) and lines[i].lstrip().startswith('|'):
                cells=split_markdown_row(lines[i])
                if len(cells)>max(idx_id,idx_text,idx_sev):
                    row_id=cells[idx_id].strip()
                    severity=cells[idx_sev].strip()
                    if row_id and severity in {'P0','P1','P2'}:
                        meta[row_id]={'severity':severity,'text':cells[idx_text],'row':{'id':row_id,'severity':severity,'statement':cells[idx_text]}}
                i+=1
            continue
        i+=1
    return meta

def markdown_bullet_acceptance_metadata(path: Path):
    try:
        lines=path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return {}
    meta={}; i=0
    bullet=re.compile(r"^\s*-\s+\*\*(?P<id>[A-Za-z0-9][A-Za-z0-9_-]+)\b[^*]*\*\*:\s*(?P<text>.*)$")
    while i<len(lines):
        m=bullet.match(lines[i])
        if not m:
            i+=1
            continue
        row_id=m.group('id')
        parts=[strip_markdown_cell(m.group('text'))]
        i+=1
        while i<len(lines):
            line=lines[i]
            if not line.strip() or line.lstrip().startswith(('- **','```')):
                break
            if line.startswith((' ', '\t')):
                parts.append(strip_markdown_cell(line))
                i+=1
                continue
            break
        meta[row_id]={'text':' '.join(part for part in parts if part),'row':{'id':row_id,'statement':' '.join(part for part in parts if part)}}
    return meta

def outcome_acceptance_metadata_from_file(bs, path: Path):
    meta=outcome_acceptance_metadata(bs)
    return meta or markdown_acceptance_metadata(path)

def acceptance_status_metadata(acceptance):
    meta={}
    if isinstance(acceptance,list):
        for row in acceptance:
            if isinstance(row,dict) and isinstance(row.get('id'),str) and row.get('id'):
                meta[row['id']]={'severity':row.get('severity'),'text':text_blob(row),'row':row}
    return meta

def row_acceptance_ref(row):
    if not isinstance(row,dict): return ''
    for k in ('acceptance_id','acceptance_ref','id'):
        v=row.get(k)
        if isinstance(v,str) and v.strip(): return v.strip()
    return ''

def list_of_strs(value):
    return isinstance(value,list) and all(isinstance(x,str) and x.strip() for x in value)

def outcome_dependency_terms(required_acceptance):
    blob=text_blob([v.get('text','') for v in required_acceptance.values()])
    return bool(re.search(r"\b(dependenc(?:y|ies)|crate|package|cargo|npm|pip|go\.mod|version|lock(?:ed)?|Cargo\.toml|Cargo\.lock|forbidden\s+dependency|no\s+new\s+dependency)\b", blob, re.I))

def has_path_root_obligation(meta):
    text=meta.get('text','') if isinstance(meta,dict) else ''
    return bool(PATH_ROOT_TERMS.search(text) and PATH_ACCESS_TERMS.search(text))

def has_request_target_obligation(meta):
    text=meta.get('text','') if isinstance(meta,dict) else ''
    return bool(REQUEST_TARGET_TERMS.search(text))

def negative_rows_for_acceptance(neg, acceptance_id):
    return [row for row in neg if isinstance(row,dict) and row_acceptance_ref(row)==acceptance_id]

def row_evidence_text(rows):
    evidence_fields=('scenario','evidence_ref','evidence_refs','evidence_kind','method','evidence_method','audit_method','evidence_summary','summary','note','details','rationale')
    values=[]
    for row in rows:
        if isinstance(row,dict):
            values.extend(row.get(field) for field in evidence_fields if field in row)
    return text_blob(values)

def subprocess_lifecycle_evidence_text(rows):
    evidence_fields=('evidence_ref','evidence_refs','method','evidence_method','audit_method','evidence_summary','summary','note','details','rationale')
    values=[]
    for row in rows:
        if isinstance(row,dict):
            values.extend(row.get(field) for field in evidence_fields if field in row)
    return text_blob(values)

def subprocess_lifecycle_kind_in_scope(rows):
    return any(isinstance(row,dict) and evidence_kind(row)==SUBPROCESS_LIFECYCLE_EVIDENCE_KIND for row in rows)

def is_dependency_compliance_claim(text):
    leading=re.sub(r"\s+"," ", text or "").strip()[:260]
    return bool(SUBPROCESS_DEPENDENCY_COMPLIANCE_CLAIM_TERMS.search(leading))

def has_vendor_command_probe_scope(text):
    text=text or ''
    if not has_non_negated_scope_term(SUBPROCESS_PROBE_SCOPE_TERMS, text):
        return False
    if SUBPROCESS_PROBE_HTTP_CONTEXT.search(text):
        return False
    return bool(SUBPROCESS_PROBE_VENDOR_CONTEXT.search(text))

def subprocess_lifecycle_claim_in_scope(text):
    if is_dependency_compliance_claim(text):
        return False
    if has_non_negated_scope_term(SUBPROCESS_LIFECYCLE_STRONG_SCOPE_TERMS, text):
        return True
    return has_vendor_command_probe_scope(text)

def subprocess_lifecycle_missing_facets(claim_text, evidence_text, *, kind_in_scope=False):
    if not kind_in_scope and not subprocess_lifecycle_claim_in_scope(claim_text):
        return []
    facets=(
        ('timeout', SUBPROCESS_TIMEOUT_FACET),
        ('process_group', SUBPROCESS_PROCESS_GROUP_FACET),
        ('reap', SUBPROCESS_REAP_FACET),
    )
    missing=[name for name,pattern in facets if not has_non_negated_scope_term(pattern, evidence_text)]
    if has_non_negated_scope_term(SUBPROCESS_STREAM_TERMS, claim_text) and not has_non_negated_scope_term(SUBPROCESS_STREAM_JOIN_FACET, evidence_text):
        missing.append('stream_join')
    if has_non_negated_scope_term(SUBPROCESS_DESCENDANT_CLAIM_TERMS, claim_text):
        if not has_non_negated_scope_term(SUBPROCESS_DESCENDANT_ESCAPE_FIXTURE, evidence_text):
            missing.append('descendant_escape_fixture')
        if not has_non_negated_scope_term(SUBPROCESS_DESCENDANT_AUDIT_FACET, evidence_text):
            missing.append('descendant_audit_or_tree_containment')
    return missing

def validate_subprocess_lifecycle_evidence(item_id, claim_text, evidence_text, errors, *, kind_in_scope=False):
    missing=subprocess_lifecycle_missing_facets(claim_text, evidence_text, kind_in_scope=kind_in_scope)
    if missing:
        errors.append(f"subprocess_lifecycle[{item_id}] missing facets: {','.join(missing)} — probe/stream subprocess surfaces require timeout + process-group + wait/reap (+ stream-task join) evidence")

def rpc_cleanup_claimed(text):
    if has_non_negated_scope_term(RPC_CLEANUP_EVERY_EXIT_CLAIM_TERMS, text):
        return True
    if has_non_negated_scope_term(RPC_CLEANUP_PAIR_TERMS, text) and has_non_negated_scope_term(RPC_CLEANUP_UNCONDITIONAL_TERMS, text):
        return True
    if has_non_negated_scope_term(RPC_CLEANUP_CLEAR_TERMS, text) and has_non_negated_scope_term(RPC_CLEANUP_ARCHIVE_TERMS, text) and has_non_negated_scope_term(RPC_CLEANUP_UNCONDITIONAL_TERMS, text):
        return True
    return False

def rpc_cleanup_negative_evidence_text(text):
    return has_non_negated_scope_term(RPC_CLEANUP_NEGATIVE_PATH_TERMS, text) and has_non_negated_scope_term(RPC_CLEANUP_ASSERTION_TERMS, text)

def rpc_cleanup_negative_evidence_in_rows(rows):
    return any(rpc_cleanup_negative_evidence_text(row_evidence_text([row])) for row in rows if isinstance(row,dict))

def row_blocking_severity(row, required_acceptance):
    rid=row_acceptance_ref(row)
    return row.get('severity_if_fail') or row.get('severity') or required_acceptance.get(rid,{}).get('severity')

def validate_rpc_cleanup_evidence(item_id, claim_text, rows, errors):
    if rpc_cleanup_claimed(claim_text) and not rpc_cleanup_negative_evidence_in_rows(rows):
        errors.append(f"rpc_cleanup[{item_id}] cleanup-on-every-exit-path claimed but no timeout/error-path cleanup evidence (negative-path test required)")

def validate_subprocess_lifecycle_acceptance_obligations(required_acceptance, rows, errors, grade_claims=None):
    grade_claims=grade_claims or {}
    by_acceptance={}
    for row in rows:
        rid=row_acceptance_ref(row)
        if rid:
            by_acceptance.setdefault(rid,[]).append(row)
    for acceptance_id, meta in sorted(required_acceptance.items()):
        if meta.get('severity') not in BLOCKING:
            continue
        related=by_acceptance.get(acceptance_id,[])
        claim_text=text_blob(meta.get('text',''), grade_claims.get(acceptance_id,{}).get('text',''), related)
        evidence_text=subprocess_lifecycle_evidence_text(related)
        validate_subprocess_lifecycle_evidence(acceptance_id, claim_text, evidence_text, errors, kind_in_scope=subprocess_lifecycle_kind_in_scope(related))

def validate_rpc_cleanup_acceptance_obligations(required_acceptance, acceptance_status, rows, errors):
    status_meta=acceptance_status_metadata(acceptance_status)
    by_acceptance={}
    for row in rows:
        rid=row_acceptance_ref(row)
        if rid:
            by_acceptance.setdefault(rid,[]).append(row)
    ids=set(required_acceptance) | set(status_meta) | set(by_acceptance)
    for acceptance_id in sorted(ids):
        related=by_acceptance.get(acceptance_id,[])
        severities=[
            required_acceptance.get(acceptance_id,{}).get('severity'),
            status_meta.get(acceptance_id,{}).get('severity'),
        ] + [row_blocking_severity(row, required_acceptance) for row in related if isinstance(row,dict)]
        if not any(severity in BLOCKING for severity in severities):
            continue
        claim_text=text_blob(
            required_acceptance.get(acceptance_id,{}).get('text',''),
            status_meta.get(acceptance_id,{}).get('text',''),
            related,
        )
        validate_rpc_cleanup_evidence(acceptance_id, claim_text, related, errors)

def event_output_names(text):
    return [name for name,pattern in EVENT_OUTPUT_PATTERNS if has_non_negated_scope_term(pattern,text)]

def canonical_event_source(raw):
    return raw.strip().strip('`"\'').strip().rstrip(':,.;').lower()

def event_source_allowed(source):
    if not source or EVENT_SOURCE_PATHLIKE.search(source):
        return False
    if source in EVENT_SOURCE_BARE:
        return True
    if '/' not in source and '.' not in source:
        return False
    parts=re.split(r"[/.]", source)
    return bool(parts and parts[0] in EVENT_SOURCE_PREFIXES and 1 < len(parts) <= 4 and all(parts))

def event_source_negated(text, start, end):
    prefix=text[max(0,start-80):start]
    suffix=text[end:end+80]
    return bool(NEGATED_SCOPE_PREFIX.search(prefix) or EVENT_SOURCE_NEGATED_SUFFIX.search(suffix))

def append_unique(seq, item):
    if item not in seq:
        seq.append(item)

def event_sources_from_segment(segment):
    sources=[]; slash_or_dot_seen=False
    for match in EVENT_SOURCE_TOKEN.finditer(segment):
        raw=None; start=end=-1
        for group in range(1,5):
            if match.group(group) is not None:
                raw=match.group(group); start,end=match.span(group); break
        source=canonical_event_source(raw or '')
        if not event_source_allowed(source) or event_source_negated(segment,start,end):
            continue
        append_unique(sources,source)
        if '/' in source or '.' in source:
            slash_or_dot_seen=True
    if slash_or_dot_seen:
        for bare in EVENT_SOURCE_BARE:
            for match in re.finditer(rf"(?<![A-Za-z0-9_]){re.escape(bare)}(?![A-Za-z0-9_])", segment, re.I):
                if not event_source_negated(segment,match.start(),match.end()):
                    append_unique(sources,bare)
    return sources

def event_source_obligations(text):
    obligations={}
    for segment in re.split(r"(?<=[.;])\s+|\n+", text or ''):
        if not has_non_negated_scope_term(EVENT_MAPPING_VERBS,segment):
            continue
        outputs=event_output_names(segment)
        if not outputs:
            continue
        sources=event_sources_from_segment(segment)
        for source in sources:
            obligations.setdefault(source,set()).update(outputs)
    return obligations

def event_source_pattern(source):
    if '/' in source or '.' in source:
        parts=[re.escape(part) for part in re.split(r"[/.]", source)]
        return re.compile(r"(?<![A-Za-z0-9])"+r"[/_.\-\s]+".join(parts)+r"(?![A-Za-z0-9])", re.I)
    return re.compile(r"(?<![A-Za-z0-9])"+re.escape(source)+r"(?![A-Za-z0-9])", re.I)

def event_evidence_chunks(text):
    return [chunk.strip() for chunk in re.split(r"\s*(?:\+|;|\n)\s*", text or '') if chunk.strip()]

def event_source_matches(source, text):
    return bool(event_source_pattern(source).search(text or ''))

def chunk_has_event_source_proof(source, outputs, all_sources, chunk):
    if not event_source_matches(source,chunk):
        return False
    matched_sources=[item for item in all_sources if event_source_matches(item,chunk)]
    if len(matched_sources)>1 and not has_non_negated_scope_term(EVENT_MULTI_SOURCE_PROOF_TERMS,chunk):
        return False
    if not has_non_negated_scope_term(EVENT_PROOF_TERMS,chunk):
        return False
    return any(pattern.search(chunk) for name,pattern in EVENT_OUTPUT_PATTERNS if name in outputs)

def event_source_has_proof(source, outputs, all_sources, evidence_text):
    return any(chunk_has_event_source_proof(source,outputs,all_sources,chunk) for chunk in event_evidence_chunks(evidence_text))

def validate_event_source_obligations(required_acceptance, rows, errors):
    by_acceptance={}
    for row in rows:
        rid=row_acceptance_ref(row)
        if rid:
            by_acceptance.setdefault(rid,[]).append(row)
    for acceptance_id, meta in sorted(required_acceptance.items()):
        if meta.get('severity') not in BLOCKING:
            continue
        obligations=event_source_obligations(meta.get('text',''))
        if not obligations:
            continue
        related=by_acceptance.get(acceptance_id,[])
        evidence_text=row_evidence_text(related)
        all_sources=sorted(obligations)
        missing=[source for source in all_sources if not event_source_has_proof(source,obligations[source],all_sources,evidence_text)]
        if missing:
            reason='aggregate-only' if has_non_negated_scope_term(EVENT_AGGREGATE_EVIDENCE_TERMS,evidence_text) else 'not per-source'
            errors.append(f"event_source[{acceptance_id}] names required source events ({', '.join(missing)}) but evidence is {reason}; per-source emission fixtures required")

def auth_status_claim_segments(text):
    return [segment.strip() for segment in re.split(r"(?<=[.;])\s+|[;\n]+", text or '') if segment.strip()]

def negation_is_auth_status_value(text):
    if re.search(r"\b(?:does\s+not|do\s+not|doesn't|don't|never|without|no)\b", text or '', re.I):
        return False
    return bool(re.search(r"\bnot[-_\s]?logged[-_\s]?in\b|\bnot\s+authenticated\b", text or '', re.I))

def has_non_negated_auth_claim_term(pattern, text):
    for match in pattern.finditer(text or ''):
        prefix=text[max(0,match.start()-80):match.start()]
        negated=NEGATED_SCOPE_PREFIX.search(prefix)
        if negated and not negation_is_auth_status_value(negated.group(0)):
            continue
        return True
    return False

def auth_status_mapping_claimed(text):
    for segment in auth_status_claim_segments(text):
        command_status=has_non_negated_auth_claim_term(AUTH_STATUS_COMMAND_TERMS,segment)
        logged_out=has_non_negated_auth_claim_term(AUTH_STATUS_LOGGED_OUT_TERMS,segment)
        strong_mapping=has_non_negated_auth_claim_term(AUTH_STATUS_MAPPING_TERMS,segment)
        distinguishes=has_non_negated_auth_claim_term(AUTH_STATUS_DISTINGUISH_TERMS,segment)
        state=has_non_negated_auth_claim_term(AUTH_STATUS_ERROR_STATE_TERMS,segment)
        if command_status and state and (strong_mapping or distinguishes):
            return True
        if command_status and distinguishes and has_non_negated_auth_claim_term(AUTH_STATUS_DISTINGUISH_FROM_TERMS,segment):
            return True
        if logged_out and state and strong_mapping:
            return True
    return False

def auth_status_has_format_tolerance_evidence(text):
    return (
        has_non_negated_scope_term(AUTH_STATUS_JSON_PARSE_EVIDENCE,text)
        or has_non_negated_scope_term(AUTH_STATUS_VARIANT_EVIDENCE,text)
        or has_non_negated_scope_term(AUTH_STATUS_MULTI_VARIANT_EVIDENCE,text)
        or has_non_negated_scope_term(AUTH_STATUS_LITERAL_VARIANT_EVIDENCE,text)
    )

def validate_auth_status_acceptance_obligations(required_acceptance, acceptance_status, spec, neg, errors):
    status_meta=acceptance_status_metadata(acceptance_status)
    spec_by_acceptance={}
    neg_by_acceptance={}
    for row in spec:
        rid=row_acceptance_ref(row)
        if rid:
            spec_by_acceptance.setdefault(rid,[]).append(row)
    for row in neg:
        rid=row_acceptance_ref(row)
        if rid:
            neg_by_acceptance.setdefault(rid,[]).append(row)
    ids=set(required_acceptance) | set(status_meta) | set(spec_by_acceptance) | set(neg_by_acceptance)
    for acceptance_id in sorted(ids):
        spec_rows=spec_by_acceptance.get(acceptance_id,[])
        neg_rows=neg_by_acceptance.get(acceptance_id,[])
        severities=[
            required_acceptance.get(acceptance_id,{}).get('severity'),
            status_meta.get(acceptance_id,{}).get('severity'),
        ] + [row_blocking_severity(row, required_acceptance) for row in spec_rows+neg_rows if isinstance(row,dict)]
        if not any(severity in BLOCKING for severity in severities):
            continue
        pass_neg_rows=[row for row in neg_rows if isinstance(row,dict) and row.get('status')=='pass']
        if not pass_neg_rows:
            continue
        claim_text=text_blob(
            required_acceptance.get(acceptance_id,{}).get('text',''),
            status_meta.get(acceptance_id,{}).get('text',''),
            spec_rows,
            pass_neg_rows,
        )
        if auth_status_mapping_claimed(claim_text) and not auth_status_has_format_tolerance_evidence(row_evidence_text(pass_neg_rows)):
            errors.append(f"auth_status[{acceptance_id}] login-status mapping claimed but evidence covers one literal form only; JSON-parsed or format-variant fixtures required")

def outcome_has_auth_secret_surface(outcome_blocks):
    rs=first(outcome_blocks or [],'risk_surface')
    surfaces=rs.get('surfaces') if isinstance(rs,dict) else None
    if isinstance(surfaces,dict):
        detail=surfaces.get('auth_or_secret')
        if detail is True or (isinstance(detail,dict) and detail.get('present') is True):
            return True
    adv=first(outcome_blocks or [],'adversarial_acceptance')
    return isinstance(adv,list) and any(isinstance(row,dict) and 'auth_or_secret' in row_surfaces(row) for row in adv)

def secret_audit_scope_text(secret):
    return text_blob(
        secret.get('checked_surfaces'),
        secret.get('evidence_ref'),
        secret.get('evidence_refs'),
        secret.get('evidence_summary'),
        secret.get('summary'),
        secret.get('note'),
        secret.get('details'),
    )

def secret_audit_requires_multi_shape(secret, outcome_blocks):
    return outcome_has_auth_secret_surface(outcome_blocks) or has_non_negated_scope_term(SECRET_AUDIT_SCOPE_TERMS, secret_audit_scope_text(secret))

def has_non_negated_scope_term(pattern, text):
    for match in pattern.finditer(text or ''):
        prefix=text[max(0,match.start()-80):match.start()]
        if NEGATED_SCOPE_PREFIX.search(prefix):
            continue
        return True
    return False

def has_bare_sk_token(text):
    for match in SECRET_BARE_SK_PATTERN.finditer(text):
        context=text[max(0,match.start()-40):match.end()+40]
        if not re.search(r"\b(?:authorization|bearer)\b", context, re.I):
            return True
    return False

def secret_probe_has_shape(name, text):
    pattern=SECRET_TOKEN_SHAPE_PATTERNS[name]
    if pattern.search(text):
        return True
    return name=='bare_token_or_key' and has_bare_sk_token(text)

def validate_cleartext_secret_probe_shape(secret, outcome_blocks, errors):
    probe=secret.get('cleartext_secret_probe')
    if isinstance(probe,str):
        if probe not in {'pass','not_applicable'}:
            errors.append('secret_leakage_audit.cleartext_secret_probe must be pass|not_applicable or a structured shape list when status pass')
            return
        if probe=='not_applicable':
            return
    elif isinstance(probe,dict):
        probe_status=probe.get('status') or probe.get('result')
        if probe_status is not None and probe_status not in {'pass','not_applicable'}:
            errors.append('secret_leakage_audit.cleartext_secret_probe.status must be pass|not_applicable when status pass')
            return
        if probe_status=='not_applicable':
            return
    elif not isinstance(probe,list):
        errors.append('secret_leakage_audit.cleartext_secret_probe must be pass|not_applicable or a structured shape list when status pass')
        return
    if not secret_audit_requires_multi_shape(secret, outcome_blocks):
        return
    probe_text=text_blob(secret)
    missing=[name for name in SECRET_TOKEN_SHAPE_PATTERNS if not secret_probe_has_shape(name, probe_text)]
    if missing:
        errors.append('secret_leakage_audit.cleartext_secret_probe missing required token shapes for in-scope auth/secret/log/evidence surfaces: '+','.join(missing))

def validate_property_obligations(required_acceptance, neg, errors):
    """Catch property escapes where a Grade covers an example but not the invariant."""
    calc={'P0':0,'P1':0}
    for acceptance_id, meta in sorted(required_acceptance.items()):
        severity=meta.get('severity')
        if severity not in BLOCKING:
            continue
        rows=negative_rows_for_acceptance(neg, acceptance_id)
        if not rows:
            continue
        text=row_evidence_text(rows)
        missing=[]
        if has_path_root_obligation(meta):
            if not STRING_TRAVERSAL_TERMS.search(text):
                missing.append('string_traversal')
            if not SYMLINK_CONTAINMENT_TERMS.search(text):
                missing.append('symlink_or_canonical_containment')
        if has_request_target_obligation(meta) and not REQUEST_TARGET_FACET_TERMS.search(text):
            missing.append('request_target_delimiter_or_control_chars')
        if missing:
            calc[severity]+=1
            errors.append(f"property_obligation[{acceptance_id}] missing required negative coverage facets: {','.join(missing)}")
    return calc

def output_contract_artifact_text(capsule):
    if not isinstance(capsule,dict):
        return ''
    output_contract=capsule.get('output_contract')
    if not isinstance(output_contract,dict):
        return ''
    return text_blob(output_contract.get('artifacts'), output_contract.get('artifact'), output_contract.get('paths'))

def primary_outcome_subject_text(outcome_blocks):
    capsule=outcome_capsule_front_matter(outcome_blocks)
    if not isinstance(capsule,dict):
        return ''
    return text_blob(
        capsule.get('title'),
        capsule.get('goal'),
        capsule.get('subject'),
        capsule.get('deliverable'),
        capsule.get('task'),
        capsule.get('task_title'),
        capsule.get('task_goal'),
        capsule.get('backlog_target'),
        capsule.get('backlog_subject'),
        capsule.get('context_subject'),
        output_contract_artifact_text(capsule),
    )

def primary_grade_header_text(grade_text):
    lines=[]
    for line in (grade_text or '').splitlines()[:80]:
        stripped=line.strip()
        if not stripped:
            continue
        if stripped.startswith('#') or re.match(r"(?i)^(task|title|goal|subject|deliverable|scope|backlog|context)\s*:", stripped):
            lines.append(stripped)
    return '\n'.join(lines)

def shape_primary_deliverable_in_scope(grade_text='', outcome_text='', outcome_blocks=None) -> bool:
    primary=text_blob(primary_outcome_subject_text(outcome_blocks), primary_grade_header_text(grade_text))
    if SHAPE_PRIMARY_TASK_TOKENS.search(primary):
        return True
    for match in SHAPE_CRATE_TOKEN.finditer(primary):
        context=primary[max(0,match.start()-80):match.end()+80]
        if not SHAPE_CRATE_PLACEHOLDER_CONTEXT.search(context):
            return True
    return False

def shape_task_in_scope(*texts) -> bool:
    return shape_primary_deliverable_in_scope(*texts)

def grade_agent_task_in_scope(grade_text, outcome_text, outcome_blocks) -> bool:
    primary=text_blob(primary_outcome_subject_text(outcome_blocks), primary_grade_header_text(grade_text))
    return bool(GRADE_AGENT_PRIMARY_TASK_TOKENS.search(primary))

def evolve_agent_task_in_scope(grade_text, outcome_text, outcome_blocks) -> bool:
    primary=text_blob(primary_outcome_subject_text(outcome_blocks), primary_grade_header_text(grade_text))
    return bool(EVOLVE_AGENT_PRIMARY_TASK_TOKENS.search(primary))

def primary_outcome_header_text(outcome_text):
    lines=[]
    for line in (outcome_text or '').splitlines()[:80]:
        stripped=line.strip()
        if not stripped:
            continue
        if stripped.startswith('#') or re.match(r"(?i)^(task|title|goal|subject|deliverable|scope|backlog|context)\s*:", stripped):
            lines.append(stripped)
    return '\n'.join(lines)

def frontend_primary_deliverable_in_scope(grade_text='', outcome_text='', outcome_blocks=None) -> bool:
    primary=text_blob(
        primary_outcome_subject_text(outcome_blocks),
        primary_outcome_header_text(outcome_text),
        primary_grade_header_text(grade_text),
    )
    return has_non_negated_scope_term(FRONTEND_PRIMARY_TASK_TOKENS, primary)

def frontend_evidence_text(bs, grade_text):
    return text_blob(
        grade_text,
        first(bs,'spec_compliance_matrix'),
        first(bs,'negative_regression_tests'),
        first(bs,'adversarial_checks'),
        first(bs,'trust_surface_inventory'),
        first(bs,'deferred_claims'),
    )

def row_collection_by_acceptance(rows):
    by_acceptance={}
    for row in rows:
        rid=row_acceptance_ref(row)
        if rid:
            by_acceptance.setdefault(rid,[]).append(row)
    return by_acceptance

def outcome_adversarial_claim_metadata(outcome_blocks):
    return adversarial_acceptance_metadata(outcome_blocks or [])

def frontend_claim_records(required_acceptance, acceptance_status, spec, neg, outcome_blocks):
    status_meta=acceptance_status_metadata(acceptance_status)
    adv_meta=outcome_adversarial_claim_metadata(outcome_blocks)
    spec_by_acceptance=row_collection_by_acceptance(spec)
    neg_by_acceptance=row_collection_by_acceptance(neg)
    ids=set(required_acceptance) | set(status_meta) | set(adv_meta) | set(spec_by_acceptance) | set(neg_by_acceptance)
    for item_id in sorted(ids):
        spec_rows=spec_by_acceptance.get(item_id,[])
        neg_rows=neg_by_acceptance.get(item_id,[])
        severities=[
            required_acceptance.get(item_id,{}).get('severity'),
            status_meta.get(item_id,{}).get('severity'),
            adv_meta.get(item_id,{}).get('severity'),
        ] + [row_blocking_severity(row, required_acceptance) for row in spec_rows+neg_rows if isinstance(row,dict)]
        if not any(severity in BLOCKING for severity in severities):
            continue
        yield item_id, text_blob(
            required_acceptance.get(item_id,{}).get('text',''),
            status_meta.get(item_id,{}).get('text',''),
            adv_meta.get(item_id,{}).get('text',''),
            spec_rows,
            neg_rows,
        )

def frontend_sse_reconnect_claimed(text):
    if not has_non_negated_scope_term(FRONTEND_SSE_SCOPE_TERMS, text):
        return False
    strong_contract=has_non_negated_scope_term(re.compile(r"\bSWR\b|\bstale[-_\s]?while[-_\s]?revalidate\b|\bfull[-_\s]?(?:GET|refresh)\b|\bGET\s+/api/v1/state\b", re.I), text)
    heartbeat_reconnect=has_non_negated_scope_term(re.compile(r"\bheartbeat\b", re.I), text) and has_non_negated_scope_term(re.compile(r"\breconnect(?:s|ed|ing)?\b", re.I), text)
    eventsource_reconnect=has_non_negated_scope_term(re.compile(r"\bEventSource\b", re.I), text) and has_non_negated_scope_term(re.compile(r"\breconnect(?:s|ed|ing)?\b", re.I), text)
    return strong_contract or heartbeat_reconnect or eventsource_reconnect

def validate_frontend_sse_reconnect_lifecycle_evidence(bs, required_acceptance, acceptance_status, spec, neg, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not frontend_primary_deliverable_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    evidence_text=frontend_evidence_text(bs, grade_text)
    facets=(
        ('old_source_close_or_dispose', FRONTEND_SSE_OLD_SOURCE_CLOSE),
        ('new_source_creation', FRONTEND_SSE_NEW_SOURCE_CREATION),
        ('stale_old_source_events_rejected', FRONTEND_SSE_STALE_OLD_EVENTS_REJECTED),
        ('full_get_state_refresh_after_new_connection', FRONTEND_SSE_FULL_GET_REFRESH),
        ('snapshot_retained_and_writes_disabled_while_disconnected', FRONTEND_SSE_SNAPSHOT_WRITES_DISABLED),
    )
    for item_id, claim_text in frontend_claim_records(required_acceptance, acceptance_status, spec, neg, outcome_blocks):
        if not frontend_sse_reconnect_claimed(claim_text):
            continue
        missing=[name for name,pattern in facets if not has_non_negated_scope_term(pattern, evidence_text)]
        if missing:
            errors.append(f"frontend_sse_reconnect_lifecycle[{item_id}] missing facets: {','.join(missing)}")

def frontend_identity_mismatch_claimed(text):
    return (
        has_non_negated_scope_term(FRONTEND_IDENTITY_SCOPE_TERMS, text)
        and has_non_negated_scope_term(FRONTEND_IDENTITY_MISMATCH_TERMS, text)
    )

def validate_frontend_identity_mismatch_recovery_evidence(bs, required_acceptance, acceptance_status, spec, neg, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not frontend_primary_deliverable_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    evidence_text=frontend_evidence_text(bs, grade_text)
    facets=(
        ('mismatched_response_rejected', FRONTEND_IDENTITY_RESPONSE_REJECTED),
        ('callback_only_side_effect_insufficient', FRONTEND_IDENTITY_CALLBACK_ONLY_INSUFFICIENT),
        ('no_connected_or_write_reenable_until_fresh_matching_identity', FRONTEND_IDENTITY_MATCH_BEFORE_CONNECTED),
        ('sse_connected_mismatched_identity_not_success', FRONTEND_IDENTITY_SSE_CONNECTED_MISMATCH_REJECTED),
    )
    for item_id, claim_text in frontend_claim_records(required_acceptance, acceptance_status, spec, neg, outcome_blocks):
        if not frontend_identity_mismatch_claimed(claim_text):
            continue
        missing=[name for name,pattern in facets if not has_non_negated_scope_term(pattern, evidence_text)]
        if missing:
            errors.append(f"frontend_identity_mismatch_recovery[{item_id}] missing facets: {','.join(missing)}")

def load_yaml_path(path):
    if yaml is not None:
        try:
            return yaml.safe_load(path.read_text(encoding='utf-8'))
        except yaml.YAMLError as exc:
            pass
    return parse_yaml_fence(path.read_text(encoding='utf-8').splitlines())

def frontend_output_package_dirs(outcome_blocks, repo_root):
    dirs=[]
    capsule=outcome_capsule_front_matter(outcome_blocks)
    output_contract=capsule.get('output_contract') if isinstance(capsule,dict) else None
    artifacts=output_contract.get('artifacts') if isinstance(output_contract,dict) else None
    if not isinstance(artifacts,list):
        return dirs
    for artifact in artifacts:
        paths=strs(artifact.get('paths')) if isinstance(artifact,dict) else []
        for raw in paths:
            rel=Path(raw)
            if rel.name in {'package.json','pnpm-lock.yaml'}:
                path=(repo_root/rel).resolve()
                if path.name=='package.json':
                    dirs.append(path.parent)
                else:
                    dirs.append(path.parent)
    unique=[]
    for item in dirs:
        if item not in unique:
            unique.append(item)
    return unique

def frontend_dependency_rows_reference_stack(dep):
    return any(
        isinstance(row,dict)
        and re.search(r"tech-stack\.yaml", text_blob(row), re.I)
        and re.search(r"frontend_locked", text_blob(row), re.I)
        for row in dep
    )

def parse_frontend_locked_versions(text):
    lines=(text or '').splitlines()
    start=None
    for i,line in enumerate(lines):
        if re.match(r"^\s*frontend_locked\s*:\s*(?:#.*)?$", line):
            start=i
            break
    if start is None:
        return {}
    base_indent=indent_of(lines[start])
    versions={}
    current_name=None
    for line in lines[start+1:]:
        stripped=line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        cur_indent=indent_of(line)
        if cur_indent<=base_indent and not stripped.startswith('- '):
            break
        if stripped.startswith('- '):
            current_name=None
            item=stripped[2:].strip()
            if item.startswith('name:'):
                current_name=str(parse_scalar(item.split(':',1)[1].strip()))
            continue
        if current_name and stripped.startswith('version:'):
            versions[current_name]=str(parse_scalar(stripped.split(':',1)[1].strip()))
    return versions

def canonical_frontend_versions(repo_root):
    path=repo_root/'docs'/'architecture'/'tech-stack.yaml'
    if not path.exists():
        raise LintError(f'frontend dependency guard missing canonical stack file: {path}')
    parsed=parse_frontend_locked_versions(path.read_text(encoding='utf-8'))
    if parsed:
        return parsed
    data=load_yaml_path(path) or {}
    locked=data.get('frontend_locked') if isinstance(data,dict) else None
    if not isinstance(locked,list):
        raise LintError(f'frontend dependency guard missing frontend_locked list in {path}')
    out={}
    for row in locked:
        if isinstance(row,dict) and isinstance(row.get('name'),str) and 'version' in row:
            out[row['name']]=str(row.get('version'))
    return out

def package_dependency_specs(package_json):
    specs={}
    for section in ('dependencies','devDependencies','optionalDependencies','peerDependencies'):
        values=package_json.get(section)
        if isinstance(values,dict):
            for name,value in values.items():
                if isinstance(name,str) and isinstance(value,str):
                    specs[name]=value
    return specs

def pnpm_importer_deps(lock_data):
    importers=lock_data.get('importers') if isinstance(lock_data,dict) else None
    if not isinstance(importers,dict):
        return {}
    importer=importers.get('.')
    if not isinstance(importer,dict):
        importer=next((value for value in importers.values() if isinstance(value,dict)), {})
    out={}
    for section in ('dependencies','devDependencies','optionalDependencies'):
        values=importer.get(section)
        if isinstance(values,dict):
            for name,detail in values.items():
                if isinstance(detail,dict):
                    out[name]={'specifier':detail.get('specifier'), 'version':detail.get('version')}
    return out

def normalize_pnpm_version(value):
    if not isinstance(value,str):
        return ''
    return value.split('(',1)[0].strip()

def exact_version(value):
    return isinstance(value,str) and bool(EXACT_VERSION_RE.fullmatch(value.strip()))

def dependency_row_allows_mismatch(row):
    if not isinstance(row,dict):
        return False
    if row.get('status') in {'fail','unverified'}:
        return True
    if any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref','update_protocol_ref','update-protocol_ref')):
        return True
    return bool(re.search(r"\b(?:tracked\s+waiver|waiver|update[-_\s]?protocol)\b", text_blob(row), re.I))

def dependency_review_rows_for_package(dep, package_name):
    package_pattern=re.compile(r"(?<![A-Za-z0-9_@./-])"+re.escape(package_name)+r"(?![A-Za-z0-9_@./-])", re.I)
    matches=[row for row in dep if isinstance(row,dict) and package_pattern.search(text_blob(row))]
    if matches:
        return matches
    if package_name=='pnpm':
        matches=[row for row in dep if isinstance(row,dict) and re.search(r"\bpackageManager\b|\bpnpm\b", text_blob(row), re.I)]
        if matches:
            return matches
    return [row for row in dep if isinstance(row,dict) and re.search(r"tech-stack\.yaml", text_blob(row), re.I)]

def dependency_mismatch_is_reported_as_blocking(dep, package_name):
    rows=dependency_review_rows_for_package(dep, package_name)
    return bool(rows) and any(dependency_row_allows_mismatch(row) for row in rows)

def append_dependency_guard_error(errors, dep, package_name, message):
    if dependency_mismatch_is_reported_as_blocking(dep, package_name):
        return
    errors.append(
        f"frontend_dependency_lock_guard[{package_name}] {message}; "
        "dependency_spec_review row must be fail/unverified or cite tracked waiver/update-protocol ref"
    )

def validate_frontend_dependency_lock_guard(dep, errors, *, grade_text='', outcome_text='', outcome_blocks=None, repo_root=None):
    if repo_root is None:
        return
    if not frontend_primary_deliverable_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    if not isinstance(dep,list) or not frontend_dependency_rows_reference_stack(dep):
        return
    repo_root=Path(repo_root).resolve()
    canonical=canonical_frontend_versions(repo_root)
    package_dirs=frontend_output_package_dirs(outcome_blocks, repo_root)
    for package_dir in package_dirs:
        package_path=package_dir/'package.json'
        lock_path=package_dir/'pnpm-lock.yaml'
        if not package_path.exists() or not lock_path.exists():
            continue
        try:
            package_json=json.loads(package_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise LintError(f'invalid package.json {package_path}: {exc}') from exc
        lock_deps=pnpm_importer_deps(load_yaml_path(lock_path) or {})
        manifest_specs=package_dependency_specs(package_json)
        if 'pnpm' in canonical and not isinstance(package_json.get('packageManager'),str):
            append_dependency_guard_error(
                errors,
                dep,
                'pnpm',
                f"{package_path.relative_to(repo_root)} omits packageManager while canonical frontend_locked pins pnpm {canonical['pnpm']}",
            )
        for name,specifier in sorted(manifest_specs.items()):
            canonical_version=canonical.get(name)
            if not canonical_version:
                continue
            lock_version=normalize_pnpm_version(lock_deps.get(name,{}).get('version'))
            if exact_version(canonical_version):
                if lock_version and exact_version(lock_version) and lock_version != canonical_version:
                    append_dependency_guard_error(
                        errors,
                        dep,
                        name,
                        f"canonical {canonical_version} but {package_path.relative_to(repo_root)} specifier {specifier} resolves {lock_version} in {lock_path.relative_to(repo_root)}",
                    )
                elif specifier.startswith(('^','~')) and lock_version and lock_version != canonical_version:
                    append_dependency_guard_error(
                        errors,
                        dep,
                        name,
                        f"canonical {canonical_version} but range {specifier} resolved away to {lock_version} in {lock_path.relative_to(repo_root)}",
                    )
            elif name in lock_deps or name in manifest_specs:
                continue

def shape_forbidden_read_row_sufficient(row):
    row_text=text_blob(row)
    return (
        bool(SHAPE_FORBIDDEN_SPEC_REF.search(row_text))
        and all(root in row_text for root in SHAPE_FORBIDDEN_ROOTS)
        and bool(SHAPE_NO_READ_EVIDENCE.search(row_text))
    )

def validate_shape_forbidden_read_isolation_audit(spec, neg, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    combined=text_blob(grade_text,outcome_text,outcome_blocks)
    if not shape_primary_deliverable_in_scope(grade_text,outcome_text,outcome_blocks) or not SHAPE_FORBIDDEN_SCOPE.search(combined):
        return
    if any(shape_forbidden_read_row_sufficient(row) for row in spec+neg if isinstance(row,dict)):
        return
    errors.append('shape_forbidden_read_isolation_audit: Shape forbidden-read proof missing — grade proves no-writes but not no-READS of memory-user/patterns-user/patterns-imported (R-AGT-6/AGENT.md capabilities.forbidden)')

def outcome_capsule_front_matter(outcome_blocks):
    for block in outcome_blocks or []:
        if isinstance(block,dict) and isinstance(block.get('schema_version'),str):
            return block
    return None

def list_of_objects_with_fields(value, fields):
    return isinstance(value,list) and all(isinstance(item,dict) and all(field in item for field in fields) for item in value)

def validate_outcome_capsule_v12_structural_schema(outcome_blocks, errors, *, grade_text='', outcome_text=''):
    if not shape_primary_deliverable_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    capsule=outcome_capsule_front_matter(outcome_blocks)
    if not isinstance(capsule,dict) or str(capsule.get('schema_version'))!='1.2':
        return
    if 'assumptions' in capsule and not list_of_objects_with_fields(capsule.get('assumptions'),SHAPE_SCHEMA_ASSUMPTION_FIELDS):
        errors.append('outcome_capsule_v12_structural_schema.assumptions: Shape schema_version 1.2 assumptions must be a list of objects with id,text,source,confirmed,risk_if_wrong')
    groundings=capsule.get('groundings')
    if groundings not in (None,[]) and not list_of_objects_with_fields(groundings,SHAPE_SCHEMA_GROUNDING_FIELDS):
        errors.append('outcome_capsule_v12_structural_schema.groundings: Shape schema_version 1.2 groundings must be a list of objects with id,source_type,fetched_at,why_relevant,supports')
    output_contract=capsule.get('output_contract')
    if isinstance(output_contract,dict):
        target=output_contract.get('target')
        artifacts=output_contract.get('artifacts')
        artifact_types={item.get('type') for item in artifacts if isinstance(item,dict) and isinstance(item.get('type'),str)} if isinstance(artifacts,list) else set()
        if not isinstance(target,str) or target not in artifact_types:
            errors.append(f"outcome_capsule_v12_structural_schema.output_contract.target: target {target!r} must equal one of output_contract.artifacts[*].type")
    else:
        errors.append('outcome_capsule_v12_structural_schema.output_contract.target: output_contract must be an object with target and artifacts')
    if capsule.get('risk_level')=='high':
        actions=capsule.get('high_risk_actions')
        if not isinstance(actions,list) or not actions or not all(isinstance(item,dict) and item.get('action') and item.get('requires') for item in actions):
            errors.append('outcome_capsule_v12_structural_schema.high_risk_actions: risk_level high requires a non-empty list of objects with action and requires')

def text_has_all_terms(text, terms):
    return all(re.search(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", text, re.I) for term in terms)

def shape_has_nine_rule_evidence(text):
    if re.search(r"\bnine[-\s]?rules?\b|\b9[-\s]?rules?\b|\b9[-\s]?rule\b", text, re.I):
        return True
    return all(re.search(rf"\brule\s*{i}\b", text, re.I) for i in range(1,10))

def shape_high_risk_action_token_present(text, token):
    if token in {'db_write','external_api','merge_pr'}:
        return bool(re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", text, re.I))
    if token=='delete':
        return bool(re.search(r"\bdelete\b|\bfile_delete\b", text, re.I))
    if token=='payment':
        return bool(re.search(r"\bpayment\b|\bpayment_api\b", text, re.I))
    return bool(re.search(r"\bdeploy\b", text, re.I))

def shape_has_high_risk_classifier_evidence(text):
    return (
        all(shape_high_risk_action_token_present(text, token) for token in SHAPE_HIGH_RISK_ACTIONS)
        and bool(re.search(r"\brisk_level\s*[:=]\s*[\"']?high\b", text, re.I))
        and bool(re.search(r"\bhigh_risk_actions\b", text, re.I))
    )

def shape_has_qa_protocol_evidence(text):
    return (
        'My assumption' in text
        and 'Source' in text
        and bool(re.search(r"\bSkip\s*(?:—|-)\s*agent decide\b|\bskip\s+agent\s+decide\b", text, re.I))
        and bool(re.search(r"\bmerged into outcome\b|\bmerged into assumptions\b|\banswers merged\b", text, re.I))
    )

def shape_has_rejected_critic_fixture(text):
    critic_rejected=(
        re.search(r"\bcritic\b[^.\n]{0,160}\b(?:approved\s*[:=]\s*false|approved\s+false|rejected|disapproved)\b", text, re.I)
        or re.search(r"\b(?:approved\s*[:=]\s*false|approved\s+false|rejected|disapproved)\b[^.\n]{0,160}\bcritic\b", text, re.I)
    )
    outcome_blocked=(
        re.search(r"\boutcome(?:\.md)?\b[^.\n]{0,160}\b(?:not\s+(?:be\s+)?written|is\s+not\s+written|does\s+not\s+(?:advance|write)|not\s+advance|must\s+not\s+advance|no\s+advance)\b", text, re.I)
        or re.search(r"\b(?:not\s+(?:be\s+)?written|does\s+not\s+(?:advance|write)|not\s+advance|must\s+not\s+advance|no\s+advance)\b[^.\n]{0,160}\boutcome(?:\.md)?\b", text, re.I)
    )
    return bool(critic_rejected and outcome_blocked)

def validate_shape_protocol_evidence(bs, outcome_blocks, errors, *, grade_text='', outcome_text=''):
    if not shape_primary_deliverable_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    evidence_text=text_blob(
        grade_text,
        first(bs,'spec_compliance_matrix'),
        first(bs,'negative_regression_tests'),
        first(bs,'adversarial_checks'),
        first(bs,'trust_surface_inventory'),
        first(bs,'deferred_claims'),
    )
    missing=[]
    if not (
        re.search(r"\bshape_session\b", evidence_text, re.I)
        and text_has_all_terms(evidence_text, SHAPE_CRITIC_ENVELOPE_FIELDS)
        and shape_has_nine_rule_evidence(evidence_text)
    ):
        missing.append('critic_envelope_input')
    if not shape_has_high_risk_classifier_evidence(evidence_text):
        missing.append('high_risk_classifier')
    if not shape_has_qa_protocol_evidence(evidence_text):
        missing.append('qa_protocol')
    if not shape_has_rejected_critic_fixture(evidence_text):
        missing.append('rejected_critic_gate')
    if missing:
        errors.append(f"shape_protocol_evidence: missing Grade evidence groups for Shape-agent work: [{', '.join(missing)}]")

def grade_agent_evidence_text(bs, grade_text):
    return text_blob(
        grade_text,
        first(bs,'spec_compliance_matrix'),
        first(bs,'negative_regression_tests'),
        first(bs,'adversarial_checks'),
        first(bs,'trust_surface_inventory'),
        first(bs,'deferred_claims'),
    )

def text_has_evidence_segment(text, patterns):
    segments=re.split(r"\n\s*-\s+|\n\n|[.;]\s+", text or '')
    return any(all(pattern.search(segment) for pattern in patterns) for segment in segments)

def raw_line_has_evidence_segment(text, patterns):
    segments=re.split(r"\n+|[.;]\s+", text or '')
    return any(all(pattern.search(segment) for pattern in patterns) for segment in segments)

def validate_grade_agent_read_only_isolation_audit(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not grade_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    claim_text=text_blob(grade_text,outcome_text)
    if not GRADE_AGENT_READ_ONLY_CLAIM.search(claim_text):
        return
    evidence_text=grade_agent_evidence_text(bs, grade_text)
    missing=[]
    if not text_has_evidence_segment(evidence_text, (GRADE_AGENT_HOSTILE_TERMS, GRADE_AGENT_COMMAND_TERMS, GRADE_AGENT_WRITE_TERMS, GRADE_AGENT_WRITE_TARGET_TERMS)):
        missing.append('hostile_write_command')
    if not text_has_evidence_segment(evidence_text, (GRADE_AGENT_HOSTILE_TERMS, GRADE_AGENT_ARTIFACT_TERMS, GRADE_AGENT_READ_OR_TRAVERSAL_TERMS)):
        missing.append('hostile_artifact_forbidden_read_or_traversal')
    if not (GRADE_AGENT_CONTAINMENT_TERMS.search(evidence_text) and GRADE_AGENT_DENYLIST_TERMS.search(evidence_text)):
        missing.append('canonical_containment_or_denylist')
    if not text_has_evidence_segment(evidence_text, (GRADE_AGENT_STABILITY_TERMS, GRADE_AGENT_HASH_BYTE_TERMS, re.compile(r"\bsource\b|\boutcome\.md\b", re.I))):
        missing.append('post_run_source_outcome_hash_or_byte_stability')
    if missing:
        errors.append('grade_agent_read_only_isolation_audit: missing evidence facets: '+','.join(missing))

def validate_grade_agent_dp13_schema_trigger(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not grade_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    claim_text=text_blob(grade_text,outcome_text)
    if not GRADE_AGENT_DP13_CLAIM.search(claim_text):
        return
    evidence_text=grade_agent_evidence_text(bs, grade_text)
    missing=[]
    if not GRADE_AGENT_HIGH_RISK_ACTIONS_TOP_LEVEL.search(evidence_text):
        missing.append('high_risk_capsule_with_top_level_high_risk_actions')
    if not GRADE_AGENT_SECOND_SIGNAL_BRANCH.search(evidence_text):
        missing.append('second_signal_branch')
    if not GRADE_AGENT_HUMAN_REVIEW_BRANCH.search(evidence_text):
        missing.append('human_review_branch')
    if missing:
        errors.append('grade_agent_dp13_schema_trigger: missing evidence facets: '+','.join(missing))

def validate_grade_agent_second_signal_unforgeable(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not grade_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    claim_text=text_blob(grade_text,outcome_text)
    if not GRADE_AGENT_DP13_CLAIM.search(claim_text):
        return
    evidence_text=grade_agent_evidence_text(bs, grade_text)
    missing=[]
    if not GRADE_AGENT_SUBSTRING_UNFORGEABLE.search(evidence_text):
        missing.append('criteria_substring_cannot_set_llm_judge_passed')
    if not GRADE_AGENT_STRUCTURED_SECOND_SIGNAL.search(evidence_text):
        missing.append('structured_independent_judge_or_human_review_artifact')
    if missing:
        errors.append('grade_agent_second_signal_unforgeable: missing evidence facets: '+','.join(missing))

def validate_grade_agent_llm_judge_fail_closed(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not grade_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    claim_text=text_blob(grade_text,outcome_text)
    if not re.search(r"\bllm_judge\b|\bhard[-_\s]?gate\b|\bevidence_refs?\b|\btrace_ref\b", claim_text, re.I):
        return
    evidence_text=grade_agent_evidence_text(bs, grade_text)
    missing=[]
    if not GRADE_AGENT_EMPTY_EVIDENCE_REFS_FAIL.search(evidence_text):
        missing.append('empty_evidence_refs_fail')
    if not GRADE_AGENT_MISSING_EVIDENCE_REF_FAIL.search(evidence_text):
        missing.append('missing_evidence_ref_fail')
    if not GRADE_AGENT_HARD_GATE_DEFAULT_CLOSED.search(evidence_text):
        missing.append('hard_gate_defaults_closed_false')
    if not GRADE_AGENT_FABRICATED_TRACE_REF_REJECTED.search(evidence_text):
        missing.append('self_fabricated_trace_ref_not_sole_evidence')
    if missing:
        errors.append('grade_agent_llm_judge_fail_closed: missing evidence facets: '+','.join(missing))

def validate_grade_agent_outcome_path_schema_fields(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not grade_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    evidence_text=grade_agent_evidence_text(bs, grade_text)
    missing=[]
    if not GRADE_AGENT_REQUIRED_EXIT_NON_DEFAULT.search(evidence_text):
        missing.append('command_required_exit_code_non_default')
    if not GRADE_AGENT_PER_ACCEPTANCE_CWD.search(evidence_text):
        missing.append('per_acceptance_cwd')
    if not GRADE_AGENT_MIN_SIZE_BYTES.search(evidence_text):
        missing.append('artifact_min_size_bytes')
    if missing:
        errors.append('grade_agent_outcome_path_schema_fields: missing evidence facets: '+','.join(missing))

def validate_grade_agent_critic_substance(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not grade_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    claim_text=text_blob(grade_text,outcome_text)
    if not re.search(r"\bGrade critic\b|\bcritic\b|\bgrade_critic\.md\b", claim_text, re.I):
        return
    evidence_text=grade_agent_evidence_text(bs, grade_text)
    missing=[]
    if not GRADE_AGENT_REJECTED_CRITIC_FIXTURE.search(evidence_text):
        missing.append('rejected_seeded_pass_or_naked_verdict_critic_fixture')
    if not (re.search(r"\brule[ _-]?1\b", evidence_text, re.I) and re.search(r"\boutcome\.md\b", evidence_text, re.I)):
        missing.append('rule1_consumes_outcome_md')
    if not (re.search(r"\brule[ _-]?3\b", evidence_text, re.I) and re.search(r"\bgrade_result\.md\b", evidence_text, re.I)):
        missing.append('rule3_consumes_grade_result_md')
    if not (re.search(r"\brule[ _-]?4\b", evidence_text, re.I) and re.search(r"\bevidence\b", evidence_text, re.I) and re.search(r"\btrace(?:_|\s|-)?json\b|\btrace.*\.json\b", evidence_text, re.I)):
        missing.append('rule4_consumes_evidence_files_and_trace_json')
    if missing:
        errors.append('grade_agent_critic_substance: missing evidence facets: '+','.join(missing))

def evolve_agent_evidence_text(bs, grade_text):
    return text_blob(
        grade_text,
        first(bs,'spec_compliance_matrix'),
        first(bs,'negative_regression_tests'),
        first(bs,'adversarial_checks'),
        first(bs,'trust_surface_inventory'),
        first(bs,'deferred_claims'),
    )

def validate_evolve_metadata_persisted_post_commit(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not evolve_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    claim_text=text_blob(grade_text,outcome_text)
    if not EVOLVE_METADATA_CLAIM.search(claim_text):
        return
    evidence_text=evolve_agent_evidence_text(bs, grade_text)
    missing=[]
    if not (EVOLVE_REAL_COMMIT_HASH_RE.search(evidence_text) and EVOLVE_POST_COMMIT_READBACK_RE.search(evidence_text)):
        missing.append('post_commit_commit_hash_readback')
    if not EVOLVE_REVERT_HINT_REAL_COMMIT_RE.search(evidence_text):
        missing.append('revert_hint_real_commit')
    if not EVOLVE_L2_METADATA_RE.search(evidence_text):
        missing.append('l2_pattern_d_p21_metadata')
    if missing:
        errors.append('evolve_metadata_persisted_post_commit: missing evidence facets: '+','.join(missing))

def validate_evolve_critic_prefilter_substance(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not evolve_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    claim_text=text_blob(grade_text,outcome_text)
    if not EVOLVE_CRITIC_PREFILTER_CLAIM.search(claim_text):
        return
    evidence_text=evolve_agent_evidence_text(bs, grade_text)
    missing=[]
    if not EVOLVE_GRADE_COMPLETED_TRACE_RE.search(evidence_text):
        missing.append('grade_completed_traceability')
    if not EVOLVE_VALIDATION_ANCHOR_BLACKLIST_RE.search(evidence_text):
        missing.append('validation_anchor_blacklist')
    if not EVOLVE_GRADE_CONSISTENCY_RE.search(evidence_text):
        missing.append('grade_consistency')
    if not EVOLVE_PER_CANDIDATE_VERDICT_RE.search(evidence_text):
        missing.append('per_candidate_structured_verdict')
    if missing:
        errors.append('evolve_critic_prefilter_substance: missing evidence facets: '+','.join(missing))

def validate_evolve_write_with_git_and_log_counts(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not evolve_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    claim_text=text_blob(grade_text,outcome_text)
    if not EVOLVE_WRITE_GIT_LOG_CLAIM.search(claim_text):
        return
    evidence_text=evolve_agent_evidence_text(bs, grade_text)
    missing=[]
    if not raw_line_has_evidence_segment(grade_text, (EVOLVE_LOG_TERMS, EVOLVE_GIT_COMMIT_TERMS)):
        missing.append('evolve_log_git_commit')
    if not EVOLVE_MEMORY_ARTIFACT_GIT_RE.search(evidence_text):
        missing.append('memory_artifacts_git_commit')
    if not EVOLVE_LOG_REAL_COUNTS_RE.search(evidence_text):
        missing.append('evolve_log_real_counts')
    if missing:
        errors.append('evolve_write_with_git_and_log_counts: missing evidence facets: '+','.join(missing))

def validate_evolve_lightweight_commit_idempotence(bs, errors, *, grade_text='', outcome_text='', outcome_blocks=None):
    if not evolve_agent_task_in_scope(grade_text,outcome_text,outcome_blocks):
        return
    claim_text=text_blob(grade_text,outcome_text)
    if not EVOLVE_LIGHTWEIGHT_CLAIM.search(claim_text):
        return
    evidence_text=evolve_agent_evidence_text(bs, grade_text)
    missing=[]
    if not EVOLVE_RECENT_RUNS_GIT_COMMIT_RE.search(evidence_text):
        missing.append('recent_runs_git_commit')
    if not EVOLVE_RECENT_RUNS_IDEMPOTENCE_RE.search(evidence_text):
        missing.append('same_digest_idempotence')
    if missing:
        errors.append('evolve_lightweight_commit_idempotence: missing evidence facets: '+','.join(missing))

def validate_code_baseline(summary, bs, errors, required_acceptance, acceptance_status, outcome_blocks=None, grade_claims=None, grade_text='', outcome_text='', repo_root=None):
    """All code tasks need replayable spec/security/negative-test evidence."""
    required_acceptance = required_acceptance or acceptance_status_metadata(acceptance_status)
    required_ids=set(required_acceptance)
    blocking_ids={k for k,v in required_acceptance.items() if v.get('severity') in BLOCKING}
    calc={'P0':0,'P1':0}

    spec=first(bs,'spec_compliance_matrix')
    if not isinstance(spec,list) or not spec:
        errors.append('code grade missing parseable spec_compliance_matrix block'); spec=[]
    covered=set()
    for i,row in enumerate(spec):
        if not isinstance(row,dict): errors.append(f'spec_compliance_matrix[{i}] must be an object'); continue
        rid=row_acceptance_ref(row); st=row.get('status'); sv=row.get('severity_if_fail') or required_acceptance.get(rid,{}).get('severity')
        if not rid: errors.append(f'spec_compliance_matrix[{i}].acceptance_id is required')
        else: covered.add(rid)
        if st not in {'pass','fail','unverified','not_applicable'}: errors.append(f'spec_compliance_matrix[{i}].status must be pass|fail|unverified|not_applicable'); continue
        if sv not in {'P0','P1','P2'}: errors.append(f'spec_compliance_matrix[{i}].severity_if_fail must be P0|P1|P2'); continue
        if st in {'fail','unverified'} and sv in BLOCKING:
            calc[sv]+=1; errors.append(f"spec_compliance_matrix[{i}] {rid} is blocking: {st}/{sv}")
        if st!='not_applicable':
            if not isinstance(row.get('evidence_ref'),str) or not row.get('evidence_ref').strip(): errors.append(f'spec_compliance_matrix[{i}].evidence_ref is required unless not_applicable')
            if not (list_of_strs(row.get('spec_refs')) or isinstance(row.get('spec_ref'),str)): errors.append(f'spec_compliance_matrix[{i}] requires spec_ref or spec_refs')
        elif not (isinstance(row.get('rationale'),str) and row.get('rationale').strip()):
            errors.append(f'spec_compliance_matrix[{i}].rationale is required when not_applicable')
    missing=sorted(required_ids-covered)
    if missing: errors.append('spec_compliance_matrix missing outcome acceptance IDs: '+','.join(missing))

    neg=first(bs,'negative_regression_tests')
    if not isinstance(neg,list) or not neg:
        errors.append('code grade missing parseable negative_regression_tests block'); neg=[]
    neg_covered=set()
    for i,row in enumerate(neg):
        if not isinstance(row,dict): errors.append(f'negative_regression_tests[{i}] must be an object'); continue
        rid=row_acceptance_ref(row); st=row.get('status'); sv=row.get('severity_if_fail') or required_acceptance.get(rid,{}).get('severity')
        if not rid: errors.append(f'negative_regression_tests[{i}].acceptance_id is required')
        else: neg_covered.add(rid)
        if st not in {'pass','fail','unverified','not_applicable'}: errors.append(f'negative_regression_tests[{i}].status must be pass|fail|unverified|not_applicable'); continue
        if sv not in {'P0','P1','P2'}: errors.append(f'negative_regression_tests[{i}].severity_if_fail must be P0|P1|P2'); continue
        if st in {'fail','unverified'} and sv in BLOCKING:
            calc[sv]+=1; errors.append(f"negative_regression_tests[{i}] {rid} is blocking: {st}/{sv}")
        if st=='pass':
            if not isinstance(row.get('evidence_ref'),str) or not row.get('evidence_ref').strip(): errors.append(f'negative_regression_tests[{i}].evidence_ref is required when pass')
            if not isinstance(row.get('scenario'),str) or not row.get('scenario').strip(): errors.append(f'negative_regression_tests[{i}].scenario is required when pass')
        if st=='not_applicable' and rid in blocking_ids and not any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('scope_basis_ref','tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref')):
            errors.append(f'negative_regression_tests[{i}] {rid} P0/P1 not_applicable requires scope_basis_ref or tracked waiver')
    missing_neg=sorted(blocking_ids-neg_covered)
    if missing_neg: errors.append('negative_regression_tests missing P0/P1 outcome acceptance IDs: '+','.join(missing_neg))
    prop_calc=validate_property_obligations(required_acceptance, neg, errors)
    calc['P0']+=prop_calc['P0']; calc['P1']+=prop_calc['P1']
    validate_shape_forbidden_read_isolation_audit(spec, neg, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_outcome_capsule_v12_structural_schema(outcome_blocks, errors, grade_text=grade_text, outcome_text=outcome_text)
    validate_shape_protocol_evidence(bs, outcome_blocks, errors, grade_text=grade_text, outcome_text=outcome_text)
    validate_grade_agent_read_only_isolation_audit(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_grade_agent_dp13_schema_trigger(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_grade_agent_second_signal_unforgeable(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_grade_agent_llm_judge_fail_closed(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_grade_agent_outcome_path_schema_fields(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_grade_agent_critic_substance(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_evolve_metadata_persisted_post_commit(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_evolve_critic_prefilter_substance(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_evolve_write_with_git_and_log_counts(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_evolve_lightweight_commit_idempotence(bs, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_frontend_sse_reconnect_lifecycle_evidence(bs, required_acceptance, acceptance_status, spec, neg, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_frontend_identity_mismatch_recovery_evidence(bs, required_acceptance, acceptance_status, spec, neg, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks)
    validate_subprocess_lifecycle_acceptance_obligations(required_acceptance, spec+neg, errors, grade_claims)
    validate_rpc_cleanup_acceptance_obligations(required_acceptance, acceptance_status, spec+neg, errors)
    validate_event_source_obligations(required_acceptance, spec+neg, errors)
    validate_auth_status_acceptance_obligations(required_acceptance, acceptance_status, spec, neg, errors)

    secret=first(bs,'secret_leakage_audit')
    if not isinstance(secret,dict):
        errors.append('code grade missing parseable secret_leakage_audit block')
    else:
        st=secret.get('status')
        if st not in {'pass','fail','unverified','not_applicable'}:
            errors.append('secret_leakage_audit.status must be pass|fail|unverified|not_applicable')
        elif st in {'fail','unverified'}:
            calc['P1']+=1; errors.append(f'secret_leakage_audit is blocking: {st}/P1')
        elif st=='pass':
            if not isinstance(secret.get('evidence_ref'),str) or not secret.get('evidence_ref').strip(): errors.append('secret_leakage_audit.evidence_ref is required when pass')
            if not list_of_strs(secret.get('checked_surfaces')): errors.append('secret_leakage_audit.checked_surfaces must be a non-empty list when pass')
            validate_cleartext_secret_probe_shape(secret, outcome_blocks, errors)
        elif st=='not_applicable' and not any(isinstance(secret.get(k),str) and secret.get(k).strip() for k in ('rationale','scope_basis_ref')):
            errors.append('secret_leakage_audit not_applicable requires rationale or scope_basis_ref')

    dep=first(bs,'dependency_spec_review')
    dep_required=outcome_dependency_terms(required_acceptance)
    if not isinstance(dep,list) or not dep:
        errors.append('code grade missing parseable dependency_spec_review block'); dep=[]
    dep_has_applicable=False
    for i,row in enumerate(dep):
        if not isinstance(row,dict): errors.append(f'dependency_spec_review[{i}] must be an object'); continue
        st=row.get('status'); sv=row.get('severity_if_fail') or 'P1'
        if st not in {'pass','fail','unverified','not_applicable'}: errors.append(f'dependency_spec_review[{i}].status must be pass|fail|unverified|not_applicable'); continue
        if sv not in {'P0','P1','P2'}: errors.append(f'dependency_spec_review[{i}].severity_if_fail must be P0|P1|P2'); continue
        if st!='not_applicable':
            dep_has_applicable=True
            if not isinstance(row.get('evidence_ref'),str) or not row.get('evidence_ref').strip(): errors.append(f'dependency_spec_review[{i}].evidence_ref is required unless not_applicable')
            if not (isinstance(row.get('spec_ref'),str) and row.get('spec_ref').strip()): errors.append(f'dependency_spec_review[{i}].spec_ref is required unless not_applicable')
        elif not (isinstance(row.get('rationale'),str) and row.get('rationale').strip()):
            errors.append(f'dependency_spec_review[{i}].rationale is required when not_applicable')
        if st in {'fail','unverified'} and sv in BLOCKING:
            calc[sv]+=1; errors.append(f"dependency_spec_review[{i}] is blocking: {st}/{sv}")
    if dep_required and not dep_has_applicable:
        errors.append('dependency_spec_review must include at least one applicable row because outcome acceptance references dependencies/versions/packages')
    validate_frontend_dependency_lock_guard(dep, errors, grade_text=grade_text, outcome_text=outcome_text, outcome_blocks=outcome_blocks, repo_root=repo_root)

    if isinstance(summary,dict):
        if nni(summary.get('p0_count')) and summary.get('p0_count')<calc['P0']: errors.append('grade_summary.p0_count undercounts blocking code-baseline P0 findings')
        if nni(summary.get('p1_count')) and summary.get('p1_count')<calc['P1']: errors.append('grade_summary.p1_count undercounts blocking code-baseline P1 findings')

def validate_adv(summary,bs,errors,required_acceptance=None):
    required_acceptance=required_acceptance or {}
    checks=first(bs,'adversarial_checks'); inv=first(bs,'trust_surface_inventory'); deferred=first(bs,'deferred_claims')
    if not isinstance(checks,list): errors.append('medium/high code grade missing parseable adversarial_checks block'); checks=[]
    if not isinstance(inv,dict): errors.append('medium/high code grade missing parseable trust_surface_inventory block'); inv={}
    if not isinstance(deferred,list): errors.append('medium/high code grade missing parseable deferred_claims block'); deferred=[]
    calc={'P0':0,'P1':0}
    covered_acceptance_ids=set()
    for i,row in enumerate(checks):
        if not isinstance(row,dict): errors.append(f'adversarial_checks[{i}] must be an object'); continue
        st=row.get('status'); sv=row.get('severity_if_fail')
        row_refs=[]
        for k in ('acceptance_id','acceptance_ref','adversarial_id','adversarial_ref'):
            if isinstance(row.get(k), str) and row.get(k): row_refs.append(row.get(k)); covered_acceptance_ids.add(row.get(k))
        if not isinstance(row.get('id'),str) or not row.get('id'): errors.append(f'adversarial_checks[{i}].id is required')
        if st not in {'pass','fail','unverified','not_applicable'}: errors.append(f'adversarial_checks[{i}].status must be pass|fail|unverified|not_applicable'); continue
        if sv not in {'P0','P1','P2'}: errors.append(f'adversarial_checks[{i}].severity_if_fail must be P0|P1|P2'); continue
        if st in {'fail','unverified'} and sv in BLOCKING: calc[sv]+=1; errors.append(f"adversarial_checks[{i}] {row.get('id')} is blocking: {st}/{sv}")
        if st!='not_applicable' and not isinstance(row.get('evidence_ref'),str): errors.append(f'adversarial_checks[{i}].evidence_ref is required unless not_applicable')
        referenced=[required_acceptance[x] for x in row_refs if x in required_acceptance]
        combined_text=text_blob(row, referenced)
        combined_surfaces=set(row_surfaces(row))
        for ref in referenced: combined_surfaces |= set(ref.get('surfaces') or set())
        if st!='not_applicable' and 'concurrency_or_locking' in combined_surfaces and CONCURRENCY_TERMS.search(combined_text) and evidence_kind(row) not in CONCURRENCY_EVIDENCE:
            errors.append(f'adversarial_checks[{i}] {row.get("id")} concurrency_or_locking check requires evidence_kind concurrency_test|atomicity_proof')
        if st!='not_applicable' and ((combined_surfaces & BOUNDARY_SURFACES) or BOUNDARY_TERMS.search(combined_text)) and evidence_kind(row) not in BOUNDARY_EVIDENCE:
            errors.append(f'adversarial_checks[{i}] {row.get("id")} boundary/input check requires evidence_kind non_ascii_boundary_test|malformed_input_test|length_boundary_test|json_boundary_test|schema_validation_test')
        if st!='not_applicable' and PANIC_TERMS.search(combined_text):
            if evidence_kind(row) not in PANIC_EVIDENCE:
                errors.append(f'adversarial_checks[{i}] {row.get("id")} panic/no-panic audit requires evidence_kind panic_audit|implicit_panic_audit')
            if method_is_mere_grep(row):
                errors.append(f'adversarial_checks[{i}] {row.get("id")} panic/no-panic audit cannot be mere grep')
        if st!='not_applicable':
            validate_subprocess_lifecycle_evidence(row.get('id') or i, combined_text, subprocess_lifecycle_evidence_text([row]), errors, kind_in_scope=evidence_kind(row)==SUBPROCESS_LIFECYCLE_EVIDENCE_KIND)
            if sv in BLOCKING or any(ref.get('severity') in BLOCKING for ref in referenced):
                validate_rpc_cleanup_evidence(row.get('id') or i, combined_text, [row], errors)
                if st=='pass' and auth_status_mapping_claimed(combined_text) and not auth_status_has_format_tolerance_evidence(row_evidence_text([row])):
                    errors.append(f"auth_status[{row.get('id') or i}] login-status mapping claimed but evidence covers one literal form only; JSON-parsed or format-variant fixtures required")
    missing_acceptance=sorted(set(required_acceptance)-covered_acceptance_ids)
    if missing_acceptance: errors.append('adversarial_checks missing shaped adversarial_acceptance IDs: '+','.join(missing_acceptance))
    for k in ('adversarial_p0_count','adversarial_p1_count'):
        if not nni(summary.get(k)): errors.append(f'grade_summary.{k} must be a non-negative integer for medium/high code')
    if nni(summary.get('adversarial_p0_count')) and summary.get('adversarial_p0_count')!=calc['P0']: errors.append(f"grade_summary.adversarial_p0_count={summary.get('adversarial_p0_count')} disagrees with calculated {calc['P0']}")
    if nni(summary.get('adversarial_p1_count')) and summary.get('adversarial_p1_count')!=calc['P1']: errors.append(f"grade_summary.adversarial_p1_count={summary.get('adversarial_p1_count')} disagrees with calculated {calc['P1']}")
    if nni(summary.get('p0_count')) and summary.get('p0_count')<calc['P0']: errors.append('grade_summary.p0_count undercounts blocking adversarial P0 findings')
    if nni(summary.get('p1_count')) and summary.get('p1_count')<calc['P1']: errors.append('grade_summary.p1_count undercounts blocking adversarial P1 findings')
    uv=inv.get('unverified_items') if isinstance(inv,dict) else None
    if uv is None: errors.append('trust_surface_inventory.unverified_items is required')
    elif not isinstance(uv,list): errors.append('trust_surface_inventory.unverified_items must be a list')
    else:
        for i,item in enumerate(uv):
            if sev(item) in BLOCKING: errors.append(f'trust_surface_inventory.unverified_items[{i}] is blocking: {sev(item)}')
    blocking_ids={k for k,v in required_acceptance.items() if v.get('severity') in BLOCKING}
    for i,row in enumerate(deferred):
        if not isinstance(row,dict): errors.append(f'deferred_claims[{i}] must be an object'); continue
        if row.get('current_scope_implementable') is True and not has_ref(row): errors.append(f'deferred_claims[{i}] current-scope item lacks evidence_ref or acceptance/waiver ref')
        if row.get('current_scope_implementable') is True and row.get('waiver') is True and sev(row) in BLOCKING and not any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref')): errors.append(f'deferred_claims[{i}] blocking current-scope waiver lacks tracked maintainer/user waiver ref')
        if blocking_ids and references_any_id(row, blocking_ids) and not has_tracked_waiver_or_scope_basis(row):
            errors.append(f'deferred_claims[{i}] defers current P0/P1 adversarial acceptance without tracked waiver or scope_basis_ref')
def lint(task_type,risk_level,grade_file,outcome_file,repo_root=None):
    errors=[]; gbs=blocks(grade_file); summary=first(gbs,'grade_summary'); acceptance=first(gbs,'acceptance_status')
    validate_required(summary,acceptance,errors); gated=is_gate(task_type,risk_level); code_gate=(task_type=='code')
    obs=blocks(outcome_file, include_front_matter=True) if code_gate or gated else []
    grade_text=grade_file.read_text(encoding='utf-8') if grade_file.exists() else ''
    outcome_text=outcome_file.read_text(encoding='utf-8') if outcome_file.exists() and (code_gate or gated) else ''
    if code_gate:
        validate_code_baseline(summary,gbs,errors,outcome_acceptance_metadata_from_file(obs,outcome_file),acceptance,obs,markdown_bullet_acceptance_metadata(grade_file),grade_text,outcome_text,repo_root=repo_root)
    if gated:
        validate_outcome(obs,errors)
        required=adversarial_acceptance_metadata(obs)
        validate_adv(summary,gbs,errors,required) if isinstance(summary,dict) else errors.append('cannot validate adversarial grade without grade_summary')
    return {'grade_lint':{'status':'fail' if errors else 'pass','task_type':task_type,'risk_level':risk_level,'code_baseline_gate':code_gate,'medium_high_code_gate':gated,'grade_file':str(grade_file),'outcome_file':str(outcome_file),'errors':errors}}
def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--task-type',required=True,choices=['code','docs','infra','refactor','spec']); ap.add_argument('--risk-level',required=True,choices=['low','medium','high']); ap.add_argument('--grade-file',required=True); ap.add_argument('--outcome-file',required=True); ap.add_argument('--evidence-file'); ap.add_argument('--repo-root')
    a=ap.parse_args(argv)
    repo_root=Path(a.repo_root).resolve() if a.repo_root else None
    try: result=lint(a.task_type,a.risk_level,Path(a.grade_file).resolve(),Path(a.outcome_file).resolve(),repo_root=repo_root)
    except LintError as e: result={'grade_lint':{'status':'fail','task_type':a.task_type,'risk_level':a.risk_level,'grade_file':str(Path(a.grade_file).resolve()),'outcome_file':str(Path(a.outcome_file).resolve()),'errors':[str(e)]}}
    payload=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if a.evidence_file:
        out=Path(a.evidence_file).resolve(); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(payload,encoding='utf-8')
    print(payload,end=''); return 0 if result['grade_lint']['status']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
