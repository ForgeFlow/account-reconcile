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


class PaypalProvider(models.Model):
    _inherit = "payment.provider"

    access_token = None

    payment_type = fields.Selection(selection_add=[("paypal", "Paypal")], ondelete={"paypal": "cascade"},)

    paypal_endpoint_url = "https://api.paypal.com/v1/reporting"

    def paypal_get_access_token(self):

        if self.access_token:
            return self.access_token

        username = self.config["username"]
        password = self.config["password"]

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {"grant_type": "client_credentials"}

        result = r.post(
            "https://api.paypal.com/v1/oauth2/token",
            auth=HTTPBasicAuth(username, password),
            headers=headers,
            data=payload,
        )
        self.access_token = result.json()["access_token"]
        return self.access_token

    def paypal_get_transactions(self):
        # start date will be 14 day ago if not set in DB
        start_date = (
            self.start_date if self.start_date else date.today() - timedelta(days=14)
        )
        # end date will be yesterday if not set in DB
        end_date = self.end_date if self.end_date else date.today() - timedelta(days=1)

        access_token = self.paypal_get_access_token()

        for day_date in self.date_range(start_date, end_date):
            try:
                day_date = day_date.strftime("%Y-%m-%d")
                query = {
                    "transaction_currency": self.config["transaction_currency"],
                    "start_date": day_date + "T00:00:00Z",
                    "end_date": day_date + "T23:59:59Z",
                    "page_size": 500,
                    "balance_affecting_records_only": "N",
                    "transaction_status": "S",
                }

                transactions = self.paypal_get_embedded_data(
                    access_token,
                    self.paypal_endpoint_url
                    + "/transactions?"
                    + urllib.parse.urlencode(query),
                    "transaction_details",
                    objects=False,
                )

                # transactions_copy = []
                for transaction in transactions:
                    # If transaction not already in DB get corresponding transactions
                    # and insert in DB
                    if not self.env["payment.provider.transaction"].search(
                        [
                            (
                                "transaction_id",
                                "=",
                                transaction["transaction_info"]["transaction_id"],
                            )
                        ]
                    ):
                        ignore = False

                        # Authorizations can be ignored
                        if (
                            "T130"
                            in transaction["transaction_info"]["transaction_event_code"]
                        ):
                            ignore = True

                        self.env["payment.provider.transaction"].create(
                            {
                                "data": json.dumps(transaction["transaction_info"]),
                                "transaction_id": transaction["transaction_info"][
                                    "transaction_id"
                                ],
                                "payment_provider_id": self.id,
                                "ignore": ignore,
                                "company_id": self.company_id.id,
                            }
                        )
            except Exception:
                _logger.exception(
                    "Failed extraction for %s on date %s",
                    (self.name, day_date.strftime("%Y-%m-%d")),
                )

    def paypal_get_embedded_data(self, access_token, url, fieldname, objects=False):
        if not objects:
            objects = []
        headers = {"Authorization": "Bearer " + access_token}
        results = r.get(url, headers=headers)
        results_json = results.json()
        try:
            objects.extend(results_json[fieldname])
        except KeyError:
            raise Exception(results_json["details"][0]["issue"])
        next_page = ""
        for link in results_json["links"]:
            if link["rel"] == "next":
                next_page = link["href"]
                objects = self.paypal_get_embedded_data(
                    access_token, next_page, fieldname, objects
                )
        return objects
