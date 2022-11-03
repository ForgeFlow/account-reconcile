from odoo import fields, models


class PaymentProviderTransactions(models.Model):
    _name = "payment.provider.transaction"
    _description = "Payment Provider Transaction"

    transaction_id = fields.Char("Settlement ID", index=True)
    payment_provider_id = fields.Many2one(
        comodel_name="payment.provider", string="Payment Provider"
    )
    data = fields.Binary("Data file for transaction")
    processed = fields.Boolean("Is Processed?", default=False)
    ignore = fields.Boolean("Ignore Transaction", default=False)
    transaction_date = fields.Datetime(string="Transaction Date")
    transaction_type = fields.Char(string="Transaction Type")
    message = fields.Text(string="Message")
    paypal_reference_id = fields.Char("Paypal Reference ID")
    reconciled = fields.Boolean(
        string="Is Reconciled?",
        default=False,
        compute="_compute_is_reconciled",
    )
    settlement_id = fields.Many2one(
        string="Klarna Settlement ID", comodel_name="payment.provider.settlement"
    )
    bank_statement_line_ids = fields.One2many(
        string="Bank Statement Lines",
        comodel_name="account.bank.statement.line",
        inverse_name="provider_transaction_id",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.user.company_id,
        required=False,
        string="Company",
    )

    def _compute_is_reconciled(self):
        for record in self:
            if record.bank_statement_line_ids:
                account_move_line = self.env["account.move.line"].search(
                    [("statement_line_id", "=", record.bank_statement_line_ids[0].id)],
                    limit=1,
                )
                if account_move_line:
                    record.reconciled = account_move_line.reconciled
            else:
                record.reconciled = False
