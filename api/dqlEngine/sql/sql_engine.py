"""Minimal SQL mode over DQL document corpora."""

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from utils.config import Config


@dataclass
class SqlPlan:
    raw_sql: str
    executable_sql: str
    table: str
    select_columns: list[str]
    where: str
    where_columns: list[str]
    group_by: str
    group_columns: list[str]
    order_by: str
    order_columns: list[str]
    limit: int | None
    has_aggregates: bool


class SqlEngine:
    """Execute a safe, small SQL subset by extracting rows from unstructured docs."""

    BASE_COLUMNS = {"id", "doc_id", "name", "type_doc", "owner", "source_ref", "source_name", "source_type"}
    INTERNAL_COLUMNS = {"evidence"}
    ROW_PREFIX_METADATA_COLUMNS = ("id", "source_ref", "source_name")
    ROW_SUFFIX_METADATA_COLUMNS = ("evidence",)
    ROW_METADATA_COLUMNS = ROW_PREFIX_METADATA_COLUMNS + ROW_SUFFIX_METADATA_COLUMNS
    AGGREGATE_FUNCTIONS = {"count", "sum", "avg", "min", "max"}
    UNSUPPORTED = (" join ", " having ", " union ", " intersect ", " except ", " with ")
    NL_SQL_MODES = {"sql_table", "natural_answer", "needs_clarification"}
    WHERE_OPERATORS = {"=", "!=", "<>", ">", ">=", "<", "<=", "like"}
    SQL_CONTEXT_REDACTIONS = (
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?)\b",
        r"\b(?:ignore|disregard|forget)\s+(?:the\s+)?(?:system|developer|user|assistant)\s+(?:prompt|instructions?)\b",
        r"\boverride\s+(?:the\s+)?(?:system|developer|user|assistant)\s+(?:prompt|instructions?)\b",
        r"\b(?:do\s+not|don't)\s+follow\s+(?:the\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?)\b",
        r"\b(?:reveal|print|show|dump)\s+(?:the\s+)?(?:system|developer)\s+(?:prompt|instructions?)\b",
        r"\bjailbreak\b",
        r"<\s*/?\s*(?:script|system|developer|assistant|user)\b[^>]*>",
    )
    STRICT_SQL_CONTEXT_MARKERS = (
        "ignore previous",
        "ignore all previous",
        "disregard previous",
        "forget previous",
        "override system",
        "override developer",
        "do not follow previous",
        "don't follow previous",
        "system prompt",
        "developer prompt",
        "system:",
        "developer:",
        "assistant:",
        "user:",
        "jailbreak",
        "prompt injection",
        "previous instructions",
        "prior instructions",
        "above instructions",
        "```",
        "<script",
    )

    def __init__(self, cfg: Config, user_id: str, request_id: str):
        self._cfg = cfg
        self._storage = cfg.get_storage()
        self._llm = cfg.get_LLM()
        self._language = cfg.get_DQL(user_id)
        self._logger = cfg.get_logger("SqlEngine", request_id)
        self._request_id = request_id

    @staticmethod
    def is_sql(prompt: str) -> bool:
        """Return True when the prompt is clearly a SELECT query."""
        sql = SqlEngine._clean_sql(prompt)
        return bool(re.match(r"(?is)^\s*select\s+", sql))

    def answer(self, prompt: str, user_id: str, chat_id: str, source_id: str) -> dict:
        """Run SQL mode and return the same high-level response shape as DQL."""
        self._logger.info("SQL mode detected.")
        try:
            return self._answer(prompt, user_id, chat_id, source_id)
        except ValueError as exc:
            self._logger.warning(f"SQL mode rejected request: {exc}")
            return self._error_response(prompt, source_id, str(exc))

    def _answer(self, prompt: str, user_id: str, chat_id: str, source_id: str) -> dict:
        """Internal SQL execution path. Raises ValueError for user-facing SQL errors."""
        plan = self._parse_sql(prompt)
        self._logger.info(f"SQL parsed. table={plan.table}; select={plan.select_columns}; where={plan.where}; order_by={plan.order_by}; limit={plan.limit}")

        docs, resolved_source, warnings = self._load_docs(plan.table, source_id)
        self._logger.info(f"Loaded {len(docs)} candidate documents from source '{resolved_source}'.")

        needed_columns = self._needed_columns(plan)
        semantic_columns = [
            c for c in needed_columns
            if c not in self.BASE_COLUMNS and c not in self.INTERNAL_COLUMNS and c != "*"
        ]
        mapped_columns, unmapped_columns = self._split_mapped_columns(semantic_columns)
        self._logger.info(f"Semantic columns: {semantic_columns}. Ontology mapped={mapped_columns}; dynamic={unmapped_columns}.")

        rows, extraction_warnings = self._extract_rows(docs, semantic_columns, plan.where)
        warnings.extend(extraction_warnings)
        raw_row_count = len(rows)
        self._logger.info(f"Extracted {raw_row_count} raw rows before SQL filtering.")

        rows, removed_duplicates = self._deduplicate_rows(rows)
        if removed_duplicates:
            self._logger.info(f"Deduplicated SQL rows: {raw_row_count} -> {len(rows)}.")
        else:
            self._logger.info("No duplicate SQL rows detected.")

        result_columns, result_rows = self._run_sqlite(rows, plan)
        self._logger.info(f"SQLite execution completed with {len(result_rows)} result rows.")

        content = self._summarize(plan, resolved_source, result_rows, unmapped_columns, warnings)
        table = {
            "id": "sql_result",
            "title": "Risultato SQL",
            "columns": result_columns,
            "rows": result_rows,
        }

        sources = self._collect_sources(docs)
        task = {
            "id": f"{self._request_id}_sql",
            "prompt": prompt,
            "structured_prompt": {
                "command": "sql",
                "from": [resolved_source],
                "what": [{"name": c} for c in needed_columns if c != "*"],
                "how": {
                    "where": plan.where,
                    "group_by": plan.group_by,
                    "order_by": plan.order_by,
                    "limit": plan.limit,
                },
            },
            "result": content,
            "sources": sources,
        }

        return {
            "content": content,
            "result": content,
            "tables": [table],
            "details": {
                "prompt_process": prompt,
                "tasks": [task],
                "sql": {
                    "plan": {
                        "table": plan.table,
                        "source": resolved_source,
                        "select_columns": plan.select_columns,
                        "where": plan.where,
                        "group_by": plan.group_by,
                        "order_by": plan.order_by,
                        "limit": plan.limit,
                        "has_aggregates": plan.has_aggregates,
                    },
                    "processed_documents": len(docs),
                    "raw_rows": raw_row_count,
                    "deduplicated_rows": len(rows),
                    "removed_duplicates": removed_duplicates,
                    "extracted_columns": semantic_columns,
                    "mapped_columns": mapped_columns,
                    "unmapped_columns": unmapped_columns,
                    "warnings": warnings,
                },
                "used_documents": list({src["source_type"] for src in sources if src.get("source_type")}),
                "used_sources": sources,
            },
        }

    def _error_response(self, prompt: str, source_id: str, error: str) -> dict:
        content = f"La query SQL non e' supportata dall'MVP corrente: {error}"
        task = {
            "id": f"{self._request_id}_sql_error",
            "prompt": prompt,
            "structured_prompt": {
                "command": "sql errore",
                "from": [source_id],
                "how": {"error": error},
            },
            "result": content,
            "sources": [],
        }

        return {
            "content": content,
            "result": content,
            "tables": [],
            "details": {
                "prompt_process": prompt,
                "tasks": [task],
                "sql": {
                    "mode": "error",
                    "error": error,
                },
                "used_documents": [],
                "used_sources": [],
            },
        }

    def answer_from_natural_language(self, prompt: str, user_id: str, chat_id: str, source_id: str) -> dict | None:
        """Try to convert a guided natural-language table request into SQL mode."""
        if not self._is_nl_sql_candidate(prompt, source_id):
            return None

        nl_prompt = self._language.prompts.get("it", {}).get("NaturalLanguageToSql.json")
        if not nl_prompt:
            self._logger.warning("NaturalLanguageToSql.json prompt template not found. Falling back to standard DQL.")
            return None

        self._logger.info("Trying guided natural-language to SQL routing.")
        requested_source = self._source_from_prompt(prompt)
        effective_source = requested_source or source_id
        if requested_source and requested_source.lower() != str(source_id).lower():
            self._logger.info(f"Natural language request explicitly targets corpus '{requested_source}'.")

        plan = self._llm.invoke(
            nl_prompt,
            {
                "query": prompt,
                "current_source": effective_source,
                "base_columns": str(sorted(self.BASE_COLUMNS)),
                "ontology_columns": self._ontology_columns_for_prompt(),
            },
        )

        if not isinstance(plan, dict):
            self._logger.warning("NL-to-SQL returned an invalid payload. Falling back to standard DQL.")
            return None

        mode = str(plan.get("mode", "")).strip().lower()
        if mode not in self.NL_SQL_MODES:
            self._logger.warning(f"NL-to-SQL returned unsupported mode '{mode}'. Falling back to standard DQL.")
            return None

        self._logger.info(f"NL-to-SQL mode: {mode}.")

        if mode == "natural_answer":
            self._logger.info("NL-to-SQL router declined SQL mode.")
            return None

        if mode == "needs_clarification":
            explicit_plan = self._plan_from_explicit_column_list(prompt, effective_source, plan)
            if explicit_plan:
                self._logger.info("NL-to-SQL clarification overridden by explicit column list.")
                plan = explicit_plan
                mode = "sql_table"
            else:
                return self._clarification_response(prompt, effective_source, plan)

        try:
            sql = self._sql_from_nl_plan(plan, effective_source, requested_source)
        except ValueError as exc:
            self._logger.warning(f"NL-to-SQL plan is incomplete: {exc}")
            plan["clarification"] = str(exc)
            return self._clarification_response(prompt, effective_source, plan)

        self._logger.info(f"Generated SQL from natural language: {sql}")
        response = self.answer(sql, user_id, chat_id, effective_source)
        response["details"].setdefault("sql", {})
        response["details"]["sql"]["natural_language_query"] = prompt
        response["details"]["sql"]["natural_language_plan"] = plan
        response["details"]["sql"]["generated_sql"] = sql
        response["details"]["prompt_process"] = sql
        return response

    def _is_nl_sql_candidate(self, prompt: str, source_id: str) -> bool:
        text = prompt.lower()
        if self.is_sql(prompt):
            return False

        tabular_signals = [
            "tabella",
            "colonne",
            "righe",
            "dataframe",
            "ordina",
            "ordinata",
            "ordinati",
            "massimo",
            "massime",
            "prime ",
            "primi ",
        ]
        has_tabular_signal = any(signal in text for signal in tabular_signals)
        if not has_tabular_signal:
            return False

        known_fields = set(self.BASE_COLUMNS)
        known_fields.update(w.get("name", "") for w in self._language.get_what())
        has_field_signal = "_" in prompt or any(field and field.lower() in text for field in known_fields)
        has_source_signal = bool(source_id and source_id.lower() in text) or "corpus" in text
        return has_field_signal or has_source_signal

    @staticmethod
    def _source_from_prompt(prompt: str) -> str:
        match = re.search(
            r"(?is)\b(?:corpus|fonte|source)\s+(?:di\s+)?[\"'`]?([A-Za-z_][\w.-]*)",
            prompt,
        )
        return match.group(1).strip().rstrip(".,;:!?)]}") if match else ""

    def _plan_from_explicit_column_list(self, prompt: str, source_id: str, plan: dict) -> dict:
        columns = self._explicit_columns_from_prompt(prompt)
        if not columns:
            return {}

        known_columns = {column.lower() for column in self.BASE_COLUMNS}
        known_columns.update(w.get("name", "").lower() for w in self._language.get_what())

        updated_plan = dict(plan)
        updated_plan["mode"] = "sql_table"
        updated_plan["table"] = source_id
        updated_plan["select"] = columns
        updated_plan.setdefault("where", [])
        updated_plan.setdefault("order_by", [])
        updated_plan.setdefault("limit", None)
        updated_plan["unmapped_columns"] = [
            column for column in columns
            if column.lower() not in known_columns
        ]
        updated_plan["clarification"] = ""
        return updated_plan

    def _explicit_columns_from_prompt(self, prompt: str) -> list[str]:
        match = re.search(
            r"(?is)\bcon\s+(.+?)(?=\s+(?:dal|dalla|dallo|dai|dalle|nel|nella|ordinat[aoie]?|massimo|massime|limite|limit)\b|[.!?]?$)",
            prompt,
        )
        if not match:
            return []

        segment = match.group(1).strip()
        if not self._looks_like_column_segment(segment):
            return []

        normalized = re.sub(r"(?i)\s+\be\b\s+", ",", segment)
        columns = []
        for raw_column in normalized.split(","):
            column = re.sub(
                r"(?i)^(?:le|la|il|lo|i|gli|l'|colonna|colonne)\s+",
                "",
                raw_column.strip(),
            ).strip(" \"'`.,;:!?)]}")
            if column:
                columns.append(column)

        return self._dedupe(columns)

    @staticmethod
    def _looks_like_column_segment(segment: str) -> bool:
        text = segment.lower()
        if not ("," in text or re.search(r"\s+\be\b\s+", text)):
            return False
        vague_terms = ("miglior", "peggior", "solid", "important", "interessant", "rischios")
        return not any(term in text for term in vague_terms)

    def _ontology_columns_for_prompt(self) -> str:
        rows = []
        for item in self._language.get_what():
            name = item.get("name", "")
            if not name:
                continue
            rows.append(f"- {name}: {item.get('definition', '')}")
        return "\n".join(rows)

    def _clarification_response(self, prompt: str, source_id: str, plan: dict) -> dict:
        clarification = str(plan.get("clarification", "")).strip()
        if not clarification:
            clarification = "Per costruire una tabella affidabile devo chiarire colonne, corpus o criterio di ordinamento."

        self._logger.info(f"NL-to-SQL needs clarification: {clarification}")
        task = {
            "id": f"{self._request_id}_nl_sql_clarification",
            "prompt": prompt,
            "structured_prompt": {
                "command": "sql chiarimento",
                "from": [source_id],
                "how": {"clarification": clarification},
            },
            "result": clarification,
            "sources": [],
        }

        return {
            "content": clarification,
            "result": clarification,
            "tables": [],
            "details": {
                "prompt_process": prompt,
                "tasks": [task],
                "sql": {
                    "natural_language_query": prompt,
                    "natural_language_plan": plan,
                    "mode": "needs_clarification",
                },
                "used_documents": [],
                "used_sources": [],
            },
        }

    def _sql_from_nl_plan(self, plan: dict, source_id: str, requested_source: str = "") -> str:
        table = str(requested_source or plan.get("table") or source_id or "").strip()
        if not table:
            raise ValueError("Non ho individuato il corpus/tabella da interrogare.")

        select_columns = self._columns_from_nl_value(plan.get("select", []))
        if not select_columns:
            raise ValueError("Non ho individuato quali colonne mostrare in tabella.")
        if "source_ref" not in select_columns:
            select_columns.append("source_ref")

        sql_parts = [
            "SELECT " + ", ".join(self._format_identifier(c) for c in select_columns),
            "FROM " + self._format_identifier(table),
        ]

        where_sql = self._where_from_nl_plan(plan.get("where", []))
        if where_sql:
            sql_parts.append("WHERE " + where_sql)

        order_sql = self._order_from_nl_plan(plan.get("order_by", []))
        if order_sql:
            sql_parts.append("ORDER BY " + order_sql)

        limit = self._limit_from_nl_plan(plan.get("limit"))
        if limit is not None:
            sql_parts.append(f"LIMIT {limit}")

        return "\n".join(sql_parts)

    def _columns_from_nl_value(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value.strip() else []
        if not isinstance(value, list):
            return []

        columns = []
        for item in value:
            if isinstance(item, dict):
                column = item.get("resolved") or item.get("column") or item.get("name") or item.get("requested")
            else:
                column = item
            column = str(column or "").strip()
            if column:
                columns.append(column)
        return self._dedupe(columns)

    def _where_from_nl_plan(self, value: Any) -> str:
        if not isinstance(value, list):
            return ""

        clauses = []
        for condition in value:
            if not isinstance(condition, dict):
                continue
            column = str(condition.get("column", "")).strip()
            operator = str(condition.get("operator", "")).strip().lower()
            if not column or operator not in self.WHERE_OPERATORS:
                continue
            clauses.append(
                f"{self._format_identifier(column)} {operator.upper()} {self._format_literal(condition.get('value', ''))}"
            )

        return " AND ".join(clauses)

    def _order_from_nl_plan(self, value: Any) -> str:
        if isinstance(value, dict):
            value = [value]
        if isinstance(value, str):
            value = [{"column": value, "direction": "ASC"}] if value.strip() else []
        if not isinstance(value, list):
            return ""

        clauses = []
        for item in value:
            if isinstance(item, dict):
                column = str(item.get("column", "")).strip()
                direction = str(item.get("direction", "ASC")).strip().upper()
            else:
                column = str(item or "").strip()
                direction = "ASC"
            if not column:
                continue
            if direction not in {"ASC", "DESC"}:
                direction = "ASC"
            clauses.append(f"{self._format_identifier(column)} {direction}")
        return ", ".join(clauses)

    @staticmethod
    def _limit_from_nl_plan(value: Any) -> int | None:
        try:
            limit = int(value)
            return limit if limit > 0 else None
        except (TypeError, ValueError):
            return None

    def _format_identifier(self, identifier: str) -> str:
        identifier = self._unquote_identifier(str(identifier).strip())
        if re.fullmatch(r"[A-Za-z_]\w*", identifier):
            return identifier
        return self._quote_ident(identifier)

    @staticmethod
    def _format_literal(value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)

        text = str(value)
        if re.fullmatch(r"-?\d+(?:\.\d+)?", text.strip()):
            return text.strip()
        return "'" + text.replace("'", "''") + "'"

    @staticmethod
    def _clean_sql(prompt: str) -> str:
        sql = prompt.strip()
        fence_match = re.match(r"(?is)^```(?:sql)?\s*(.*?)\s*```$", sql)
        if fence_match:
            sql = fence_match.group(1).strip()
        return sql.rstrip(";").strip()

    def _parse_sql(self, prompt: str) -> SqlPlan:
        sql = self._clean_sql(prompt)
        lowered = f" {sql.lower()} "

        if not lowered.lstrip().startswith("select "):
            raise ValueError("SQL mode supports only SELECT queries.")
        if any(token in lowered for token in self.UNSUPPORTED):
            raise ValueError("SQL MVP supports SELECT/FROM/WHERE/GROUP BY/ORDER BY/LIMIT only; joins, HAVING and set operations are not supported.")
        if ";" in sql:
            raise ValueError("Multiple SQL statements are not supported.")

        match = re.match(
            r"(?is)^\s*select\s+(?P<select>.*?)\s+from\s+(?P<table>\"[^\"]+\"|'[^']+'|`[^`]+`|\[[^\]]+\]|[A-Za-z_][\w.-]*)(?P<rest>.*)$",
            sql,
        )
        if not match:
            raise ValueError("Could not parse SQL. Expected: SELECT ... FROM ...")

        select_part = match.group("select").strip()

        table = self._unquote_identifier(match.group("table").strip())
        rest = match.group("rest").strip()

        where = self._section(rest, "where", ["group by", "order by", "limit"])
        group_by = self._section(rest, "group by", ["order by", "limit"])
        order_by = self._section(rest, "order by", ["limit"])
        limit_value = self._parse_limit(rest)
        select_columns = self._parse_select_columns(select_part)
        where_columns = self._columns_from_expression(where)
        group_columns = self._columns_from_group(group_by)
        order_columns = self._columns_from_order(order_by)
        executable_sql = self._replace_from_table(sql)

        return SqlPlan(
            raw_sql=sql,
            executable_sql=executable_sql,
            table=table,
            select_columns=select_columns,
            where=where,
            where_columns=where_columns,
            group_by=group_by,
            group_columns=group_columns,
            order_by=order_by,
            order_columns=order_columns,
            limit=limit_value,
            has_aggregates=self._has_aggregate(select_part),
        )

    @staticmethod
    def _section(text: str, start_keyword: str, stop_keywords: list[str]) -> str:
        pattern = rf"(?is)\b{re.escape(start_keyword)}\b\s+(.*)"
        match = re.search(pattern, text)
        if not match:
            return ""
        section = match.group(1).strip()
        stop_positions = []
        for keyword in stop_keywords:
            stop = re.search(rf"(?is)\b{re.escape(keyword)}\b", section)
            if stop:
                stop_positions.append(stop.start())
        if stop_positions:
            section = section[:min(stop_positions)].strip()
        return section

    @staticmethod
    def _parse_limit(text: str) -> int | None:
        match = re.search(r"(?is)\blimit\s+(\d+)\b", text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _replace_from_table(sql: str) -> str:
        return re.sub(
            r"(?is)\bfrom\s+(\"[^\"]+\"|'[^']+'|`[^`]+`|\[[^\]]+\]|[A-Za-z_][\w.-]*)",
            "FROM dql_rows",
            sql,
            count=1,
        )

    def _parse_select_columns(self, select_part: str) -> list[str]:
        if select_part.strip() == "*":
            return ["*"]
        columns = []
        for raw in self._split_csv(select_part):
            columns.extend(self._columns_from_select_item(raw))
        return columns

    def _columns_from_select_item(self, item: str) -> list[str]:
        expression = re.split(r"(?is)\s+as\s+", item.strip())[0].strip()
        aggregate_match = re.fullmatch(
            r"(?is)(count|sum|avg|min|max)\s*\((.*?)\)",
            expression,
        )
        if aggregate_match:
            argument = re.sub(r"(?is)^\s*distinct\s+", "", aggregate_match.group(2).strip())
            if argument == "*":
                return []
            return [self._unquote_identifier(argument)]

        return [self._unquote_identifier(expression)]

    @classmethod
    def _has_aggregate(cls, select_part: str) -> bool:
        functions = "|".join(sorted(cls.AGGREGATE_FUNCTIONS))
        return bool(re.search(rf"(?is)\b({functions})\s*\(", select_part))

    @staticmethod
    def _split_csv(text: str) -> list[str]:
        parts = []
        current = []
        quote = None
        for char in text:
            if char in ("'", '"', "`"):
                quote = None if quote == char else char if quote is None else quote
            if char == "," and quote is None:
                parts.append("".join(current).strip())
                current = []
                continue
            current.append(char)
        if current:
            parts.append("".join(current).strip())
        return [p for p in parts if p]

    def _columns_from_expression(self, expression: str) -> list[str]:
        if not expression:
            return []
        columns = [self._unquote_identifier(c) for c in re.findall(r'"([^"]+)"|`([^`]+)`|\[([^\]]+)\]', expression) for c in c if c]
        bare_pattern = r"(?i)\b([A-Za-z_][\w.-]*)\s*(?:=|!=|<>|>=|<=|>|<|\bin\b|\blike\b)"
        for column in re.findall(bare_pattern, expression):
            if column.lower() not in {"and", "or", "not", "is", "null"}:
                columns.append(column)
        return self._dedupe(columns)

    def _columns_from_group(self, group_by: str) -> list[str]:
        if not group_by:
            return []
        return self._dedupe([
            self._unquote_identifier(item.strip())
            for item in self._split_csv(group_by)
            if item.strip()
        ])

    def _columns_from_order(self, order_by: str) -> list[str]:
        if not order_by:
            return []
        columns = []
        for item in self._split_csv(order_by):
            column = re.sub(r"(?is)\s+(asc|desc)\s*$", "", item.strip())
            columns.extend(self._columns_from_select_item(column))
        return self._dedupe(columns)

    @staticmethod
    def _unquote_identifier(identifier: str) -> str:
        identifier = identifier.strip()
        if len(identifier) >= 2 and (
            (identifier[0] == identifier[-1] and identifier[0] in ("'", '"', "`"))
            or (identifier[0] == "[" and identifier[-1] == "]")
        ):
            return identifier[1:-1]
        return identifier

    def _needed_columns(self, plan: SqlPlan) -> list[str]:
        columns = []
        if plan.select_columns == ["*"]:
            columns.extend(sorted(self.BASE_COLUMNS))
        else:
            columns.extend(plan.select_columns)
        columns.extend(plan.where_columns)
        columns.extend(plan.group_columns)
        columns.extend(plan.order_columns)
        columns.extend(["source_ref", "evidence"])
        return self._dedupe(columns)

    def _split_mapped_columns(self, columns: list[str]) -> tuple[list[str], list[str]]:
        known = {w.get("name", "").lower() for w in self._language.get_what()}
        mapped = [c for c in columns if c.lower() in known]
        unmapped = [
            c for c in columns
            if c.lower() not in known and c not in self.BASE_COLUMNS and c not in self.INTERNAL_COLUMNS
        ]
        return mapped, unmapped

    def _load_docs(self, table: str, source_id: str) -> tuple[list[dict], str, list[str]]:
        warnings = []
        candidates = [table]
        if table.lower() in {"documents", "docs", "corpus"}:
            candidates = [source_id]
        elif source_id and source_id not in candidates:
            candidates.append(source_id)

        for candidate in candidates:
            docs = self._storage.get_all_documents(candidate) or []
            if docs:
                return docs, candidate, warnings

        raise ValueError(f"No documents found for SQL source '{table}'.")

    def _extract_rows(self, docs: list[dict], semantic_columns: list[str], where: str) -> tuple[list[dict], list[str]]:
        if not semantic_columns:
            return [self._base_row(doc) for doc in docs], []

        prompt = self._language.prompts.get("it", {}).get("SqlExtractRows.json")
        if not prompt:
            raise ValueError("SqlExtractRows.json prompt template not found.")

        rows = []
        warnings = []
        for index, doc in enumerate(docs, start=1):
            self._logger.info(f"Extracting SQL rows from document {index}/{len(docs)}: {doc.get('name', '')}")
            base_row = self._base_row(doc)
            result = self._extract_rows_from_doc(
                prompt,
                doc,
                semantic_columns,
                where,
                index,
                len(docs),
                warnings,
            )
            if not isinstance(result, list):
                result = []
            for item in result:
                if not isinstance(item, dict):
                    continue
                row = dict(base_row)
                for column in semantic_columns + ["evidence"]:
                    row[column] = self._scalar(item.get(column, ""))
                rows.append(row)

        return rows, warnings

    def _extract_rows_from_doc(
        self,
        prompt: Any,
        doc: dict,
        semantic_columns: list[str],
        where: str,
        index: int,
        total_docs: int,
        warnings: list[str],
    ) -> Any:
        inputs = {
            "columns": str(semantic_columns),
            "where": where or "Nessuna condizione WHERE.",
            "context": self._format_sql_context(doc, sanitize=False),
        }
        try:
            return self._llm.invoke(prompt, inputs)
        except Exception as exc:
            if not self._is_content_filter_error(exc):
                raise

            doc_name = doc.get("name", "") or f"documento {index}"
            self._logger.warning(
                f"Provider content filter while extracting SQL rows from {doc_name}. "
                "Retrying with stricter document redaction."
            )

        inputs["context"] = self._format_sql_context(doc, sanitize=True, strict=True)
        try:
            return self._llm.invoke(prompt, inputs)
        except Exception as exc:
            if not self._is_content_filter_error(exc):
                raise

            doc_name = doc.get("name", "") or f"documento {index}"
            self._logger.warning(
                f"Skipping SQL extraction for document {index}/{total_docs} ({doc_name}) "
                "because the provider content filter rejected the document."
            )
            warnings.append(
                f"Documento {doc_name} saltato durante l'estrazione SQL: il provider LLM ha bloccato il contenuto."
            )
            return []

    def _format_sql_context(self, doc: dict, sanitize: bool = True, strict: bool = False) -> str:
        normalized = self._normalize_doc(doc)
        text = str(normalized.get("text", ""))
        if sanitize:
            text = self._sanitize_sql_document_text(text, strict)
        payload = {
            "source_ref": str(normalized["source_ref"]),
            "source_name": str(normalized["source_name"]),
            "source_type": str(normalized["source_type"]),
            "document_text": text,
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def _sanitize_sql_document_text(cls, text: str, strict: bool = False) -> str:
        safe_text = text
        for pattern in cls.SQL_CONTEXT_REDACTIONS:
            safe_text = re.sub(pattern, "[instruction-like text omitted]", safe_text, flags=re.IGNORECASE)

        if strict:
            safe_lines = []
            for line in safe_text.splitlines():
                lowered = line.lower()
                if any(marker in lowered for marker in cls.STRICT_SQL_CONTEXT_MARKERS):
                    safe_lines.append("[instruction-like line omitted]")
                else:
                    safe_lines.append(line)
            safe_text = "\n".join(safe_lines)

        return safe_text

    @staticmethod
    def _is_content_filter_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return (
            "content_filter" in text
            or "responsibleaipolicyviolation" in text
            or "filtered due to the prompt" in text
        )

    @staticmethod
    def _normalize_doc(doc: dict) -> dict:
        source_ref = str(doc.get("source_ref") or doc.get("name") or doc.get("_id") or doc.get("type_doc") or "")
        return {
            "name": doc.get("name") or source_ref,
            "text": doc.get("text", ""),
            "type": doc.get("type_doc") or doc.get("type") or "",
            "source_ref": source_ref,
            "source_name": doc.get("name") or source_ref,
            "source_type": doc.get("type_doc") or doc.get("type") or "",
        }

    def _base_row(self, doc: dict) -> dict:
        normalized = self._normalize_doc(doc)
        return {
            "id": self._normalize_uda_id(normalized["source_ref"]),
            "doc_id": str(doc.get("_id") or normalized["source_ref"]),
            "name": normalized["source_name"],
            "type_doc": normalized["source_type"],
            "owner": doc.get("owner", ""),
            "source_ref": normalized["source_ref"],
            "source_name": normalized["source_name"],
            "source_type": normalized["source_type"],
            "evidence": "",
        }

    @staticmethod
    def _normalize_uda_id(source_ref: Any) -> str:
        text = str(source_ref or "").strip()
        if not text:
            return ""

        name = text.replace("\\", "/").rsplit("/", 1)[-1]
        stem = name.rsplit(".", 1)[0] if "." in name else name
        if re.fullmatch(r"\d+", stem):
            return str(int(stem))
        return stem or text

    def _deduplicate_rows(self, rows: list[dict]) -> tuple[list[dict], int]:
        deduplicated = []
        seen = set()

        for row in rows:
            key = tuple(
                (column, self._normalize_for_deduplication(row.get(column, "")))
                for column in sorted(row.keys())
                if column != "evidence"
            )
            if key in seen:
                continue

            seen.add(key)
            deduplicated.append(row)

        return deduplicated, len(rows) - len(deduplicated)

    @staticmethod
    def _normalize_for_deduplication(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return str(value)
        return re.sub(r"\s+", " ", str(value).strip().lower())

    def _run_sqlite(self, rows: list[dict], plan: SqlPlan) -> tuple[list[str], list[dict]]:
        if not rows:
            return self._result_columns(plan), []

        columns = self._dedupe([c for row in rows for c in row.keys()])
        if self._is_row_level_result(plan):
            prefix_metadata_columns = self._result_metadata_columns(plan, columns, self.ROW_PREFIX_METADATA_COLUMNS)
            suffix_metadata_columns = self._result_metadata_columns(plan, columns, self.ROW_SUFFIX_METADATA_COLUMNS)
        else:
            prefix_metadata_columns = []
            suffix_metadata_columns = []
        executable_sql = self._sql_with_result_metadata(
            plan.executable_sql,
            prefix_metadata_columns,
            suffix_metadata_columns,
        )
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "CREATE TABLE dql_rows ("
                + ", ".join(f"{self._quote_ident(c)} NUMERIC" for c in columns)
                + ")"
            )
            placeholders = ", ".join("?" for _ in columns)
            quoted_columns = ", ".join(self._quote_ident(c) for c in columns)
            conn.executemany(
                f"INSERT INTO dql_rows ({quoted_columns}) VALUES ({placeholders})",
                [[row.get(c, "") for c in columns] for row in rows],
            )
            cursor = conn.execute(executable_sql)
            result_columns = [desc[0] for desc in cursor.description]
            result_rows = [self._normalize_result_metadata(dict(row)) for row in cursor.fetchall()]
            return result_columns, result_rows
        except sqlite3.Error as exc:
            raise ValueError(f"SQL execution failed: {exc}") from exc
        finally:
            conn.close()

    def _result_columns(self, plan: SqlPlan) -> list[str]:
        if plan.select_columns == ["*"]:
            return sorted(self.BASE_COLUMNS | self.INTERNAL_COLUMNS)
        if not self._is_row_level_result(plan):
            return self._dedupe(plan.select_columns)
        return self._dedupe(
            list(self.ROW_PREFIX_METADATA_COLUMNS) + plan.select_columns + list(self.ROW_SUFFIX_METADATA_COLUMNS)
        )

    @staticmethod
    def _is_row_level_result(plan: SqlPlan) -> bool:
        return not plan.has_aggregates and not plan.group_by

    def _result_metadata_columns(
        self,
        plan: SqlPlan,
        available_columns: list[str],
        wanted_columns: tuple[str, ...],
    ) -> list[str]:
        if plan.select_columns == ["*"]:
            return []

        selected = {column.lower() for column in plan.select_columns}
        available = {column.lower(): column for column in available_columns}
        return [
            available[column]
            for column in wanted_columns
            if column in available and column not in selected
        ]

    def _sql_with_result_metadata(
        self,
        sql: str,
        prefix_metadata_columns: list[str],
        suffix_metadata_columns: list[str],
    ) -> str:
        if not prefix_metadata_columns and not suffix_metadata_columns:
            return sql

        match = re.match(r"(?is)^\s*select\s+(?P<select>.*?)\s+from\s+dql_rows(?P<rest>.*)$", sql)
        if not match:
            metadata_columns = prefix_metadata_columns + suffix_metadata_columns
            metadata_select = ", ".join(self._quote_ident(column) for column in metadata_columns)
            return re.sub(r"(?is)^\s*select\s+", f"SELECT {metadata_select}, ", sql, count=1)

        select_parts = []
        if prefix_metadata_columns:
            select_parts.append(", ".join(self._quote_ident(column) for column in prefix_metadata_columns))
        select_parts.append(match.group("select").strip())
        if suffix_metadata_columns:
            select_parts.append(", ".join(self._quote_ident(column) for column in suffix_metadata_columns))

        return f"SELECT {', '.join(select_parts)} FROM dql_rows{match.group('rest')}"

    def _normalize_result_metadata(self, row: dict) -> dict:
        for column in self.ROW_METADATA_COLUMNS:
            if column in row and row[column] is not None:
                row[column] = str(row[column])
        return row

    @staticmethod
    def _quote_ident(identifier: str) -> str:
        return '"' + str(identifier).replace('"', '""') + '"'

    @staticmethod
    def _scalar(value: Any) -> Any:
        if isinstance(value, (int, float)) or value is None:
            return value
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        if isinstance(value, dict):
            return str(value)
        return str(value)

    @staticmethod
    def _collect_sources(docs: list[dict]) -> list[dict]:
        sources = []
        seen = set()
        for doc in docs:
            normalized = SqlEngine._normalize_doc(doc)
            key = (normalized["source_ref"], normalized["source_name"], normalized["source_type"])
            if key in seen:
                continue
            seen.add(key)
            sources.append({
                "source_ref": normalized["source_ref"],
                "source_name": normalized["source_name"],
                "source_type": normalized["source_type"],
            })
        return sources

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        result = []
        seen = set()
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    @staticmethod
    def _summarize(plan: SqlPlan, source: str, rows: list[dict], unmapped: list[str], warnings: list[str]) -> str:
        parts = [
            f"Ho eseguito la query SQL sul corpus '{source}' e ho ottenuto {len(rows)} righe.",
            "La tabella contiene il risultato strutturato della query.",
        ]
        if unmapped:
            parts.append("Colonne non presenti nell'ontologia trattate come concetti dinamici: " + ", ".join(unmapped) + ".")
        if warnings:
            parts.extend(warnings)
        return "\n\n".join(parts)
