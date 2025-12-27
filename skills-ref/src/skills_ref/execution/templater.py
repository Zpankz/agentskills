# skills_ref/execution/templater.py — Templater command processing engine

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
import re
from pathlib import Path
import os


@dataclass
class TemplaterConfig:
    """Configuration for Templater execution."""
    allow_system_commands: bool = False
    allow_file_operations: bool = False
    template_folder: Optional[Path] = None
    date_format: str = "YYYY-MM-DD"
    time_format: str = "HH:mm"


@dataclass
class TemplaterResult:
    """Result of Templater command execution."""
    success: bool
    output: str = ""
    error: Optional[str] = None
    cursor_position: Optional[int] = None


class TemplaterModule:
    """Base class for Templater modules (tp.*)."""

    def __init__(self, context: Dict[str, Any]):
        self.context = context


class DateModule(TemplaterModule):
    """tp.date module implementation."""

    def now(self, format: str = "YYYY-MM-DD", offset: int = 0, reference: str = None, reference_format: str = None) -> str:
        """Get current date with optional offset."""
        dt = datetime.now()
        if offset:
            dt += timedelta(days=offset)
        return self._format_date(dt, format)

    def tomorrow(self, format: str = "YYYY-MM-DD") -> str:
        """Get tomorrow's date."""
        return self.now(format, offset=1)

    def yesterday(self, format: str = "YYYY-MM-DD") -> str:
        """Get yesterday's date."""
        return self.now(format, offset=-1)

    def weekday(self, format: str = "dddd", offset: int = 0) -> str:
        """Get weekday name."""
        dt = datetime.now() + timedelta(days=offset)
        formats = {
            'dddd': dt.strftime('%A'),
            'ddd': dt.strftime('%a'),
            'd': str(dt.isoweekday())
        }
        return formats.get(format, dt.strftime('%A'))

    def _format_date(self, dt: datetime, format: str) -> str:
        """Convert moment.js-style format to Python strftime."""
        # Order matters! Longer patterns must be replaced first to avoid partial matches
        replacements = [
            ('YYYY', '%Y'),
            ('YY', '%y'),
            ('MMMM', '%B'),
            ('MMM', '%b'),
            ('MM', '%m'),
            ('dddd', '%A'),
            ('ddd', '%a'),
            ('DD', '%d'),
            ('HH', '%H'),
            ('mm', '%M'),
            ('ss', '%S'),
            # Single letter replacements last - use padded version for simplicity
            ('D', '%d'),
            ('H', '%H'),
            ('M', '%m'),
            ('s', '%S'),
        ]
        result = format
        for moment_fmt, py_fmt in replacements:
            result = result.replace(moment_fmt, py_fmt)
        return dt.strftime(result)


class FileModule(TemplaterModule):
    """tp.file module implementation."""

    def __init__(self, context: Dict[str, Any], config: TemplaterConfig):
        super().__init__(context)
        self.config = config

    @property
    def title(self) -> str:
        """Get current file title (without extension)."""
        path = self.context.get('file_path', '')
        return Path(path).stem if path else 'Untitled'

    @property
    def path(self) -> str:
        """Get current file path."""
        return self.context.get('file_path', '')

    @property
    def folder(self) -> str:
        """Get current file folder."""
        path = self.context.get('file_path', '')
        return str(Path(path).parent) if path else ''

    @property
    def tags(self) -> List[str]:
        """Get file tags."""
        return self.context.get('tags', [])

    def creation_date(self, format: str = "YYYY-MM-DD") -> str:
        """Get file creation date."""
        # In real implementation, would get from file metadata
        return DateModule(self.context)._format_date(datetime.now(), format)

    def last_modified_date(self, format: str = "YYYY-MM-DD") -> str:
        """Get file last modified date."""
        return DateModule(self.context)._format_date(datetime.now(), format)

    def include(self, template_path: str) -> str:
        """Include content from another template."""
        if not self.config.allow_file_operations:
            return f"[File operations disabled: {template_path}]"

        if self.config.template_folder:
            full_path = self.config.template_folder / template_path
            if full_path.exists():
                return full_path.read_text()

        return f"[Template not found: {template_path}]"

    def cursor(self, order: int = 0) -> str:
        """Insert cursor position marker."""
        return f"<cursor:{order}>"

    def cursor_append(self, content: str) -> str:
        """Append content at cursor."""
        return content


