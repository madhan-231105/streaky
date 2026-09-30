from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Checkbox, Footer, Header, Input, Static


APP_DIR = Path.home() / ".kakarot-todo"
DB_PATH = APP_DIR / "todo.db"


class TodoDB:
    """Small SQLite data layer for tasks, recurring rules, and holidays."""

    def __init__(self, path: Path = DB_PATH):
        APP_DIR.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS recurring (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                recurrence TEXT NOT NULL DEFAULT 'daily',
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                recurring_id INTEGER,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (recurring_id) REFERENCES recurring(id)
            );

            CREATE TABLE IF NOT EXISTS holidays (
                holiday_date TEXT PRIMARY KEY,
                note TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_due_date
            ON tasks(due_date);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_occurrence
            ON tasks(recurring_id, due_date)
            WHERE recurring_id IS NOT NULL;
            """
        )
        self.conn.commit()

    # ---------- Tasks ----------

    def add_task(self, title: str, due_date: date, recurring: bool) -> None:
        """Add either a one-time task or a daily recurring task."""
        now = datetime.now().isoformat(timespec="seconds")

        if recurring:
            cursor = self.conn.execute(
                """
                INSERT INTO recurring(title, recurrence)
                VALUES (?, 'daily')
                """,
                (title,),
            )
            recurring_id = cursor.lastrowid

            # Create enough occurrences for the near future.
            for offset in range(120):
                occurrence_date = due_date + timedelta(days=offset)
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO tasks
                    (title, due_date, recurring_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        title,
                        occurrence_date.isoformat(),
                        recurring_id,
                        now,
                    ),
                )
        else:
            self.conn.execute(
                """
                INSERT INTO tasks(title, due_date, created_at)
                VALUES (?, ?, ?)
                """,
                (title, due_date.isoformat(), now),
            )

        self.conn.commit()

    def get_tasks(self, selected_date: date) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE due_date = ?
            ORDER BY completed ASC, recurring_id IS NULL ASC, id ASC
            """,
            (selected_date.isoformat(),),
        ).fetchall()

    def toggle_task(self, task_id: int) -> None:
        task = self.conn.execute(
            "SELECT completed FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if task is None:
            return

        completed = not bool(task["completed"])
        completed_at = (
            datetime.now().isoformat(timespec="seconds")
            if completed
            else None
        )

        self.conn.execute(
            """
            UPDATE tasks
            SET completed = ?, completed_at = ?
            WHERE id = ?
            """,
            (int(completed), completed_at, task_id),
        )
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    # ---------- Holidays ----------

    def set_holiday(self, holiday_date: date, note: str = "") -> None:
        """Mark a date as a holiday/excluded day."""
        self.conn.execute(
            """
            INSERT INTO holidays(holiday_date, note)
            VALUES (?, ?)
            ON CONFLICT(holiday_date)
            DO UPDATE SET note = excluded.note
            """,
            (holiday_date.isoformat(), note),
        )
        self.conn.commit()

    def remove_holiday(self, holiday_date: date) -> None:
        self.conn.execute(
            "DELETE FROM holidays WHERE holiday_date = ?",
            (holiday_date.isoformat(),),
        )
        self.conn.commit()

    def is_holiday(self, selected_date: date) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM holidays WHERE holiday_date = ?",
            (selected_date.isoformat(),),
        ).fetchone()
        return row is not None

    def holiday_dates(self, year: int, month: int) -> set[str]:
        first_day = date(year, month, 1)
        last_day = date(
            year + 1, 1, 1
        ) if month == 12 else date(year, month + 1, 1)

        rows = self.conn.execute(
            """
            SELECT holiday_date
            FROM holidays
            WHERE holiday_date >= ? AND holiday_date < ?
            """,
            (first_day.isoformat(), last_day.isoformat()),
        ).fetchall()

        return {row["holiday_date"] for row in rows}

    # ---------- Calendar / stats ----------

    def month_task_counts(self, year: int, month: int) -> dict[str, tuple[int, int]]:
        first_day = date(year, month, 1)
        last_day = (
            date(year + 1, 1, 1)
            if month == 12
            else date(year, month + 1, 1)
        )

        rows = self.conn.execute(
            """
            SELECT
                due_date,
                SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed
            FROM tasks
            WHERE due_date >= ? AND due_date < ?
            GROUP BY due_date
            """,
            (first_day.isoformat(), last_day.isoformat()),
        ).fetchall()

        return {
            row["due_date"]: (row["pending"], row["completed"])
            for row in rows
        }

    def today_stats(self) -> tuple[int, int]:
        today = date.today().isoformat()

        pending = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM tasks
            WHERE due_date = ? AND completed = 0
            """,
            (today,),
        ).fetchone()[0]

        completed = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM tasks
            WHERE due_date = ? AND completed = 1
            """,
            (today,),
        ).fetchone()[0]

        return pending, completed


