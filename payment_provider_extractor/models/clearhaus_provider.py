import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

import requests as r
from requests.auth import HTTPBasicAuth

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ClearhausProvider(models.Model):
    _inherit = "payment.provider"

    payment_type = fields.Selection(selection_add=[("clearhaus", "Clearhaus")], ondelete={"clearhaus": "cascade"},)

    clearhaus_endpoint_url = "https://merchant.clearhaus.com/"

    def clearhaus_get_access_token(self):
        client_id = self.config["client_id"]
        client_secret = self.config["client_secret"]

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "grant_type": "client_credentials",
            "audience": "https://merchant.clearhaus.com",
        }

        result = r.post(
            self.clearhaus_endpoint_url + "oauth/token",
            auth=HTTPBasicAuth(client_id, client_secret),
            headers=headers,
            data=payload,
        )
        return result.json()["access_token"]

    def clearhaus_get_transactions(self):
        # start date will be 14 days ago if not set in DB
        start_date = (
            self.start_date if self.start_date else date.today() - timedelta(days=14)
        )
        # end date will be yesterday if not set in DB
        end_date = self.end_date if self.end_date else date.today() - timedelta(days=1)

        access_token = self.clearhaus_get_access_token()

        for day_date in self.date_range(start_date, end_date):

            try:
                query = {
                    "per_page": 50,
                    "query": "date:"
                    + str(day_date)
                    + ".."
                    + str(day_date + timedelta(1))
                    + " "
                    "merchant_id:" + self.config["merchant_id"] + " "
                    "is:capture,refund",
                }

                transactions = self.clearhaus_get_embedded_data(
                    access_token,
                    self.clearhaus_endpoint_url
                    + "transactions?"
                    + urllib.parse.urlencode(query),
                    "ch:transactions",
                )

                # transactions_copy = []
                for transaction in transactions:
                    if "settlement" not in transaction:
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
            except Exception:
                _logger.exception(
                    "Failed extraction for %s on date %s",
                    (self.name, day_date.strftime("%Y-%m-%d")),
                )

    def clearhaus_get_embedded_data(self, access_token, url, fieldname, objects=False):
        if not objects:
            objects = []
        headers = {"Authorization": "Bearer " + access_token}
        results = r.get(url, headers=headers)
        results_json = results.json()
        objects.extend(results_json["_embedded"][fieldname])

        if "next" in results_json["_links"]:
            next_page = results_json["_links"]["next"]["href"]
            objects = self.clearhaus_get_embedded_data(
                access_token, next_page, fieldname, objects
            )
        return objects

    def clearhaus_get_settlements(self):
        # start date will be 14 days ago if not set in DB
        start_date = (
            self.start_date if self.start_date else date.today() - timedelta(days=14)
        )
        # end date will be yesterday if not set in DB
        end_date = self.end_date if self.end_date else date.today() - timedelta(days=1)

        access_token = self.clearhaus_get_access_token()

        for day_date in self.date_range(start_date, end_date):

            try:
                query = {
                    "per_page": 50,
                    "query": "period.end_date:>=" + str(day_date) + " "
                    "period.start_date:<=" + str(day_date + timedelta(1)) + " "
                    "merchant_id:" + self.config["merchant_id"],
                }

                settlements = self.clearhaus_get_embedded_data(
                    access_token,
                    self.clearhaus_endpoint_url
                    + "settlements?"
                    + urllib.parse.urlencode(query),
                    "ch:settlements",
                )

                settlements_copy = []
                for settlement in settlements:
                    transaction_url = settlement["_links"]["ch:transactions"][
                        "href"
                    ].replace("{?query,page,per_page}", "")

                    # If settlement not already in DB get corresponding transactions
                    # and insert in DB
                    if not self.env["payment.provider.settlement"].search(
                        [("settlement_id", "=", settlement["id"])]
                    ):
                        settlement["transactions"] = self.clearhaus_get_embedded_data(
                            access_token,
                            transaction_url,
                            "ch:transactions",
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
                        break
                        # insert only one settlement, next cron job will get the rest

            except Exception:
                _logger.exception(
                    "Failed extraction for %s on date %s",
                    (self.name, day_date.strftime("%Y-%m-%d")),
                )
