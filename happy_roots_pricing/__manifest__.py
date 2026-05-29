{
    'name': 'Happy Roots — Pricing Engine',
    'version': '19.0.1.0.0',
    'category': 'Sales/Pricing',
    'summary': 'Motor de pricing EXW → FOB → DDP → Wholesale → MSRP para exportación a USA',
    'description': """
        Módulo de gestión de precios profesional para Happy Roots.
        Replica y automatiza el modelo de pricing Excel v9 directamente en Odoo 19 Community.

        Funcionalidades:
        - Cascada de precios: EXW → FOB → DDP → Wholesale → MSRP
        - 3 canales: Direct-to-Retailer, Vía Distribuidor (UNFI/KeHE), DTC
        - Gestión de supuestos globales (TC, logística, aranceles US, márgenes)
        - Catálogo de condimentos Maluquer con dosificación por SKU
        - 10 combos (SKU × sabor) con precios calculados automáticamente
        - Simulador de contenedor con proyección mensual/anual
        - Benchmark vs competencia USA
        - Sincronización automática con listas de precios nativas de Odoo
        - Reportes PDF: Resumen Ejecutivo, Ficha de Producto, Cotización Incoterms
        - Wizard de escenarios what-if sin guardar cambios
    """,
    'author': 'Happy Roots',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'sale',
        'sale_management',
        'account',
        'stock',
        'purchase',
        'mrp',
        'mrp_subcontracting',
    ],
    'data': [
        'security/hr_pricing_security.xml',
        'security/ir.model.access.csv',
        'data/hr_pricing_config_data.xml',
        'data/hr_seasoning_data.xml',
        'data/hr_product_base_data.xml',
        'data/hr_product_combo_data.xml',
        'data/hr_benchmark_data.xml',
        'data/hr_destination_data.xml',
        'data/ir_cron.xml',
        'views/hr_pricing_config_views.xml',
        'views/hr_seasoning_views.xml',
        'views/hr_product_base_views.xml',
        'views/hr_product_combo_views.xml',
        'views/hr_container_sim_views.xml',
        'views/hr_benchmark_views.xml',
        'views/hr_destination_views.xml',
        'views/hr_sale_order_views.xml',
        'views/product_template_views.xml',
        'wizard/hr_scenario_wizard_views.xml',
        'report/report_actions.xml',
        'report/report_summary.xml',
        'report/report_product_sheet.xml',
        'report/report_incoterm_quote.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'happy_roots_pricing/static/src/scss/pricing.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}
