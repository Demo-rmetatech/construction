from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BoqMaster(models.Model):
    _name = 'boq.master'
    _description = 'BOQ Master model'
    _rec_name = 'name'
    _order="sequence asc, id"


    boq_type = fields.Selection([
            ('struct', 'Structural'),
            ('archi', 'Architectural')
        ], string='Type of BOQ')
    project_stage = fields.Char(string="Project Stages")
    boq_line_ids = fields.One2many('boq.master.line','boq_master_id', string="BOQ Line")
    name = fields.Char(string="Name", index=True)
    sequence = fields.Integer(string="Sequence", help="This sequence determines the sorting order when creating a BOQ. And 1 will be first.")

    @api.constrains('sequence')
    def _check_sequence_constraints(self):
        for record in self:
            if record.sequence < 0:
                raise ValidationError("The sequence field cannot be negative.")
            
            if record.sequence > 0:
                existing_sequences = self.search([('name','=',record.name),('boq_type','=',record.boq_type),('sequence', '=', record.sequence), ('id', '!=', record.id)])
                if existing_sequences:
                    raise ValidationError("The sequence must be unique.")