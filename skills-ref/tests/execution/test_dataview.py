"""Tests for Dataview execution framework."""
import pytest
from skills_ref.execution.dataview import (
    DataviewExecutor, DataviewParser, DataviewQuery,
    DataviewQueryType, DataviewResult
)


@pytest.fixture
def sample_registry():
    """Sample skill registry for testing queries."""
    return {
        'skill1': {
            'name': 'skill1',
            'file': 'skill1/SKILL.md',
            'folder': 'skills',
            'tags': ['python', 'automation'],
            'description': 'A Python skill',
            'date': '2024-01-01'
        },
        'skill2': {
            'name': 'skill2',
            'file': 'skill2/SKILL.md',
            'folder': 'skills',
            'tags': ['javascript', 'web'],
            'description': 'A JavaScript skill',
            'date': '2024-02-01'
        },
        'skill3': {
            'name': 'skill3',
            'file': 'skill3/SKILL.md',
            'folder': 'tools',
            'tags': ['python', 'data'],
            'description': 'A data processing skill',
            'date': '2024-03-01',
            'tasks': [
                {'text': 'Complete implementation', 'checked': True},
                {'text': 'Add tests', 'checked': False}
            ]
        }
    }


class TestDataviewParser:

    def test_parse_table_query(self):
        parser = DataviewParser()
        query = parser.parse('TABLE file, description FROM #python')

        assert query.query_type == DataviewQueryType.TABLE
        assert len(query.fields) == 2
        assert query.source == '#python'

    def test_parse_list_query(self):
        parser = DataviewParser()
        query = parser.parse('LIST FROM "skills"')

        assert query.query_type == DataviewQueryType.LIST
        assert query.source == '"skills"'

    def test_parse_task_query(self):
        parser = DataviewParser()
        query = parser.parse('TASK FROM #python')

        assert query.query_type == DataviewQueryType.TASK
        assert query.source == '#python'

    def test_parse_where_clause(self):
        parser = DataviewParser()
        query = parser.parse('LIST FROM #python WHERE contains(tags, "automation")')

        assert query.where == 'contains(tags, "automation")'

    def test_parse_sort_clause(self):
        parser = DataviewParser()
        query = parser.parse('TABLE file FROM #python SORT date DESC')

        assert query.sort == 'date DESC'

    def test_parse_limit_clause(self):
        parser = DataviewParser()
        query = parser.parse('LIST LIMIT 10')

        assert query.limit == 10

    def test_parse_complex_query(self):
        parser = DataviewParser()
        query = parser.parse('''
            TABLE file, description AS "Desc", date
            FROM #python
            WHERE contains(tags, "automation")
            SORT date DESC
            LIMIT 5
        ''')

        assert query.query_type == DataviewQueryType.TABLE
        assert len(query.fields) == 3
        assert query.fields[1].alias == "Desc"
        assert query.source == '#python'
        assert 'automation' in query.where
        assert 'DESC' in query.sort
        assert query.limit == 5


class TestDataviewExecutor:

    def test_execute_list_query(self, sample_registry):
        executor = DataviewExecutor(sample_registry)
        result = executor.execute('LIST')

        assert result.success
        assert result.query_type == DataviewQueryType.LIST
        assert len(result.data) == 3
        assert '[[skill1]]' in result.rendered

    def test_execute_table_query(self, sample_registry):
        executor = DataviewExecutor(sample_registry)
        result = executor.execute('TABLE name, description')

        assert result.success
        assert result.query_type == DataviewQueryType.TABLE
        assert 'name' in result.headers
        assert '|' in result.rendered  # Markdown table

    def test_execute_with_tag_filter(self, sample_registry):
        executor = DataviewExecutor(sample_registry)
        result = executor.execute('LIST FROM #python')

        assert result.success
        assert len(result.data) == 2  # skill1 and skill3

    def test_execute_with_where(self, sample_registry):
        executor = DataviewExecutor(sample_registry)
        result = executor.execute('LIST WHERE name = "skill1"')

        assert result.success
        assert len(result.data) == 1
        assert result.data[0]['name'] == 'skill1'

    def test_execute_with_sort(self, sample_registry):
        executor = DataviewExecutor(sample_registry)
        result = executor.execute('TABLE name SORT date DESC')

        assert result.success
        # Most recent should be first
        assert result.data[0]['date'] == '2024-03-01'

    def test_execute_with_limit(self, sample_registry):
        executor = DataviewExecutor(sample_registry)
        result = executor.execute('LIST LIMIT 2')

        assert result.success
        assert len(result.data) == 2

    def test_execute_task_query(self, sample_registry):
        executor = DataviewExecutor(sample_registry)
        result = executor.execute('TASK FROM #python')

        assert result.success
        assert result.query_type == DataviewQueryType.TASK
        # Should have task items in output
        assert '[x]' in result.rendered or '[ ]' in result.rendered

    def test_inline_expression(self, sample_registry):
        executor = DataviewExecutor(sample_registry)

        context = {'title': 'Test Skill', 'count': 42}
        result = executor.execute_inline('this.title', context)
        assert result == 'Test Skill'

        result = executor.execute_inline('this.count', context)
        assert result == '42'

    def test_invalid_query(self, sample_registry):
        executor = DataviewExecutor(sample_registry)
        result = executor.execute('INVALID QUERY TYPE')

        assert not result.success
        assert result.error is not None
