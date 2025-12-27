# skills_ref/execution/dataview.py — Dataview query execution framework

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum, auto
import re
from pathlib import Path


class DataviewQueryType(Enum):
    """Supported Dataview query types."""
    TABLE = auto()
    LIST = auto()
    TASK = auto()
    CALENDAR = auto()


@dataclass
class DataviewField:
    """A field in a Dataview query."""
    name: str
    alias: Optional[str] = None
    expression: Optional[str] = None


@dataclass
class DataviewQuery:
    """Parsed Dataview query."""
    query_type: DataviewQueryType
    fields: List[DataviewField] = field(default_factory=list)
    source: Optional[str] = None  # FROM clause
    where: Optional[str] = None
    sort: Optional[str] = None
    group_by: Optional[str] = None
    flatten: Optional[str] = None
    limit: Optional[int] = None
    raw_query: str = ""


@dataclass
class DataviewResult:
    """Result of Dataview query execution."""
    success: bool
    data: List[Dict[str, Any]] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    error: Optional[str] = None
    query_type: DataviewQueryType = DataviewQueryType.LIST
    rendered: str = ""  # Markdown-rendered output


class DataviewParser:
    """Parse Dataview query language into structured query objects."""

    # Query type patterns
    QUERY_TYPE_PATTERN = re.compile(
        r'^(TABLE|LIST|TASK|CALENDAR)\b',
        re.IGNORECASE | re.MULTILINE
    )

    # Clause patterns
    FROM_PATTERN = re.compile(r'\bFROM\s+(.+?)(?=\bWHERE\b|\bSORT\b|\bGROUP\b|\bFLATTEN\b|\bLIMIT\b|$)', re.IGNORECASE | re.DOTALL)
    WHERE_PATTERN = re.compile(r'\bWHERE\s+(.+?)(?=\bSORT\b|\bGROUP\b|\bFLATTEN\b|\bLIMIT\b|$)', re.IGNORECASE | re.DOTALL)
    SORT_PATTERN = re.compile(r'\bSORT\s+(.+?)(?=\bGROUP\b|\bFLATTEN\b|\bLIMIT\b|$)', re.IGNORECASE | re.DOTALL)
    GROUP_PATTERN = re.compile(r'\bGROUP BY\s+(.+?)(?=\bFLATTEN\b|\bLIMIT\b|$)', re.IGNORECASE | re.DOTALL)
    FLATTEN_PATTERN = re.compile(r'\bFLATTEN\s+(.+?)(?=\bLIMIT\b|$)', re.IGNORECASE | re.DOTALL)
    LIMIT_PATTERN = re.compile(r'\bLIMIT\s+(\d+)', re.IGNORECASE)

    def parse(self, query: str) -> DataviewQuery:
        """Parse a Dataview query string."""
        query = query.strip()

        # Determine query type
        type_match = self.QUERY_TYPE_PATTERN.match(query)
        if not type_match:
            raise ValueError(f"Invalid Dataview query: must start with TABLE, LIST, TASK, or CALENDAR")

        query_type_str = type_match.group(1).upper()
        query_type = DataviewQueryType[query_type_str]

        # Extract fields (for TABLE queries)
        fields = []
        if query_type == DataviewQueryType.TABLE:
            fields = self._parse_fields(query, type_match.end())

        # Extract clauses
        from_match = self.FROM_PATTERN.search(query)
        where_match = self.WHERE_PATTERN.search(query)
        sort_match = self.SORT_PATTERN.search(query)
        group_match = self.GROUP_PATTERN.search(query)
        flatten_match = self.FLATTEN_PATTERN.search(query)
        limit_match = self.LIMIT_PATTERN.search(query)

        return DataviewQuery(
            query_type=query_type,
            fields=fields,
            source=from_match.group(1).strip() if from_match else None,
            where=where_match.group(1).strip() if where_match else None,
            sort=sort_match.group(1).strip() if sort_match else None,
            group_by=group_match.group(1).strip() if group_match else None,
            flatten=flatten_match.group(1).strip() if flatten_match else None,
            limit=int(limit_match.group(1)) if limit_match else None,
            raw_query=query
        )

    def _parse_fields(self, query: str, start_pos: int) -> List[DataviewField]:
        """Parse TABLE field list."""
        fields = []

        # Find the field section (between TABLE and FROM/WHERE/SORT/etc)
        clauses_pattern = re.compile(r'\b(FROM|WHERE|SORT|GROUP|FLATTEN|LIMIT)\b', re.IGNORECASE)
        clause_match = clauses_pattern.search(query, start_pos)

        if clause_match:
            field_section = query[start_pos:clause_match.start()].strip()
        else:
            field_section = query[start_pos:].strip()

        if not field_section:
            return fields

        # Split by comma, handling nested expressions
        field_parts = self._split_fields(field_section)

        for part in field_parts:
            part = part.strip()
            if not part:
                continue

            # Check for alias (AS keyword)
            as_match = re.search(r'\s+AS\s+"?([^"]+)"?\s*$', part, re.IGNORECASE)
            if as_match:
                alias = as_match.group(1)
                expression = part[:as_match.start()].strip()
                fields.append(DataviewField(
                    name=alias,
                    alias=alias,
                    expression=expression
                ))
            else:
                fields.append(DataviewField(name=part, expression=part))

        return fields

    def _split_fields(self, field_section: str) -> List[str]:
        """Split field section by commas, respecting parentheses."""
        fields = []
        current = []
        depth = 0

        for char in field_section:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ',' and depth == 0:
                fields.append(''.join(current))
                current = []
                continue
            current.append(char)

        if current:
            fields.append(''.join(current))

        return fields


