import json
import logging
from datetime import date, timedelta

import requests
from requests.auth import HTTPBasicAuth

import odoo.tools.config
from odoo import fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class KlarnaProvider(models.Model):
    _inherit = "payment.provider"

    payment_type = fields.Selection(selection_add=[("klarna_v3", "Klarna v3")], ondelete={"klarna_v3": "cascade"},)

    mode = (
        "live"
        if odoo.tools.config["db_host"]
        in [
            "odoo-prod-new.cc4lknwmecvy.eu-west-1.rds.amazonaws.com",
            # CPH and sokind prod server
        ]
        else "beta"
    )

    klarna_base_url = (
        "https://api.klarna.com/"
        if mode == "live"
        else "https://api.playground.klarna.com"
    )

    def _klarna_v3_request(self, url, data, timeout=60):
        headers = {"Content-Type": "application/json"}
        auth = HTTPBasicAuth(self.config["username"], self.config["password"])
        resp = requests.get(
            url=url, data=json.dumps(data), headers=headers, auth=auth, timeout=timeout
        )
        if resp and resp.status_code and resp.status_code == 200:
            response = resp.json()
            return response
        else:
            raise ValidationError(
                resp.json().get("description", "Could not retrieve data from Klarna")
            )

    def _get_embedded_data(self, url, transactions=False):
        if not transactions:
            transactions = []
        response = self._klarna_v3_request(url, {})
        transactions.extend(response.get("transactions", []))
        # Get pagination information
        pagination = response.get("pagination", {})
        count = int(pagination.get("count", 0))
        offset = int(pagination.get("offset", 0))
        total = int(pagination.get("total", 0))
        next_page = pagination.get("next", False)
        # If count+offset < total we go to the next page to extract missing transactions
        if (count + offset) < total and next_page:
            self._get_embedded_data(next_page, transactions)
        return transactions

    def _get_settlement_transactions(self, transactions_url):
        transactions = self._get_embedded_data(transactions_url)
        transactions_copy = []
        transaction_ids = []
        for transaction in transactions:
            # If transaction not already in DB get corresponding transactions
            # and insert in DB
            transaction_id = (
                transaction["type"]
                + "_"
                + transaction.get("detailed_type", "")
                + "_"
                + transaction["order_id"]
                + "_"
                + transaction["capture_date"]
            )
            if not self.env["payment.provider.transaction"].search(
                [
                    ("transaction_id", "=", transaction_id),
                    ("transaction_type", "=", transaction["type"]),
                ]
            ):
                transactions_copy.append(transaction)
                ignore = False
                if transaction["type"] in [
                    "FEE",
                    "COMMISSION",
                    "CREDIT",
                    "CHARGE",
                ]:
                    ignore = True
                transaction = self.env["payment.provider.transaction"].create(
                    {
                        "data": json.dumps(transaction),
                        "transaction_id": transaction_id,
                        "payment_provider_id": self.id,
                        "transaction_date": transaction["sale_date"],
                        "ignore": ignore,
                        "transaction_type": transaction["type"],
                        "company_id": self.company_id.id,
                    }
                )
                transaction_ids.append(transaction.id)
        return transactions_copy, transaction_ids

    def _extract_settlements(self, response):
        settlements = response.get("payouts", [])
        for settlement in settlements:
            # It can happen that we receive settlements of all currencies
            if settlement["currency_code"] != self.settlement_journal.currency_id.name:
                continue
            settlement_reference = settlement["payment_reference"]
            if not self.env["payment.provider.settlement"].search(
                [("settlement_id", "=", settlement_reference)]
            ):
                (
                    settlement["transactions"],
                    transaction_ids,
                ) = self._get_settlement_transactions(settlement["transactions"])
                self.env["payment.provider.settlement"].create(
                    {
                        "data": json.dumps([settlement]),
                        "settlement_id": settlement_reference,
                        "payment_provider_id": self.id,
                        "settlement_date": settlement["payout_date"],
                        "transaction_ids": [(6, 0, transaction_ids)],
                        "company_id": self.company_id.id,
                    }
                )
        return

    def klarna_v3_get_settlements(self):
        # start date will be 14 days ago if not set in DB
        start_date = (
            self.start_date if self.start_date else date.today() - timedelta(days=14)
        )
        # end date will be today if not set in DB
        end_date = self.end_date if self.end_date else date.today() - timedelta(days=1)
        currency_code = self.config.get("currency_code", False)

        for day_date in self.date_range(start_date, end_date):
            try:
                if isinstance(day_date, date):
                    start_date = day_date.strftime("%Y-%m-%d")
                    end_date = (day_date + timedelta(1)).strftime("%Y-%m-%d")

                url = self.klarna_base_url + "/settlements/v1/payouts"
                data = {
                    "start_date": start_date,
                    "end_date": end_date,
                    "currency_code": currency_code,
                    "size": 20,
                }
                response = self._klarna_v3_request(url, data)
                self._extract_settlements(response)
            except Exception:
                _logger.exception(
                    "Failed extraction for %s on date %s",
                    (self.name, day_date.strftime("%Y-%m-%d")),
                )