class CalendarWidget(Static):
    """Render the month calendar without owning application state."""

    def __init__(self, app: "KakarotTodo"):
        super().__init__()
        self.todo_app = app

    def render(self) -> Text:
        app = self.todo_app
        year = app.calendar_month.year
        month = app.calendar_month.month

        task_counts = app.db.month_task_counts(year, month)
        holidays = app.db.holiday_dates(year, month)

        output = Text()
        title = f"{calendar.month_name[month]} {year}"
        output.append(title.center(31) + "\n", style="bold")
        output.append("Mo  Tu  We  Th  Fr  Sa  Su\n", style="dim")

        for week in calendar.monthcalendar(year, month):
            for day_number in week:
                if day_number == 0:
                    output.append("    ")
                    continue

                current = date(year, month, day_number)
                key = current.isoformat()
                pending, completed = task_counts.get(key, (0, 0))

                if current == app.selected_date:
                    style = "bold reverse"
                    marker = "[]"
                elif key in holidays:
                    style = "bold"
                    marker = "H "
                elif current == date.today():
                    style = "bold underline"
                    marker = "  "
                elif completed:
                    style = "bold"
                    marker = "✓ "
                elif pending:
                    style = "bold"
                    marker = "• "
                else:
                    style = ""
                    marker = "  "

                output.append(f"{marker}{day_number:2d} ", style=style)

            output.append("\n")

        output.append("\n")
        output.append("H ", style="bold")
        output.append("Holiday  ")
        output.append("• ", style="bold")
        output.append("Task  ")
        output.append("✓ ", style="bold")
        output.append("Done  ")
        output.append("[] ", style="reverse")
        output.append("Selected")

        return output


class AddTaskDialog(Vertical):
    """Simple inline dialog for creating a task."""

    def compose(self) -> ComposeResult:
        yield Static("Add Task", classes="dialog_title")
        yield Input(placeholder="Task name", id="task_title")
        yield Checkbox("Repeat every day", id="repeat_daily")
        yield Static("Enter = Save   Esc = Cancel", classes="dialog_help")


