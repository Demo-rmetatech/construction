{
    'name': 'BIR Form',
    'version': '17.1',
    'summary': 'Generate and manage BIR forms in Odoo',
    'description': """
        This module provides functionality for generating and managing BIR forms for compliance reporting.
        It includes predefined templates, views, and security configurations to facilitate BIR reporting.
    """,
    'category': 'Accounting/Reports',
    'author': 'Nioses',
    'license': 'LGPL-3',
    'depends': ['account', 'base', 'l10n_ph'],
    'data': [
        'views/account_tax_view.xml',
        'views/company_view.xml',
        'report/bir_form_template.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
