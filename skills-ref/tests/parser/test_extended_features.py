"""Tests for extended parser features: blockquotes, lists, links."""
import pytest
from pathlib import Path
from skills_ref.parser.extended_parser import ExtendedSkillParser
from skills_ref.types.ast import (
    BlockquoteNode, ListNode, ListItemNode,
    ExternalLinkNode, FileLinkNode
)


@pytest.fixture
def skill_with_blockquote(tmp_path):
    d = tmp_path / "blockquote_skill"
    d.mkdir()
    (d / "SKILL.md").write_text("""---
name: blockquote-test
description: Test blockquotes
---

> This is a blockquote
> with multiple lines
> and content

Regular paragraph after.
""", encoding='utf-8')
    return d


@pytest.fixture
def skill_with_tasklist(tmp_path):
    d = tmp_path / "tasklist_skill"
    d.mkdir()
    (d / "SKILL.md").write_text("""---
name: tasklist-test
description: Test task lists
---

- [x] Completed task
- [ ] Incomplete task
- [X] Also completed (uppercase X)
- Normal list item
""", encoding='utf-8')
    return d


@pytest.fixture
def skill_with_links(tmp_path):
    d = tmp_path / "links_skill"
    d.mkdir()
    (d / "SKILL.md").write_text("""---
name: links-test
description: Test various link types
---

Check out [Example](https://example.com) for more info.

Also see [Google](https://google.com "Search Engine") with title.

File link: [Local Doc](file:///path/to/doc.md)

Email: [Contact](mailto:test@example.com)
""", encoding='utf-8')
    return d


def test_blockquote_parsing(skill_with_blockquote):
    parser = ExtendedSkillParser(skill_with_blockquote)
    result = parser.parse()

    # Find blockquote in AST
    blockquotes = [n for n in result.ast if isinstance(n, BlockquoteNode)]
    assert len(blockquotes) >= 1

    blockquote = blockquotes[0]
    assert blockquote.type == 'blockquote'
    assert len(blockquote.children) > 0


def test_tasklist_parsing(skill_with_tasklist):
    parser = ExtendedSkillParser(skill_with_tasklist)
    result = parser.parse()

    # Find list in AST
    lists = [n for n in result.ast if isinstance(n, ListNode)]
    assert len(lists) >= 1

    task_list = lists[0]
    assert task_list.type == 'list'
    assert len(task_list.items) == 4

    # Check task states
    assert task_list.items[0].is_task == True
    assert task_list.items[0].checked == True

    assert task_list.items[1].is_task == True
    assert task_list.items[1].checked == False

    assert task_list.items[2].is_task == True
    assert task_list.items[2].checked == True

    # Normal list item should not be a task
    assert task_list.items[3].is_task == False


def test_external_link_parsing(skill_with_links):
    parser = ExtendedSkillParser(skill_with_links)
    result = parser.parse()

    # Check that external links are parsed
    all_inline = []
    for node in result.ast:
        if hasattr(node, 'inline_content'):
            all_inline.extend(node.inline_content)

    external_links = [n for n in all_inline if isinstance(n, ExternalLinkNode)]
    assert len(external_links) >= 2

    # Check link types
    https_links = [l for l in external_links if l.link_type == 'https']
    assert len(https_links) >= 2

    # Check for title
    links_with_title = [l for l in external_links if l.title]
    assert len(links_with_title) >= 1
    assert links_with_title[0].title == "Search Engine"


def test_file_link_parsing(skill_with_links):
    parser = ExtendedSkillParser(skill_with_links)
    result = parser.parse()

    # Check that file links are parsed
    all_inline = []
    for node in result.ast:
        if hasattr(node, 'inline_content'):
            all_inline.extend(node.inline_content)

    file_links = [n for n in all_inline if isinstance(n, FileLinkNode)]
    assert len(file_links) >= 1

    # Check file link properties
    file_link = file_links[0]
    assert file_link.type == 'file_link'
    assert '/path/to/doc.md' in file_link.path
    assert file_link.is_absolute == True


def test_ordered_list(tmp_path):
    d = tmp_path / "ordered_skill"
    d.mkdir()
    (d / "SKILL.md").write_text("""---
name: ordered-test
description: Test ordered lists
---

1. First item
2. Second item
3. Third item
""", encoding='utf-8')

    parser = ExtendedSkillParser(d)
    result = parser.parse()

    lists = [n for n in result.ast if isinstance(n, ListNode)]
    assert len(lists) >= 1

    ordered_list = lists[0]
    assert ordered_list.ordered == True
    assert len(ordered_list.items) == 3


def test_nested_blockquote_content(tmp_path):
    d = tmp_path / "nested_skill"
    d.mkdir()
    (d / "SKILL.md").write_text("""---
name: nested-test
description: Test nested blockquote content
---

> # Heading in blockquote
>
> Paragraph with [[wikilink]] and #tag
""", encoding='utf-8')

    parser = ExtendedSkillParser(d)
    result = parser.parse()

    blockquotes = [n for n in result.ast if isinstance(n, BlockquoteNode)]
    assert len(blockquotes) >= 1

    # Blockquote should have parsed children
    blockquote = blockquotes[0]
    assert len(blockquote.children) > 0
