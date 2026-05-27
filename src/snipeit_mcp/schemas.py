"""Pydantic schemas for Snipe-IT MCP tool inputs and outputs."""

from typing import Literal

from pydantic import BaseModel, Field


class AssetData(BaseModel):
    """Model for asset data used in create/update operations."""
    status_id: int | None = Field(None, description="ID of the status label")
    model_id: int | None = Field(None, description="ID of the asset model")
    asset_tag: str | None = Field(None, description="Asset tag identifier")
    name: str | None = Field(None, description="Asset name")
    serial: str | None = Field(None, description="Serial number")
    purchase_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD)")
    purchase_cost: float | None = Field(None, description="Purchase cost")
    order_number: str | None = Field(None, description="Order number")
    notes: str | None = Field(None, description="Additional notes")
    warranty_months: int | None = Field(None, description="Warranty period in months")
    location_id: int | None = Field(None, description="Location ID")
    rtd_location_id: int | None = Field(None, description="Default location ID")
    supplier_id: int | None = Field(None, description="Supplier ID")
    company_id: int | None = Field(None, description="Company ID")
    requestable: bool | None = Field(None, description="Whether asset is requestable")


class CheckoutData(BaseModel):
    """Model for asset checkout operations."""
    checkout_to_type: Literal["user", "asset", "location"] = Field(
        ..., 
        description="Type of entity to checkout to"
    )
    assigned_to_id: int = Field(..., description="ID of the user/asset/location")
    expected_checkin: str | None = Field(None, description="Expected checkin date (YYYY-MM-DD)")
    checkout_at: str | None = Field(None, description="Checkout date (YYYY-MM-DD)")
    note: str | None = Field(None, description="Checkout notes")
    name: str | None = Field(None, description="Name for the checkout")


class CheckinData(BaseModel):
    """Model for asset checkin operations."""
    note: str | None = Field(None, description="Checkin notes")
    location_id: int | None = Field(None, description="Location ID to checkin to")


class AuditData(BaseModel):
    """Model for asset audit operations."""
    location_id: int | None = Field(None, description="Location ID")
    note: str | None = Field(None, description="Audit notes")
    next_audit_date: str | None = Field(None, description="Next audit date (YYYY-MM-DD)")


class MaintenanceData(BaseModel):
    """Model for asset maintenance records."""
    asset_improvement: str = Field(..., description="Type of maintenance/improvement")
    supplier_id: int = Field(..., description="Supplier ID")
    title: str = Field(..., description="Maintenance title")
    cost: float | None = Field(None, description="Maintenance cost")
    start_date: str | None = Field(None, description="Start date (YYYY-MM-DD)")
    completion_date: str | None = Field(None, description="Completion date (YYYY-MM-DD)")
    notes: str | None = Field(None, description="Maintenance notes")


class ConsumableData(BaseModel):
    """Model for consumable data used in create/update operations."""
    name: str | None = Field(None, description="Consumable name")
    qty: int | None = Field(None, description="Quantity")
    category_id: int | None = Field(None, description="Category ID")
    company_id: int | None = Field(None, description="Company ID")
    location_id: int | None = Field(None, description="Location ID")
    manufacturer_id: int | None = Field(None, description="Manufacturer ID")
    model_number: str | None = Field(None, description="Model number")
    item_no: str | None = Field(None, description="Item number")
    order_number: str | None = Field(None, description="Order number")
    purchase_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD)")
    purchase_cost: float | None = Field(None, description="Purchase cost")
    min_amt: int | None = Field(None, description="Minimum quantity threshold")
    notes: str | None = Field(None, description="Additional notes")


class CategoryData(BaseModel):
    """Model for category data used in create/update operations."""
    name: str | None = Field(None, description="Category name")
    category_type: Literal["asset", "accessory", "consumable", "component", "license"] | None = Field(
        None, description="Type of category"
    )
    eula_text: str | None = Field(None, description="EULA text for this category")
    use_default_eula: bool | None = Field(None, description="Use default EULA")
    require_acceptance: bool | None = Field(None, description="Require users to accept EULA")
    checkin_email: bool | None = Field(None, description="Send email on checkin")
    image: str | None = Field(None, description="Image filename")


class ManufacturerData(BaseModel):
    """Model for manufacturer data used in create/update operations."""
    name: str | None = Field(None, description="Manufacturer name")
    url: str | None = Field(None, description="Manufacturer URL")
    support_url: str | None = Field(None, description="Support URL")
    support_phone: str | None = Field(None, description="Support phone number")
    support_email: str | None = Field(None, description="Support email address")
    image: str | None = Field(None, description="Image filename")


class AssetModelData(BaseModel):
    """Model for asset model data used in create/update operations."""
    name: str | None = Field(None, description="Model name")
    model_number: str | None = Field(None, description="Model number")
    manufacturer_id: int | None = Field(None, description="Manufacturer ID")
    category_id: int | None = Field(None, description="Category ID")
    eol: int | None = Field(None, description="End of life in months")
    depreciation_id: int | None = Field(None, description="Depreciation ID")
    notes: str | None = Field(None, description="Additional notes")
    fieldset_id: int | None = Field(None, description="Custom fieldset ID")
    requestable: bool | None = Field(None, description="Whether assets of this model are requestable")
    image: str | None = Field(None, description="Image filename")


