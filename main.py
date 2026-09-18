import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import config  # noqa: E402


def main():
    config.ensure_dirs()
    from ui.app_window import AppWindow

    app = AppWindow()
    app.mainloop()


if __name__ == "__main__":
    main()