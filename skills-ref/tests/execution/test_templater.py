"""Tests for Templater processing engine."""
import pytest
from datetime import datetime
from skills_ref.execution.templater import (
    TemplaterProcessor, TemplaterTemplate, TemplaterResult,
    TemplaterConfig, DateModule, FileModule
)


class TestTemplaterProcessor:

    def test_basic_processing(self):
        processor = TemplaterProcessor()
        content = "Hello, World!"
        result = processor.process(content)

        assert result.success
        assert result.output == "Hello, World!"

    def test_date_now(self):
        processor = TemplaterProcessor()
        content = "<%= tp.date.now() %>"
        result = processor.process(content)

        assert result.success
        # Should contain today's date
        today = datetime.now().strftime('%Y-%m-%d')
        assert today in result.output

    def test_date_now_custom_format(self):
        processor = TemplaterProcessor()
        content = "<%= tp.date.now('YYYY/MM/DD') %>"
        result = processor.process(content)

        assert result.success
        today = datetime.now().strftime('%Y/%m/%d')
        assert today in result.output

    def test_date_tomorrow(self):
        processor = TemplaterProcessor()
        content = "<%= tp.date.tomorrow() %>"
        result = processor.process(content)

        assert result.success
        # Output should be a date string
        assert len(result.output) == 10  # YYYY-MM-DD format

    def test_date_yesterday(self):
        processor = TemplaterProcessor()
        content = "<%= tp.date.yesterday() %>"
        result = processor.process(content)

        assert result.success
        assert len(result.output) == 10

    def test_file_title(self):
        processor = TemplaterProcessor()
        processor.set_context({'file_path': '/path/to/MyNote.md'})
        content = "<%= tp.file.title %>"
        result = processor.process(content)

        assert result.success
        assert result.output == "MyNote"

    def test_file_path(self):
        processor = TemplaterProcessor()
        processor.set_context({'file_path': '/path/to/note.md'})
        content = "<%= tp.file.path %>"
        result = processor.process(content)

        assert result.success
        assert '/path/to/note.md' in result.output

    def test_file_folder(self):
        processor = TemplaterProcessor()
        processor.set_context({'file_path': '/path/to/note.md'})
        content = "<%= tp.file.folder %>"
        result = processor.process(content)

        assert result.success
        assert '/path/to' in result.output

    def test_frontmatter_access(self):
        processor = TemplaterProcessor()
        processor.set_context({
            'frontmatter': {'title': 'Test Title', 'author': 'Test Author'}
        })
        content = "<%= tp.frontmatter.title %>"
        result = processor.process(content)

        assert result.success
        assert result.output == "Test Title"

    def test_cursor_marker(self):
        processor = TemplaterProcessor()
        content = "Before <%= tp.file.cursor() %> After"
        result = processor.process(content)

        assert result.success
        # Cursor markers should be removed
        assert '<cursor' not in result.output
        assert 'Before' in result.output
        assert 'After' in result.output

    def test_multiple_commands(self):
        processor = TemplaterProcessor()
        processor.set_context({'file_path': '/notes/daily.md'})
        content = """
Date: <%= tp.date.now() %>
File: <%= tp.file.title %>
Weekday: <%= tp.date.weekday() %>
"""
        result = processor.process(content)

        assert result.success
        assert 'Date:' in result.output
        assert 'File: daily' in result.output
        assert 'Weekday:' in result.output

    def test_execution_block(self):
        processor = TemplaterProcessor()
        content = """<%* myVar = "Hello" %>
Value: <%= myVar %>"""
        result = processor.process(content)

        assert result.success
        assert 'Value: Hello' in result.output

    def test_string_literal(self):
        processor = TemplaterProcessor()
        content = '<%= "Static Text" %>'
        result = processor.process(content)

        assert result.success
        assert result.output == "Static Text"

    def test_context_variable(self):
        processor = TemplaterProcessor()
        processor.set_context({'custom_var': 'Custom Value'})
        content = "<%= custom_var %>"
        result = processor.process(content)

        assert result.success
        assert result.output == "Custom Value"

    def test_system_prompt_returns_default(self):
        processor = TemplaterProcessor()
        content = '<%= tp.system.prompt("Enter name", "Default") %>'
        result = processor.process(content)

        assert result.success
        assert result.output == "Default"

    def test_error_handling(self):
        processor = TemplaterProcessor()
        content = "<%= tp.invalid.method() %>"
        result = processor.process(content)

        # Should handle gracefully
        assert result.success  # Continues despite error
        assert 'invalid' in result.output or 'Error' in result.output


class TestTemplaterTemplate:

    def test_template_rendering(self):
        template = TemplaterTemplate("""
# Daily Note for <%= tp.date.now() %>

## Tasks
- [ ] Morning routine
- [ ] Check emails
""")
        result = template.render()

        assert result.success
        assert 'Daily Note for' in result.output
        assert '- [ ] Morning routine' in result.output

    def test_template_with_context(self):
        template = TemplaterTemplate("""
# <%= project_name %>
Author: <%= author %>
""")
        result = template.render({
            'project_name': 'My Project',
            'author': 'John Doe'
        })

        assert result.success
        assert '# My Project' in result.output
        assert 'Author: John Doe' in result.output


class TestDateModule:

    def test_now_with_offset(self):
        module = DateModule({})
        today = module.now()
        tomorrow = module.now(offset=1)
        yesterday = module.now(offset=-1)

        assert today != tomorrow
        assert today != yesterday
        assert tomorrow != yesterday

    def test_weekday_formats(self):
        module = DateModule({})

        full = module.weekday('dddd')
        short = module.weekday('ddd')

        # Full name should be longer
        assert len(full) > len(short)

    def test_date_formats(self):
        module = DateModule({})

        iso = module.now('YYYY-MM-DD')
        slash = module.now('DD/MM/YYYY')
        compact = module.now('YYYYMMDD')

        assert '-' in iso
        assert '/' in slash
        assert '-' not in compact
