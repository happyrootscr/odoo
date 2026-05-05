from odoo import api, fields, models


class HrBenchmarkCompetitor(models.Model):
    """
    Benchmark vs competencia USA — equivale a la hoja 'Benchmark' del Excel.
    Competidores en canal premium (Tier 1: Whole Foods/Sprouts) y
    canal étnico/Latino (Tier 2: Walmart/Sedanos).
    """
    _name = 'hr.benchmark.competitor'
    _description = 'Happy Roots — Benchmark Competidores USA'
    _order = 'tier, name'
    _rec_name = 'display_name_full'

    name = fields.Char('Marca', required=True)
    product_name = fields.Char('Nombre del producto', required=True)
    origin_country = fields.Char('País de origen', help='Ej: Colombia, Ecuador, Costa Rica, USA')
    tier = fields.Selection([
        ('1', 'Tier 1 — Premium Natural Channel'),
        ('2', 'Tier 2 — Ethnic / Latino Channel'),
    ], required=True, string='Tier de mercado',
        help='Tier 1: Whole Foods, Sprouts, Thrive Market (~$1.00-1.30/oz). '
             'Tier 2: Sedanos, Walmart, Amazon (~$0.35-1.00/oz).')
    channel = fields.Selection([
        ('whole_foods', 'Whole Foods'),
        ('sprouts', 'Sprouts'),
        ('thrive', 'Thrive Market'),
        ('walmart', 'Walmart'),
        ('amazon', 'Amazon'),
        ('publix', 'Publix'),
        ('target', 'Target'),
        ('sedanos', 'Sedanos'),
        ('other', 'Otro'),
    ], string='Canal principal')
    channel_notes = fields.Char('Notas de canal')

    weight_oz = fields.Float('Peso (oz)', required=True, digits=(10, 4))
    weight_g = fields.Float('Peso (g)', compute='_compute_weight_g', store=True, digits=(10, 2))
    msrp_usd = fields.Float('MSRP (USD)', required=True, digits=(10, 4))
    price_per_oz = fields.Float(
        'USD/oz', compute='_compute_per_oz', store=True, digits=(10, 4))
    is_bogo = fields.Boolean('Precio BOGO / promoción',
                              help='Si el precio es de oferta especial (Buy One Get One, etc.)')

    date_checked = fields.Date('Fecha verificación', default=fields.Date.today)
    source = fields.Char('Fuente', help='Ej: Publix precio regular, Whole Foods shelf, Instacart')
    source_url = fields.Char('URL fuente')
    notes = fields.Text('Notas estratégicas')
    active = fields.Boolean(default=True)
    is_direct_competitor = fields.Boolean(
        'Competidor directo', default=True,
        help='True = compite directamente con yuca/plátano chips de Happy Roots.')
    display_name_full = fields.Char(
        compute='_compute_display', store=True, string='Nombre completo')

    @api.depends('name', 'product_name')
    def _compute_display(self):
        for rec in self:
            rec.display_name_full = f'{rec.name} — {rec.product_name}'

    @api.depends('weight_oz')
    def _compute_weight_g(self):
        for rec in self:
            rec.weight_g = rec.weight_oz * 28.3495

    @api.depends('msrp_usd', 'weight_oz')
    def _compute_per_oz(self):
        for rec in self:
            rec.price_per_oz = (
                rec.msrp_usd / rec.weight_oz if rec.weight_oz else 0.0
            )

    def name_get(self):
        return [(rec.id, rec.display_name_full) for rec in self]
