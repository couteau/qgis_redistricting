Create a New Redistricting Plan
===============================

.. note::   
            Before you can create a plan, you must create a QGIS project that 
            includes the layer or layers containing the geographic units and 
            demographic data from which your redistricting plan will be built.

The \"Create New Plan\" dialog
------------------------------

When New Redistricting Plan is selected from the QGIS redistricting plugin toolbar or 
menu, the "Create New Plan" dialog guides you through creating a redistricting plan.

.. _page-1:

Page 1 - Plan Details
^^^^^^^^^^^^^^^^^^^^^

The first page of the "Create New Plan" dialog allows you to select a name for your plan,
provide the path to a new GeoPackage file that will contain your plan layers, and specify
the number of districts in your plan and the number of members who will represent those 
districts. You may also provide an optional description. The following constraints apply. 

* The plan name must be unique among redistricting plans for your project
* There must be two or more districts in your plan
* The number of members must be equal to or greater than the number

.. image:: /images/create_plan_page1.png

.. _page-2:

Page 2 - Geography
^^^^^^^^^^^^^^^^^^

The second page of the "Create New Plan" dialog allows you to define the geography from
which your plan will be built.

``Import Geography from Layer`` - Specify the layer containing the smallest units of 
geography you will use to create your plan (e.g., census blocks). 

``Primary Geography ID Field`` - Specify the layer attribute that uniquely identifies 
the geographic units. This field will be used to join the layer containing the demographic 
data (if it is different from the geography layer).

``Geography Name`` - You may also provide a more descriptive label for your geographic units here.

``Additional Geography`` - Here, you may define additional units of geography that may be used 
to build your districts. Geography is defined using fields from the primary geography layer.
For example, if your primary layer is U.S. Census Bureau census blocks, and each block contains 
an identifier for the county or census tract in which it falls, you can add that field to the 
list of additional geography to allow building districts from counties or census tracts. You may
define additional geography using individual attriabutes or QGIS expressions. Once the 
addtional unit is added, a more descriptive caption or label can be provided.

.. image:: /images/create_plan_page2.png

.. _page-3:

Page 3 - Population
^^^^^^^^^^^^^^^^^^^
The third page of the "Create New Plan" dialog allows you to specify the layer
containing the population data your plan will use.

``Population Layer`` - If your population data is contained in a separate layer from
your geographical building blocks, specify the population layer here. Population data 
must be provided at the same level of geography as the geographic units. If not using a
separate population layer, specify "Use the geography layer" here.

``Join Field`` - If using a separate population layer from the geography layer,
specify the field in the population layer that will be used to join the population 
data to the geographic units. This field must contain the same geographic identifier 
as the Geo ID Field used to uniquely identify the geography.

``Total Population Field`` - Specify the name of the attribute containing the total
population for each geographic unit.

``Maximum Deviation`` - Specify the maximum population deviation above or below the 
ideal population for each district that is permitted for your plan.

``Voting Age Population Field`` - Optionally specify a field containing the total 
voting age population for each geographic unit.

``Citizen VAP Field`` - Optionally specify a field containing the total 
citizen voting age population for each geographic unit.

.. image:: /images/create_plan_page3.png

.. _page-4:

Page 4 - Additional Demographic Data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fourth page of the "Create New Plan" dialog allows you to specify additiolnal 
demographic data that will be tracked for each district in your plan.

Demographic data is defined using fields from the population layer. You may
define demographic using individual attributes from the population layer or 
QGIS expressions. Once the addtional demographic data field is added, a more 
descriptive caption or label can be provided, and you can specify whether to track
the total population for the demographic group and/or the population of the deographic 
group as a percentage of total population, voting age population, or citizen voting
age population.

.. image:: /images/create_plan_page4.png

.. _page-5:

Page 5 - Import Assignments
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fifth and final page of the "Create New Plan" dialog allows you to optional
import district assignments for your plan from a CSV or Microsoft Excel file. You
may also import assignments at a later point using the "Import Assignments" option
available on the QGIS redistricting plugin menu.

.. image:: /images/create_plan_page5.png