class SystemModule(TemplaterModule):
    """tp.system module implementation (restricted)."""

    def __init__(self, context: Dict[str, Any], config: TemplaterConfig):
        super().__init__(context)
        self.config = config

    def clipboard(self) -> str:
        """Get clipboard content (disabled for security)."""
        return "[Clipboard access disabled]"

    def prompt(self, prompt_text: str, default: str = "", throw_on_cancel: bool = False, multiline: bool = False) -> str:
        """Prompt for user input (returns default in non-interactive mode)."""
        return default

    def suggester(self, options: List[str], values: List[str] = None, throw_on_cancel: bool = False, placeholder: str = "") -> str:
        """Show suggester (returns first option in non-interactive mode)."""
        return values[0] if values else (options[0] if options else "")


class FrontmatterModule(TemplaterModule):
    """tp.frontmatter module implementation."""

    def __getitem__(self, key: str) -> Any:
        """Get frontmatter field value."""
        frontmatter = self.context.get('frontmatter', {})
        return frontmatter.get(key, '')

    def __getattr__(self, name: str) -> Any:
        """Get frontmatter field as attribute."""
        frontmatter = self.context.get('frontmatter', {})
        return frontmatter.get(name, '')


class TemplaterProcessor:
    """
    Process Templater commands in skill/note content.

    Supports a subset of Templater functionality for safe execution
    within the AgentSkills framework.
    """

    # Pattern for Templater commands
    OUTPUT_PATTERN = re.compile(r'<%[=~-]?\s*(.+?)\s*%>', re.DOTALL)
    EXEC_PATTERN = re.compile(r'<%\*\s*(.+?)\s*[*-]?%>', re.DOTALL)

    def __init__(self, config: Optional[TemplaterConfig] = None):
        self.config = config or TemplaterConfig()
        self.context: Dict[str, Any] = {}
        self.modules: Dict[str, Any] = {}
        self._setup_modules()

    def _setup_modules(self):
        """Initialize Templater modules."""
        self.modules = {
            'date': DateModule(self.context),
            'file': FileModule(self.context, self.config),
            'system': SystemModule(self.context, self.config),
            'frontmatter': FrontmatterModule(self.context),
        }

    def set_context(self, context: Dict[str, Any]):
        """Set execution context (file info, frontmatter, etc.)."""
        self.context.update(context)
        self._setup_modules()  # Reinitialize modules with new context

    def process(self, content: str) -> TemplaterResult:
        """Process all Templater commands in content."""
        try:
            result = content

            # Process execution blocks first (<%* ... %>)
            result = self._process_exec_blocks(result)

            # Process output blocks (<%= ... %>)
            result = self._process_output_blocks(result)

            # Find cursor position if any
            cursor_pos = self._find_cursor_position(result)
            result = re.sub(r'<cursor:\d*>', '', result)

            return TemplaterResult(
                success=True,
                output=result,
                cursor_position=cursor_pos
            )

        except Exception as e:
            return TemplaterResult(
                success=False,
                output=content,
                error=str(e)
            )

    def _process_exec_blocks(self, content: str) -> str:
        """Process execution blocks (<%* ... %>)."""
        def replace_exec(match: re.Match) -> str:
            code = match.group(1)
            try:
                # Execute in restricted environment
                self._execute_code(code)
                return ""  # Exec blocks don't produce output
            except Exception as e:
                return f"[Error: {e}]"

        return self.EXEC_PATTERN.sub(replace_exec, content)

    def _process_output_blocks(self, content: str) -> str:
        """Process output blocks (<%= ... %>)."""
        def replace_output(match: re.Match) -> str:
            expr = match.group(1)
            try:
                result = self._evaluate_expression(expr)
                return str(result) if result is not None else ""
            except Exception as e:
                return f"[Error: {e}]"

        return self.OUTPUT_PATTERN.sub(replace_output, content)

    def _evaluate_expression(self, expr: str) -> Any:
        """Evaluate a Templater expression."""
        expr = expr.strip()

        # Handle tp.module.method() calls
        tp_match = re.match(r'tp\.(\w+)\.(\w+)(?:\((.*)\))?', expr)
        if tp_match:
            module_name = tp_match.group(1)
            method_name = tp_match.group(2)
            args_str = tp_match.group(3) or ""

            if module_name in self.modules:
                module = self.modules[module_name]

                # Check for property access
                if hasattr(module, method_name):
                    attr = getattr(module, method_name)
                    if callable(attr):
                        args = self._parse_args(args_str)
                        return attr(*args)
                    else:
                        return attr

        # Handle simple variable access
        if expr in self.context:
            return self.context[expr]

        # Handle string literals
        if expr.startswith('"') and expr.endswith('"'):
            return expr[1:-1]
        if expr.startswith("'") and expr.endswith("'"):
            return expr[1:-1]

        return expr

    def _parse_args(self, args_str: str) -> List[Any]:
        """Parse function arguments."""
        if not args_str.strip():
            return []

        args = []
        current = []
        depth = 0
        in_string = False
        string_char = None

        for char in args_str:
            if char in '"\'':
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
            elif char == '(' and not in_string:
                depth += 1
            elif char == ')' and not in_string:
                depth -= 1
            elif char == ',' and depth == 0 and not in_string:
                args.append(self._parse_single_arg(''.join(current).strip()))
                current = []
                continue
            current.append(char)

        if current:
            args.append(self._parse_single_arg(''.join(current).strip()))

        return args

    def _parse_single_arg(self, arg: str) -> Any:
        """Parse a single argument value."""
        arg = arg.strip()

        # String literal
        if (arg.startswith('"') and arg.endswith('"')) or \
           (arg.startswith("'") and arg.endswith("'")):
            return arg[1:-1]

        # Number
        try:
            if '.' in arg:
                return float(arg)
            return int(arg)
        except ValueError:
            pass

        # Boolean
        if arg.lower() == 'true':
            return True
        if arg.lower() == 'false':
            return False

        # None/null
        if arg.lower() in ('null', 'none'):
            return None

        return arg

    def _execute_code(self, code: str):
        """Execute Templater code block (restricted)."""
        # For security, we only allow very limited operations
        # This is a placeholder for more complex execution

        # Handle variable assignments
        assign_match = re.match(r'(\w+)\s*=\s*(.+)', code.strip())
        if assign_match:
            var_name = assign_match.group(1)
            value_expr = assign_match.group(2)
            self.context[var_name] = self._evaluate_expression(value_expr)

    def _find_cursor_position(self, content: str) -> Optional[int]:
        """Find cursor position marker in content."""
        match = re.search(r'<cursor:(\d*)>', content)
        if match:
            return match.start()
        return None


class TemplaterTemplate:
    """Represents a Templater template file."""

    def __init__(self, content: str, name: str = ""):
        self.content = content
        self.name = name
        self.processor = TemplaterProcessor()

    def render(self, context: Dict[str, Any] = None) -> TemplaterResult:
        """Render the template with given context."""
        if context:
            self.processor.set_context(context)
        return self.processor.process(self.content)

    @classmethod
    def from_file(cls, path: Path) -> 'TemplaterTemplate':
        """Load template from file."""
        content = path.read_text(encoding='utf-8')
        return cls(content, name=path.stem)
