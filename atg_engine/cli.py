"""CLI entrypoint: run-daily, run-publish, run-analytics, run-weekly, dashboard, scheduler, db init."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="atg_engine", description="Autonomous Twitter Growth Engine")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run-daily
    p_daily = subparsers.add_parser("run-daily", help="Run daily content generation pipeline")
    p_daily.add_argument("--n-ideas", type=int, default=3, help="Number of ideas to generate")
    p_daily.add_argument("--no-verbose", action="store_true", help="Disable verbose output")
    p_daily.add_argument("--dry-run", action="store_true", help="Run pipeline but do not save approved candidates to DB")
    p_daily.set_defaults(func=_run_daily)

    # run-publish
    p_publish = subparsers.add_parser("run-publish", help="Run publishing pipeline")
    p_publish.add_argument("--limit", type=int, default=5, help="Max tweets to publish")
    p_publish.add_argument("--dry-run", action="store_true", help="List what would be published without posting")
    p_publish.add_argument("--preview", action="store_true", help="Same as --dry-run")
    p_publish.set_defaults(func=_run_publish)

    # run-analytics
    p_analytics = subparsers.add_parser("run-analytics", help="Run performance ingestion pipeline")
    p_analytics.set_defaults(func=_run_analytics)

    # run-weekly
    p_weekly = subparsers.add_parser("run-weekly", help="Run weekly review and evolution pipeline")
    p_weekly.add_argument("--no-verbose", action="store_true", help="Disable verbose output")
    p_weekly.set_defaults(func=_run_weekly)

    # run-trending
    p_trending = subparsers.add_parser("run-trending", help="Run trending content discovery and curation pipeline")
    p_trending.add_argument("--query", type=str, default="", help="Search query (empty for recent non-RT tweets)")
    p_trending.add_argument("--max-results", type=int, default=10, help="Max trending tweets to analyze")
    p_trending.add_argument("--min-likes", type=int, default=100, help="Minimum likes threshold")
    p_trending.add_argument("--min-retweets", type=int, default=10, help="Minimum retweets threshold")
    p_trending.add_argument("--no-verbose", action="store_true", help="Disable verbose output")
    p_trending.add_argument("--dry-run", action="store_true", help="Run pipeline but do not save to DB")
    p_trending.set_defaults(func=_run_trending)

    # dashboard
    p_dashboard = subparsers.add_parser("dashboard", help="Show CLI scoreboard (followers, engagement, evolution)")
    p_dashboard.set_defaults(func=_dashboard)

    # scheduler
    p_scheduler = subparsers.add_parser("scheduler", help="Start APScheduler (daily, hourly, weekly jobs)")
    p_scheduler.set_defaults(func=_scheduler)

    # db init
    p_db = subparsers.add_parser("db", help="Database commands")
    p_db_sub = p_db.add_subparsers(dest="db_command")
    p_db_init = p_db_sub.add_parser("init", help="Create all tables")
    p_db_init.set_defaults(func=_db_init)

    # init-persona
    p_persona = subparsers.add_parser("init-persona", help="Create/update persona and optional voice/strategy from config file")
    p_persona.add_argument("--config", "-c", required=True, help="Path to JSON config (persona, optional voice_genome, strategy)")
    p_persona.set_defaults(func=_init_persona)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    if args.command == "db" and not getattr(args, "db_command", None):
        p_db.print_help()
        sys.exit(0)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        sys.exit(1)
    try:
        if args.command == "run-daily":
            func(
                n_ideas=getattr(args, "n_ideas", 3),
                verbose=not getattr(args, "no_verbose", False),
                dry_run=getattr(args, "dry_run", False),
            )
        elif args.command == "run-publish":
            func(
                limit=getattr(args, "limit", 5),
                dry_run=getattr(args, "dry_run", False) or getattr(args, "preview", False),
                preview=getattr(args, "preview", False),
            )
        elif args.command == "run-analytics":
            func()
        elif args.command == "run-weekly":
            func(verbose=not getattr(args, "no_verbose", False))
        elif args.command == "run-trending":
            func(
                query=getattr(args, "query", ""),
                max_results=getattr(args, "max_results", 10),
                min_likes=getattr(args, "min_likes", 100),
                min_retweets=getattr(args, "min_retweets", 10),
                verbose=not getattr(args, "no_verbose", False),
                dry_run=getattr(args, "dry_run", False),
            )
        elif args.command == "dashboard":
            func()
        elif args.command == "scheduler":
            func()
        elif args.command == "db":
            func()
        elif args.command == "init-persona":
            func(config=getattr(args, "config", None))
        else:
            func()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _run_daily(**kwargs):
    from atg_engine.pipelines.daily_generation import run
    print(run(**kwargs))


def _run_publish(**kwargs):
    from atg_engine.pipelines.publishing import run
    print(run(**kwargs))


def _run_analytics(**kwargs):
    from atg_engine.pipelines.performance_ingestion import run
    print(run(**kwargs))


def _run_weekly(**kwargs):
    from atg_engine.pipelines.weekly_review import run
    print(run(**kwargs))


def _run_trending(**kwargs):
    from atg_engine.pipelines.trending_content_pipeline import run
    print(run(**kwargs))


def _dashboard(**kwargs):
    from atg_engine.db.session import SessionLocal
    from atg_engine.models import AccountSnapshot, TweetPerformance, StrategyState, MutationLog

    db = SessionLocal()
    try:
        perf_list = db.query(TweetPerformance).order_by(TweetPerformance.timestamp.desc()).limit(100).all()
        avg_engagement = (
            sum(p.engagement_rate for p in perf_list) / len(perf_list)
            if perf_list else 0.0
        )
        mutations = db.query(MutationLog).count()
        strategy = db.query(StrategyState).order_by(StrategyState.last_reviewed.desc()).first()
        daily_target = strategy.daily_post_target if strategy else 0
        snapshots = db.query(AccountSnapshot).order_by(AccountSnapshot.recorded_at.desc()).limit(2).all()
        follower_count = snapshots[0].follower_count if snapshots else None
        follower_delta = (snapshots[0].follower_count - snapshots[1].follower_count) if len(snapshots) >= 2 else None

        try:
            from rich.console import Console
            from rich.table import Table
            console = Console()
            table = Table(title="ATGE Scoreboard")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            if follower_count is not None:
                table.add_row("Follower count (account)", str(follower_count))
                if follower_delta is not None:
                    table.add_row("Follower delta (since last ingestion)", f"{follower_delta:+d}")
            table.add_row("Avg engagement rate", f"{avg_engagement:.4f}")
            table.add_row("Mutation log count", str(mutations))
            table.add_row("Daily post target", str(daily_target))
            console.print(table)
        except ImportError:
            print("Metric                                  | Value")
            print("----------------------------------------|--------")
            if follower_count is not None:
                print(f"Follower count (account)              | {follower_count}")
                if follower_delta is not None:
                    print(f"Follower delta (since last ingestion) | {follower_delta:+d}")
            print(f"Avg engagement rate                    | {avg_engagement:.4f}")
            print(f"Mutation log count                     | {mutations}")
            print(f"Daily post target                      | {daily_target}")
    finally:
        db.close()


def _scheduler(**kwargs):
    from atg_engine.services.scheduler import start_scheduler
    start_scheduler()


def _db_init(**kwargs):
    from atg_engine.db.init_db import init_db
    init_db()
    print("Database tables created.")


def _init_persona(**kwargs):
    config_path = kwargs.get("config")
    if not config_path:
        print("Error: --config is required.", file=sys.stderr)
        sys.exit(1)
    from atg_engine.services.bootstrap import apply_persona_config
    msg = apply_persona_config(config_path)
    print(msg)
