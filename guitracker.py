#!/usr/bin/env python3
from typing import (
    cast,
    Any,
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
import logging
import datetime

from event import GameEvent, EventType
from retrotracker import RetroTracker


class GuiWorker(QObject):

    finished = pyqtSignal()
    log_event = pyqtSignal(GameEvent)
    log_string = pyqtSignal(str)
    log_tick = pyqtSignal()

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
                self.log_tick.emit()
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


#
# custom widgets
#


class ClickableLineEdit(QLineEdit):

    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        QLineEdit.mousePressEvent(self, event)


class PlayerSelect(QWidget):

    username_changed = pyqtSignal(int, str)
    class_changed = pyqtSignal(int, str)

    def __init__(
        self,
        player_index: int,
        class_options: List[str],
    ) -> None:
        super().__init__()
        self.player_index = player_index
        self.class_names = list(class_options)
        self.username = ''

        self.username_editor = ClickableLineEdit()
        self.username_editor.setText('username')
        self.username_editor.setAlignment(Qt.AlignCenter) # type: ignore
        self.username_editor.textChanged.connect(self.on_username_changed) # type: ignore
        self.username_editor.clicked.connect(self.on_username_clicked)

        self.class_index = 0
        self.class_options = QComboBox()
        self.class_options.addItem('-')
        self.players: List[Tuple[int, str]] = []
        for pid, name in enumerate(class_options):
            self.class_options.addItem(name)
            self.players.append((pid, name))
        self.class_options.currentIndexChanged.connect(self.on_class_selected) # type: ignore

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.username_editor)
        layout.addWidget(self.class_options)
        self.setLayout(layout)

    @property
    def selected_class(self) -> str:
        return self.class_names[self.class_index]

    def on_username_changed(self, s: str) -> None:
        """called any time username text box changes"""
        if s != '' and s != 'username':
            self.username = s
            self.username_changed.emit(
                self.player_index,
                self.username,
            )

    def on_username_clicked(self) -> None:
        """called when username text box clicked, clears placeholder"""
        if self.username_editor.text() == 'username':
            self.username_editor.setText('')

    def on_class_selected(self, i: int) -> None:
        """called when a class is chosen from drop down"""
        if i == 0:
            if self.class_index > 0:
                # don't allow selection
                self.class_options.setCurrentIndex(self.class_index + 1)
            return

        class_index = i - 1
        if class_index != self.class_index:
            self.class_index = class_index
            self.class_changed.emit(
                self.player_index,
                self.selected_class,
            )


class PartyMenu(QWidget):

    players_changed = pyqtSignal(list)

    def __init__(
        self,
        tracker: RetroTracker,
    ) -> None:
        super().__init__()
        class_options: List[str] = [
            r[0] for r in
            tracker.database.select('SELECT name FROM players', ())
        ]
        self.players: List[List[str]] = [
            ['', ''],
            ['', ''],
            ['', ''],
        ]

        layout = QVBoxLayout()
        # layout.setSpacing(0)
        # layout.setContentsMargins(0, 0, 0, 0)
        for i in range(3):
            player_select = PlayerSelect(i, class_options)
            player_select.username_changed.connect(self.username_changed)
            player_select.class_changed.connect(self.class_changed)
            layout.addWidget(player_select)
        self.setLayout(layout)

    def username_changed(self, i: int, username: str) -> None:
        self.players[i][0] = username
        self.players_changed.emit(self.players)

    def class_changed(self, i: int, classname: str) -> None:
        self.players[i][1] = classname
        self.players_changed.emit(self.players)


#
# main application widget
#


