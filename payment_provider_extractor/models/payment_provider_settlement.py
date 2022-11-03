import contextlib
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PaymentProviderSettlement(models.Model):
    _name = "payment.provider.settlement"
    _description = "Payment Provider Settlement"

    settlement_id = fields.Char("Settlement ID", index=True)
    payment_provider_id = fields.Many2one(
        comodel_name="payment.provider", string="Payment Provider"
    )
    data = fields.Binary("Data file for settlement")
    processed = fields.Boolean("Is Processed?", default=False)
    ignore = fields.Boolean("Ignore Settlement", default=False)
    settlement_date = fields.Datetime(string="Settlement Date")
    message = fields.Text(string="Message")
    transaction_ids = fields.One2many(
        string="Transactions",
        comodel_name="payment.provider.transaction",
        inverse_name="settlement_id",
    )
    transaction_count = fields.Integer(
        compute="_compute_transaction_count",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.user.company_id,
        required=False,
        string="Company",
    )

    @api.depends("transaction_ids")
    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = len(rec.transaction_ids)

    @contextlib.contextmanager
    def session(self):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            try:
                yield new_cr
                new_cr.commit()
            except Exception as ex:
                _logger.info("Failed to write to database!")
                new_cr.rollback()
                raise ex
            finally:
                new_cr.close()

    def action_view_transactions(self):
        self.ensure_one()
        return {
            "name": _("Transactions"),
            "view_mode": "tree,form",
            "res_model": "payment.provider.transaction",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", self.transaction_ids.ids)],
        }
