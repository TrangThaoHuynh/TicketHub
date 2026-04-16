import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

# Cấu hình môi trường test trước khi import app
os.environ["DB_AUTO_INIT"] = "false"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import create_app
from app.services import report_service


class FakeQuery:
    def __init__(self, all_result=None, one_result=None):
        self._all_result = all_result if all_result is not None else []
        self._one_result = one_result

    def select_from(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def outerjoin(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._all_result

    def one(self):
        return self._one_result


class FakeEventQuery:
    def __init__(self, events):
        self._events = events

    def filter_by(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._events


class TestReportService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Tạo app test
        cls.app = create_app()
        cls.app.config.update(TESTING=True)

        # Push app context để dùng Event.query / db.session
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        # Pop app context sau khi test xong
        cls.app_context.pop()

    # =========================
    # HELPER FUNCTIONS
    # =========================
    def test_to_float(self):
        self.assertEqual(report_service._to_float(None), 0.0)
        self.assertEqual(report_service._to_float(100), 100.0)
        self.assertEqual(report_service._to_float("12.5"), 12.5)

    def test_period_label(self):
        dt = datetime(2026, 4, 15, 10, 30, 0)

        self.assertEqual(report_service._period_label(dt, "day"), "15/04")
        self.assertEqual(report_service._period_label(dt, "month"), "04/2026")
        self.assertEqual(report_service._period_label(None, "day"), "Không rõ")

    def test_event_state_cancelled(self):
        event = SimpleNamespace(
            status="CANCELLED",
            startTime=datetime(2026, 4, 10, 8, 0, 0),
            endTime=datetime(2026, 4, 10, 22, 0, 0),
        )

        label, badge = report_service._event_state(event)
        self.assertEqual(label, "Đã hủy")
        self.assertEqual(badge, "danger")

    def test_event_state_finished(self):
        event = SimpleNamespace(
            status="FINISHED",
            startTime=datetime(2026, 4, 10, 8, 0, 0),
            endTime=datetime(2026, 4, 10, 22, 0, 0),
        )

        label, badge = report_service._event_state(event)
        self.assertEqual(label, "Đã kết thúc")
        self.assertEqual(badge, "secondary")

    def test_event_state_pending(self):
        event = SimpleNamespace(
            status="PENDING",
            startTime=datetime(2026, 4, 10, 8, 0, 0),
            endTime=datetime(2026, 4, 10, 22, 0, 0),
        )

        label, badge = report_service._event_state(event)
        self.assertEqual(label, "Chờ duyệt")
        self.assertEqual(badge, "dark")

    def test_build_status_payload(self):
        counter = {
            "SUCCESS": 5,
            "FAILED": 1,
        }
        mapping = {
            "SUCCESS": "Thành công",
            "FAILED": "Thất bại",
        }

        payload = report_service._build_status_payload(counter, mapping)

        self.assertEqual(payload["labels"], ["Thành công", "Thất bại"])
        self.assertEqual(payload["values"], [5, 1])

    # =========================
    # ORGANIZER DASHBOARD SERVICE
    # =========================
    def test_get_organizer_report_dashboard(self):
        events = [
            SimpleNamespace(
                id=10,
                title="Event Organizer A",
                organizerId=2,
                startTime=datetime(2026, 4, 20, 19, 0, 0),
                endTime=datetime(2026, 4, 20, 22, 0, 0),
                status="PUBLISHED",
            ),
            SimpleNamespace(
                id=11,
                title="Event Organizer B",
                organizerId=2,
                startTime=datetime(2026, 4, 25, 19, 0, 0),
                endTime=datetime(2026, 4, 25, 22, 0, 0),
                status="PENDING",
            ),
        ]

        fake_chart_query = FakeQuery(
            all_result=[
                (datetime(2026, 4, 1, 9, 0, 0), 300000),
                (datetime(2026, 4, 1, 10, 0, 0), 200000),
                (datetime(2026, 4, 2, 11, 0, 0), 500000),
            ]
        )

        with patch.object(report_service.Event, "query", FakeEventQuery(events)), \
             patch("app.services.report_service._build_event_capacity_map") as mock_capacity, \
             patch("app.services.report_service._build_event_sales_map") as mock_sales, \
             patch("app.services.report_service._event_state") as mock_event_state, \
             patch("app.services.report_service.db.session.query", return_value=fake_chart_query):

            mock_capacity.return_value = {10: 100, 11: 200}
            mock_sales.return_value = {
                10: {"sold_tickets": 2, "revenue": 500000.0},
                11: {"sold_tickets": 1, "revenue": 250000.0},
            }
            mock_event_state.side_effect = [
                ("Đang diễn ra", "primary"),
                ("Chờ duyệt", "dark"),
            ]

            result = report_service.get_organizer_report_dashboard(
                organizer_id=2,
                event_id=10,
                start_date=datetime(2026, 4, 1, 0, 0, 0),
                end_date=datetime(2026, 4, 30, 23, 59, 59),
            )

        self.assertEqual(result["filters"]["event_id"], 10)
        self.assertEqual(result["filters"]["start_date"], "2026-04-01")
        self.assertEqual(result["filters"]["end_date"], "2026-04-30")

        self.assertEqual(result["cards"]["total_events"], 2)
        self.assertEqual(result["cards"]["total_revenue"], 750000.0)
        self.assertEqual(result["cards"]["ongoing_events"], 1)

        self.assertEqual(result["chart"]["labels"], ["01/04", "02/04"])
        self.assertEqual(result["chart"]["values"], [500000.0, 500000.0])

        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["rows"][0]["total_tickets"], 100)
        self.assertEqual(result["rows"][0]["sold_tickets"], 2)
        self.assertEqual(result["rows"][0]["revenue"], 500000.0)

    # =========================
    # ADMIN DASHBOARD SERVICE
    # =========================
    def test_get_admin_report_dashboard(self):
        organizer_options_query = FakeQuery(
            all_result=[
                SimpleNamespace(id=2, name="Organizer A"),
                SimpleNamespace(id=3, name="Organizer B"),
            ]
        )

        summary_query = FakeQuery(
            one_result=SimpleNamespace(total_revenue=1750000, total_tickets=7)
        )

        time_query = FakeQuery(
            all_result=[
                (datetime(2026, 4, 1, 9, 0, 0), 500000),
                (datetime(2026, 4, 2, 9, 0, 0), 750000),
                (datetime(2026, 4, 2, 10, 0, 0), 500000),
            ]
        )

        event_revenue_query = FakeQuery(
            all_result=[
                (10, "Event A", 1250000, 5),
                (11, "Event B", 500000, 2),
            ]
        )

        booking_status_query = FakeQuery(
            all_result=[
                (1, "SUCCESS"),
                (2, "SUCCESS"),
                (3, "FAILED"),
            ]
        )

        event_status_query = FakeQuery(
            all_result=[
                ("PUBLISHED", 2),
                ("PENDING", 1),
            ]
        )

        ticket_status_query = FakeQuery(
            all_result=[
                ("VALID", 5),
                ("USED", 2),
            ]
        )

        query_side_effects = [
            organizer_options_query,
            summary_query,
            time_query,
            event_revenue_query,
            booking_status_query,
            event_status_query,
            ticket_status_query,
        ]

        with patch("app.services.report_service.db.session.query", side_effect=query_side_effects):
            result = report_service.get_admin_report_dashboard(
                organizer_id=2,
                start_date=datetime(2026, 4, 1, 0, 0, 0),
                end_date=datetime(2026, 4, 30, 23, 59, 59),
                group_by="day",
            )

        self.assertEqual(result["filters"]["organizer_id"], 2)
        self.assertEqual(result["filters"]["start_date"], "2026-04-01")
        self.assertEqual(result["filters"]["end_date"], "2026-04-30")
        self.assertEqual(result["filters"]["group_by"], "day")

        self.assertEqual(result["cards"]["total_revenue"], 1750000.0)
        self.assertEqual(result["cards"]["total_tickets_sold"], 7)

        self.assertEqual(result["charts"]["time_revenue"]["labels"], ["01/04", "02/04"])
        self.assertEqual(result["charts"]["time_revenue"]["values"], [500000.0, 1250000.0])

        self.assertEqual(result["charts"]["event_revenue"]["labels"], ["Event A", "Event B"])
        self.assertEqual(result["charts"]["event_revenue"]["values"], [1250000.0, 500000.0])

        self.assertEqual(result["charts"]["booking_status"]["labels"], ["Thành công", "Thất bại"])
        self.assertEqual(result["charts"]["booking_status"]["values"], [2, 1])

        self.assertEqual(result["charts"]["event_status"]["labels"], ["Đã xuất bản", "Chờ duyệt"])
        self.assertEqual(result["charts"]["event_status"]["values"], [2, 1])

        self.assertEqual(result["charts"]["ticket_status"]["labels"], ["Hợp lệ", "Đã dùng"])
        self.assertEqual(result["charts"]["ticket_status"]["values"], [5, 2])

        self.assertEqual(len(result["event_revenue_rows"]), 2)
        self.assertEqual(result["event_revenue_rows"][0]["event_title"], "Event A")
        self.assertEqual(result["event_revenue_rows"][0]["revenue"], 1250000.0)


if __name__ == "__main__":
    unittest.main()