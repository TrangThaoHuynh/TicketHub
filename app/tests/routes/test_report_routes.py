import os
import unittest
from unittest.mock import patch

# Cấu hình môi trường test trước khi import app
os.environ["DB_AUTO_INIT"] = "false"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import create_app


class TestReportRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
        )

    def setUp(self):
        self.client = self.app.test_client()

    # =========================
    # ADMIN REPORTS
    # =========================
    def test_admin_reports_redirect_if_not_logged_in(self):
        response = self.client.get("/admin/reports", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers.get("Location", ""))

    def test_admin_reports_forbidden_if_user_is_not_admin(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = 2

            with patch("app.routes.report_routes.Admin") as mock_admin:
                mock_admin.query.get.return_value = None

                response = c.get("/admin/reports", follow_redirects=False)

        self.assertEqual(response.status_code, 403)

    def test_admin_reports_success_for_admin(self):
        fake_dashboard = {
            "filters": {
                "organizer_id": None,
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
                "group_by": "day",
            },
            "organizer_options": [],
            "cards": {
                "total_revenue": 1000000,
                "total_tickets_sold": 10,
            },
            "charts": {
                "time_revenue": {"labels": ["01/04"], "values": [1000000]},
                "event_revenue": {"labels": ["Event A"], "values": [1000000]},
                "booking_status": {"labels": ["Thành công"], "values": [1]},
                "event_status": {"labels": ["Đã xuất bản"], "values": [1]},
                "ticket_status": {"labels": ["Hợp lệ"], "values": [10]},
            },
            "event_revenue_rows": [],
        }

        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = 1

            with patch("app.routes.report_routes.Admin") as mock_admin, \
                 patch("app.routes.report_routes.get_admin_report_dashboard") as mock_service, \
                 patch("app.routes.report_routes.render_template", return_value="ADMIN_REPORT_OK") as mock_render:

                mock_admin.query.get.return_value = object()
                mock_service.return_value = fake_dashboard

                response = c.get(
                    "/admin/reports?startDate=2026-04-01&endDate=2026-04-30",
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"ADMIN_REPORT_OK", response.data)

        called_kwargs = mock_service.call_args.kwargs
        self.assertIsNone(called_kwargs["organizer_id"])
        self.assertEqual(called_kwargs["group_by"], "day")
        self.assertEqual(called_kwargs["start_date"].strftime("%Y-%m-%d"), "2026-04-01")
        self.assertEqual(called_kwargs["end_date"].strftime("%Y-%m-%d"), "2026-04-30")
        mock_render.assert_called_once()

    # =========================
    # ORGANIZER REPORTS
    # =========================
    def test_organizer_reports_redirect_if_not_logged_in(self):
        response = self.client.get("/organizer/reports", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers.get("Location", ""))

    def test_organizer_reports_forbidden_if_user_is_not_organizer(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = 3

            with patch("app.routes.report_routes.Organizer") as mock_organizer:
                mock_organizer.query.get.return_value = None

                response = c.get("/organizer/reports", follow_redirects=False)

        self.assertEqual(response.status_code, 403)

    def test_organizer_reports_success_for_organizer(self):
        fake_dashboard = {
            "filters": {
                "event_id": 5,
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
            },
            "event_options": [{"id": 5, "title": "Event B"}],
            "cards": {
                "total_events": 1,
                "total_revenue": 500000,
                "ongoing_events": 0,
            },
            "chart": {
                "labels": ["01/04"],
                "values": [500000],
            },
            "rows": [],
        }

        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = 2

            with patch("app.routes.report_routes.Organizer") as mock_organizer, \
                 patch("app.routes.report_routes.get_organizer_report_dashboard") as mock_service, \
                 patch("app.routes.report_routes.render_template", return_value="ORGANIZER_REPORT_OK") as mock_render:

                mock_organizer.query.get.return_value = object()
                mock_service.return_value = fake_dashboard

                response = c.get(
                    "/organizer/reports?eventId=5&startDate=2026-04-01&endDate=2026-04-30",
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"ORGANIZER_REPORT_OK", response.data)

        called_kwargs = mock_service.call_args.kwargs
        self.assertEqual(called_kwargs["organizer_id"], 2)
        self.assertEqual(called_kwargs["event_id"], 5)
        self.assertEqual(called_kwargs["start_date"].strftime("%Y-%m-%d"), "2026-04-01")
        self.assertEqual(called_kwargs["end_date"].strftime("%Y-%m-%d"), "2026-04-30")
        mock_render.assert_called_once()

    def test_organizer_reports_invalid_event_id_should_not_crash(self):
        fake_dashboard = {
            "filters": {"event_id": None, "start_date": "", "end_date": ""},
            "event_options": [],
            "cards": {"total_events": 0, "total_revenue": 0, "ongoing_events": 0},
            "chart": {"labels": [], "values": []},
            "rows": [],
        }

        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = 2

            with patch("app.routes.report_routes.Organizer") as mock_organizer, \
                 patch("app.routes.report_routes.get_organizer_report_dashboard") as mock_service, \
                 patch("app.routes.report_routes.render_template", return_value="ORGANIZER_REPORT_OK"):

                mock_organizer.query.get.return_value = object()
                mock_service.return_value = fake_dashboard

                response = c.get("/organizer/reports?eventId=abc", follow_redirects=False)

        self.assertEqual(response.status_code, 200)
        called_kwargs = mock_service.call_args.kwargs
        self.assertIsNone(called_kwargs["event_id"])


if __name__ == "__main__":
    unittest.main()