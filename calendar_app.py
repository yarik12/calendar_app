"""
Advanced calendar application built with Flet.

This program implements a simple desktop calendar with task management and
note‑taking capabilities. Users can pick a date, view tasks scheduled
for that day, add new tasks, schedule recurring events, and move tasks to
other days. The application demonstrates core object‑oriented principles
such as encapsulation, inheritance and composition. Data is persisted to
a JSON file in the current working directory so that tasks are retained
between sessions.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import flet as ft


@dataclass
class Task:
    """Represents a single task or note on the calendar."""

    title: str
    description: str
    date: _dt.date
    time: Optional[_dt.time] = None
    completed: bool = False
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, str | bool]:
        """Return a serialisable representation for persistence."""
        return {
            "type": "task",
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "date": self.date.isoformat(),
            "time": self.time.isoformat() if self.time else None,
            "completed": self.completed,
        }

    @staticmethod
    def from_dict(data: Dict[str, str | bool]) -> "Task":
        """Reconstruct a Task object from a dictionary."""
        date = _dt.date.fromisoformat(data["date"])
        time_str = data.get("time")
        time: Optional[_dt.time] = None
        if time_str:
            time = _dt.time.fromisoformat(time_str)
        return Task(
            title=data["title"],
            description=data.get("description", ""),
            date=date,
            time=time,
            completed=bool(data.get("completed", False)),
            task_id=data.get("task_id", str(uuid.uuid4())),
        )


@dataclass
class RecurringTask(Task):
    """Task that repeats on a schedule (daily, weekly or monthly)."""

    frequency: str = "daily"  # accepted values: daily, weekly, monthly
    start_date: _dt.date = field(default_factory=lambda: _dt.date.today())

    def occurs_on(self, date: _dt.date) -> bool:
        """Determine whether this recurring task occurs on the provided date."""
        if date < self.start_date:
            return False
        if self.frequency == "daily":
            return True
        if self.frequency == "weekly":
            return date.weekday() == self.start_date.weekday()
        if self.frequency == "monthly":
            return date.day == self.start_date.day
        return False

    def to_dict(self) -> Dict[str, str | bool]:
        base = super().to_dict()
        base.update(
            {
                "type": "recurring",
                "frequency": self.frequency,
                "start_date": self.start_date.isoformat(),
            }
        )
        return base

    @staticmethod
    def from_dict(data: Dict[str, str | bool]) -> "RecurringTask":
        """Reconstruct a RecurringTask from a dictionary."""
        base_task = Task.from_dict(data)
        frequency = data.get("frequency", "daily")
        start_date_str = data.get("start_date")
        start_date = _dt.date.fromisoformat(start_date_str) if start_date_str else _dt.date.today()
        return RecurringTask(
            title=base_task.title,
            description=base_task.description,
            date=base_task.date,
            time=base_task.time,
            completed=base_task.completed,
            task_id=base_task.task_id,
            frequency=frequency,
            start_date=start_date,
        )


class CalendarManager:
    """Manages tasks on a calendar, including recurring events and persistence."""

    def __init__(self, storage_path: str = "calendar_data.json") -> None:
        self.storage_path = storage_path
        self._tasks: Dict[str, List[Task]] = {}
        self._recurring: List[RecurringTask] = []
        self._load()

    def _load(self) -> None:
        """Load tasks from the JSON storage file if it exists."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("tasks", []):
                    if item.get("type") == "recurring":
                        self._recurring.append(RecurringTask.from_dict(item))
                    else:
                        task = Task.from_dict(item)
                        self._tasks.setdefault(task.date.isoformat(), []).append(task)
            except (json.JSONDecodeError, OSError):
                self._tasks = {}
                self._recurring = []

    def _save(self) -> None:
        """Persist tasks to the JSON storage file."""
        serialised: List[Dict[str, str | bool]] = []
        for tasks in self._tasks.values():
            for task in tasks:
                serialised.append(task.to_dict())
        for rec in self._recurring:
            serialised.append(rec.to_dict())
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"tasks": serialised}, f, indent=2)
        except OSError:
            print("Warning: failed to save calendar data.")

    def add_task(self, task: Task) -> None:
        """Add a new one‑off task to the calendar and persist."""
        self._tasks.setdefault(task.date.isoformat(), []).append(task)
        self._save()

    def add_recurring_task(self, task: RecurringTask) -> None:
        """Add a new recurring task to the calendar and persist."""
        self._recurring.append(task)
        self._save()

    def get_tasks_for_date(self, date: _dt.date) -> List[Task]:
        """Return tasks scheduled for a given date, including recurring ones."""
        results: List[Task] = []
        results.extend(self._tasks.get(date.isoformat(), []))
        for rec in self._recurring:
            if rec.occurs_on(date):
                cloned = Task(
                    title=rec.title,
                    description=rec.description,
                    date=date,
                    time=rec.time,
                    completed=rec.completed,
                    task_id=f"{rec.task_id}_{date.isoformat()}",
                )
                results.append(cloned)
        def sort_key(t: Task) -> tuple:
            return (t.time.isoformat() if t.time else "", t.title)
        return sorted(results, key=sort_key)

    def remove_task(self, task_id: str, date: _dt.date) -> None:
        tasks_on_date = self._tasks.get(date.isoformat())
        if not tasks_on_date:
            return
        self._tasks[date.isoformat()] = [t for t in tasks_on_date if t.task_id != task_id]
        self._save()

    def mark_complete(self, task_id: str, date: _dt.date, completed: bool) -> None:
        tasks_on_date = self._tasks.get(date.isoformat())
        if not tasks_on_date:
            return
        for t in tasks_on_date:
            if t.task_id == task_id:
                t.completed = completed
                break
        self._save()

    def move_task(self, task_id: str, from_date: _dt.date, to_date: _dt.date) -> None:
        if from_date.isoformat() == to_date.isoformat():
            return
        tasks_on_from = self._tasks.get(from_date.isoformat())
        if not tasks_on_from:
            return
        moved: Optional[Task] = None
        remaining: List[Task] = []
        for t in tasks_on_from:
            if t.task_id == task_id:
                moved = t
            else:
                remaining.append(t)
        if moved:
            moved.date = to_date
            self._tasks[from_date.isoformat()] = remaining
            self._tasks.setdefault(to_date.isoformat(), []).append(moved)
            self._save()


