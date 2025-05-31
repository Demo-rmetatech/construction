# -*- coding: utf-8 -*-

{
    'name': 'Project Management Customisation',
    'version': '17.0.1.0.2',
    'category': 'Project',
    'summary': 'Project Module Customisation',
    'description': 'Project Module Customisation',
    'author': 'Nioses Pvt. Ltd.',
    'company': 'Nioses Pvt. Ltd.',
    'maintainer': 'Nioses Pvt. Ltd.',
    'depends': ['base', 'project', 'stock', 'sale_management', 'purchase', 'account', 'sale_project', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/project_project_view.xml',
        'views/stock_location_view.xml',
        'views/boq_view.xml',
        'views/quantity_computation_view.xml',
        'views/purchase_order_view.xml',
        'views/product_view.xml',
        'views/sale_order_view.xml',
        'views/billing_statement_view.xml',
        'wizard/create_po_wizard.xml',
        'wizard/set_stage_wizard.xml',
        'wizard/billing_statement_wizard_view.xml',
        'report/reports.xml',
        'report/billing_stmnt_template.xml',
        'report/purchase_template.xml',
        'report/vendor_payment_receipt.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'project_custom/static/src/js/action_manager.js',
            'project_custom/static/src/scss/form_controller.scss',
        ]
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
