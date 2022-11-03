from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    provider_transaction_id = fields.Many2one(
        "payment.provider.transaction",
        string="Payment Transaction",
    )

    fee_amount = fields.Float(
        string="Fee Amount", help="Amount of the fee for Paypal transactions"
    )
