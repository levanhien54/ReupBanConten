"""
UI Utilities — Multithreading workers.
"""
from __future__ import annotations

import sys
import traceback
import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class _QLogSignal(QObject):
    log_msg = Signal(str)

class QLogHandler(logging.Handler):
    """
    Custom Logging Handler để gửi log từ backend lên PySide6 UI thông qua Signal.
    """
    def __init__(self) -> None:
        super().__init__()
        self.emitter = _QLogSignal()
        self.log_signal = self.emitter.log_msg
        
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.emitter.log_msg.emit(msg)


class WorkerSignals(QObject):
    """
    Khai báo các signals cho Worker.
    """
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(str)


class Worker(QRunnable):
    """
    Worker cho background thread.
    Đảm bảo UI không bị đơ khi chạy các tác vụ nặng (scan, download...).
    """

    def __init__(self, fn: Callable, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        """Thực thi function trong background thread."""
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()
            exctype, value = sys.exc_info()
            # Gửi tuple lỗi qua signal
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            # Gửi kết quả thành công qua signal
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
