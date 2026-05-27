"""Snipe-IT MCP Server.

Public API surface re-exports the FastMCP instance, every Pydantic schema, and
every tool function so callers (and tests) can ``from snipeit_mcp import X``
without knowing the internal module layout.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("snipeit-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

from snipeit.exceptions import (
    SnipeITAuthenticationError,
    SnipeITException,
    SnipeITNotFoundError,
    SnipeITValidationError,
)

from .__main__ import main
from .client import SnipeITDirectAPI
from .mcp_server import mcp
from .schemas import (
    AccessoryCheckout,
    AccessoryData,
    AssetData,
    AssetModelData,
    AssetRequestData,
    AuditData,
    CategoryData,
    CheckinData,
    CheckoutData,
    CompanyData,
    ComponentCheckout,
    ComponentData,
    ConsumableData,
    DepartmentData,
    DepreciationData,
    FieldData,
    FieldsetData,
    GroupData,
    ImportData,
    LicenseData,
    LicenseSeatCheckout,
    LocationData,
    MaintenanceData,
    ManufacturerData,
    StatusLabelData,
    SupplierData,
    UserData,
)
from .tools.assets import (
    asset_files,
    asset_labels,
    asset_licenses,
    asset_maintenance,
    asset_operations,
    asset_requests,
    manage_assets,
)
from .tools.custom_fields import manage_fields, manage_fieldsets
from .tools.foundational import (
    manage_categories,
    manage_depreciations,
    manage_locations,
    manage_manufacturers,
    manage_models,
    manage_status_labels,
    manage_suppliers,
    model_files,
)
from .tools.imports import manage_imports
from .tools.inventory import (
    accessory_operations,
    component_operations,
    manage_accessories,
    manage_components,
    manage_consumables,
)
from .tools.licenses import license_files, license_seats, manage_licenses
from .tools.people import (
    manage_companies,
    manage_departments,
    manage_groups,
    manage_users,
    user_assets,
    user_two_factor,
)
from .tools.reports import activity_reports, audit_tracking, status_summary
from .tools.system import ldap_operations, manage_backups, system_info
