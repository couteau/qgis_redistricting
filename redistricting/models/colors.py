from qgis.core import QgsCategorizedSymbolRenderer
from qgis.PyQt.QtGui import (
    QColor,
    QPalette
)

from .plan import RdsPlan


def getColorForDistrict(plan: RdsPlan, district: int):
    renderer = plan.assignLayer.renderer()
    if isinstance(renderer, QgsCategorizedSymbolRenderer):
        idx = renderer.categoryIndexForValue(district)
        if idx == -1:
            idx = 0

        cat = renderer.categories()[idx]
        return QColor(cat.symbol().color())

    return QColor(QPalette().color(QPalette.Normal, QPalette.Window))
