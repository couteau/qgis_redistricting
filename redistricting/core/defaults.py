# -*- coding: utf-8 -*-
"""QGIS Reidstricting Plugin - constants and default values

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
import re
from .Utils import tr

POP_FIELDS = ['pop_total', 'p0010001']
VAP_FIELDS = ['vap_total', 'p0030001']
CVAP_FIELDS = ['cvap_total', re.compile(r'^cvap_(?:\d{4}_)total$')]

GEOID_FIELDS = ['geoid20', 'geoid30', 'geoid10', 'geoid', 'block', 'block_id']

GEOID_LABELS = [
    tr('Block'),
    tr('Block Group'),
    tr('Tract'),
    tr('Precinct/VTD'),
    tr('County/Parish'),
]
