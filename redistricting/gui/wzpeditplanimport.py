# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin New/Edit Plan Wizard - Import Page

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful, but   *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the          *
 *   GNU General Public License for more details. You should have          *
 *   received a copy of the GNU General Public License along with this     *
 *   program. If not, see <http://www.gnu.org/licenses/>.                  *
 *                                                                         *
 ***************************************************************************/
"""
import csv
import os
from io import IOBase
from itertools import islice
from typing import (
    Iterable,
    Union
)

from osgeo import gdal
from qgis.core import QgsVectorLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QLabel,
    QTableWidgetItem,
    QWizardPage
)

from .ui.WzpEditPlanImportPage import Ui_wzpImport


class dlgEditPlanImportPage(Ui_wzpImport, QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.registerField('importPath', self.fileImportFrom,
                           'path', self.fileImportFrom.fileChanged)
        self.registerField('importField', self.cmbJoinField)
        self.registerField('headerRow', self.cbxHeaderRow)
        self.registerField('geoCol', self.sbxGeographyCol)
        self.registerField('distCol', self.sbxDistrictCol)
        self.registerField('delimiter', delim := QLabel(self), 'text')
        self.registerField('quote',  quote := QLabel(self), 'text')
        delim.setVisible(False)
        quote.setVisible(False)

        self.fileImportFrom.fileChanged.connect(self.fileChanged)

        self.rbComma.toggled.connect(self.updateDelimiter)
        self.rbTab.toggled.connect(self.updateDelimiter)
        self.rbOther.toggled.connect(self.updateDelimiter)

        self.rbDoubleQuote.toggled.connect(self.updateQuote)
        self.rbSingleQuote.toggled.connect(self.updateQuote)
        self.rbOtherQuote.toggled.connect(self.updateQuote)

        self.cbxHeaderRow.toggled.connect(self.updatePreview)

        self.edOther.textChanged.connect(self.updatePreview)
        self.edOtherQuote.textChanged.connect(self.updatePreview)

        self.cmbGeographyCol.currentIndexChanged.connect(self.updateFields)
        self.cmbDistrictCol.currentIndexChanged.connect(self.updateFields)

        self.cmbGeographyCol.setVisible(False)
        self.cmbDistrictCol.setVisible(False)
        self.useFieldNames = False

        flt = '*.csv;*.txt;*.xls;*.xlsx;*.xlsm;*.ods'
        self.fileImportFrom.setFilter(flt)

        self.setFinalPage(True)

    def initializePage(self):
        super().initializePage()
        self.blockSignals(True)
        self.cmbJoinField.setLayer(self.field('sourceLayer'))
        self.cmbJoinField.setField(self.field('geoIdField'))
        self.updateDelimiter()
        self.updateQuote()
        self.blockSignals(False)

    @property
    def delimiter(self):
        return ',' if self.rbComma.isChecked() else \
            '\t' if self.rbTab.isChecked() else \
            ' ' if self.rbSpace.isChecked() else \
            self.edOther.text() if self.edOther.text() else ','

    @property
    def quotechar(self):
        return '"' if self.rbDoubleQuote.isChecked() else \
            '\'' if self.rbSingleQuote.isChecked() else \
            self.edOtherQuote.text() if self.edOtherQuote.text() else '"'

    @property
    def headerRow(self):
        return self.cbxHeaderRow.isChecked()

    @property
    def importPath(self):
        return self.fileImportFrom.path

    @property
    def joinField(self):
        return self.cmbJoinField.field

    @property
    def geoColumn(self):
        return self.cmbGeographyCol.currentIndex() if self.useFieldNames else (self.sbxGeographyCol.value() - 1)

    @property
    def distColumn(self):
        return self.cmbDistrictCol.currentIndex() if self.useFieldNames else (self.sbxDistrictCol.value() - 1)

    def updateDelimiter(self):
        self.setField('delimiter', self.delimiter)
        self.updatePreview()

    def updateQuote(self):
        self.setField('quote', self.quotechar)
        self.updatePreview()

    def updateFields(self):
        self.setField('geoCol', self.cmbGeographyCol.currentIndex() + 1)
        self.setField('distCol', self.cmbDistrictCol.currentIndex() + 1)

    def updatePreview(self):
        if self.signalsBlocked():
            return

        if not os.path.exists(self.fileImportFrom.path):
            self.gbPreview.setVisible(False)
            self.cmbGeographyCol.clear()
            self.cmbDistrictCol.clear()
            return

        _, ext = os.path.splitext(self.fileImportFrom.path)

        if ext in ('.xls', '.xlsx', '.xlsm', '.ods'):
            self.updatePreviewExcel(ext)
        else:
            self.updatePreviewCsv()

    def updateWidgets(self, fields: Union[Iterable[str], int] = 2):
        self.useFieldNames = isinstance(fields, Iterable)
        if self.useFieldNames:
            self.cmbGeographyCol.setVisible(True)
            self.cmbGeographyCol.clear()
            self.cmbGeographyCol.addItems(fields)
            self.cmbGeographyCol.setCurrentIndex(0)
            self.cmbDistrictCol.setVisible(True)
            self.cmbDistrictCol.clear()
            self.cmbDistrictCol.addItems(fields)
            self.cmbDistrictCol.setCurrentIndex(1)
            self.sbxDistrictCol.setVisible(False)
            self.sbxGeographyCol.setVisible(False)
        else:
            self.cmbGeographyCol.setVisible(False)
            self.cmbDistrictCol.setVisible(False)
            self.sbxDistrictCol.setVisible(True)
            self.sbxGeographyCol.setVisible(True)
            self.sbxGeographyCol.setMaximum(fields)
            self.sbxDistrictCol.setMaximum(fields)

    def updatePreviewCsv(self, csvfile=None, header=None, dialect=None):
        close = not isinstance(csvfile, IOBase)
        if close:
            csvfile = open(  # pylint: disable=unspecified-encoding,consider-using-with
                self.fileImportFrom.path,
                newline=''
            )
        try:
            if header is None:
                header = self.cbxHeaderRow.isChecked()

            if dialect is None:
                dialect = csv.Sniffer().sniff('"",""')
                dialect.delimiter = self.delimiter
                dialect.quotechar = self.quotechar
                dialect.skipinitialspace = True

            reader = csv.reader(csvfile, dialect=dialect)
            fields = next(reader)
            self.tbPreview.setColumnCount(len(fields))
            self.tbPreview.setRowCount(2)
            if header:
                self.tbPreview.setHorizontalHeaderLabels(fields)
            else:
                self.tbPreview.setHorizontalHeaderLabels(
                    (str(n+1) for n in range(0, len(fields))))
                csvfile.seek(0)  # rewind the file

            for i in range(0, len(fields)):
                self.tbPreview.horizontalHeaderItem(
                    i).setTextAlignment(Qt.AlignLeft)

            for row, line in enumerate(islice(reader, 0, 2)):
                for k, v in enumerate(line):
                    self.tbPreview.setItem(row, k, QTableWidgetItem(str(v)))

            self.updateWidgets(fields if header else len(fields))
            self.gbPreview.setVisible(True)
        finally:
            if close:
                csvfile.close()

    def updatePreviewExcel(self, ext):
        headerConfigKey = 'OGR_XLS_HEADERS' if ext == '.xls' \
            else 'OGR_XLSX_HEADERS' if ext in ('.xlsx', '.xlsm') \
            else 'OGR_ODS_HEADERS'
        oldHeaders = gdal.GetConfigOption(headerConfigKey)
        try:
            gdal.SetConfigOption(
                headerConfigKey, 'FORCE' if self.cbxHeaderRow.isChecked() else 'DISABLE')
            l = QgsVectorLayer(self.fileImportFrom.path, '__import', 'ogr')
            if l.isValid():
                fields = [f.name() for f in l.fields()]
                self.updateWidgets(
                    fields if self.cbxHeaderRow.isChecked() else len(fields))
                self.tbPreview.setColumnCount(len(fields))
                self.tbPreview.setHorizontalHeaderLabels(fields)
                self.tbPreview.setRowCount(2)
                for i in range(0, len(fields)):
                    self.tbPreview.horizontalHeaderItem(
                        i).setTextAlignment(Qt.AlignLeft)

                i = l.getFeatures()
                for n in range(0, min(2, l.featureCount())):
                    f = next(i)
                    for k, v in enumerate(f.attributes()):
                        self.tbPreview.setItem(n, k, QTableWidgetItem(str(v)))
        finally:
            gdal.SetConfigOption(headerConfigKey, oldHeaders)

    def fileChanged(self):
        if not os.path.exists(self.fileImportFrom.path):
            self.gbPreview.setVisible(False)
            self.cmbGeographyCol.clear()
            self.cmbDistrictCol.clear()
            return

        _, ext = os.path.splitext(self.fileImportFrom.path)
        if ext in ('.xls', '.xlsx', '.xlsm', '.ods'):
            self.updatePreviewExcel(ext)
            self.gbDelimiter.setEnabled(False)
            self.gbQuote.setEnabled(False)
            return

        with open(self.fileImportFrom.path, newline='', encoding="utf-8-sig") as csvfile:  # pylint: disable=unspecified-encoding,consider-using-with
            sample = csvfile.read(1024)
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample)
            dialect.skipinitialspace = True

            header = sniffer.has_header(sample)

            self.blockSignals(True)
            self.cbxHeaderRow.setChecked(header)

            if dialect.delimiter == ',':
                self.rbComma.setChecked(True)
            elif dialect.delimiter == '\t':
                self.rbTab.setChecked(True)
            elif dialect.delimiter == ' ':
                self.rbSpace.setChecked(True)
            else:
                self.rbOther.setChecked(True)
                self.edOther.setText(dialect.delimiter)

            if dialect.quotechar == '"':
                self.rbDoubleQuote.setChecked(True)
            elif dialect.quotechar == '\'':
                self.rbSingleQuote.setChecked(True)
            else:
                self.rbOtherQuote.setChecked(True)
                self.edOtherQuote.setText(dialect.quotechar)
            self.blockSignals(False)

            csvfile.seek(0)
            self.updatePreviewCsv(csvfile, header, dialect)
            self.gbDelimiter.setEnabled(True)
            self.gbQuote.setEnabled(True)
