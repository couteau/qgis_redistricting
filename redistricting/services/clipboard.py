"""QGIS Redistricting Plugin - Utility to copy extract district data
        for copy/paste

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

from collections.abc import Iterable

import pandas as pd
from qgis.PyQt.QtCore import QAbstractTableModel, Qt
from qgis.PyQt.QtGui import QBrush

from ..models import RdsDistrictDataModel, RdsPlan
from ..utils import tr


class DistrictClipboardAccess:
    def getSelectionData(self, model: QAbstractTableModel, selection: Iterable[tuple[int, int]]) -> pd.DataFrame:
        data = {}
        index = [model.data(model.createIndex(d, 0), Qt.ItemDataRole.DisplayRole) for d in range(model.rowCount())]
        for c in range(1, model.columnCount()):
            data[model.headerData(c, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)] = [
                model.data(model.createIndex(d, c), Qt.ItemDataRole.DisplayRole) for d in range(model.rowCount())
            ]
        selectionData = pd.DataFrame(data=data, index=index).fillna("")

        if selection is not None:
            # create a dataframe of bools with the same dimensions as data
            s = (selectionData != selectionData).fillna(False)  # noqa: PLR0124
            # set elements to True if in selection
            for row, col in selection:
                s.iloc[row, col] = True
            # select the elements of data that are contained in selection
            selectionData = selectionData[s]

            # drop the unselected rows and columns
            selectionData = selectionData.dropna(axis=0, how="all").dropna(axis=1, how="all")

        selectionData.columns.name = tr("District")
        return selectionData

    def getAsHtml(self, plan: RdsPlan, selection: Iterable[tuple[int, int]]) -> str:
        def colorRowHeader(row):
            r = 0 if row == tr("Unassigned") else selectionData.index.get_loc(row)
            clr: QBrush = model.data(model.index(r, 0), Qt.ItemDataRole.BackgroundRole)
            return f"background-color: #{clr.color().rgb() & 0xFFFFFF:x};"

        model = RdsDistrictDataModel(plan)
        selectionData = self.getSelectionData(model, selection)
        return selectionData.style.map_index(colorRowHeader).to_html(doctype_html=True)

    def getAsCsv(self, plan: RdsPlan, selection: Iterable[tuple[int, int]]) -> str:
        model = RdsDistrictDataModel(plan)
        return self.getSelectionData(model, selection).to_csv()
