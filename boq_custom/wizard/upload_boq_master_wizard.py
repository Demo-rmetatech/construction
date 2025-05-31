from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import csv
import re
import pandas as pd
from io import StringIO, BytesIO

class BoqCsvUploadWizard(models.TransientModel):
    _name = 'boq.csv.upload.wizard'
    _description = 'BOQ CSV Upload Wizard'

    csv_file = fields.Binary(string="CSV/XLSX File")
    file_name = fields.Char(string="File Name")
    can_upload = fields.Boolean(string="Can Upload?", default=False)

    @api.onchange('csv_file')
    def _onchange_csv_file(self):
        self.can_upload = False

    def action_download_boq_sample_xlsx(self):
        excel_mime_types = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # XLSX
            'application/vnd.ms-excel',  # XLS
        ]
        document = self.env['documents.document'].search([
            ('folder_id.name', '=', 'Sample BOQ'),  # Ensure folder name matches
            ('mimetype', 'in', excel_mime_types)
        ], limit=1)

        if not document:
            raise UserError("No XLSX file found in Sample BOQ folder.")

        # Return the file as a download action
        return {
            'type': 'ir.actions.act_url',
            'url': f"/documents/content/{document.id}?download=true",
            'target': 'self',
        }

    def generate_particulars(self, particulars):
        result = []
        parts = particulars.split(',')

        for part in parts:
            match = re.match(r"([A-Za-z]*\d*[A-Za-z]*)(\d+)-\1(\d+)", part.strip())
            if match:
                prefix, start_num, end_num = match.groups()
                start_num, end_num = int(start_num), int(end_num)
                result.extend([f"{prefix}{i}" for i in range(start_num, end_num + 1)])
            else:
                result.append(part.strip())

        return result

    def action_import_csv(self):
        if not self.csv_file:
            raise UserError(_("Please upload a CSV or XLSX file."))
        if not self.can_upload:
            raise UserError(_("Please Test The file Before Uploading It."))

        # Decode the file
        file_data = base64.b64decode(self.csv_file)

        try:
            # Try reading as CSV
            csv_data = file_data.decode('utf-8')
            csv_reader = csv.reader(StringIO(csv_data))
            next(csv_reader, None)  # Skip header
            data = list(csv_reader)  # Convert iterator to list
        except UnicodeDecodeError:
            # If decoding as CSV fails, assume it's an XLSX file
            excel_data = BytesIO(file_data)
            df = pd.read_excel(excel_data, engine='openpyxl')
            
            # Convert dataframe to list of lists
            data = df.fillna("").values.tolist()  # Replace NaN with empty string

        # Initialize variables
        old_project_stage = None
        boq_master = None
        boq_line = None
        old_parent_task = None
        old_sub_task = None
        old_job_work = None
        old_boq_type = None
        sequence = 1
        # Process Rows
        for row in data:
            if len(row) < 9:  # Ensure row has enough columns
                continue
            boq_type = str(row[0]).strip()
            project_stage = str(row[1]).strip()
            parent_task = str(row[2]).strip()
            sub_task = str(row[3]).strip()
            job_work = str(row[4]).strip()
            product_name = str(row[5]).strip()
            uom_name = str(row[6]).strip()
            create_product_qty_computation = str(row[7]).strip()
            particulars = str(row[8]).strip()

            # Skip empty rows
            if not any([project_stage, parent_task, sub_task, job_work, product_name]):
                continue
            
            # Check if it's a new project stage
            if project_stage and (not old_project_stage == project_stage or not old_boq_type == boq_type):
                old_project_stage = project_stage
                old_boq_type = boq_type
                old_parent_task = None
                old_sub_task = None
                old_job_work = None
                if boq_type:
                    if boq_type.lower() == 'architectural':
                        n_boq_type = 'archi'
                    elif boq_type.lower() == 'structural':
                        n_boq_type = 'struct'
                else:
                    n_boq_type = None
                boq_master = self.env['boq.master'].create({
                    'boq_type': n_boq_type,
                    'name' : self.file_name.rsplit('.', 1)[0] if '.' in self.file_name else self.file_name,
                    'project_stage': project_stage,
                    'sequence':sequence
                })
                sequence+=1

            if any([parent_task, sub_task, job_work]):
                if not parent_task:
                    parent_task = old_parent_task
                if not sub_task:
                    sub_task = old_sub_task
                if not job_work:
                    job_work = old_job_work
                old_parent_task = parent_task
                old_sub_task = sub_task
                old_job_work = job_work

            # Create BOQ Line
            if (parent_task or sub_task or job_work) and boq_master:
                boq_line = self.env['boq.master.line'].create({
                    'boq_master_id': boq_master.id,
                    'parent_task': parent_task,
                    'sub_task': sub_task,
                    'job_work': job_work,
                    'create_product_qty_computation': True if create_product_qty_computation.lower()=='yes' else False if create_product_qty_computation else False,
                })

            # Create Product if not exists
            if product_name and boq_line:
                domain = [('name','=',product_name)]
                if uom_name:
                    domain.append(('uom_po_id.name','=',uom_name))
                product = self.env['product.product'].search(domain, limit=1)
                # Add product to BOQ Line
                self.env['boq.line.product'].create({
                    'boq_line_id': boq_line.id,
                    'product_id': product.id,
                })
        
            if particulars and boq_line and create_product_qty_computation and create_product_qty_computation.lower()=='yes':
                particulars_list = self.generate_particulars(particulars)
                for particular in particulars_list:
                    self.env['qty.particular'].create({
                        'boq_line_id': boq_line.id,
                        'name': particular,
                    })

        self._save_csv_as_spreadsheet()

        # Display success message
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _save_csv_as_spreadsheet(self):
        # Get or create the folder
        folder = self.env['documents.folder'].search([('name', '=', 'uploaded BOQ')], limit=1)
        if not folder:
            folder = self.env['documents.folder'].create({'name': 'uploaded BOQ'})
        
        # Save the file in Documents as a spreadsheet
        attachment = self.env['ir.attachment'].create({
            'name': self.file_name,
            'type': 'binary',
            'datas': self.csv_file,
            'res_model': 'documents.document',
        })

        self.env['documents.document'].create({
            'name': self.file_name,
            'attachment_id': attachment.id,
            'folder_id': folder.id,
            'file_extension':'csv',
            'mimetype': 'csv'
        })


    def test_csv(self):
        # Ensure a file is uploaded
        if not self.csv_file:
            raise UserError(_("Please upload a CSV or XLSX file."))
        
        if self.file_name:
            name = self.file_name.rsplit('.', 1)[0] if '.' in self.file_name else self.file_name
            boq_id = self.env['boq.master'].search([('name','=',name)])
            if boq_id:
                raise UserError("This file has already been uploaded. Please rename the file before uploading.")

        # Decode the file
        file_data = base64.b64decode(self.csv_file)
        missing_data = []

        try:
            # Try reading as CSV with UTF-8 encoding
            csv_data = file_data.decode('utf-8')
            csv_reader = csv.reader(StringIO(csv_data))
            next(csv_reader, None)  # Skip header
            data = list(csv_reader)  # Convert iterator to list
        except UnicodeDecodeError:
            try:
                # If UTF-8 fails, assume it's an XLSX file
                excel_data = BytesIO(file_data)
                df = pd.read_excel(excel_data, engine='openpyxl')

                # Convert dataframe to list of lists
                data = df.fillna("").values.tolist()  # Replace NaN with empty string
            except Exception as e:
                raise UserError(_("Invalid file format. Please upload a valid CSV or XLSX file.\nError: %s") % str(e))

        # Process Rows
        for index, row in enumerate(data, start=2):  # Start at row 2 (since row 1 is header)
            if len(row) < 9:  # Ensure row has enough columns
                continue

            # Extract required fields
            boq_type = str(row[0]).strip()
            product_name = str(row[5]).strip()
            uom_name = str(row[6]).strip()
            particulars = str(row[8]).strip()
            if boq_type and boq_type.lower() not in ['architectural','structural']:
                missing_data.append({
                        'product': boq_type,
                        'uom': '',
                        'error': "Stage should be either 'architectural' or 'structural'."
                    })

            if not product_name and not uom_name:
                continue
            if not product_name and uom_name:
                missing_data.append({
                        'product': product_name or 'N/A',
                        'uom': uom_name,
                        'error': 'Provide Product Name'
                    })
                continue

            # Search for UOM first
            if uom_name:
                uom = self.env['uom.uom'].search([('name', '=', uom_name)], limit=1)
                if not uom:
                    missing_data.append({
                        'product': product_name,
                        'uom': uom_name,
                        'error': 'UOM Not Found'
                    })
                    continue  # Skip product check if UOM not found

                # Search for Product only if UOM is found
                product = self.env['product.product'].search([
                    ('name', '=', product_name),
                    ('uom_id', '=', uom.id)
                ], limit=1)
                if not product:
                    missing_data.append({
                        'product': product_name,
                        'uom': uom_name,
                        'error': 'Product Not Found with Given UOM.'
                    })
                # if particulars:
                #     particulars_list = self.generate_particulars(particulars)
                #     for particular in particulars_list:
                #         service_product = self.env['product.product'].search([
                #                 ('name', 'ilike', particular),
                #                 ('uom_id', '=', uom.id),
                #                 ('detailed_type','=','service')
                #             ], limit=1)
                #         if not service_product:
                #             missing_data.append({
                #                 'product': particular,
                #                 'uom': uom_name,
                #                 'error': 'Particular Not Found with Given UOM.'
                #             })
            else:
                product = self.env['product.product'].search([
                    ('name', '=', product_name)
                ], limit=1)
            
                if not product:
                    missing_data.append({
                        'product': product_name or 'N/A',
                        'uom': uom_name or 'N/A',
                        'error': 'Product Not Found'
                    })

        if missing_data:
            # Prepare table header
            unique_errors = set()
            missing_data_ids = []
            # Prepare table rows
            for item in missing_data:
                error_tuple = (item['product'], item['uom'], item['error'])
                if error_tuple not in unique_errors:
                    unique_errors.add(error_tuple)
                    missing_data_ids.append(item)
            wizard = self.env['csv.missing.data.wizard'].create({
                'missing_data_ids': [(0, 0, data) for data in missing_data_ids]
            })
            return {
                'name': "Missing Data",
                'type': 'ir.actions.act_window',
                'res_model': 'csv.missing.data.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new'
            }
        else:
            self.can_upload = True
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('All products and UOMs are valid. You can now upload.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
