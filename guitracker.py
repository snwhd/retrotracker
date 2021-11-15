#!/usr/bin/env python3
from typing import (
    cast,
    List,
    Tuple,
)
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import (
    pyqtSignal,
    QObject,
    QThread,
    Qt,
)
import time
import pymouse

from event import GameEvent, EventType
from retrotracker import RetroTracker


class ClickableLineEdit(QLineEdit):

    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        QLineEdit.mousePressEvent(self, event)


class GuiWorker(QObject):

    finished = pyqtSignal()
    log_event = pyqtSignal(GameEvent)
    log_string = pyqtSignal(str)

    def __init__(self, tracker: RetroTracker, parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.started = False
        self.paused = True
        self.working = True
        self.duration = 0.0

        self.resize_timer = 0.0
        self.resizing = False
        self.resize_p = (0, 0)
        self.m = pymouse.PyMouse()

    def do_work(self) -> None:
        self.started = True
        last_time = time.time()
        self.tracker.gamestate.init_second_db()
        while self.working:
            try:
                now = time.time()
                delta = now - last_time
                last_time = now
                if self.resizing:
                    self.resize_timer += delta
                    if self.resize_timer >= 3.0 and self.resize_p == (0, 0):
                        self.resize_p = self.m.position()
                        text = 'now move to bottom right'
                        self.log_string.emit(text)
                        self.resize_timer = 0.0
                    elif self.resize_timer >= 3.0:
                        x, y = self.resize_p
                        x2, y2 = self.m.position()
                        bbox = (x, y, x2 - x, y2 - y)
                        self.tracker.ocr.set_bbox(*bbox)
                        self.log_string.emit(f'bbox set to {bbox}')
                        self.resize_p = (0, 0)
                        self.resize_timer = 0.0
                        self.resizing = False
                elif not self.paused:
                    self.duration += delta
                    for line in self.tracker.ocr.gen_retrommo_lines():
                        event = self.tracker.gamestate.handle_line(line, second_db=True)
                        if event is not None:
                            self.handle_event(event)
                time.sleep(0.25)
            except Exception as e:
                print(f'error: {e}')
        self.finished.emit()

    def pause(self) -> None:
        self.paused = True

    def unpause(self) -> None:
        self.paused = False

    def handle_event(self, e: GameEvent) -> None:
        self.log_event.emit(e)

    def stop(self) -> None:
        self.working = False

    def resize_button_clicked(self) -> None:
        self.resize_timer = 0.0
        self.resizing = True
        text = 'place (but don\'t click) cursor at top left of battle text'
        self.log_string.emit(text)


class GuiTracker(QWidget):

    def __init__(
        self,
        tracker: RetroTracker,
    ) -> None:
        super().__init__()
        self.tracker = tracker
        self.players: List[Tuple[int, str]] = []
        self.selected_player_index = -1
        self.username = ''

        # ignore some warnings because value is set in create_ui
        self.scroll: QScrollArea = None        # type: ignore
        self.log_layout: QVBoxLayout = None    # type: ignore
        self.exp_display: QLabel = None        # type: ignore
        self.gold_display: QLabel = None       # type: ignore
        self.player_options: QComboBox = None  # type: ignore
        self.username_editor: QLineEdit = None # type: ignore
        self.setWindowTitle('RetroTracker')
        self.create_worker()
        self.create_ui()
        self.thread.start()

    def create_ui(self) -> None:
        layout = QVBoxLayout()

        top_side = QWidget()
        top_side_layout = QHBoxLayout()
        top_side_layout.addWidget(self.create_focus_catch())
        top_side_layout.addWidget(self.create_username_box())
        top_side_layout.addWidget(self.create_player_select())
        top_side_layout.addWidget(self.create_resize_button())
        top_side.setLayout(top_side_layout)

        self.start_button = QPushButton('start')
        self.start_button.clicked.connect(self.main_button_clicked)

        self.gold_display = QLabel('0 gold (0/hr)')
        self.exp_display = QLabel('0 exp (0/hr)')

        bottom_side = QWidget()
        bottom_side_layout = QVBoxLayout()
        bottom_side_layout.addWidget(QLabel('Log'))
        bottom_side.setLayout(bottom_side_layout)
        self.log_layout = bottom_side_layout

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(bottom_side)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        vbar = self.scroll.verticalScrollBar()
        vbar.rangeChanged.connect(lambda: vbar.setValue(vbar.maximum()))

        layout.addWidget(top_side)
        layout.addWidget(self.start_button)
        layout.addWidget(self.gold_display)
        layout.addWidget(self.exp_display)
        # layout.addWidget(bottom_side)
        layout.addWidget(self.scroll)
        self.setLayout(layout)

    def create_focus_catch(self) -> QWidget:
        button = QPushButton()
        button.setFixedWidth(0)
        button.setFixedHeight(0)
        return button

    def create_worker(self) -> None:
        self.thread = QThread()
        self.worker = GuiWorker(self.tracker)
        # stop signal?
        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.log_event.connect(self.on_event_logged)
        self.worker.log_string.connect(self.on_string_logged)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.started.connect(self.worker.do_work)
        self.thread.finished.connect(self.worker.stop)

    def main_button_clicked(self) -> None:
        if self.worker.paused:
            self.worker.unpause()
            self.start_button.setText('pause')
        else:
            self.worker.pause()
            self.start_button.setText('unpause')

    def on_event_logged(self, e: GameEvent) -> None:
        if e.type == EventType.get_gold:
            self.update_gold_count()
        elif e.type == EventType.get_exp:
            self.update_exp_count()
        try:
            self.log_layout.addWidget(QLabel(str(e)))
        except ValueError as e:
            print(f'value error from event: {e}')

    def on_string_logged(self, s: str) -> None:
        self.log_layout.addWidget(QLabel(s));

    def update_gold_count(self) -> None:
        hours = self.worker.duration / (60 * 60)
        gold = self.tracker.gamestate.gold_count
        hourly = gold // hours
        self.gold_display.setText(f'{gold} gold ({hourly}/hr)')

    def update_exp_count(self) -> None:
        hours = self.worker.duration / (60 * 60)
        exp = self.tracker.gamestate.exp_count
        hourly = exp // hours
        self.exp_display.setText(f'{exp} exp ({hourly}/hr)')

    #
    # username input
    #

    def create_username_box(self) -> QWidget:
        self.username_editor = ClickableLineEdit()
        self.username_editor.setText('username')
        self.username_editor.textChanged.connect(self.username_changed)
        self.username_editor.clicked.connect(self.username_clicked)
        self.username_editor.setAlignment(Qt.AlignCenter)
        return self.username_editor

    def username_changed(self, s: str) -> None:
        if s in self.tracker.gamestate.players:
            del self.tracker.gamestate.players[s]
        if s != '' and s != 'username':
            self.update_player()
            self.username = s

    def username_clicked(self) -> None:
        if self.username_editor.text() == 'username':
            self.username_editor.setText('')

    #
    # player select
    #

    def create_player_select(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout()
        widget.setLayout(layout)

        self.player_options = QComboBox()
        self.player_options.addItem('-')
        rows = tracker.database.select('SELECT id, name FROM players', ())
        for row in rows:
            row = cast(Tuple[int, str], row)
            pid, name = row
            self.player_options.addItem(name)
            self.players.append((pid, name))
        self.player_options.currentIndexChanged.connect(
            self.player_name_selected
        )

        # layout.addWidget(QLabel('player: '))
        layout.addWidget(self.player_options)
        return widget

    def player_name_selected(self, i: int) -> None:
        if i == 0:
            # don't allow the default blank option
            if self.selected_player_index >= 0:
                self.player_options.setCurrentIndex(
                    self.selected_player_index + 1
                )
        elif i - 1 != self.selected_player_index:
            self.selected_player_index = i - 1
            self.update_player()

    def update_player(self) -> None:
        pid, name = self.players[self.selected_player_index]
        player = self.tracker.database.load_player(name)
        self.tracker.gamestate.players[self.username] = player

    #
    # screen selection
    #

    def create_resize_button(self) -> QWidget:
        button = QPushButton('screen region')
        button.clicked.connect(lambda: self.worker.resize_button_clicked())
        return button


if __name__ == '__main__':
    with RetroTracker() as tracker:
        app = QApplication([])
        window = GuiTracker(tracker)
        window.show()
        app.exec()
