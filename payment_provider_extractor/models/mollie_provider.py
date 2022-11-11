import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

import requests as r

from odoo import fields, models


class MollieProvider(models.Model):
    _inherit = "payment.provider"

    payment_type = fields.Selection(selection_add=[("mollie", "Mollie")], ondelete={"mollie": "cascade"},)

    mollie_endpoint_url = "https://api.mollie.com/v2/"

    def mollie_get_transactions(self):

        access_token = self.config["access_token"]
        query = {"limit": 250}

        # start date will be 14 days ago if not set in DB
        start_date = (
            self.start_date if self.start_date else date.today() - timedelta(days=14)
        )

        transactions = self.mollie_get_embedded_data(
            access_token,
            self.mollie_endpoint_url + "payments?" + urllib.parse.urlencode(query),
            start_date,
            fieldname="payments",
            objects=False,
        )

        refunds = self.mollie_get_embedded_data(
            access_token,
            self.mollie_endpoint_url + "refunds?" + urllib.parse.urlencode(query),
            start_date,
            fieldname="refunds",
            objects=False,
        )

        transactions += refunds

        # transactions_copy = []
        for transaction in transactions:
            if transaction["status"] in ["open", "pending", "processing"]:
                continue

            # If transaction not already in DB get corresponding transactions
            # and insert in DB
            if not self.env["payment.provider.transaction"].search(
                [("transaction_id", "=", transaction["id"])]
            ):
                self.env["payment.provider.transaction"].create(
                    {
                        "data": json.dumps(transaction),
                        "transaction_id": transaction["id"],
                        "payment_provider_id": self.id,
                        "company_id": self.company_id.id,
                    }
                )

    def mollie_get_embedded_data(
        self, access_token, url, start_date, fieldname, objects=False
    ):
        if not objects:
            objects = []
        headers = {"Authorization": "Bearer " + access_token}
        results = r.get(url, headers=headers)
        results_json = results.json()
        objects.extend(results_json["_embedded"][fieldname])
        if results_json["_links"]["next"]:
            dates = [
                object["createdAt"] for object in results_json["_embedded"][fieldname]
            ]
            dates_obj = [
                datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M:%S+00:00")
                for date_time_str in dates
            ]
            oldest_date = min(dates_obj)
            if oldest_date.date() >= start_date:
                next_page = results_json["_links"]["next"]["href"]
                objects = self.mollie_get_embedded_data(
                    access_token, next_page, start_date, fieldname, objects
                )
        return objects

    def mollie_get_settlements(self):
        access_token = self.config["access_token"]

        query = {"limit": 50}

        # start date will be 14 days ago if not set in DB
        start_date = (
            self.start_date if self.start_date else date.today() - timedelta(days=14)
        )

        settlements = self.mollie_get_embedded_data(
            access_token,
            self.mollie_endpoint_url + "settlements?" + urllib.parse.urlencode(query),
            start_date,
            "settlements",
            objects=False,
        )

        for settlement in settlements:
            if settlement["status"] in ["open", "pending", "processing"]:
                continue

            settlements_copy = []
            transaction_url = (
                self.mollie_endpoint_url + "settlements/" + settlement["id"]
            )

            # If settlement not already in DB get corresponding transactions
            # and insert in DB
            if not self.env["payment.provider.settlement"].search(
                [("settlement_id", "=", settlement["id"])]
            ):
                settlement["payments"] = self.mollie_get_embedded_settlement_data(
                    access_token,
                    transaction_url + "/payments?",
                    "payments",
                    objects=False,
                )

                settlement["refunds"] = self.mollie_get_embedded_settlement_data(
                    access_token,
                    transaction_url + "/refunds?",
                    "refunds",
                    objects=False,
                )

                settlements_copy.append(settlement)
                settlements_json = json.dumps(settlements_copy)
                self.env["payment.provider.settlement"].create(
                    {
                        "data": settlements_json,
                        "settlement_id": settlement["id"],
                        "payment_provider_id": self.id,
                        "company_id": self.company_id.id,
                    }
                )

    def mollie_get_embedded_settlement_data(
        self, access_token, url, fieldname, objects=False
    ):
        if not objects:
            objects = []
        headers = {"Authorization": "Bearer " + access_token}
        results = r.get(url, headers=headers)
        results_json = results.json()
        objects.extend(results_json["_embedded"][fieldname])
        if results_json["_links"]["next"]:
            next_page = results_json["_links"]["next"]["href"]
            objects = self.mollie_get_embedded_settlement_data(
                access_token, next_page, fieldname, objects
            )
        return objects
