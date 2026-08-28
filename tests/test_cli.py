from __future__ import annotations

from algoworlds.cli import main


def test_top_level_help_lists_curated_commands(capsys) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "worlds list" in output
    assert "evaluate" in output
    assert "score" in output
    assert "release verify" in output


def test_world_listing_uses_public_ids(capsys) -> None:
    assert (
        main(
            [
                "worlds",
                "list",
                "--task-family",
                "transit_routing",
                "--workload-level",
                "L1",
                "--instance-index",
                "1",
                "--tool-interface",
                "direct",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == (
        "algoworlds/transit_routing/L1/instance-1/direct"
    )
