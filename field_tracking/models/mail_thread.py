# -*- coding: utf-8 -*-

from odoo import tools, models, fields

class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'
    
    @tools.ormcache("self.env.uid", "self.env.su")
    def _track_get_fields(self):
        model_alt_fields = []
        model_id = self.env['ir.model'].search([('model', '=', str(self._name))]).track_all_fields
        if model_id:
            for name, field in self._fields.items():
                if name not in ['write_date', '__last_update']:
                    model_alt_fields.append(name)
            model_fields = {name for name in model_alt_fields}
        else:
            model_fields = {name for name, field in self._fields.items() if getattr(field, 'tracking', None) or getattr(field, 'track_visibility', None)}
        return model_fields and set(self.fields_get(model_fields, attributes=()))


class IrModel(models.Model):
    _inherit = 'ir.model'

    track_all_fields = fields.Boolean(string="Track all fields", help="If enabled, all fields of this model will be tracked for changes.")
