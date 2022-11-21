from odoo import models
from odoo.exceptions import UserError


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    def _cron_bank_automatic_reconciliation(self):
        bs_ids = self.search([('state', '=', 'posted')])
        for bs in bs_ids:
            for stl in bs.line_ids:
                if not stl.is_reconciled:
                    counterpart_aml_dicts = []
                    amls = self.env['account.move.line'].search([
                        ('reconciled', '=', False),
                        ('name', 'ilike', stl.payment_ref),
                        ('parent_state', '=', 'posted')
                    ])
                    amls = amls.filtered(
                        lambda l: l.account_id.internal_type in ['receivable', 'payable'] or l.account_id.id in [bs.journal_id.payment_debit_account_id.id, bs.journal_id.payment_credit_account_id.id]
                    )
                    if len(amls) == 0:
                        continue
                    elif len(amls) == 1:
                        counterpart_aml_dicts.append({
                            'move_line': amls,
                            'name': "{}".format(amls.name),
                            'credit': abs(stl.amount) if stl.amount > 0 else 0.0,
                            'debit': abs(stl.amount) if stl.amount < 0 else 0.0,
                            'ref': amls.name,
                        })
                    else:
                        if sum(abs(amls.residual_amount)) == abs(stl.amount):
                            for aml in amls:
                                counterpart_aml_dicts.append({
                                    'move_line': aml,
                                    'name': "{}".format(aml.name),
                                    'credit': abs(aml.amount_residual) if amls.amount_residual > 0 else 0.0,
                                    'debit': abs(aml.amount_residual) if amls.amount_residual < 0 else 0.0,
                                    'ref': aml.name,
                                })
                    if len(counterpart_aml_dicts) > 0:
                        stl.process_reconciliation(counterpart_aml_dicts=counterpart_aml_dicts)
            if bs.all_lines_reconciled:
                try:
                    bs.button_validate()
                except UserError:
                    pass
