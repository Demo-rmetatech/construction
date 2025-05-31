from odoo import models, fields

class CSVMissingDataWizard(models.TransientModel):
    _name = 'csv.missing.data.wizard'
    _description = 'Wizard to Display Missing Data'

    missing_data_ids = fields.One2many(
        'csv.missing.data.line', 'wizard_id', string="Missing Data"
    )

class CSVMissingDataLine(models.TransientModel):
    _name = 'csv.missing.data.line'
    _description = 'Missing Data Line'

    wizard_id = fields.Many2one('csv.missing.data.wizard', string="Wizard")
    product = fields.Char(string="Product Name")
    uom = fields.Char(string="UOM")
    error = fields.Char(string="Issue/Error")
