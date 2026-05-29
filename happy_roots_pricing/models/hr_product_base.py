from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrProductBase(models.Model):
    """
    SKU físico base (Yuca 126g, Plátano 126g, Mixto 126g, Mixto 340g).
    Contiene los costos de maquila, empaque y la configuración de contenedor.
    Todos los combos (sabores) del mismo SKU comparten el mismo precio
    Wholesale y MSRP — estándar retail US.
    """
    _name = 'hr.product.base'
    _description = 'Happy Roots — SKU Base (Formato Físico)'
    _order = 'format_weight_g, name'
    _rec_name = 'display_name_full'

    # ─── IDENTIFICACIÓN ───────────────────────────────────────────────────────
    name = fields.Char('SKU base', required=True,
                        help='Ej: Yuca 126g, Plátano 126g, Mixto 340g')
    format_weight_g = fields.Integer(
        'Peso bolsa (g)', required=True,
        help='Peso neto del producto por bolsa de venta (gramos).')
    format_weight_oz = fields.Float(
        'Peso bolsa (oz)', compute='_compute_oz', store=True, digits=(10, 4))
    display_name_full = fields.Char(
        compute='_compute_display', store=True, string='Nombre completo')
    box_type = fields.Selection([
        ('normal', 'Caja máster normal (18 bolsas)'),
        ('shipper', 'Caja Shipper display (30 bolsas)'),
    ], string='Tipo de caja', required=True, default='normal')
    active = fields.Boolean(default=True)
    channel_recommendation = fields.Text('Recomendación canal/estrategia')
    product_template_id = fields.Many2one(
        'product.template', 'Producto Odoo',
        help='Vincula este SKU base con un producto del catálogo nativo de Odoo.')

    # ─── 2. MAQUILA ADM ───────────────────────────────────────────────────────
    maquila_cost_crc_per_kg = fields.Float(
        'Costo maquila ADM (₡/kg chip terminado)', required=True, digits=(12, 2),
        help='Precio por kg de chip terminado, sin IVA, con sal base incluida. '
             'Fuente: cotización Don Mariano ADM.')
    maquila_supplier_id = fields.Many2one(
        'res.partner', 'Maquilador',
        domain=[('supplier_rank', '>', 0)],
        help='ADM — Alimentos Don Mariano S.A., Sarapiquí, Heredia.')
    maquila_quotation_date = fields.Date(
        'Fecha cotización maquila', default='2026-04-01')
    maquila_confirmed = fields.Boolean(
        'Precio confirmado', default=True,
        help='True = cotización formal Don Mariano. False = estimación.')
    maquila_notes = fields.Char(
        'Notas maquila',
        help='Ej: incluye sal base · NO incluye IVA, empaque ni condimento especial')

    # ─── 3. BOLSAS INDUPARK ───────────────────────────────────────────────────
    bag_cost_usd = fields.Float(
        'Costo bolsa laminada (USD/bolsa)', required=True, digits=(10, 6),
        help='Costo por bolsa. Se calcula como: precio_film_INDELSA (USD/kg) ÷ rendimiento (bolsas/kg). '
             'Se actualiza automáticamente al cambiar el Rendimiento INDELSA.')
    bag_rendimiento = fields.Integer(
        'Rendimiento INDELSA (bolsas/kg film)', default=0,
        help='Número de bolsas que se obtiene por kilogramo de film BOPP de INDELSA. '
             'Depende del tamaño de la bolsa y el micronaje elegido. '
             '63 micras (BOPP 20/BOPP40) — bobina 305mm×370mm: 150 bolsas/kg para formatos 126g y 155g. '
             'Al cambiar este campo se recalcula automáticamente el Costo bolsa. '
             '0 = rendimiento pendiente de cotización INDELSA para este formato.')
    bag_dimensions = fields.Char(
        'Dimensiones / especificación bolsa',
        help='Ej: 305mm bobina × 370mm · 63 micras BOPP 20/BOPP40 · INDELSA')
    bag_supplier_id = fields.Many2one(
        'res.partner', 'Proveedor bolsas',
        domain=[('supplier_rank', '>', 0)],
        help='INDELSA — Industrias Elegantes S.A. (desde mayo 2026). '
             'Contacto: Luis Salgado luiss@indelsaccr.com · Tel: 2272-1282 ext 806.')

    @api.onchange('bag_rendimiento')
    def _onchange_bag_rendimiento(self):
        if self.bag_rendimiento > 0:
            config = self.env['hr.pricing.config'].get_config()
            film_price = config.bag_film_price_usd_per_kg or 10.0
            self.bag_cost_usd = film_price / self.bag_rendimiento

    # ─── 4. CAJAS MÁSTER ─────────────────────────────────────────────────────
    box_cost_usd = fields.Float(
        'Costo caja (USD/caja)', required=True, digits=(10, 4),
        help='Caja máster normal (18 bolsas × $1.09) o '
             'Caja Shipper display (30 bolsas × $1.79). CONFIRMADO ADM.')
    bags_per_box = fields.Integer(
        'Bolsas por caja', required=True,
        help='126g = 18 bolsas/caja normal · 340g = 30 bolsas/caja Shipper.')

    # ─── 5. CONFIGURACIÓN CONTENEDOR ─────────────────────────────────────────
    bags_per_container = fields.Integer(
        'Bolsas por contenedor (40HC)', required=True,
        help='126g = 33,264 (18 × 84 × 22 pallets). '
             '340g = 7,920 (30 × 12 × 22 pallets). Tabla oficial ADM.')
    boxes_per_container = fields.Integer(
        compute='_compute_container_metrics', store=True,
        string='Cajas por contenedor')
    kg_neto_per_container = fields.Float(
        compute='_compute_container_metrics', store=True,
        string='Kg neto por contenedor', digits=(10, 3))

    # ─── 6. PRECIOS WHOLESALE/MSRP (nivel SKU) ───────────────────────────────
    margin_hr_override = fields.Boolean(
        'Margen HR personalizado', default=False,
        help='Si True, usa el margen específico de este SKU. '
             'Si False, usa el margen global de Supuestos.')
    margin_hr_custom_pct = fields.Float(
        'Margen HR personalizado (%)', digits=(6, 4),
        help='Solo aplica si "Margen HR personalizado" está activo.')
    price_wholesale_usd = fields.Float(
        'Wholesale HR (USD/bolsa)',
        compute='_compute_wholesale_msrp', store=True, digits=(10, 6),
        help='Precio que Happy Roots cobra al retailer directo. '
             'Mismo para todos los sabores del mismo SKU (estándar retail US). '
             'Calculado desde el DDP mínimo del SKU (sabor más barato).')
    price_msrp_usd = fields.Float(
        'MSRP (USD/bolsa)',
        compute='_compute_wholesale_msrp', store=True, digits=(10, 6),
        help='Manufacturer Suggested Retail Price. '
             'Lo que paga el shopper en el estante. '
             'Calculado como Wholesale / (1 - margen_retailer).')
    price_wholesale_distributor_usd = fields.Float(
        'Wholesale distribuidor (USD/bolsa)',
        compute='_compute_wholesale_msrp', store=True, digits=(10, 6),
        help='Precio a UNFI/KeHE. Wholesale Direct × (1 - descuento_distribuidor).')

    # ─── COMBOS VINCULADOS ────────────────────────────────────────────────────
    combo_ids = fields.One2many('hr.product.combo', 'base_id', 'Combos / Sabores')
    combo_count = fields.Integer(compute='_compute_combo_count', string='# Sabores')
    min_ddp_usd = fields.Float(
        'DDP mínimo (USD/bolsa)',
        compute='_compute_min_ddp', store=True, digits=(10, 6),
        help='DDP del combo más económico (base para calcular Wholesale).')

    # ─── COMPUTED ─────────────────────────────────────────────────────────────
    @api.depends('format_weight_g')
    def _compute_oz(self):
        for rec in self:
            rec.format_weight_oz = rec.format_weight_g / 28.3495

    @api.depends('name', 'format_weight_g')
    def _compute_display(self):
        for rec in self:
            rec.display_name_full = rec.name

    @api.depends('bags_per_box', 'bags_per_container')
    def _compute_container_metrics(self):
        for rec in self:
            rec.boxes_per_container = (
                rec.bags_per_container // rec.bags_per_box
                if rec.bags_per_box else 0
            )
            rec.kg_neto_per_container = (
                rec.bags_per_container * rec.format_weight_g / 1000.0
            )

    def _compute_combo_count(self):
        for rec in self:
            rec.combo_count = len(rec.combo_ids)

    @api.depends('combo_ids.price_ddp')
    def _compute_min_ddp(self):
        for rec in self:
            ddps = rec.combo_ids.filtered(
                lambda c: c.state == 'active'
            ).mapped('price_ddp')
            rec.min_ddp_usd = min(ddps) if ddps else 0.0

    @api.depends(
        'min_ddp_usd',
        'margin_hr_override', 'margin_hr_custom_pct',
    )
    def _compute_wholesale_msrp(self):
        config = self.env['hr.pricing.config'].get_config()
        for rec in self:
            margin = (
                rec.margin_hr_custom_pct
                if rec.margin_hr_override
                else config.margin_hr_pct
            )
            retailer_margin = config.margin_retailer_pct
            dist_discount = config.distributor_discount_pct

            if rec.min_ddp_usd > 0 and margin < 1.0:
                wholesale = rec.min_ddp_usd / (1.0 - margin)
            else:
                wholesale = 0.0

            rec.price_wholesale_usd = wholesale
            rec.price_wholesale_distributor_usd = wholesale * (1.0 - dist_discount)
            rec.price_msrp_usd = (
                wholesale / (1.0 - retailer_margin)
                if retailer_margin < 1.0 else 0.0
            )

    @api.constrains('bags_per_box', 'bags_per_container', 'format_weight_g')
    def _check_positive(self):
        for rec in self:
            if rec.bags_per_box <= 0:
                raise ValidationError('Bolsas por caja debe ser mayor que 0.')
            if rec.bags_per_container <= 0:
                raise ValidationError('Bolsas por contenedor debe ser mayor que 0.')
            if rec.format_weight_g <= 0:
                raise ValidationError('Peso debe ser mayor que 0.')

    def action_view_combos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Combos — {self.name}',
            'res_model': 'hr.product.combo',
            'view_mode': 'list,form',
            'domain': [('base_id', '=', self.id)],
            'context': {'default_base_id': self.id},
        }

    def name_get(self):
        return [(rec.id, rec.display_name_full) for rec in self]
