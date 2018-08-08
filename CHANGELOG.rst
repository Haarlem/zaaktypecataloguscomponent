==============
Change history
==============

0.1.1
=====

*August 6, 2018*

* Added Docker related files and instructions.
* Show all resources (only catalogussen) on the root resource and redirect to
  default API version resources if no version provided.
* Changed the StUF date format to ISO8601 format throughout the API. This
  affects all ``ingangsdatumObject``, ``einddatumObject`` and ``versiedatum``
  fields.
* Changed the storage of dates from StUF date format to native date format.
* Added missing code coverage requirement.
* Fixes incorrect admin-behaviour for saving Zaak ``Eigenschappen``.


0.1.0
=====

*February 21, 2018*

* Initial public release.