class GuiTracker(QWidget):

    def __init__(
        self,
        tracker: RetroTracker,
    ) -> None:
        super().__init__()
        self.tracker = tracker

        # ignore some warnings because value is set in create_ui
        self.log_layout: QVBoxLayout = None    # type: ignore
        self.exp_display: QLabel = None        # type: ignore
        self.gold_display: QLabel = None       # type: ignore
        self.time_display: QLabel = None       # type: ignore

        self.setWindowTitle('RetroTracker')
        self.create_worker()
        self.create_ui()
        self.worker_thread.start()

    #
    # ui creation
    #

    def create_ui(self) -> None:
        layout = QVBoxLayout()
        layout.addWidget(self.create_focus_catch())
        layout.addWidget(self.create_party_menu())
        layout.addWidget(self.create_buttons())
        layout.addWidget(self.create_stats())
        layout.addWidget(self.create_log())
        self.setLayout(layout)

    def create_focus_catch(self) -> QWidget:
        button = QPushButton()
        button.setFixedWidth(0)
        button.setFixedHeight(0)
        return button

    def create_party_menu(self) -> QWidget:
        menu = PartyMenu(self.tracker)
        menu.players_changed.connect(self.on_players_changed)
        return menu

    def create_buttons(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout()

        # screen area selection
        button = QPushButton('set screen region')
        button.clicked.connect(lambda: self.worker.resize_button_clicked()) # type: ignore
        layout.addWidget(button)

        # start / pause / unpause
        self.start_button = QPushButton('start')
        self.start_button.clicked.connect(self.main_button_clicked) # type: ignore
        layout.addWidget(self.start_button)

        # reset timer
        reset_button = QPushButton('reset')
        reset_button.clicked.connect(self.reset_button_clicked) # type: ignore
        layout.addWidget(reset_button)

        widget.setLayout(layout)
        return widget

    def create_stats(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        self.time_display = QLabel('0:00:00')
        self.gold_display = QLabel('0 gold (0/hr)')
        self.exp_display = QLabel('0 exp (0/hr)')

        layout.addWidget(self.time_display)
        layout.addWidget(self.gold_display)
        layout.addWidget(self.exp_display)

        widget.setLayout(layout)
        return widget

    def create_log(self) -> QWidget:
        widget = QWidget()
        self.log_layout = QVBoxLayout()
        self.log_layout.addWidget(QLabel('event log'))
        widget.setLayout(self.log_layout)

        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # type: ignore
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # type: ignore

        # keep scroll at the bottom
        vbar = scroll.verticalScrollBar()
        vbar.rangeChanged.connect(lambda: vbar.setValue(vbar.maximum())) # type: ignore

        # self.log_layout.addWidget(scroll)
        return scroll

    #
    # ui callbacks
    #

    def main_button_clicked(self) -> None:
        if self.worker.paused:
            self.worker.unpause()
            self.start_button.setText('pause')
        else:
            self.worker.pause()
            self.start_button.setText('unpause')

    def reset_button_clicked(self) -> None:
        self.tracker.gamestate.gold_count = 0
        self.tracker.gamestate.exp_count = 0
        self.worker.duration = 0

    def on_players_changed(self, players: List[List[str]]) -> None:
        self.tracker.gamestate.players = {}
        for player in players:
            if len(player) != 2:
                logging.error('invalid player options: {player}')
                continue

            username, classname = player
            if username == '' or classname == '':
                # less than full party
                continue

            if self.tracker.database.player_exists(classname):
                player = self.tracker.database.load_player(classname)
                self.tracker.gamestate.players[username] = player

    #
    # worker
    #

    def create_worker(self) -> None:
        self.worker_thread = QThread()
        self.worker = GuiWorker(self.tracker)
        # stop signal?
        self.worker.moveToThread(self.worker_thread)
        self.worker.finished.connect(self.worker_thread.quit)        # type: ignore
        self.worker.finished.connect(self.worker.deleteLater) # type: ignore
        self.worker.log_event.connect(self.on_event_logged)   # type: ignore
        self.worker.log_string.connect(self.on_string_logged) # type: ignore
        self.worker.log_tick.connect(self.update_timer)       # type: ignore
        self.worker_thread.finished.connect(self.worker_thread.deleteLater) # type: ignore

        self.worker_thread.started.connect(self.worker.do_work) # type: ignore
        self.worker_thread.finished.connect(self.worker.stop)   # type: ignore

    #
    # worker callbacks
    #

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

    def update_timer(self) -> None:
        total_time = self.worker.duration
        td = datetime.timedelta(seconds=total_time)
        self.time_display.setText(str(td).split('.')[0])


if __name__ == '__main__':
    with RetroTracker() as tracker:
        app = QApplication([])
        window = GuiTracker(tracker)
        window.show()
        app.exec()
