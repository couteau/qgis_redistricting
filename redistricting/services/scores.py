# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - district compactness score calculations

        begin                : 2024-10-03
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
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
import math
from typing import Callable

import geopandas as gpd
import pandas as pd
from packaging import version
from qgis.core import QgsGeometry

from ..models import MetricsColumns


def PolsbyPopper(cea: gpd.GeoSeries, area: pd.Series) -> pd.Series:
    return 4 * math.pi * area / (cea.length**2)


def Reock(cea: gpd.GeoSeries, area: pd.Series) -> pd.Series:
    if version.parse(gpd.__version__) < version.parse('1.0.0'):
        return cea.apply(lambda g: g.area / QgsGeometry.fromWkt(g.wkt).minimalEnclosingCircle()[0].area())

    return area / cea.minimum_bounding_circle().area


def ConvexHull(cea: gpd.GeoSeries, area: pd.Series) -> pd.Series:
    return area / cea.convex_hull.area


MetricsFunctions: dict[str, Callable[[gpd.GeoSeries, pd.Series], pd.Series]] = {
    MetricsColumns.POLSBYPOPPER: PolsbyPopper,
    MetricsColumns.REOCK: Reock,
    MetricsColumns.CONVEXHULL: ConvexHull
}
