from typing import Iterable

import pandas as pd

from ..models import District
from ..utils import tr


class DistrictClipboardAccess:
    def getSelectionData(self, districts: Iterable[District], selection: Iterable[tuple[int, int]]) -> pd.DataFrame:
        if len(districts) == 0:
            return pd.DataFrame()

        data: dict[str, list] = {}
        index = []
        for y, d in enumerate(districts):
            index.append(y)
            for c in d.columns:
                if c not in data:
                    data[c] = []
                data[c].append(d[c])
        df = pd.DataFrame(data=data, index=index)

        if selection is not None:
            # create a dataframe of bools with the same dimensions as data
            s = (df != df).fillna(False)
            # set elements to True if in selection
            for row, col in selection:
                s.iloc[row, col] = True
            # select the elements of data that are contained in selection
            df = df[s]

            # drop the unselected rows and columns
            df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")

        df.columns.name = tr("District")
        return df

    def getAsHtml(self, districts: Iterable[District], selection: Iterable[tuple[int, int]]) -> str:
        return self.getSelectionData(districts, selection).style.to_html()

    def getAsCsv(self, districts: Iterable[District], selection: Iterable[tuple[int, int]]) -> str:
        return self.getSelectionData(districts, selection).to_csv()
