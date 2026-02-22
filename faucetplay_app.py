#!/usr/bin/env python3
"""
FaucetPlay — Entry Point
Usage:
  python faucetplay_app.py            # Launch GUI
  python faucetplay_app.py --no-gui   # Headless bot run (uses saved config)
  python faucetplay_app.py --minimized # Launch GUI minimized (auto-start use)
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="faucetplay")
    parser.add_argument("--no-gui",    action="store_true",
                        help="Run bot headlessly using saved config")
    parser.add_argument("--minimized", action="store_true",
                        help="Start GUI minimized to tray")
    args = parser.parse_args()

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
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    from core.bot import FaucetBot
    bot = FaucetBot(config=cfg, log_callback=print)
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    main()
