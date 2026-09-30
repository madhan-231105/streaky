from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, ListItem, ListView, Static, TextArea

APP_DIR = Path.home() / ".streaky"
DB_PATH = APP_DIR / "streaky.db"
DAYS_TO_GENERATE = 120


def fmt_day(value: date) -> str:
    return value.isoformat()


class TodoDB:
    """SQLite data layer for Streaky."""

    def __init__(self, path: Path = DB_PATH) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                recurring INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS holidays (
                day TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS recurring (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            """
        )

        columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(tasks)")
        }
        if "notes" not in columns:
            self.conn.execute(
                "ALTER TABLE tasks ADD COLUMN notes TEXT NOT NULL DEFAULT ''"
            )
        if "recurring" not in columns:
            self.conn.execute(
                "ALTER TABLE tasks ADD COLUMN recurring INTEGER NOT NULL DEFAULT 0"
            )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def add_task(
        self, title: str, due: date, recurring: bool = False, notes: str = ""
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO tasks(title, due_date, completed, recurring, notes, created_at)
            VALUES (?, ?, 0, ?, ?, ?)
            """,
            (title, fmt_day(due), int(recurring), notes, datetime.now().isoformat()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_daily(self, title: str, start: date, notes: str = "") -> None:
        self.conn.execute(
            "INSERT INTO recurring(title, notes, created_at) VALUES (?, ?, ?)",
            (title, notes, datetime.now().isoformat()),
        )

        for offset in range(DAYS_TO_GENERATE):
            day = start + timedelta(days=offset)
            self.conn.execute(
                """
                INSERT INTO tasks(title, due_date, completed, recurring, notes, created_at)
                VALUES (?, ?, 0, 1, ?, ?)
                """,
                (title, fmt_day(day), notes, datetime.now().isoformat()),
            )
        self.conn.commit()

    def ensure_recurring_future(self) -> None:
        horizon = date.today() + timedelta(days=DAYS_TO_GENERATE)

        for row in self.conn.execute(
            "SELECT id, title, notes FROM recurring ORDER BY id"
        ).fetchall():
            last = self.conn.execute(
                "SELECT MAX(due_date) AS d FROM tasks WHERE recurring=1 AND title=?",
                (row["title"],),
            ).fetchone()["d"]

            start = date.fromisoformat(last) + timedelta(days=1) if last else date.today()

            while start <= horizon:
                self.conn.execute(
                    """
                    INSERT INTO tasks(title, due_date, completed, recurring, notes, created_at)
                    VALUES (?, ?, 0, 1, ?, ?)
                    """,
                    (
                        row["title"],
                        fmt_day(start),
                        row["notes"],
                        datetime.now().isoformat(),
                    ),
                )
                start += timedelta(days=1)

        self.conn.commit()

    def tasks_for(self, day: date):
        return self.conn.execute(
            "SELECT * FROM tasks WHERE due_date=? ORDER BY id",
            (fmt_day(day),),
        ).fetchall()

    def task(self, task_id: int):
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)
        ).fetchone()

    def all_tasks(self):
        return self.conn.execute(
            "SELECT * FROM tasks ORDER BY due_date, id"
        ).fetchall()

    def set_completed(self, task_id: int, completed: bool) -> None:
        self.conn.execute(
            "UPDATE tasks SET completed=? WHERE id=?",
            (int(completed), task_id),
        )
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def update_notes(self, task_id: int, notes: str) -> None:
        self.conn.execute(
            "UPDATE tasks SET notes=? WHERE id=?", (notes, task_id)
        )
        self.conn.commit()

    def is_holiday(self, day: date) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM holidays WHERE day=?", (fmt_day(day),)
            ).fetchone()
            is not None
        )

    def set_holiday(self, day: date) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO holidays(day) VALUES (?)", (fmt_day(day),)
        )
        self.conn.commit()

    def remove_holiday(self, day: date) -> None:
        self.conn.execute(
            "DELETE FROM holidays WHERE day=?", (fmt_day(day),)
        )
        self.conn.commit()

    def holidays(self) -> set[date]:
        return {
            date.fromisoformat(row["day"])
            for row in self.conn.execute("SELECT day FROM holidays")
        }

    def carry_pending_tasks_to_next_day(self, holiday: date) -> None:
        next_day = holiday + timedelta(days=1)

        for row in self.tasks_for(holiday):
            if row["completed"]:
                continue

            # The next recurring occurrence already exists.
            if row["recurring"]:
                continue

            self.conn.execute(
                """
                INSERT INTO tasks(title, due_date, completed, recurring, notes, created_at)
                VALUES (?, ?, 0, 0, ?, ?)
                """,
                (
                    row["title"],
                    fmt_day(next_day),
                    row["notes"],
                    datetime.now().isoformat(),
                ),
            )
            self.conn.execute("DELETE FROM tasks WHERE id=?", (row["id"],))

        self.conn.commit()

    def completion_counts(self, start: date, end: date) -> dict[date, int]:
        rows = self.conn.execute(
            """
            SELECT due_date, COUNT(*) AS n
            FROM tasks
            WHERE completed=1 AND due_date BETWEEN ? AND ?
            GROUP BY due_date
            """,
            (fmt_day(start), fmt_day(end)),
        ).fetchall()

        return {
            date.fromisoformat(row["due_date"]): row["n"]
            for row in rows
        }

    def active_days(self, start: date, end: date) -> set[date]:
        rows = self.conn.execute(
            """
            SELECT due_date
            FROM tasks
            WHERE completed=1 AND due_date BETWEEN ? AND ?
            GROUP BY due_date
            """,
            (fmt_day(start), fmt_day(end)),
        ).fetchall()

        return {date.fromisoformat(row["due_date"]) for row in rows}