class KakarotTodo(App):
    """Main application."""

    TITLE = "Kakarot Todo"

    CSS = """
    Screen {
        background: #0b0b0b;
        color: #e8e8e8;
    }

    #main {
        height: 1fr;
    }

    #tasks_panel {
        width: 60%;
        border: round #444444;
        padding: 1 2;
    }

    #calendar_panel {
        width: 40%;
        border: round #444444;
        padding: 1 2;
    }

    #task_header {
        height: 3;
        text-style: bold;
    }

    #task_list {
        height: 1fr;
    }

    .task_row {
        height: 2;
        padding: 0 1;
    }

    .selected_task {
        background: #333333;
        text-style: bold;
    }

    .completed {
        color: #777777;
        text-style: strike;
    }

    #dialog {
        display: none;
        height: auto;
        padding: 1 2;
        border: round #777777;
        margin-top: 1;
    }

    .dialog_title {
        text-style: bold;
        margin-bottom: 1;
    }

    .dialog_help {
        color: #888888;
        margin-top: 1;
    }

    #status {
        height: 3;
        border-top: solid #444444;
        padding: 0 1;
        content-align: center middle;
    }

    Footer {
        background: #111111;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("up", "previous_task", "Task ↑"),
        ("down", "next_task", "Task ↓"),
        ("space", "toggle_task", "Complete"),
        ("left", "previous_day", "Date ←"),
        ("right", "next_day", "Date →"),
        ("pageup", "previous_month", "Month ←"),
        ("pagedown", "next_month", "Month →"),
        ("a", "show_add_dialog", "Add"),
        ("h", "toggle_holiday", "Holiday"),
        ("d", "delete_task", "Delete"),
        ("t", "today", "Today"),
    ]

    def __init__(self):
        super().__init__()

        self.db = TodoDB()
        self.selected_date = date.today()
        self.calendar_month = date.today().replace(day=1)
        self.selected_task_index = 0
        self.dialog_open = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main"):
            with Vertical(id="tasks_panel"):
                yield Static(id="task_header")
                yield VerticalScroll(id="task_list")

                with Vertical(id="dialog"):
                    yield Static("Add Task", classes="dialog_title")
                    yield Input(placeholder="Task name", id="task_title")
                    yield Checkbox("Repeat every day", id="repeat_daily")
                    yield Static(
                        "Enter = Save   Esc = Cancel",
                        classes="dialog_help",
                    )

            with Vertical(id="calendar_panel"):
                yield CalendarWidget(self)
                yield Static(id="status")

        yield Footer()

    def on_mount(self) -> None:
        self.refresh_view()

    # ---------- View ----------

    def refresh_view(self) -> None:
        tasks = self.db.get_tasks(self.selected_date)

        header = self.query_one("#task_header", Static)
        holiday_label = "  •  HOLIDAY" if self.db.is_holiday(self.selected_date) else ""

        header.update(
            f"{self.selected_date.strftime('%A, %d %B %Y')}{holiday_label}\n"
            "Tasks"
        )

        task_list = self.query_one("#task_list", VerticalScroll)
        task_list.remove_children()

        if not tasks:
            task_list.mount(
                Static(
                    "No tasks for this date.\n"
                    "Press 'a' to add a task.",
                    classes="task_row",
                )
            )
        else:
            for index, task in enumerate(tasks):
                prefix = "✓" if task["completed"] else "☐"
                recurring = "  🔁 daily" if task["recurring_id"] else ""
                text = f"{prefix}  {task['title']}{recurring}"

                classes = "task_row"
                if task["completed"]:
                    classes += " completed"
                if index == self.selected_task_index:
                    classes += " selected_task"

                task_list.mount(Static(text, classes=classes))

        pending, completed = self.db.today_stats()
        holiday = "  •  Holiday marked" if self.db.is_holiday(date.today()) else ""

        self.query_one("#status", Static).update(
            f"Today: {completed} completed • {pending} pending{holiday}\n"
            "←→ date   ↑↓ task   Space complete   a add   h holiday"
        )

        self.query_one(CalendarWidget).refresh()

    # ---------- Task navigation ----------

    def current_tasks(self) -> list[sqlite3.Row]:
        return self.db.get_tasks(self.selected_date)

    def action_previous_task(self) -> None:
        if self.current_tasks():
            self.selected_task_index = max(0, self.selected_task_index - 1)
            self.refresh_view()

    def action_next_task(self) -> None:
        tasks = self.current_tasks()
        if tasks:
            self.selected_task_index = min(
                len(tasks) - 1,
                self.selected_task_index + 1,
            )
            self.refresh_view()

    def action_toggle_task(self) -> None:
        tasks = self.current_tasks()
        if not tasks:
            return

        self.db.toggle_task(tasks[self.selected_task_index]["id"])
        self.refresh_view()

    def action_delete_task(self) -> None:
        tasks = self.current_tasks()
        if not tasks:
            return

        self.db.delete_task(tasks[self.selected_task_index]["id"])
        self.selected_task_index = max(0, self.selected_task_index - 1)
        self.refresh_view()

    # ---------- Date navigation ----------

    def move_date(self, days: int) -> None:
        self.selected_date += timedelta(days=days)
        self.calendar_month = self.selected_date.replace(day=1)
        self.selected_task_index = 0
        self.refresh_view()

    def action_previous_day(self) -> None:
        self.move_date(-1)

    def action_next_day(self) -> None:
        self.move_date(1)

    def action_previous_month(self) -> None:
        current = self.calendar_month
        self.calendar_month = (
            date(current.year - 1, 12, 1)
            if current.month == 1
            else date(current.year, current.month - 1, 1)
        )
        self.query_one(CalendarWidget).refresh()

    def action_next_month(self) -> None:
        current = self.calendar_month
        self.calendar_month = (
            date(current.year + 1, 1, 1)
            if current.month == 12
            else date(current.year, current.month + 1, 1)
        )
        self.query_one(CalendarWidget).refresh()

    def action_today(self) -> None:
        self.selected_date = date.today()
        self.calendar_month = date.today().replace(day=1)
        self.selected_task_index = 0
        self.refresh_view()

    # ---------- Add task dialog ----------

    def action_show_add_dialog(self) -> None:
        self.dialog_open = True
        dialog = self.query_one("#dialog", Vertical)
        dialog.display = True

        title_input = self.query_one("#task_title", Input)
        title_input.value = ""
        self.query_one("#repeat_daily", Checkbox).value = False
        title_input.focus()

    def close_add_dialog(self) -> None:
        self.dialog_open = False
        self.query_one("#dialog", Vertical).display = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "task_title":
            return

        title = event.value.strip()
        if not title:
            self.close_add_dialog()
            return

        recurring = self.query_one("#repeat_daily", Checkbox).value

        self.db.add_task(
            title=title,
            due_date=self.selected_date,
            recurring=recurring,
        )

        self.selected_task_index = 0
        self.close_add_dialog()
        self.refresh_view()

    # ---------- Holidays ----------

    def action_toggle_holiday(self) -> None:
        """
        Mark/unmark the selected date as a holiday.

        A holiday is an explicitly excluded day. It is stored before the day
        ends, so future streak logic can treat it as an allowed gap.
        """
        if self.db.is_holiday(self.selected_date):
            self.db.remove_holiday(self.selected_date)
        else:
            self.db.set_holiday(self.selected_date)

        self.refresh_view()

    def on_key(self, event) -> None:
        if event.key == "escape" and self.dialog_open:
            self.close_add_dialog()
            event.stop()


def main() -> None:
    KakarotTodo().run()


if __name__ == "__main__":
    main()
