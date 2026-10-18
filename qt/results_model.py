# Created By: Virgil Dupras
# Created On: 2009-04-23
# Copyright 2015 Hardcoded Software (http://www.hardcoded.net)
#
# This software is licensed under the "GPLv3" License as described in the "LICENSE" file,
# which should be included with this package. The terms are also available at
# http://www.gnu.org/licenses/gpl-3.0.html

from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPalette
from PyQt6.QtWidgets import QTableView

from qt.table import Table

# Per-group row colors: every member of a group gets one color, and successive groups cycle
# through the palette so adjacent groups are clearly distinct. Two palettes, one per theme, each
# tuned so the table's text keeps a comfortable contrast ratio (>= WCAG AA 4.5:1 for the default
# text color): pale tints for light mode (dark text), deep tones for dark mode (white text). The
# hues are kept distinct from each other so neighbouring groups never look alike.
GROUP_COLORS_LIGHT = [
    QColor(0xFB, 0xD4, 0xD4),  # red
    QColor(0xD4, 0xE8, 0xFB),  # blue
    QColor(0xD8, 0xF3, 0xD1),  # green
    QColor(0xFB, 0xEE, 0xC9),  # yellow
    QColor(0xEA, 0xD9, 0xF6),  # purple
    QColor(0xCB, 0xF1, 0xEE),  # teal
]
GROUP_COLORS_DARK = [
    QColor(0x5C, 0x30, 0x30),  # red
    QColor(0x26, 0x3F, 0x5C),  # blue
    QColor(0x2C, 0x50, 0x2C),  # green
    QColor(0x59, 0x4D, 0x24),  # yellow
    QColor(0x45, 0x2F, 0x5C),  # purple
    QColor(0x22, 0x55, 0x50),  # teal
]


class ResultsModel(Table):
    def __init__(self, app, view, **kwargs):
        model = app.model.result_table
        super().__init__(model, view, **kwargs)
        view.horizontalHeader().setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        font = view.font()
        font.setPointSize(app.prefs.tableFontSize)
        view.setFont(font)
        fm = QFontMetrics(font)
        view.verticalHeader().setDefaultSectionSize(fm.height() + 2)

        app.willSavePrefs.connect(self.appWillSavePrefs)
        self.prefs = app.prefs

    def _group_background(self, row):
        # Every member of a group (including its representative) shares one color; successive
        # groups cycle through the palette so adjacent groups are clearly separated. The palette
        # is picked per theme so the table text stays readable; the representative stays
        # identifiable via the bold reference font rather than a different background.
        dark = self.view.palette().color(QPalette.ColorRole.Base).lightness() < 128
        colors = GROUP_COLORS_DARK if dark else GROUP_COLORS_LIGHT
        return QBrush(colors[row.group_color_index % len(colors)])

    def _getData(self, row, column, role):
        if column.name == "marked":
            if role == Qt.ItemDataRole.BackgroundRole:
                return self._group_background(row)
            if role == Qt.ItemDataRole.CheckStateRole and row.markable:
                return Qt.CheckState.Checked if row.marked else Qt.CheckState.Unchecked
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            data = row.data_delta if self.model.delta_values else row.data
            return data[column.name]
        elif role == Qt.ItemDataRole.ForegroundRole:
            if row.isref:
                return QBrush(self.prefs.result_table_ref_foreground_color)
            elif row.is_cell_delta(column.name):
                return QBrush(self.prefs.result_table_delta_foreground_color)
        elif role == Qt.ItemDataRole.BackgroundRole:
            return self._group_background(row)
        elif role == Qt.ItemDataRole.FontRole:
            font = QFont(self.view.font())
            if self.prefs.reference_bold_font:
                font.setBold(row.isref)
            return font
        elif role == Qt.ItemDataRole.EditRole and column.name == "name":
            return row.data[column.name]
        return None

    def _getFlags(self, row, column):
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if column.name == "marked":
            if row.markable:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
        elif column.name == "name":
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def _setData(self, row, column, value, role):
        if role == Qt.ItemDataRole.CheckStateRole:
            if column.name == "marked":
                row.marked = bool(value)
                return True
        elif role == Qt.ItemDataRole.EditRole and column.name == "name":
            return self.model.rename_selected(value)
        return False

    def sort(self, column, order):
        column = self.model.COLUMNS[column]
        self.model.sort(column.name, order == Qt.SortOrder.AscendingOrder)

    # --- Properties
    @property
    def power_marker(self):
        return self.model.power_marker

    @power_marker.setter
    def power_marker(self, value):
        self.model.power_marker = value

    @property
    def delta_values(self):
        return self.model.delta_values

    @delta_values.setter
    def delta_values(self, value):
        self.model.delta_values = value

    # --- Events
    def appWillSavePrefs(self):
        self.model._columns.save_columns()

    # --- model --> view
    def invalidate_markings(self):
        # redraw view
        # HACK. this is the only way I found to update the widget without reseting everything
        self.view.scroll(0, 1)
        self.view.scroll(0, -1)


class ResultsView(QTableView):
    # --- Override
    def keyPressEvent(self, event):
        if event.text() == " ":
            self.spacePressed.emit()
            return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(QModelIndex())
        # We don't call the superclass' method because the default behavior is to rename the cell.

    # --- Signals
    spacePressed = pyqtSignal()
