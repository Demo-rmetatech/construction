from odoo import models, api

class AccountJournalInherit(models.Model):
    _inherit = 'account.journal'

    # Overriding the create method
    @api.model_create_multi
    def create(self, vals):
        records = super(AccountJournalInherit, self).create(vals)
        # Log a message in the chatter
        model_id = self.env['ir.model'].search([('model', '=', str(self._name))]).track_all_fields
        if model_id:
            for rec in records:
                if rec:
                    rec.message_post(body="Journal created")
        return records
