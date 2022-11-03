from datetime import timedelta

from odoo import api, fields, models


class PaymentProvider(models.Model):
    _name = "payment.provider"
    _description = "Payment Provider"

    name = fields.Char("Provider Name")
    payment_type = fields.Selection(
        [("default", "Default")], string="Provider", required=True, default="default"
    )
    start_date = fields.Date("Start Date")
    end_date = fields.Date("End Date")
    active = fields.Boolean("Provider status", default=True)
    config = fields.Serialized(string="Configuration JSON")

    adjustment_account = fields.Many2one(
        "account.account",
        string="Adjustment Account",
    )

    transaction_journal = fields.Many2one(
        "account.journal",
        string="Transaction Journal",
        help="Previously: SETTLEMENT_JOURNAL",
    )

    multi_currency = fields.Boolean(string="Multi-currency", default=False)

    settlement_journal = fields.Many2one(
        "account.journal",
        string="Settlement Journal",
        help="Previously: PAYMENT_JOURNAL_CODE and PAYOUT_JOURNAL_CODE",
    )

    inter_bank_account = fields.Many2one(
        "account.account",
        string="Inter-Bank Account",
    )

    receiveable_account = fields.Many2one(
        "account.account",
        string="Receiveable Account",
    )

    debtor_loss_account = fields.Many2one(
        "account.account", string="Debtor Loss Account"
    )

    psp_fee_account = fields.Many2one("account.account", string="PSP Fee Account")

    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.user.company_id,
        required=False,
        string="Company",
    )

    def get_all_settlements(self):
        for provider in self.env["payment.provider"].search([("active", "=", True)]):
            provider.get_settlements()

        return True

    def get_all_transactions(self):
        for provider in self.env["payment.provider"].search([("active", "=", True)]):
            provider.get_transactions()

        return True

    def get_settlements(self):
        self.ensure_one()
        if hasattr(self, "%s_get_settlements" % self.payment_type):
            return getattr(self, "%s_get_settlements" % self.payment_type)()

    def get_transactions(self):
        self.ensure_one()
        if hasattr(self, "%s_get_transactions" % self.payment_type):
            return getattr(self, "%s_get_transactions" % self.payment_type)()

    @api.model
    def date_range(self, start_date, end_date):
        for n in range(int((end_date - start_date).days)):
            yield start_date + timedelta(n)
