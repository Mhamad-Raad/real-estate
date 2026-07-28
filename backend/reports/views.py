"""Dashboard + reports endpoints — thin HTTP wrappers over `selectors` (§10.1, §10.2, §14.2)."""

import csv

from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin

from .selectors import dashboard_stats, process_report, user_report


class ReportFilterSerializer(serializers.Serializer):
    """Query-string validation, so a malformed date is a 400 and never a 500."""

    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    category = serializers.IntegerField(required=False)

    def validate(self, attrs):
        date_from, date_to = attrs.get("date_from"), attrs.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError("date_from must not be after date_to.")
        return attrs


def _csv_response(filename: str, header: list[str], rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    # Excel on the office's Windows machines needs the BOM to read Sorani/Arabic as UTF-8.
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


class DashboardView(APIView):
    """Pre-aggregated home-page stats for any authenticated user (§10.1)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(dashboard_stats())


class ReportView(APIView):
    """Shared plumbing: validate the filters, then render JSON or CSV. Admin-only (§10.2)."""

    permission_classes = (IsAdmin,)

    def filters(self, request) -> dict:
        payload = ReportFilterSerializer(data=request.query_params)
        payload.is_valid(raise_exception=True)
        return payload.validated_data

    def wants_csv(self, request) -> bool:
        # Deliberately not `format` — DRF reserves that for renderer negotiation, so `?format=csv`
        # is a 404 for lack of a csv renderer rather than reaching this code at all.
        return request.query_params.get("export") == "csv"


class ProcessReportView(ReportView):
    def get(self, request):
        data = process_report(**self.filters(request))
        if not self.wants_csv(request):
            return Response(data)
        rows = [("total", "", data["total"])]
        rows += [("status", key, count) for key, count in data["by_status"].items()]
        rows += [("step", key, count) for key, count in data["by_step"].items()]
        rows += [("category", row["name"], row["count"]) for row in data["by_category"]]
        return _csv_response("processes-report.csv", ["group", "key", "count"], rows)


class UserReportView(ReportView):
    def get(self, request):
        data = user_report(**self.filters(request))
        if not self.wants_csv(request):
            return Response(data)
        rows = [
            (row["username"], row["assigned"], row["in_progress"], row["completed"])
            for row in data
        ]
        return _csv_response(
            "users-report.csv", ["username", "assigned", "in_progress", "completed"], rows
        )
