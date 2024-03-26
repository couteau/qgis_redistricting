from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)


class Feedback(QObject):
    canceled = pyqtSignal()

    def setValue(self, progress: int):
        pass
