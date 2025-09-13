Getting Started with Redistricting
==================================

The QGIS Redistricting plugin allows you to create redistricting plans for
legislative and other governmental bodies. You specify the number of
districts and the geographic units from which plans will be built, as well as
other plan parameters, such as what layer and attributes to use for population
demographics, the allowable population deviation, and additional geographies
to use for drawing districts. Plan parameters are stored as part of the QGIS
project, while assignments of geographies to districts and district geometry
and metrics are stored as vector layers in a GeoPackage file.

Plugin Toolbar
--------------

When you install the QGIS redistricting plugin, it will add the redistricting
toolbar to the QGIS main window.

.. image:: /images/plugin_toolbar.png

All of the QGIS redistricting plugin functions available form the plugin
toolbar can also be accessed from the QGIS main menu at
:menuselection:`Vector --> Redistricting`.

..  |planmgr| image:: /images/icon.svg
    :height: 32px
    :width: 32px
    :align: top

..  |toolbox| image:: /images/paintdistricts.svg
    :height: 32px
    :width: 32px
    :align: top

..  |preview| image:: /images/preview.svg
    :height: 32px
    :width: 32px
    :align: top

..  |datatbl| image:: /images/district_data.svg
    :height: 32px
    :width: 32px
    :align: top

..  |metrics| image:: /images/planmetrics.svg
    :height: 32px
    :width: 32px
    :align: top

..  |button| image:: /images/menu_button.png
    :height: 32px
    :width: 40px
    :align: top

..  |menu| image:: /images/plugin_menu.png
    :scale: 50%

..  table::
    :widths: 25 125
    :align: left
    :class: help-table

    ========= =========================================================================
    |planmgr| Display the plan manager.
    |toolbox| Display or hide the redistricting toolbox. The toolbox provides
              access to tools for painting districts by geography.
    |preview| Display or hide the the preview window. The preview window displays
              the effect on district demographics of pending unsaved changes.
    |datatbl| Display or hide the the district data window. The district data
              window displays demographic data and metrics for each district,
              and indicates whether districts are within the required deviation.
    |metrics| Display or hide the metrics window. The metrics window displays plan
              metrics for the entire plan, including population deviation, compactness,
              and split geographies.
    |button|  Clicking the arrow next to the plan manager button opens the
              redistricting menu, which provides access to additional plugin
              functionality.

              |menu|
    ========= =========================================================================