class StatusLabelData(BaseModel):
    """Model for status label data used in create/update operations."""
    name: str | None = Field(None, description="Status label name")
    type: Literal["deployable", "pending", "archived", "undeployable"] | None = Field(
        None, description="Status type"
    )
    color: str | None = Field(None, description="Color hex code (e.g., #ff0000)")
    show_in_nav: bool | None = Field(None, description="Show in navigation")
    default_label: bool | None = Field(None, description="Use as default status")
    notes: str | None = Field(None, description="Additional notes")


class LocationData(BaseModel):
    """Model for location data used in create/update operations."""
    name: str | None = Field(None, description="Location name")
    address: str | None = Field(None, description="Street address")
    address2: str | None = Field(None, description="Address line 2")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State/Province")
    country: str | None = Field(None, description="Country (2-letter ISO code)")
    zip: str | None = Field(None, description="ZIP/Postal code")
    ldap_ou: str | None = Field(None, description="LDAP OU")
    manager_id: int | None = Field(None, description="Manager user ID")
    parent_id: int | None = Field(None, description="Parent location ID")
    currency: str | None = Field(None, description="Currency code (e.g., USD)")
    image: str | None = Field(None, description="Image filename")


class SupplierData(BaseModel):
    """Model for supplier data used in create/update operations."""
    name: str | None = Field(None, description="Supplier name")
    address: str | None = Field(None, description="Street address")
    address2: str | None = Field(None, description="Address line 2")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State/Province")
    country: str | None = Field(None, description="Country (2-letter ISO code)")
    zip: str | None = Field(None, description="ZIP/Postal code")
    phone: str | None = Field(None, description="Phone number")
    fax: str | None = Field(None, description="Fax number")
    email: str | None = Field(None, description="Email address")
    contact: str | None = Field(None, description="Contact person name")
    url: str | None = Field(None, description="Website URL")
    notes: str | None = Field(None, description="Additional notes")
    image: str | None = Field(None, description="Image filename")


class DepreciationData(BaseModel):
    """Model for depreciation data used in create/update operations."""
    name: str | None = Field(None, description="Depreciation name (e.g., 'Computer Equipment (3 Years)')")
    months: int | None = Field(None, description="Depreciation period in months")


class LicenseData(BaseModel):
    """Model for license data used in create/update operations."""
    name: str | None = Field(None, description="License name")
    seats: int | None = Field(None, description="Number of seats/installations allowed")
    category_id: int | None = Field(None, description="Category ID")
    company_id: int | None = Field(None, description="Company ID")
    manufacturer_id: int | None = Field(None, description="Manufacturer ID")
    serial: str | None = Field(None, description="License key/serial number")
    purchase_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD)")
    purchase_cost: float | None = Field(None, description="Purchase cost")
    expiration_date: str | None = Field(None, description="Expiration date (YYYY-MM-DD)")
    license_name: str | None = Field(None, description="Licensed to name")
    license_email: str | None = Field(None, description="Licensed to email")
    maintained: bool | None = Field(None, description="Whether license has maintenance/support")
    reassignable: bool | None = Field(None, description="Whether license can be reassigned")
    notes: str | None = Field(None, description="Additional notes")
    order_number: str | None = Field(None, description="Order number")
    supplier_id: int | None = Field(None, description="Supplier ID")
    termination_date: str | None = Field(None, description="Termination date (YYYY-MM-DD)")


class LicenseSeatCheckout(BaseModel):
    """Model for license seat checkout operations."""
    assigned_to: int | None = Field(None, description="User ID to assign the seat to")
    asset_id: int | None = Field(None, description="Asset ID to assign the seat to")
    note: str | None = Field(None, description="Checkout notes")


class AccessoryData(BaseModel):
    """Model for accessory data used in create/update operations."""
    name: str | None = Field(None, description="Accessory name")
    qty: int | None = Field(None, description="Total quantity available")
    category_id: int | None = Field(None, description="Category ID (must be accessory-type)")
    manufacturer_id: int | None = Field(None, description="Manufacturer ID")
    supplier_id: int | None = Field(None, description="Supplier ID")
    location_id: int | None = Field(None, description="Location ID")
    company_id: int | None = Field(None, description="Company ID")
    model_number: str | None = Field(None, description="Model number")
    order_number: str | None = Field(None, description="Order number")
    purchase_cost: float | None = Field(None, description="Purchase cost")
    purchase_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD)")
    min_amt: int | None = Field(None, description="Minimum quantity threshold for reorder alerts")
    notes: str | None = Field(None, description="Additional notes")


