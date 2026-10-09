from lorenzo_beyond.html import to_lorenzoscript as md


def test_paragraphs_and_emphasis() -> None:
    assert md("<p>A <strong>bold</strong> and <em>quiet</em> word.</p><p>Next.</p>") == (
        "A **bold** and *quiet* word.\n\nNext."
    )


def test_whitespace_and_entities_are_normalised() -> None:
    assert md("<p>Can&rsquo;t   stop\n  here &amp; now</p>") == "Can\u2019t stop here & now"


def test_line_breaks_are_hard_breaks() -> None:
    assert md("<p>one<br />two</p>") == "one  \ntwo"


def test_lists_are_tight_and_nest() -> None:
    html = "<ul><li>one</li><li>two<ul><li>deep</li></ul></li></ul><ol><li>a</li><li>b</li></ol>"

    assert md(html) == "- one\n- two\n  - deep\n\n1. a\n2. b"


def test_headings() -> None:
    assert md("<h4>Title</h4><p>Text</p>") == "#### Title\n\nText"


def test_a_table_becomes_a_github_table() -> None:
    html = (
        "<table><thead><tr><th>d8</th><th>Spell</th></tr></thead>"
        "<tbody><tr><td>1</td><td>Fire | Bolt</td></tr>"
        "<tr><td>2</td><td>Light</td></tr></tbody></table>"
    )

    assert md(html) == "| d8 | Spell |\n| --- | --- |\n| 1 | Fire \\| Bolt |\n| 2 | Light |"


def test_links_keep_an_absolute_address_and_lose_a_relative_one() -> None:
    html = '<p><a href="https://example.com/x">out</a> and <a href="/spells/12-fire">Fire</a></p>'

    assert md(html) == "[out](https://example.com/x) and Fire"


def test_sup_sub_code_and_rules() -> None:
    assert md("<p>x<sup>2</sup> H<sub>2</sub>O <code>d20</code></p><hr /><p>after</p>") == (
        "x^2^ H~2~O `d20`\n\n---\n\nafter"
    )


def test_unknown_tags_are_read_through_and_scripts_are_dropped() -> None:
    assert md("<div><span class='x'>seen</span><script>alert(1)</script></div>") == "seen"


def test_plain_text_keeps_its_lines() -> None:
    assert md("A sack.\nWith a hole.\n") == "A sack.\nWith a hole."


def test_nothing_in_nothing_out() -> None:
    assert md(None) == ""
    assert md("  ") == ""
    assert md("<p> </p>") == ""
