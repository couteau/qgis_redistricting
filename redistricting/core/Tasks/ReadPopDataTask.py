from typing import TYPE_CHECKING

from qgis.core import (
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsTask
)

if TYPE_CHECKING:
    from ..Plan import RedistrictingPlan

from ..Exception import CancelledError
from ..layer import RdsLayerUtilities


class LoadPopulationDataTask(QgsTask):
    def __init__(self, plan: "RedistrictingPlan", description: str = '', flags: QgsTask.Flags | QgsTask.Flag = QgsTask.Flag.AllFlags):
        super().__init__(description, flags)
        self._plan = plan
        self.data = None
        self.exception = None

    def run(self):
        try:
            utils = RdsLayerUtilities(self._plan.popLayer)

            cols = [self._plan.popJoinField, self._plan.popField]
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
            for f in self.popFields:
                if f.isExpression:
                    expr = QgsExpression(f.field)
                    expr.prepare(context)
                    cols += expr.referencedColumns()
                else:
                    cols.append(f.field)

            for f in self._plan.dataFields:
                if f.isExpression:
                    expr = QgsExpression(f.field)
                    expr.prepare(context)
                    cols += expr.referencedColumns()
                else:
                    cols.append(f.field)

            fc = self._plan.popLayer.featureCount()
            chunksize = fc // 9 if fc % 10 != 0 else fc // 10  # we want 10 full or partial chunks
            df = utils.read_layer(columns=cols, order=self._plan.popJoinField,
                                  read_geometry=False, chunksize=chunksize)
            for f in self._plan.popFields:
                if f.isExpression:
                    df[f.fieldName] = df.query(f.field)
            for f in self._plan.dataFields:
                if f.isExpression:
                    df[f.fieldName] = df.query(f.field)

            self.data = df
        except CancelledError:
            self.cancel()
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        return True
