"""CLI commands: recentlybooked live / scrape / misclassify / import-mirror."""
from __future__ import annotations

import argparse


def cmd_recentlybooked(args: argparse.Namespace) -> None:
    from .database import Database
    from .recentlybooked import RecentlyBookedScraper
    from .searcher import ArrestSearcher  # noqa: F401 — kept for parity

    action = args.rb_action
    db_path = args.database or "data/arrests.db"

    if action == "misclassify":
        if not getattr(args, "source_system", None):
            args.source_system = "recentlybooked"
        from .cli_cmds_analysis import cmd_misclassify

        cmd_misclassify(args)
        return

    if action == "import-mirror":
        _cmd_import_mirror(args, db_path)
        return

    with_photos = not args.no_photos
    with_html = not args.no_html
    scraper = RecentlyBookedScraper(delay=float(args.delay or 1.0))
    try:
        if action == "live":
            print("Fetching RecentlyBooked live feed…")
            rows = scraper.scrape_live(
                import_details=True,
                with_photos=with_photos,
                with_html=with_html,
            )
            print(f"  Live cards/details: {len(rows)}")
            if args.do_import:
                db = Database(db_path)
                try:
                    purged = db.delete_arrests_without_real_photos(
                        source_system="recentlybooked"
                    )
                    if purged:
                        print(f"  Deleted {purged} arrests without a real photo")
                    r = db.import_records(
                        rows,
                        skip_existing_urls=not args.force,
                        require_photo=True,
                    )
                    print(
                        f"  Import +{r['imported']} "
                        f"(skipped {r['skipped']}, "
                        f"no-photo dropped {r.get('rejected_no_photo', 0)})"
                    )
                finally:
                    db.close()
            return

        # scrape
        print("RecentlyBooked scrape…")
        workers = max(1, int(getattr(args, "threads", 1) or 1))
        if workers > 1:
            print(f"  Using {workers} threads (delay {args.delay}s)")
        if args.all:
            rows = scraper.scrape_all(
                limit_counties=int(args.limit_counties or 0),
                with_photos=with_photos,
                with_html=with_html,
                workers=workers,
            )
        elif args.state and args.county:
            rows = scraper.scrape_county(
                args.state,
                args.county,
                max_pages=int(args.max_pages or 0),
                with_photos=with_photos,
                with_html=with_html,
                workers=workers,
            )
        elif args.state:
            rows = scraper.scrape_state(
                args.state,
                with_photos=with_photos,
                with_html=with_html,
                workers=workers,
            )
        else:
            print("Specify --all, --state ST, or --state ST --county slug")
            return
        print(f"  Collected {len(rows)} records")
        db = Database(db_path)
        try:
            purged = db.delete_arrests_without_real_photos(
                source_system="recentlybooked"
            )
            if purged:
                print(f"  Deleted {purged} arrests without a real photo")
            r = db.import_records(
                rows,
                skip_existing_urls=not args.force,
                require_photo=True,
            )
            print(
                f"  Import +{r['imported']} "
                f"(skipped {r['skipped']}, "
                f"no-photo dropped {r.get('rejected_no_photo', 0)}) → {db_path}"
            )
        finally:
            db.close()
    finally:
        scraper.close()


def _cmd_import_mirror(args: argparse.Namespace, db_path: str) -> None:
    from .database import Database
    from .recentlybooked.import_mirror import import_mirror, resolve_site_root

    mirror = args.mirror_path
    try:
        site = resolve_site_root(mirror)
    except FileNotFoundError as exc:
        print(f"  Error: {exc}")
        return
    print(f"Importing RecentlyBooked mirror…")
    print(f"  Root: {site}")
    if args.state:
        print(f"  State: {args.state}" + (f" / {args.county}" if args.county else ""))
    with_photos = not args.no_photos
    with_html = not args.no_html
    require_photo = not args.allow_no_photo

    def progress(n: int, st: dict) -> None:
        print(
            f"  … seen {n} | parsed {st.get('parsed', 0)} | "
            f"+{st.get('imported', 0)} imported | "
            f"skip {st.get('skipped', 0)} | "
            f"no-photo {st.get('rejected_no_photo', 0)} | "
            f"err {st.get('errors', 0)}",
            flush=True,
        )

    db = Database(db_path)
    try:
        stats = import_mirror(
            mirror,
            db,
            state=args.state,
            county=args.county,
            limit=int(args.limit or 0),
            with_photos=with_photos,
            with_html=with_html,
            skip_existing_urls=not args.force,
            require_photo=require_photo,
            progress_cb=progress,
        )
        print(
            f"  Done: seen {stats['seen']}, parsed {stats['parsed']}, "
            f"imported {stats['imported']}, skipped {stats['skipped']}, "
            f"no-photo {stats['rejected_no_photo']}, errors {stats['errors']} "
            f"→ {db_path}"
        )
    finally:
        db.close()
