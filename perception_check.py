from __future__ import annotations

import tkinter as tk
from gui.app import PerceptualEquationsApp


def main() -> None:
    """Create and run the Tkinter application."""
    root = tk.Tk()
    app = PerceptualEquationsApp(root)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()
