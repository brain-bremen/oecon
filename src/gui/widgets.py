from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView,
)


class ListEditor(QWidget):
    """Editable list[str] — one entry per line. Empty text → None."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QTextEdit()
        self._edit.setFixedHeight(80)
        self._edit.setPlaceholderText("One entry per line (empty = include all)")
        layout.addWidget(self._edit)

    def get_value(self) -> list[str] | None:
        text = self._edit.toPlainText().strip()
        if not text:
            return None
        return [line for line in text.splitlines() if line.strip()]

    def set_value(self, value: list[str] | None) -> None:
        self._edit.setPlainText("\n".join(value) if value else "")


class DictEditor(QWidget):
    """Editable dict[str, int] — a table with Key and Value columns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Key", "Value"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setFixedHeight(120)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.clicked.connect(self._add_row)
        remove_btn = QPushButton("−")
        remove_btn.setFixedWidth(30)
        remove_btn.clicked.connect(self._remove_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(""))
        self._table.setItem(row, 1, QTableWidgetItem("0"))

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)

    def get_value(self) -> dict[str, int] | None:
        result: dict[str, int] = {}
        for row in range(self._table.rowCount()):
            key_item = self._table.item(row, 0)
            val_item = self._table.item(row, 1)
            if key_item and val_item:
                key = key_item.text().strip()
                if key:
                    try:
                        result[key] = int(val_item.text())
                    except ValueError:
                        pass
        return result if result else None

    def set_value(self, value: dict[str, int] | None) -> None:
        self._table.setRowCount(0)
        if not value:
            return
        for key, val in value.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(key)))
            self._table.setItem(row, 1, QTableWidgetItem(str(val)))