class ConfirmDelete(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f'Delete "{self.title}"?'),
            Label("This cannot be undone."),
            Horizontal(
                Button("Delete", id="yes", variant="error"),
                Button("Cancel", id="no"),
                classes="modal-buttons",
            ),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_cancel(self) -> None:
        self.dismiss(False)


class HolidayCarryDialog(ModalScreen[bool]):
    BINDINGS = [
        ("y", "carry", "Carry"),
        ("n", "keep", "Keep"),
        ("escape", "keep", "Keep"),
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Mark this day as a holiday?"),
            Label("Carry unfinished tasks to the next day?"),
            Horizontal(
                Button("Yes", id="yes"),
                Button("No", id="no"),
            ),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_carry(self) -> None:
        self.dismiss(True)

    def action_keep(self) -> None:
        self.dismiss(False)


class AddTaskDialog(ModalScreen[tuple[str, bool] | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Add task"),
            Input(placeholder="Task title", id="title"),
            Checkbox("Repeat every day", id="recurring"),
            Horizontal(
                Button("Add", id="add", variant="success"),
                Button("Cancel", id="cancel"),
            ),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        title = self.query_one("#title", Input).value.strip()
        if title:
            self.dismiss(
                (title, self.query_one("#recurring", Checkbox).value)
            )

    def action_cancel(self) -> None:
        self.dismiss(None)


class AllTasksScreen(Screen):
    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "back", "Back"),
        ("l", "back", "Back"),
    ]

    def __init__(self, db: TodoDB) -> None:
        super().__init__()
        self.db = db

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("All Tasks", id="screen-title")
        yield ListView(id="all-task-list")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_tasks()

    def refresh_tasks(self) -> None:
        view = self.query_one("#all-task-list", ListView)
        view.clear()

        current_day = None
        for row in self.db.all_tasks():
            due = date.fromisoformat(row["due_date"])

            if due != current_day:
                current_day = due
                view.append(
                    ListItem(Label(f"── {due:%a, %d %b %Y} ──"))
                )

            mark = "✓" if row["completed"] else "○"
            repeat = " ↻" if row["recurring"] else ""
            view.append(
                ListItem(Label(f"{mark} {row['title']}{repeat}"))
            )

    def action_back(self) -> None:
        self.app.pop_screen()


class Streaky(App):
    TITLE = "Streaky"
    SUB_TITLE = "Tasks • streaks • progress"

    CSS = """
    Screen {
        background: $surface;
    }

    #main {
        height: 1fr;
    }

    #tasks-panel {
        width: 60%;
        border: round $accent;
        padding: 1;
    }

    #right-panel {
        width: 40%;
        border: round $accent;
        padding: 1;
    }

    #task-list {
        height: 1fr;
    }

    #calendar {
        height: 14;
        border: round $secondary;
        padding: 1;
    }

    #notes-label {
        margin-top: 1;
    }

    #notes {
        height: 7;
        border: round $secondary;
    }

    #streak {
        height: 3;
        content-align: center middle;
        text-style: bold;
    }

    #heatmap {
        height: 9;
        border: round $secondary;
        padding: 1;
    }

    #dialog {
        width: 60;
        max-width: 90%;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
        align: center middle;
    }

    .modal-buttons {
        height: 3;
        align-horizontal: center;
    }

    #screen-title {
        padding: 1;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("a", "add", "Add"),
        ("d", "delete", "Delete"),
        ("h", "holiday", "Holiday"),
        ("l", "all_tasks", "All tasks"),
        ("space", "toggle", "Complete"),
        ("ctrl+s", "save_notes", "Save notes"),
        ("left", "prev_day", "Previous day"),
        ("right", "next_day", "Next day"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.db = TodoDB()
        self.selected_day = date.today()
        self.selected_task_id: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main"):
            with Vertical(id="tasks-panel"):
                yield Label("", id="day-title")
                yield ListView(id="task-list")

            with Vertical(id="right-panel"):
                yield Static("", id="streak")
                yield Static("", id="heatmap")
                yield Static("", id="calendar")
                yield Label("Notes for selected task", id="notes-label")
                yield TextArea("", id="notes")

        yield Footer()

    def on_mount(self) -> None:
        self.db.ensure_recurring_future()
        self.refresh()

    def refresh(self) -> None:
        self.refresh_tasks()
        self.refresh_calendar()
        self.refresh_heatmap()
        self.refresh_streak()
        self.refresh_notes()

    def refresh_tasks(self) -> None:
        title = self.query_one("#day-title", Label)
        title.update(
            f"{self.selected_day:%A, %d %B %Y}"
            + ("  [HOLIDAY]" if self.db.is_holiday(self.selected_day) else "")
        )

        view = self.query_one("#task-list", ListView)
        view.clear()
        rows = self.db.tasks_for(self.selected_day)
        self.selected_task_id = None

        for row in rows:
            mark = "✓" if row["completed"] else "○"
            repeat = " ↻" if row["recurring"] else ""

            item = ListItem(
                Label(f"{mark} {row['title']}{repeat}")
            )
            item.data = row["id"]  # type: ignore[attr-defined]
            view.append(item)

        if rows:
            self.selected_task_id = rows[0]["id"]
            view.index = 0

    def refresh_notes(self) -> None:
        area = self.query_one("#notes", TextArea)
        area.load_text("")

        if self.selected_task_id is not None:
            row = self.db.task(self.selected_task_id)
            if row:
                area.load_text(row["notes"])

    def refresh_calendar(self) -> None:
        widget = self.query_one("#calendar", Static)

        start = self.selected_day - timedelta(days=self.selected_day.weekday())
        lines = ["Mon  Tue  Wed  Thu  Fri  Sat  Sun"]

        for week in range(5):
            parts = []

            for col in range(7):
                day = start + timedelta(days=week * 7 + col)
                rows = self.db.tasks_for(day)
                count = len(rows)
                done = sum(row["completed"] for row in rows)

                if self.db.is_holiday(day):
                    token = f"[#ff7777]{day.day:2}H[/#ff7777]"
                elif day == self.selected_day:
                    token = f"[bold reverse]{day.day:2}[/bold reverse]"
                elif count and done == count:
                    token = f"[green]{day.day:2}✓[/green]"
                elif count:
                    token = f"{day.day:2}•"
                else:
                    token = f"{day.day:2} "

                parts.append(token)

            lines.append("  ".join(parts))

        widget.update("\n".join(lines))

    def refresh_heatmap(self) -> None:
        end = date.today()
        start = end - timedelta(days=83)
        counts = self.db.completion_counts(start, end)

        lines = ["Activity — last 12 weeks"]

        for row in range(7):
            cells = []

            for col in range(12):
                day = start + timedelta(days=col * 7 + row)
                cells.append(self.level_cell(counts.get(day, 0)))

            lines.append(" ".join(cells))

        self.query_one("#heatmap", Static).update("\n".join(lines))

    @staticmethod
    def level_cell(count: int) -> str:
        if count == 0:
            return "[#303030]■[/#303030]"
        if count == 1:
            return "[#6b7280]■[/#6b7280]"
        if count == 2:
            return "[#9ca3af]■[/#9ca3af]"
        if count <= 4:
            return "[#d1d5db]■[/#d1d5db]"
        return "[bold #ffffff]■[/bold #ffffff]"

    def refresh_streak(self) -> None:
        completed = self.db.active_days(
            date.today() - timedelta(days=365),
            date.today(),
        )
        holidays = self.db.holidays()

        streak = 0
        cursor = date.today()

        while cursor >= date.today() - timedelta(days=365):
            if cursor in holidays:
                cursor -= timedelta(days=1)
                continue

            if cursor in completed:
                streak += 1
                cursor -= timedelta(days=1)
                continue

            break

        self.query_one("#streak", Static).update(
            f"🔥 Current streak: {streak} day(s)"
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        task_id = getattr(event.item, "data", None)

        if task_id is not None:
            self.selected_task_id = int(task_id)
            self.refresh_notes()

    def action_toggle(self) -> None:
        if self.selected_task_id is None:
            return

        row = self.db.task(self.selected_task_id)

        if row:
            self.db.set_completed(
                self.selected_task_id,
                not bool(row["completed"]),
            )
            self.refresh()

    def action_add(self) -> None:
        def done(result: tuple[str, bool] | None) -> None:
            if not result:
                return

            title, recurring = result

            if recurring:
                self.db.add_daily(title, self.selected_day)
            else:
                self.db.add_task(title, self.selected_day)

            self.refresh()

        self.push_screen(AddTaskDialog(), done)

    def action_delete(self) -> None:
        if self.selected_task_id is None:
            return

        row = self.db.task(self.selected_task_id)

        if not row:
            return

        def done(confirmed: bool) -> None:
            if confirmed and self.selected_task_id is not None:
                self.db.delete_task(self.selected_task_id)
                self.refresh()

        self.push_screen(
            ConfirmDelete(row["title"]),
            done,
        )

    def action_holiday(self) -> None:
        if self.db.is_holiday(self.selected_day):
            self.db.remove_holiday(self.selected_day)
            self.refresh()
            return

        def done(carry: bool) -> None:
            self.db.set_holiday(self.selected_day)

            if carry:
                self.db.carry_pending_tasks_to_next_day(
                    self.selected_day
                )

            self.refresh()

        self.push_screen(
            HolidayCarryDialog(),
            done,
        )

    def action_save_notes(self) -> None:
        if self.selected_task_id is None:
            return

        notes = self.query_one("#notes", TextArea).text
        self.db.update_notes(self.selected_task_id, notes)
        self.notify("Notes saved.")

    def action_prev_day(self) -> None:
        self.selected_day -= timedelta(days=1)
        self.refresh()

    def action_next_day(self) -> None:
        self.selected_day += timedelta(days=1)
        self.refresh()

    def action_all_tasks(self) -> None:
        self.push_screen(AllTasksScreen(self.db))

    def on_unmount(self) -> None:
        self.db.close()


def show_storage() -> None:
    """Show the same kind of useful storage information users expect from Taskwarrior."""
    print("Streaky storage")
    print("----------------")
    print(f"Data directory : {APP_DIR}")
    print(f"Database       : {DB_PATH}")
    exists = "yes" if DB_PATH.exists() else "no"
    print(f"Database exists: {exists}")
    print()
    print("Source/config")
    print("-------------")
    print("Application    : installed through uv tool")
    print("Project source : the directory from which Streaky was installed")
    print()
    print("Commands")
    print("--------")
    print("streaky        Start the TUI")
    print("streaky show   Show storage information")


def main() -> None:
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command in {"show", "info", "--show"}:
            show_storage()
            return

        if command in {"--version", "-V", "version"}:
            print("Streaky 0.6.2")
            return

        if command in {"--help", "-h", "help"}:
            print("Streaky - terminal-first daily task manager")
            print()
            print("Usage:")
            print("  streaky        Start the TUI")
            print("  streaky show   Show storage information")
            print("  streaky --version")
            return

    Streaky().run()


if __name__ == "__main__":
    main()