class CalendarApp:
    """Graphical user interface for the calendar using Flet."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.manager = CalendarManager()
        self.selected_date: _dt.date = _dt.date.today()
        self._build_ui()

    def _build_ui(self) -> None:
        page = self.page
        page.title = "Advanced Calendar"
        page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        page.vertical_alignment = ft.MainAxisAlignment.START
        page.window_width = 900
        page.window_height = 600
        self.date_picker = ft.DatePicker(
            on_change=self._on_date_change,
            first_date=_dt.datetime(2000, 1, 1),
            last_date=_dt.datetime(2100, 12, 31),
            current_date=_dt.datetime.combine(self.selected_date, _dt.time()),
        )
        date_button = ft.Button(
            content=lambda: ft.Row([
                ft.Icon(ft.Icons.CALENDAR_MONTH),
                ft.Text(self.selected_date.strftime("%A, %d %B %Y")),
            ], alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda _: page.show_dialog(self.date_picker),
        )
        self.task_list_view = ft.ListView(
            expand=True,
            spacing=10,
            padding=10,
            auto_scroll=False,
        )
        self.title_input = ft.TextField(label="Название задачи", expand=True)
        self.description_input = ft.TextField(
            label="Описание", multiline=True, min_lines=1, max_lines=3, expand=True
        )
        self.time_picker = ft.TimePicker(
            on_change=lambda e: None,
            help_text="Выберите время",
        )
        time_button = ft.Button(
            content="Время", icon=ft.Icons.ACCESS_TIME,
            on_click=lambda _: page.show_time_picker(self.time_picker),
        )
        self.recurring_dropdown = ft.Dropdown(
            label="Повторение",
            options=[
                ft.dropdown.Option("none", "Не повторять"),
                ft.dropdown.Option("daily", "Ежедневно"),
                ft.dropdown.Option("weekly", "Еженедельно"),
                ft.dropdown.Option("monthly", "Ежемесячно"),
            ],
            value="none",
            expand=True,
        )
        add_button = ft.ElevatedButton(
            text="Добавить задачу",
            icon=ft.Icons.ADD_TASK,
            on_click=self._on_add_task,
        )
        self.input_panel = ft.Container(
            content=ft.Column(
                [
                    self.title_input,
                    self.description_input,
                    ft.Row(
                        [
                            time_button,
                            self.recurring_dropdown,
                        ],
                        spacing=10,
                    ),
                    add_button,
                ],
                spacing=10,
            ),
            padding=20,
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=10,
            width=300,
        )
        page.add(
            ft.Column(
                [
                    ft.Row([date_button], alignment=ft.MainAxisAlignment.START),
                    ft.Row(
                        [
                            self.task_list_view,
                            self.input_panel,
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        expand=True,
                    ),
                ],
                expand=True,
            )
        )
        self._refresh_task_list()

    def _on_date_change(self, e: ft.Event[ft.DatePicker]) -> None:
        if isinstance(e.control, ft.DatePicker):
            date = e.control.value
        else:
            date = e.data
        if isinstance(date, _dt.datetime):
            self.selected_date = date.date()
        elif isinstance(date, _dt.date):
            self.selected_date = date
        self.page.controls[0].content.controls[0].controls[1].value = self.selected_date.strftime(
            "%A, %d %B %Y"
        )
        self._refresh_task_list()
        self.page.update()

    def _on_add_task(self, e: ft.Event) -> None:
        title = self.title_input.value.strip()
        desc = self.description_input.value.strip()
        if not title:
            self.page.snack_bar = ft.SnackBar(ft.Text("Название задачи обязательно"))
            self.page.snack_bar.open = True
            self.page.update()
            return
        time_value = None
        if self.time_picker.value:
            time_value = self.time_picker.value
        recurrence = self.recurring_dropdown.value
        if recurrence and recurrence != "none":
            task = RecurringTask(
                title=title,
                description=desc,
                date=self.selected_date,
                time=time_value,
                frequency=recurrence,
                start_date=self.selected_date,
            )
            self.manager.add_recurring_task(task)
        else:
            task = Task(
                title=title,
                description=desc,
                date=self.selected_date,
                time=time_value,
            )
            self.manager.add_task(task)
        self.title_input.value = ""
        self.description_input.value = ""
        self.time_picker.value = None
        self.recurring_dropdown.value = "none"
        self.page.update()
        self._refresh_task_list()
    def _refresh_task_list(self) -> None:
        """Refresh the visible list of tasks for the currently selected date."""
        self.task_list_view.controls.clear()
        tasks = self.manager.get_tasks_for_date(self.selected_date)
        if not tasks:
            self.task_list_view.controls.append(
                ft.Text("Нет задач на этот день", italic=True, color=ft.colors.ON_SURFACE_VARIANT)
            )
        for t in tasks:
            one_off = not isinstance(t, RecurringTask) and not t.task_id.endswith(self.selected_date.isoformat())
            checkbox = ft.Checkbox(
                value=t.completed,
                on_change=(
                    (lambda task=t: lambda ev: self._toggle_complete(task, ev)) if one_off else None
                ),
            )
            title_text = ft.Text(
                f"{t.time.strftime('%H:%M') + ' ' if t.time else ''}{t.title}",
                weight=ft.FontWeight.BOLD if not t.completed else ft.FontWeight.NORMAL,
                decoration=ft.TextDecoration.LINE_THROUGH if t.completed else ft.TextDecoration.NONE,
            )
            desc_text = ft.Text(
                t.description,
                size=12,
                italic=bool(t.description),
            )
            actions: List[ft.Control] = []
            if one_off:
                actions.append(
                    ft.IconButton(
                        icon=ft.Icons.ARROW_FORWARD,
                        tooltip="Перенести на другую дату",
                        on_click=(lambda task=t: lambda _: self._prompt_move_task(task)),
                    )
                )
                actions.append(
                    ft.IconButton(
                        icon=ft.Icons.DELETE,
                        tooltip="Удалить",
                        on_click=(lambda task=t: lambda _: self._delete_task(task)),
                    )
                )
            tile = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([
                                checkbox if one_off else ft.Icon(ft.Icons.EVENT_REPEAT),
                                title_text,
                                ft.Row(actions, spacing=0),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            desc_text if t.description else ft.Container(),
                        ],
                        spacing=2,
                    ),
                    padding=10,
                ),
            )
            self.task_list_view.controls.append(tile)
        self.page.update()

    def _toggle_complete(self, task: Task, event: ft.Event[ft.Checkbox]) -> None:
        self.manager.mark_complete(task.task_id, task.date, event.control.value)
        self._refresh_task_list()

    def _delete_task(self, task: Task) -> None:
        self.manager.remove_task(task.task_id, task.date)
        self._refresh_task_list()

    def _prompt_move_task(self, task: Task) -> None:
        move_picker = ft.DatePicker(
            first_date=_dt.datetime(2000, 1, 1),
            last_date=_dt.datetime(2100, 12, 31),
        )
        def on_move_change(e: ft.Event[ft.DatePicker]) -> None:
            new_date_val = e.control.value
            if isinstance(new_date_val, _dt.datetime):
                new_date = new_date_val.date()
            elif isinstance(new_date_val, _dt.date):
                new_date = new_date_val
            else:
                return
            self.manager.move_task(task.task_id, task.date, new_date)
            self._refresh_task_list()
            self.page.update()
        move_picker.on_change = on_move_change
        self.page.show_dialog(move_picker)
 def main(page: ft.Page) -> None:
    """Entry point for Flet. Called by ft.run()."""
    CalendarApp(page)


if __name__ == "__main__":
    # For testing within a Python interpreter, run as a native desktop app
    ft.app(target=main)