class AccessoryCheckout(BaseModel):
    """Model for accessory checkout operations."""
    assigned_to: int | None = Field(None, description="User ID to checkout to")
    note: str | None = Field(None, description="Checkout notes")


class UserData(BaseModel):
    """Model for user data used in create/update operations."""
    first_name: str | None = Field(None, description="First name")
    last_name: str | None = Field(None, description="Last name")
    username: str | None = Field(None, description="Username for login")
    password: str | None = Field(None, description="Password (required for create)")
    password_confirmation: str | None = Field(None, description="Password confirmation (required for create)")
    email: str | None = Field(None, description="Email address")
    permissions: dict | None = Field(None, description="User permissions object")
    activated: bool | None = Field(None, description="Whether user account is activated")
    phone: str | None = Field(None, description="Phone number")
    jobtitle: str | None = Field(None, description="Job title")
    manager_id: int | None = Field(None, description="Manager user ID")
    employee_num: str | None = Field(None, description="Employee number")
    department_id: int | None = Field(None, description="Department ID")
    company_id: int | None = Field(None, description="Company ID")
    location_id: int | None = Field(None, description="Location ID")
    notes: str | None = Field(None, description="Additional notes")
    groups: list[int] | None = Field(None, description="List of group IDs")
    ldap_import: bool | None = Field(None, description="Whether user was imported from LDAP")


class ComponentData(BaseModel):
    """Model for component data used in create/update operations."""
    name: str | None = Field(None, description="Component name")
    qty: int | None = Field(None, description="Total quantity")
    category_id: int | None = Field(None, description="Category ID (must be component-type)")
    company_id: int | None = Field(None, description="Company ID")
    location_id: int | None = Field(None, description="Location ID")
    manufacturer_id: int | None = Field(None, description="Manufacturer ID")
    supplier_id: int | None = Field(None, description="Supplier ID")
    model_number: str | None = Field(None, description="Model number")
    serial: str | None = Field(None, description="Serial number")
    order_number: str | None = Field(None, description="Order number")
    purchase_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD)")
    purchase_cost: float | None = Field(None, description="Purchase cost per unit")
    min_amt: int | None = Field(None, description="Minimum quantity threshold for alerts")
    notes: str | None = Field(None, description="Additional notes")


class ComponentCheckout(BaseModel):
    """Model for component checkout operations."""
    assigned_to: int = Field(..., description="Asset ID to checkout component to")
    assigned_qty: int = Field(1, description="Quantity to checkout")
    note: str | None = Field(None, description="Checkout notes")


class CompanyData(BaseModel):
    """Model for company data used in create/update operations."""
    name: str | None = Field(None, description="Company name")
    image: str | None = Field(None, description="Image filename")


class DepartmentData(BaseModel):
    """Model for department data used in create/update operations."""
    name: str | None = Field(None, description="Department name")
    company_id: int | None = Field(None, description="Company ID")
    location_id: int | None = Field(None, description="Location ID")
    manager_id: int | None = Field(None, description="Manager user ID")
    notes: str | None = Field(None, description="Additional notes")
    image: str | None = Field(None, description="Image filename")


class GroupData(BaseModel):
    """Model for group data used in create/update operations."""
    name: str | None = Field(None, description="Group name")
    permissions: dict | None = Field(None, description="Permissions object defining group access rights")


class FieldData(BaseModel):
    """Model for custom field data used in create/update operations."""
    name: str | None = Field(None, description="Field name")
    element: Literal["text", "textarea", "listbox", "checkbox", "radio"] | None = Field(
        None, description="Field element type"
    )
    field_values: str | None = Field(None, description="Possible values for listbox/radio (newline separated)")
    field_encrypted: bool | None = Field(None, description="Whether field value is encrypted")
    show_in_email: bool | None = Field(None, description="Show field in emails")
    help_text: str | None = Field(None, description="Help text displayed with field")
    format: Literal["ANY", "ALPHA", "ALPHA-DASH", "NUMERIC", "ALPHA-NUMERIC", "EMAIL", "DATE", "URL", "IP", "IPV4", "IPV6", "MAC", "BOOLEAN", "REGEX"] | None = Field(
        None, description="Validation format for the field"
    )
    custom_format: str | None = Field(None, description="Custom regex pattern when format is REGEX")


class FieldsetData(BaseModel):
    """Model for fieldset data used in create/update operations."""
    name: str | None = Field(None, description="Fieldset name")


class ImportData(BaseModel):
    """Model for import configuration."""
    import_type: Literal["asset", "accessory", "consumable", "component", "license", "user", "location"] | None = Field(
        None, description="Type of data being imported"
    )
    field_map: dict | None = Field(
        None, description="Maps CSV column names to Snipe-IT field names"
    )
    run_backup: bool | None = Field(
        None, description="Whether to backup database before import"
    )


class AssetRequestData(BaseModel):
    """Model for asset checkout request."""
    expected_checkout: str | None = Field(
        None, description="Expected checkout date (YYYY-MM-DD)"
    )
    note: str | None = Field(
        None, description="Note explaining the request"
    )

