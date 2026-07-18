"""CLI for Arrest Public Archiver — misclassification-first."""
from __future__ import annotations

from .cli_cmds_analysis import cmd_dedupe, cmd_misclassify, cmd_mugshot, cmd_reclassify
from .cli_cmds_data import (
    cmd_enrich_nc_dac,
    cmd_import,
    cmd_import_nc_dac,
    cmd_import_state_bulk,
    cmd_scrape,
    cmd_search,
    cmd_status,
)
from .cli_cmds_rb import cmd_recentlybooked
from .cli_parser import build_parser


def main() -> None:
    p = build_parser()
    args = p.parse_args()
    # recentlybooked scrape vs live share handler via rb_action
    if args.command == "recentlybooked" and args.rb_action == "scrape":
        args.do_import = True  # scrape always imports
    dispatch = {
        "status": cmd_status,
        "scrape": cmd_scrape,
        "import": cmd_import,
        "import-nc-dac": cmd_import_nc_dac,
        "import-state-bulk": cmd_import_state_bulk,
        "enrich-nc-dac": cmd_enrich_nc_dac,
        "search": cmd_search,
        "misclassify": cmd_misclassify,
        "dedupe": cmd_dedupe,
        "reclassify-charges": cmd_reclassify,
        "recentlybooked": cmd_recentlybooked,
        "mugshot": cmd_mugshot,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
