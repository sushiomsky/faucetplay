#!/usr/bin/env python3
"""
FaucetPlay — Entry Point
Usage:
  python faucetplay_app.py              # Launch GUI
  python faucetplay_app.py --no-gui    # Headless bot run (uses saved config)
  python faucetplay_app.py --minimized # Launch GUI minimized (auto-start use)
  python faucetplay_app.py --version   # Print version and exit
"""
import argparse
import sys


def main():
    from core.version import APP_NAME, APP_VERSION, TAGLINE

    parser = argparse.ArgumentParser(
        prog="faucetplay",
        description=f"{APP_NAME} — {TAGLINE}",
    )
    parser.add_argument("--no-gui",    action="store_true",
                        help="Run bot headlessly using saved config")
    parser.add_argument("--minimized", action="store_true",
                        help="Start GUI minimized (for system auto-start)")
    parser.add_argument("--version",   action="store_true",
                        help="Print version and exit")
    args = parser.parse_args()

    if args.version:
        print(f"{APP_NAME} v{APP_VERSION}")
        sys.exit(0)

    from core.config import BotConfig
    cfg = BotConfig()
    cfg.load()

    if args.no_gui:
        _run_headless(cfg)
    else:
        _run_gui(cfg, minimized=args.minimized)


def _run_gui(cfg, minimized: bool = False):
    from gui.main_window import MainWindow
    app = MainWindow(config=cfg)
    if minimized:
        app.iconify()
    app.mainloop()


def _run_headless(cfg):
    import logging
    from core.version import APP_NAME, APP_VERSION
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger().info("%s v%s — headless mode", APP_NAME, APP_VERSION)
    from core.bot import FaucetBot
    bot = FaucetBot(config=cfg, log_callback=print)
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    main()
