import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lorenzo_beyond import __version__, cli, prompts
from lorenzo_beyond.errors import NotAvailable
from lorenzo_beyond.models import Character

from .conformance import problems

FIXTURE = Path(__file__).parent / "fixtures" / "character.json"
runner = CliRunner()


def run(*args: str, **kwargs: object):  # type: ignore[no-untyped-def]
    return runner.invoke(cli.app, list(args), **kwargs)  # type: ignore[arg-type]


def fixture_sheet() -> Character:
    return Character.model_validate(json.loads(FIXTURE.read_text())["data"])


def test_a_saved_sheet_becomes_a_ledger_file(tmp_path: Path) -> None:
    out = tmp_path / "mira.ledger.md"

    done = run("inventory", "--from-file", str(FIXTURE), "-o", str(out), "--no-input")

    assert done.exit_code == 0, done.output
    text = out.read_text(encoding="utf-8")
    assert text.startswith("format: lorenzo-ledger/1\nowner: Mira\n")
    assert problems(text) == []
    assert "Wrote" in done.stderr and "lorenzo inventory import" in done.stderr
    assert done.stdout == ""


def test_the_default_file_is_named_for_the_character(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert run("inventory", "--from-file", str(FIXTURE), "--no-input").exit_code == 0
    assert (tmp_path / "mira.ledger.md").exists()
    assert run("inventory", "--from-file", str(FIXTURE), "--no-input", "--json").exit_code == 0
    assert json.loads((tmp_path / "mira.ledger.json").read_text())["format"] == "lorenzo-ledger/1"


def test_standard_output_carries_the_ledger_and_nothing_else() -> None:
    done = run("inventory", "--from-file", str(FIXTURE), "-o", "-", "--no-input")

    assert done.exit_code == 0
    assert done.stdout.startswith("format: lorenzo-ledger/1\n")
    assert problems(done.stdout) == []
    assert "Wrote standard output" in done.stderr


def test_an_existing_file_is_kept_unless_forced(tmp_path: Path) -> None:
    out = tmp_path / "x.md"
    out.write_text("mine")

    refused = run("inventory", "--from-file", str(FIXTURE), "-o", str(out), "--no-input")
    assert refused.exit_code == 1 and "already exists" in " ".join(refused.stderr.split())
    assert out.read_text() == "mine"

    forced = run("inventory", "--from-file", str(FIXTURE), "-o", str(out), "--no-input", "-f")
    assert forced.exit_code == 0 and out.read_text().startswith("format:")


def test_carry_and_leave_behind_move_things_between_the_sections() -> None:
    done = run(
        "inventory", "--from-file", str(FIXTURE), "-o", "-", "--no-input",
        "--leave-behind", "clothes, common", "--carry", "Barrel",
    )  # fmt: skip

    top = [line for line in done.stdout.splitlines() if line.startswith(("- ", "## "))]
    split = top.index("## Not carried")
    assert any("Barrel" in line for line in top[:split])
    assert any("Clothes, Common" in line for line in top[split:])


def test_an_unknown_name_lists_what_there_is() -> None:
    done = run("inventory", "--from-file", str(FIXTURE), "-o", "-", "--carry", "Moon", "--no-input")

    assert done.exit_code == 1
    assert "“Moon”" in done.stderr and "Barrel" in done.stderr


def test_options_leave_out_text_and_coins() -> None:
    done = run(
        "inventory", "--from-file", str(FIXTURE), "-o", "-", "--no-input",
        "--no-descriptions", "--no-coins", "--owner", "Mira",
    )  # fmt: skip

    assert "  > " not in done.stdout and "Coin purse" not in done.stdout
    assert "owner: Mira" in done.stdout


def test_a_link_is_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[int] = []

    def fetch(character_id: int) -> Character:
        asked.append(character_id)
        return fixture_sheet()

    monkeypatch.setattr("lorenzo_beyond.client.fetch", fetch)

    done = run(
        "inventory", "https://www.dndbeyond.com/characters/12345678/AbC123", "-o", "-", "--no-input"
    )

    assert done.exit_code == 0 and asked == [12345678]


def test_a_character_that_is_private_exits_2_and_says_what_to_do(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fetch(character_id: int) -> Character:
        raise NotAvailable("D&D Beyond has no public character 1.", "Make it Public.")

    monkeypatch.setattr("lorenzo_beyond.client.fetch", fetch)

    done = run("inventory", "1", "-o", "-", "--no-input")

    assert done.exit_code == 2
    assert "Couldn't do that." in done.stderr and "Make it Public." in done.stderr


def test_something_that_is_not_a_character_exits_1() -> None:
    done = run("inventory", "character", "--no-input")

    assert done.exit_code == 1 and "not a D&D Beyond character" in done.stderr


def test_with_nobody_to_ask_a_character_is_required() -> None:
    done = run("inventory")

    assert done.exit_code == 1 and "Which character?" in done.stderr


def test_a_missing_file_is_said_plainly(tmp_path: Path) -> None:
    done = run("inventory", "--from-file", str(tmp_path / "nope.json"), "--no-input")

    assert done.exit_code == 1 and "Could not read" in done.stderr


def test_a_document_in_a_new_shape_exits_3(tmp_path: Path) -> None:
    broken = tmp_path / "x.json"
    broken.write_text('{"success": true, "data": {"id": 1}}')

    done = run("inventory", "--from-file", str(broken), "--no-input")

    assert done.exit_code == 3 and "issues" in done.stderr


def test_version_and_bare_help() -> None:
    assert run("--version").stdout.strip() == f"lorenzo-beyond {__version__}"
    bare = run()
    assert bare.exit_code == 0 and "inventory" in bare.stdout


class TestAsking:
    """With someone at the keyboard (the questions are stood in for)."""

    @pytest.fixture(autouse=True)
    def keyboard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cli, "_can_ask", lambda: True)

    def test_everything_is_asked_and_the_pick_is_used(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(prompts, "ask_character", lambda: "12345678")
        monkeypatch.setattr("lorenzo_beyond.client.fetch", lambda _: fixture_sheet())
        offered: list[list[str]] = []

        def carried(name: str, entries: list, default: set[int]) -> set[int]:  # type: ignore[type-arg]
            offered.append([e.name for e in entries])
            assert name == "Mira" and default
            return set()  # nothing but what is equipped

        monkeypatch.setattr(prompts, "ask_carried", carried)

        done = run()

        assert done.exit_code == 0, done.output
        assert "Backpack" in offered[0] and "Riding Horse" in offered[0]
        text = (tmp_path / "mira.ledger.md").read_text()
        not_carried = text.split("## Not carried")[1]
        assert "Backpack" in not_carried and "Clothes, Common" in not_carried

    def test_the_picker_is_skipped_when_flags_decide(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        def never(*_: object) -> set[int]:
            raise AssertionError("asked")

        monkeypatch.setattr(prompts, "ask_carried", never)

        done = run("inventory", "--from-file", str(FIXTURE), "--leave-behind", "Backpack")

        assert done.exit_code == 0

    def test_replacing_a_file_is_confirmed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = tmp_path / "x.md"
        out.write_text("mine")
        monkeypatch.setattr(prompts, "ask_carried", lambda n, e, d: d)
        monkeypatch.setattr(prompts, "confirm_overwrite", lambda name: False)

        done = run("inventory", "--from-file", str(FIXTURE), "-o", str(out))

        assert done.exit_code == 130 and out.read_text() == "mine"

    def test_stopping_at_a_question_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        def stop() -> str:
            raise prompts.Cancelled

        monkeypatch.setattr(prompts, "ask_character", stop)

        done = run("inventory")

        assert done.exit_code == 130 and "Nothing was written" in done.stderr
        assert list(tmp_path.iterdir()) == []
