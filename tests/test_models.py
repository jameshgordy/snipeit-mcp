"""Tests for all Pydantic models."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAssetData:
    def test_valid(self):
        from server import AssetData
        a = AssetData(status_id=1, model_id=5, name="Laptop", asset_tag="LAP-001", serial="ABC")
        assert a.status_id == 1
        assert a.name == "Laptop"

    def test_optional_fields(self):
        from server import AssetData
        a = AssetData(status_id=1, model_id=5)
        assert a.name is None
        assert a.serial is None
        assert a.purchase_cost is None


class TestCheckoutData:
    def test_valid(self):
        from server import CheckoutData
        c = CheckoutData(checkout_to_type="user", assigned_to_id=10)
        assert c.checkout_to_type == "user"
        assert c.assigned_to_id == 10

    def test_optional_fields(self):
        from server import CheckoutData
        c = CheckoutData(checkout_to_type="asset", assigned_to_id=1)
        assert c.expected_checkin is None
        assert c.note is None


class TestCheckinData:
    def test_valid(self):
        from server import CheckinData
        c = CheckinData(note="Returned", location_id=5)
        assert c.note == "Returned"

    def test_defaults(self):
        from server import CheckinData
        c = CheckinData()
        assert c.note is None
        assert c.location_id is None


class TestAuditData:
    def test_valid(self):
        from server import AuditData
        a = AuditData(location_id=1, note="Audited", next_audit_date="2025-06-01")
        assert a.next_audit_date == "2025-06-01"


class TestMaintenanceData:
    def test_valid(self):
        from server import MaintenanceData
        m = MaintenanceData(asset_improvement="Upgrade", supplier_id=1, title="RAM upgrade")
        assert m.title == "RAM upgrade"
        assert m.cost is None


class TestConsumableData:
    def test_valid(self):
        from server import ConsumableData
        c = ConsumableData(name="Toner", qty=100, category_id=2)
        assert c.name == "Toner"

    def test_optional(self):
        from server import ConsumableData
        c = ConsumableData()
        assert c.name is None


class TestCategoryData:
    def test_valid(self):
        from server import CategoryData
        c = CategoryData(name="Laptops", category_type="asset")
        assert c.category_type == "asset"


class TestManufacturerData:
    def test_valid(self):
        from server import ManufacturerData
        m = ManufacturerData(name="Dell", url="https://dell.com")
        assert m.name == "Dell"


class TestAssetModelData:
    def test_valid(self):
        from server import AssetModelData
        m = AssetModelData(name="XPS 15", category_id=1, manufacturer_id=2)
        assert m.name == "XPS 15"

    def test_optional(self):
        from server import AssetModelData
        m = AssetModelData()
        assert m.fieldset_id is None


class TestStatusLabelData:
    def test_valid(self):
        from server import StatusLabelData
        s = StatusLabelData(name="Deployed", type="deployable")
        assert s.type == "deployable"


class TestLocationData:
    def test_valid(self):
        from server import LocationData
        l = LocationData(name="Main Office", city="New York", country="US")
        assert l.city == "New York"


class TestSupplierData:
    def test_valid(self):
        from server import SupplierData
        s = SupplierData(name="Acme", email="info@acme.com")
        assert s.name == "Acme"


class TestDepreciationData:
    def test_valid(self):
        from server import DepreciationData
        d = DepreciationData(name="3 Year", months=36)
        assert d.months == 36


class TestLicenseData:
    def test_valid(self):
        from server import LicenseData
        l = LicenseData(name="Office 365", seats=50, serial="KEY-123")
        assert l.seats == 50

    def test_optional(self):
        from server import LicenseData
        l = LicenseData()
        assert l.expiration_date is None


class TestLicenseSeatCheckout:
    def test_valid(self):
        from server import LicenseSeatCheckout
        l = LicenseSeatCheckout(assigned_to=1, asset_id=2)
        assert l.assigned_to == 1


class TestAccessoryData:
    def test_valid(self):
        from server import AccessoryData
        a = AccessoryData(name="Mouse", qty=50, category_id=3)
        assert a.qty == 50


class TestAccessoryCheckout:
    def test_valid(self):
        from server import AccessoryCheckout
        a = AccessoryCheckout(assigned_to=5, note="For project")
        assert a.assigned_to == 5


class TestUserData:
    def test_valid(self):
        from server import UserData
        u = UserData(first_name="John", last_name="Doe", username="jdoe",
                     password="secret", password_confirmation="secret")
        assert u.username == "jdoe"

    def test_optional(self):
        from server import UserData
        u = UserData()
        assert u.groups is None


class TestComponentData:
    def test_valid(self):
        from server import ComponentData
        c = ComponentData(name="8GB RAM", qty=20, category_id=5)
        assert c.name == "8GB RAM"


class TestComponentCheckout:
    def test_valid(self):
        from server import ComponentCheckout
        c = ComponentCheckout(assigned_to=10, assigned_qty=2)
        assert c.assigned_qty == 2

    def test_default_qty(self):
        from server import ComponentCheckout
        c = ComponentCheckout(assigned_to=1)
        assert c.assigned_qty == 1


class TestCompanyData:
    def test_valid(self):
        from server import CompanyData
        c = CompanyData(name="Acme Corp")
        assert c.name == "Acme Corp"


class TestDepartmentData:
    def test_valid(self):
        from server import DepartmentData
        d = DepartmentData(name="Engineering", company_id=1, manager_id=5)
        assert d.name == "Engineering"


class TestGroupData:
    def test_valid(self):
        from server import GroupData
        g = GroupData(name="Admins", permissions={"admin": "1"})
        assert g.permissions == {"admin": "1"}


class TestFieldData:
    def test_valid(self):
        from server import FieldData
        f = FieldData(name="MAC Address", element="text", format="MAC")
        assert f.element == "text"


class TestFieldsetData:
    def test_valid(self):
        from server import FieldsetData
        f = FieldsetData(name="Hardware Fields")
        assert f.name == "Hardware Fields"


class TestImportData:
    def test_valid(self):
        from server import ImportData
        i = ImportData(import_type="asset", run_backup=True)
        assert i.import_type == "asset"

    def test_field_map(self):
        from server import ImportData
        i = ImportData(import_type="asset", field_map={"Col A": "asset_tag"})
        assert i.field_map == {"Col A": "asset_tag"}


class TestAssetRequestData:
    def test_valid(self):
        from server import AssetRequestData
        r = AssetRequestData(expected_checkout="2025-02-01", note="Need for project")
        assert r.expected_checkout == "2025-02-01"
