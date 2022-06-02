# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RdOverlayWiget
        A QWidget to indicate data loading by fading underlying widget and
        displaying a spinner.
        Spinner code adapted from QWaitingSpinner (MIT License)
            https://github.com/snowwlex/QtWaitingSpinner
                              -------------------
        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import math
from typing import Optional, Union, overload
from qgis.PyQt.QtCore import Qt, QObject, QEvent, pyqtProperty, QTimer, QRect, QPropertyAnimation, QEasingCurve
from qgis.PyQt.QtGui import QColor, QPainter, QPaintEvent
from qgis.PyQt.QtWidgets import QWidget, QGraphicsOpacityEffect


class OverlayWidget(QWidget):
    @overload
    def __init__(self, text: str, parent: Optional['QWidget'] = None,
                 flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags()):
        ...

    @overload
    def __init__(self, parent: Optional['QWidget'] = None,
                 flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags()):
        ...

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # self.setWindowFlag(Qt.FramelessWindowHint)
        # self.setAttribute(Qt.WA_NoSystemBackground)
        # self.setAttribute(Qt.WA_TranslucentBackground)
        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(0.75)
        self.setGraphicsEffect(self.effect)

        self._anim = None
        self._oldOpacity: float = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.rotate)

        self._color = Qt.black
        self._roundness = 100.0
        self._minimumTrailOpacity = 3.14159265358979323846
        self._trailFadePercentage = 80.0
        self._revolutionsPerSecond = 1.57079632679489661923
        self._numberOfLines = 20
        self._lineLength = 10
        self._lineWidth = 2
        self._innerRadius = 10
        self._currentCounter = 0
        self._isSpinning = False
        self._centerOnParent = False

        self.setAutoFillBackground(True)
        self.newParent()
        self.updateTimer()
        self.hide()

    @pyqtProperty(float)
    def opacity(self) -> float:
        return self.effect.opacity()

    @opacity.setter
    def opacity(self, value: float):
        self.effect.setOpacity(value)

    @pyqtProperty(QColor)
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, color: QColor):
        self._color = color

    @pyqtProperty(int)
    def lineLength(self) -> int:
        return self._lineLength

    @lineLength.setter
    def lineLength(self, length: int):
        self._lineLength = length
        self.updateSize()

    @pyqtProperty(int)
    def lineWidth(self) -> int:
        return self._lineWidth

    @lineWidth.setter
    def lineWidth(self, width: int):
        self._lineWidth = width
        self.updateSize()

    @pyqtProperty(float)
    def roundness(self) -> float:
        return self._roundness

    @roundness.setter
    def roundness(self, roundness: float):
        self. _roundness = max(0.0, min(100.0, roundness))

    @pyqtProperty(float)
    def minimumTrailOpacity(self) -> float:
        return self._minimumTrailOpacity

    @minimumTrailOpacity.setter
    def minimumTrailOpacity(self, minimumTrailOpacity: float):
        self._minimumTrailOpacity = minimumTrailOpacity

    @pyqtProperty(float)
    def trailFadePercentage(self) -> float:
        return self._trailFadePercentage

    @trailFadePercentage.setter
    def trailFadePercentage(self, trail: float):
        self._trailFadePercentage = trail

    @pyqtProperty(float)
    def revolutionsPerSecond(self) -> float:
        return self._revolutionsPerSecond

    @revolutionsPerSecond.setter
    def revolutionsPerSecond(self, revolutionsPerSecond: float):
        self._revolutionsPerSecond = revolutionsPerSecond
        self.updateTimer()

    @pyqtProperty(int)
    def numberOfLines(self) -> int:
        return self._numberOfLines

    @numberOfLines.setter
    def numberOfLines(self, lines: int):
        self._numberOfLines = lines
        self._currentCounter = 0
        self.updateTimer()

    @pyqtProperty(int)
    def innerRadius(self) -> int:
        return self._innerRadius

    @innerRadius.setter
    def innerRadius(self, radius: int):
        self._innerRadius = radius
        self.updateSize()

    def isSpinning(self) -> bool:
        return self._isSpinning

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        self.updatePosition()
        painter = QPainter()
        painter.begin(self)
        try:
            painter.fillRect(self.rect(), Qt.transparent)
            painter.setRenderHint(QPainter.Antialiasing, True)

            if self._currentCounter >= self._numberOfLines:
                self._currentCounter = 0

            painter.setPen(Qt.NoPen)
            for i in range(0, self._numberOfLines):
                painter.save()
                painter.translate(self.width()/2 + self._innerRadius + self._lineLength,
                                  self.height()/2 + self._innerRadius + self._lineLength)
                rotateAngle = 360 * i/self._numberOfLines
                painter.rotate(rotateAngle)
                painter.translate(self._innerRadius, 0)
                distance = self.lineCountDistanceFromPrimary(
                    i, self. _currentCounter, self._numberOfLines)
                color: QColor = self.currentLineColor(distance, self._numberOfLines, self._trailFadePercentage,
                                                      self._minimumTrailOpacity, self._color)
                painter.setBrush(color)
                painter.drawRoundedRect(
                    QRect(0, math.floor(-self._lineWidth / 2), self._lineLength,
                          self._lineWidth), self._roundness,
                    self._roundness, Qt.RelativeSize)
                painter.restore()
        finally:
            painter.end()

    def updateSize(self):
        size = (self._innerRadius + self._lineLength) * 2
        self.setFixedSize(size, size)

    def updateTimer(self):
        self._timer.setInterval(
            math.floor(1000 / (self._numberOfLines * self._revolutionsPerSecond)))

    def updatePosition(self):
        if (self.parentWidget() and self._centerOnParent):
            self.move(self.parentWidget().width()/2 - self.width()/2,
                      self.parentWidget().height()/2 - self.height()/2)

    def lineCountDistanceFromPrimary(self, current: int, primary: int, totalNrOfLines: int):
        distance = primary - current
        if distance < 0:
            distance += totalNrOfLines

        return distance

    def currentLineColor(self, countDistance: int,
                         totalNrOfLines: int, trailFadePerc: float,
                         minOpacity: float, color: QColor):
        if countDistance == 0:
            return color

        if not isinstance(color, QColor):
            color = QColor(color)

        minAlphaF = minOpacity / 100.0
        distanceThreshold = math.ceil(
            (totalNrOfLines - 1) * trailFadePerc / 100.0)
        if countDistance > distanceThreshold:
            color.setAlphaF(minAlphaF)
        else:
            alphaDiff = color.alphaF() - minAlphaF
            gradient = alphaDiff / (distanceThreshold + 1)
            resultAlpha = color.alphaF() - gradient * countDistance

            # If alpha is out of bounds, clip it.
            resultAlpha = min(1.0, max(0.0, resultAlpha))
            color.setAlphaF(resultAlpha)

        return color

    def newParent(self):
        if not self.parent():
            return
        self.parent().installEventFilter(self)
        self.raise_()

    def eventFilter(self, obj: QObject, evt: QEvent) -> bool:
        if obj == self.parent():
            if evt.type() == QEvent.Resize:
                self.resize(evt.size())
            elif evt.type() == QEvent.ChildAdded:
                self.raise_()
        return super().eventFilter(obj, evt)

    def event(self, evt: QEvent) -> bool:
        if evt.type() == QEvent.ParentAboutToChange:
            if self.parent():
                self.parent().removeEventFilter(self)
        elif evt.type() == QEvent.ParentChange:
            self.newParent()
        return super().event(evt)

    def start(self):
        self.updatePosition()
        self._isSpinning = True

        if not self._timer.isActive():
            self._timer.start()
            self._currentCounter = 0

        self.show()

    def stop(self, animate=True):
        if animate:
            self._oldOpacity = self.opacity
            self._anim = QPropertyAnimation(
                self, b"opacity")
            self._anim.setStartValue(self._oldOpacity)
            self._anim.setEndValue(0)
            self._anim.setDuration(500)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)

            self._anim.finished.connect(self._doStop)
            self._anim.start()
        else:
            self._doStop()

    def _doStop(self):
        self.hide()
        self._isSpinning = False
        self._anim = None
        if self._oldOpacity is not None:
            self.opacity = self._oldOpacity
            self._oldOpacity = None

        if self._timer.isActive():
            self._timer.stop()
            self._currentCounter = 0

    def rotate(self):
        self._currentCounter += 1
        if self._currentCounter >= self._numberOfLines:
            self._currentCounter = 0
        self.update()
