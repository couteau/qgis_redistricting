from enum import Enum


class DistrictColumns(str, Enum):
    DISTRICT = "district"
    NAME = "name"
    MEMBERS = "members"
    POPULATION = "population"
    DEVIATION = "deviation"
    PCT_DEVIATION = "pct_deviation"

    def __int__(self):
        return list(self.__class__).index(self)