class DataviewExecutor:
    """
    Execute Dataview queries against a skill/note collection.

    This is a simplified implementation that works within the AgentSkills
    framework. It doesn't have access to a full Obsidian vault, so it
    operates on registered skill files.
    """

    def __init__(self, skill_registry: Optional[Dict[str, Any]] = None):
        self.skill_registry = skill_registry or {}
        self.parser = DataviewParser()
        self.functions: Dict[str, Callable] = self._register_default_functions()

    def _register_default_functions(self) -> Dict[str, Callable]:
        """Register built-in Dataview functions."""
        return {
            'link': lambda x: f"[[{x}]]",
            'date': lambda x: str(x),
            'length': len,
            'contains': lambda arr, val: val in arr if arr else False,
            'choice': lambda cond, t, f: t if cond else f,
            'default': lambda val, default: val if val else default,
            'round': round,
            'min': min,
            'max': max,
            'sum': sum,
            'average': lambda arr: sum(arr) / len(arr) if arr else 0,
        }

    def execute(self, query_str: str) -> DataviewResult:
        """Execute a Dataview query."""
        try:
            query = self.parser.parse(query_str)
            return self._execute_query(query)
        except Exception as e:
            return DataviewResult(
                success=False,
                error=str(e)
            )

    def _execute_query(self, query: DataviewQuery) -> DataviewResult:
        """Execute a parsed query."""
        # Get source data
        data = self._get_source_data(query.source)

        # Apply WHERE filter
        if query.where:
            data = self._apply_where(data, query.where)

        # Apply FLATTEN
        if query.flatten:
            data = self._apply_flatten(data, query.flatten)

        # Apply GROUP BY
        if query.group_by:
            data = self._apply_group_by(data, query.group_by)

        # Apply SORT
        if query.sort:
            data = self._apply_sort(data, query.sort)

        # Apply LIMIT
        if query.limit:
            data = data[:query.limit]

        # Build result based on query type
        if query.query_type == DataviewQueryType.TABLE:
            return self._build_table_result(query, data)
        elif query.query_type == DataviewQueryType.LIST:
            return self._build_list_result(query, data)
        elif query.query_type == DataviewQueryType.TASK:
            return self._build_task_result(query, data)
        elif query.query_type == DataviewQueryType.CALENDAR:
            return self._build_calendar_result(query, data)

        return DataviewResult(success=False, error="Unknown query type")

    def _get_source_data(self, source: Optional[str]) -> List[Dict[str, Any]]:
        """Get data from the specified source."""
        if not source:
            # Return all registered skills/notes
            return list(self.skill_registry.values())

        # Parse source specification
        # Examples: #tag, "folder", [[link]], #tag AND "folder"
        data = []

        # Simple tag filter
        if source.startswith('#'):
            tag = source[1:]
            for item in self.skill_registry.values():
                if tag in item.get('tags', []):
                    data.append(item)
        # Folder filter
        elif source.startswith('"') and source.endswith('"'):
            folder = source[1:-1]
            for item in self.skill_registry.values():
                if item.get('folder', '').startswith(folder):
                    data.append(item)
        else:
            # Return all for unrecognized sources
            data = list(self.skill_registry.values())

        return data

    def _apply_where(self, data: List[Dict], condition: str) -> List[Dict]:
        """Apply WHERE filter to data."""
        # Simple expression evaluator
        # Supports: field = value, field != value, contains(field, value)
        filtered = []

        for item in data:
            try:
                if self._evaluate_condition(item, condition):
                    filtered.append(item)
            except Exception:
                continue

        return filtered

    def _evaluate_condition(self, item: Dict, condition: str) -> bool:
        """Evaluate a condition expression."""
        # Handle contains()
        contains_match = re.match(r'contains\((\w+),\s*"([^"]+)"\)', condition)
        if contains_match:
            field = contains_match.group(1)
            value = contains_match.group(2)
            field_value = item.get(field, '')
            return value in str(field_value)

        # Handle equality
        eq_match = re.match(r'(\w+)\s*=\s*"([^"]+)"', condition)
        if eq_match:
            field = eq_match.group(1)
            value = eq_match.group(2)
            return str(item.get(field, '')) == value

        # Handle inequality
        neq_match = re.match(r'(\w+)\s*!=\s*"([^"]+)"', condition)
        if neq_match:
            field = neq_match.group(1)
            value = neq_match.group(2)
            return str(item.get(field, '')) != value

        return True

    def _apply_flatten(self, data: List[Dict], flatten_expr: str) -> List[Dict]:
        """Apply FLATTEN to expand array fields."""
        flattened = []
        for item in data:
            value = item.get(flatten_expr, [])
            if isinstance(value, list):
                for v in value:
                    new_item = item.copy()
                    new_item[flatten_expr] = v
                    flattened.append(new_item)
            else:
                flattened.append(item)
        return flattened

    def _apply_group_by(self, data: List[Dict], group_expr: str) -> List[Dict]:
        """Apply GROUP BY to aggregate data."""
        groups: Dict[Any, List[Dict]] = {}
        for item in data:
            key = item.get(group_expr, 'Unknown')
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        # Convert to grouped format
        grouped = []
        for key, items in groups.items():
            grouped.append({
                'key': key,
                'rows': items,
                'count': len(items)
            })
        return grouped

    def _apply_sort(self, data: List[Dict], sort_expr: str) -> List[Dict]:
        """Apply SORT to order data."""
        # Parse sort expression: field [ASC|DESC]
        parts = sort_expr.split()
        field = parts[0]
        reverse = len(parts) > 1 and parts[1].upper() == 'DESC'

        try:
            return sorted(data, key=lambda x: x.get(field, ''), reverse=reverse)
        except TypeError:
            return data

    def _build_table_result(self, query: DataviewQuery, data: List[Dict]) -> DataviewResult:
        """Build TABLE query result."""
        headers = [f.alias or f.name for f in query.fields] if query.fields else ['file']

        # Render as markdown table
        lines = []
        lines.append('| ' + ' | '.join(headers) + ' |')
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')

        for item in data:
            row = []
            for f in query.fields or [DataviewField(name='file')]:
                value = item.get(f.name, '')
                row.append(str(value))
            lines.append('| ' + ' | '.join(row) + ' |')

        return DataviewResult(
            success=True,
            data=data,
            headers=headers,
            query_type=DataviewQueryType.TABLE,
            rendered='\n'.join(lines)
        )

    def _build_list_result(self, query: DataviewQuery, data: List[Dict]) -> DataviewResult:
        """Build LIST query result."""
        lines = []
        for item in data:
            name = item.get('name', item.get('file', 'Unknown'))
            lines.append(f"- [[{name}]]")

        return DataviewResult(
            success=True,
            data=data,
            query_type=DataviewQueryType.LIST,
            rendered='\n'.join(lines)
        )

    def _build_task_result(self, query: DataviewQuery, data: List[Dict]) -> DataviewResult:
        """Build TASK query result."""
        lines = []
        for item in data:
            tasks = item.get('tasks', [])
            for task in tasks:
                checkbox = '[x]' if task.get('checked') else '[ ]'
                lines.append(f"- {checkbox} {task.get('text', '')}")

        return DataviewResult(
            success=True,
            data=data,
            query_type=DataviewQueryType.TASK,
            rendered='\n'.join(lines)
        )

    def _build_calendar_result(self, query: DataviewQuery, data: List[Dict]) -> DataviewResult:
        """Build CALENDAR query result (simplified text output)."""
        # Calendar rendering would need a proper UI; return simple list for now
        lines = ["*Calendar view (text representation):*", ""]
        for item in data:
            date = item.get('date', 'No date')
            name = item.get('name', 'Unknown')
            lines.append(f"- {date}: {name}")

        return DataviewResult(
            success=True,
            data=data,
            query_type=DataviewQueryType.CALENDAR,
            rendered='\n'.join(lines)
        )

    def execute_inline(self, expression: str, context: Dict[str, Any] = None) -> str:
        """Execute an inline Dataview expression like `= this.field`."""
        context = context or {}

        # Handle this.field syntax
        if expression.startswith('this.'):
            field = expression[5:]
            return str(context.get(field, ''))

        # Handle function calls
        func_match = re.match(r'(\w+)\((.*)\)', expression)
        if func_match:
            func_name = func_match.group(1)
            args_str = func_match.group(2)
            if func_name in self.functions:
                try:
                    # Simple arg parsing
                    args = [a.strip().strip('"') for a in args_str.split(',') if a.strip()]
                    return str(self.functions[func_name](*args))
                except Exception:
                    return f"Error: {expression}"

        return expression
