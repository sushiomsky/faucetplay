"""
FaucetPlay — Application Entrypoint
Boots the GUI or falls back to CLI mode with --no-gui flag.
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    parser = argparse.ArgumentParser(description="FaucetPlay DuckDice Bot")
    parser.add_argument("--no-gui",    action="store_true", help="Run in CLI mode")
    parser.add_argument("--minimized", action="store_true", help="Start minimized (auto-launch)")
    parser.add_argument("--account",   help="Account ID to run in CLI mode")
    args = parser.parse_args()

    from core.config import BotConfig
    from core.accounts import AccountManager
    from core.network import NetworkProfileManager
    from core.scheduler import BotScheduler

    cfg     = BotConfig();     cfg.load()
    net_mgr = NetworkProfileManager()
    acc_mgr = AccountManager(network_mgr=net_mgr)
    sched   = BotScheduler()

    if args.no_gui:
        _run_cli(acc_mgr, net_mgr, cfg, args)
    else:
        _run_gui(cfg, acc_mgr, net_mgr, sched, minimized=args.minimized)


def _run_gui(cfg, acc_mgr, net_mgr, sched, minimized: bool = False):
    from gui.main_window import MainWindow
    app = MainWindow(cfg, acc_mgr, net_mgr, sched)
    if minimized:
        app.iconify()
    app.mainloop()


def _run_cli(acc_mgr, net_mgr, cfg, args):
    from core.bot import FaucetBot
    accounts = acc_mgr.all()
    if not accounts:
        print("No accounts configured. Run without --no-gui to use the setup wizard.")
        sys.exit(1)

    acct = None
    if args.account:
        acct = acc_mgr.get(args.account)
        if not acct:
            print(f"Account '{args.account}' not found.")
            sys.exit(1)
    else:
        acct = accounts[0]
        print(f"Running account: {acct.label}")

    bot = FaucetBot(
        account=acct,
        network_mgr=net_mgr,
        target_amount=float(cfg.get("target_amount") or 20.0),
        house_edge=float(cfg.get("house_edge") or 0.03),
    )
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    main()
