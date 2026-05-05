from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrProductCombo(models.Model):
    """
    SKU × Sabor — los 10 combos del portafolio Happy Roots.
    Contiene toda la cascada de precios: EXW → FOB → DDP → Wholesale → MSRP.
    Equivale a las hojas 'Combos EXW', 'Precios 3 Incoterms' y 'Wholesale & MSRP'.
    """
    _name = 'hr.product.combo'
    _description = 'Happy Roots — Combo (SKU × Sabor)'
    _order = 'sequence, base_id, name'
    _rec_name = 'display_name_full'

    # ─── IDENTIFICACIÓN ───────────────────────────────────────────────────────
    sequence = fields.Integer(default=10)
    internal_code = fields.Char(
        'Código interno', required=True, copy=False,
        help='Ej: YUC126-SAL, PLT126-LIM, MIX340-MED')
    name = fields.Char(
        'Nombre combo', required=True,
        help='Ej: Yuca 126g — Sal Marina')
    display_name_full = fields.Char(
        compute='_compute_display', store=True, string='Nombre completo')
    base_id = fields.Many2one(
        'hr.product.base', 'SKU base', required=True, ondelete='restrict')
    seasoning_id = fields.Many2one(
        'hr.seasoning', 'Condimento', required=True, ondelete='restrict')
    dosification_kg_per_bag = fields.Float(
        'Dosificación (kg condimento / bolsa)', required=True, digits=(10, 5),
        help='Kg de condimento aplicados por bolsa de producto terminado. '
             'Ej: 0.07 = 7g por bolsa 126g (7% sobre peso del chip).')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('discontinued', 'Descontinuado'),
    ], default='active', required=True, string='Estado')
    channel_recommendation = fields.Char(
        'Recomendación estratégica',
        help='Ej: Hero product · entrada al mercado')
    notes = fields.Text('Notas')
    product_id = fields.Many2one(
        'product.product', 'Variante de producto Odoo',
        help='Vincula este combo con la variante de producto del catálogo nativo de Odoo. '
             'Se usa para sincronizar precios con las listas de precios.')

    # Campos relacionados para facilitar vistas
    format_weight_g = fields.Integer(related='base_id.format_weight_g', store=True)
    format_weight_oz = fields.Float(related='base_id.format_weight_oz', store=True, digits=(10, 4))
    bags_per_container = fields.Integer(related='base_id.bags_per_container', store=True)
    box_type = fields.Selection(related='base_id.box_type', store=True)

    # ─── DESGLOSE EXW ────────────────────────────────────────────────────────
    cost_maquila_usd = fields.Float(
        'Maquila (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6))
    cost_bag_usd = fields.Float(
        'Bolsa (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6))
    cost_seasoning_usd = fields.Float(
        'Condimento (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6))
    cost_box_usd = fields.Float(
        'Caja prorrateo (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6))
    cost_pallet_usd = fields.Float(
        'Tarima prorrateo (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6))

    # ─── PRECIOS INCOTERMS ────────────────────────────────────────────────────
    price_exw = fields.Float(
        'EXW (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='Ex Works — precio en planta ADM Sarapiquí. '
             'Incluye: maquila + bolsa + condimento + caja + tarima.')
    logistics_origin_per_bag = fields.Float(
        'Logística origen (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='Prorrateo del costo de origen CR: trucking + handling + docs.')
    price_fob = fields.Float(
        'FOB Limón (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='Free On Board Puerto Limón. EXW + logística origen.')
    logistics_intl_per_bag = fields.Float(
        'Logística internacional + destino (USD/bolsa)',
        compute='_compute_all_prices', store=True, digits=(10, 6),
        help='Flete marítimo + seguro + trucking destino Miami → 3PL.')
    customs_per_bag = fields.Float(
        'Aranceles + fees US (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='Section 122 + HMF + broker + FDA + bond, prorrateado por bolsa.')
    price_ddp = fields.Float(
        'DDP Miami (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='Delivered Duty Paid — precio puesto en bodega Miami. '
             'FOB + flete + seguro + destino + aranceles US.')
    delta_fob_exw = fields.Float(
        'Δ FOB - EXW (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6))
    delta_ddp_fob = fields.Float(
        'Δ DDP - FOB (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6))

    # ─── PRECIOS DE VENTA ─────────────────────────────────────────────────────
    price_wholesale_direct = fields.Float(
        'Wholesale HR directo (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='Precio a retailer directo. '
             'Desde base_id — igual para todos los sabores del mismo SKU.')
    price_wholesale_distributor = fields.Float(
        'Wholesale distribuidor (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='Precio a UNFI/KeHE. Wholesale Direct × (1 - descuento_distribuidor).')
    price_msrp = fields.Float(
        'MSRP (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='Precio sugerido al consumidor final en el estante.')
    price_dtc = fields.Float(
        'Precio DTC (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='Precio en Shopify/Amazon (igual al MSRP).')
    profit_dtc = fields.Float(
        'Ganancia HR canal DTC (USD/bolsa)', compute='_compute_all_prices',
        store=True, digits=(10, 6),
        help='DTC_price × (1 - fees_plataforma) - DDP. Ganancia real de HR en DTC.')

    # ─── MÁRGENES REALES POR COMBO ────────────────────────────────────────────
    margin_pct_direct = fields.Float(
        'Margen real canal directo (%)', compute='_compute_all_prices',
        store=True, digits=(6, 4),
        help='(Wholesale - DDP) / Wholesale. Varía por sabor dentro del mismo SKU.')
    margin_pct_distributor = fields.Float(
        'Margen real canal distribuidor (%)', compute='_compute_all_prices',
        store=True, digits=(6, 4))
    margin_pct_dtc = fields.Float(
        'Margen real canal DTC (%)', compute='_compute_all_prices',
        store=True, digits=(6, 4))

    # ─── MÉTRICAS POR ONZA Y BENCHMARK ───────────────────────────────────────
    price_per_oz_msrp = fields.Float(
        'MSRP (USD/oz)', compute='_compute_all_prices',
        store=True, digits=(10, 4))
    vs_benchmark_per_oz = fields.Float(
        'vs. Benchmark (USD/oz)', compute='_compute_all_prices',
        store=True, digits=(10, 4),
        help='MSRP/oz - precio referencia benchmark. Negativo = por debajo del mercado.')
    benchmark_status = fields.Selection([
        ('competitive', 'Competitivo'),
        ('below_market', 'Bajo (oportunidad de subir precio)'),
        ('above_market', 'Premium'),
    ], compute='_compute_all_prices', store=True, string='Posición vs mercado')

    # ─── MÉTRICAS POR CONTENEDOR ──────────────────────────────────────────────
    container_total_exw = fields.Float(
        'EXW total contenedor (USD)', compute='_compute_all_prices',
        store=True, digits=(10, 2))
    container_total_fob = fields.Float(
        'FOB total contenedor (USD)', compute='_compute_all_prices',
        store=True, digits=(10, 2))
    container_total_ddp = fields.Float(
        'DDP total contenedor (USD)', compute='_compute_all_prices',
        store=True, digits=(10, 2))
    container_ddp_per_kg = fields.Float(
        'DDP por kg neto (USD/kg)', compute='_compute_all_prices',
        store=True, digits=(10, 4))

    # ─── CORE: CASCADA DE PRECIOS ─────────────────────────────────────────────
    @api.depends(
        'base_id.maquila_cost_crc_per_kg',
        'base_id.format_weight_g',
        'base_id.bag_cost_usd',
        'base_id.box_cost_usd',
        'base_id.bags_per_box',
        'base_id.bags_per_container',
        'base_id.price_wholesale_usd',
        'base_id.price_msrp_usd',
        'base_id.price_wholesale_distributor_usd',
        'seasoning_id.price_per_kg_usd',
        'dosification_kg_per_bag',
        'state',
    )
    def _compute_all_prices(self):
        config = self.env['hr.pricing.config'].get_config()
        for rec in self:
            if rec.state == 'discontinued':
                _zero_all(rec)
                continue

            tc = config.exchange_rate_crc_usd or 1.0
            weight_kg = rec.base_id.format_weight_g / 1000.0
            bags = rec.base_id.bags_per_container or 1

            # ── EXW COMPONENTS ──────────────────────────────────────────────
            maquila_usd = (
                rec.base_id.maquila_cost_crc_per_kg * weight_kg / tc
            )
            bag_usd = rec.base_id.bag_cost_usd
            seasoning_usd = (
                rec.seasoning_id.price_per_kg_usd * rec.dosification_kg_per_bag
            )
            box_usd = (
                rec.base_id.box_cost_usd / rec.base_id.bags_per_box
                if rec.base_id.bags_per_box else 0.0
            )
            pallet_usd = (
                config.pallet_cost_usd * config.pallets_per_container / bags
            )

            exw = maquila_usd + bag_usd + seasoning_usd + box_usd + pallet_usd

            # ── FOB (EXW + logística origen) ─────────────────────────────────
            origin_per_bag = config.logistics_origin_total_usd / bags
            fob = exw + origin_per_bag

            # ── DDP (FOB + international + destination + customs) ─────────────
            #   Flete marítimo
            freight_per_bag = config.freight_maritime_usd / bags
            #   Seguro (sobre FOB del contenedor completo)
            insurance_per_bag = fob * config.insurance_pct
            #   Destino
            destination_per_bag = config.trucking_destination_usd / bags

            #   Aranceles US — base CIF ≈ FOB (carga seca)
            cif_container = fob * bags
            duty_cafta = cif_container * config.cafta_duty_pct
            section_122 = (
                cif_container * config.section_122_pct
                if config.section_122_active else 0.0
            )
            hmf = cif_container * config.hmf_pct
            fixed_fees = config.fixed_fees_per_entry_usd
            customs_total = duty_cafta + section_122 + hmf + fixed_fees
            customs_per_bag = customs_total / bags

            intl_per_bag = freight_per_bag + insurance_per_bag + destination_per_bag
            ddp = fob + intl_per_bag + customs_per_bag

            # ── PRECIOS DE VENTA (vienen del SKU base) ─────────────────────
            wholesale_direct = rec.base_id.price_wholesale_usd
            wholesale_dist = rec.base_id.price_wholesale_distributor_usd
            msrp = rec.base_id.price_msrp_usd
            dtc_price = msrp
            profit_dtc = dtc_price * (1.0 - config.dtc_fees_pct) - ddp

            # ── MÁRGENES ───────────────────────────────────────────────────
            margin_direct = (
                (wholesale_direct - ddp) / wholesale_direct
                if wholesale_direct else 0.0
            )
            margin_dist = (
                (wholesale_dist - ddp) / wholesale_dist
                if wholesale_dist else 0.0
            )
            margin_dtc = profit_dtc / dtc_price if dtc_price else 0.0

            # ── USD / OZ y BENCHMARK ──────────────────────────────────────
            oz = rec.base_id.format_weight_oz or 1.0
            msrp_per_oz = msrp / oz
            vs_benchmark = msrp_per_oz - config.benchmark_ref_per_oz
            if vs_benchmark < -0.05:
                bm_status = 'below_market'
            elif vs_benchmark > 0.10:
                bm_status = 'above_market'
            else:
                bm_status = 'competitive'

            # ── MÉTRICAS CONTENEDOR ───────────────────────────────────────
            cont_exw = exw * bags
            cont_fob = fob * bags
            cont_ddp = ddp * bags
            kg_neto = rec.base_id.kg_neto_per_container or 1.0
            ddp_per_kg = cont_ddp / kg_neto

            # ── ASIGNACIÓN ────────────────────────────────────────────────
            rec.cost_maquila_usd = maquila_usd
            rec.cost_bag_usd = bag_usd
            rec.cost_seasoning_usd = seasoning_usd
            rec.cost_box_usd = box_usd
            rec.cost_pallet_usd = pallet_usd
            rec.price_exw = exw
            rec.logistics_origin_per_bag = origin_per_bag
            rec.price_fob = fob
            rec.logistics_intl_per_bag = intl_per_bag
            rec.customs_per_bag = customs_per_bag
            rec.price_ddp = ddp
            rec.delta_fob_exw = origin_per_bag
            rec.delta_ddp_fob = intl_per_bag + customs_per_bag
            rec.price_wholesale_direct = wholesale_direct
            rec.price_wholesale_distributor = wholesale_dist
            rec.price_msrp = msrp
            rec.price_dtc = dtc_price
            rec.profit_dtc = profit_dtc
            rec.margin_pct_direct = margin_direct
            rec.margin_pct_distributor = margin_dist
            rec.margin_pct_dtc = margin_dtc
            rec.price_per_oz_msrp = msrp_per_oz
            rec.vs_benchmark_per_oz = vs_benchmark
            rec.benchmark_status = bm_status
            rec.container_total_exw = cont_exw
            rec.container_total_fob = cont_fob
            rec.container_total_ddp = cont_ddp
            rec.container_ddp_per_kg = ddp_per_kg

    @api.depends('internal_code', 'name')
    def _compute_display(self):
        for rec in self:
            rec.display_name_full = (
                f'[{rec.internal_code}] {rec.name}'
                if rec.internal_code else rec.name
            )

    @api.constrains('dosification_kg_per_bag')
    def _check_dosification(self):
        for rec in self:
            if rec.dosification_kg_per_bag < 0:
                raise ValidationError('La dosificación no puede ser negativa.')

    def name_get(self):
        return [(rec.id, rec.display_name_full) for rec in self]

    def action_push_to_pricelists(self):
        """Abre el wizard para sincronizar precios con listas de precios de Odoo."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sincronizar con listas de precios',
            'res_model': 'hr.pricelist.push.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_combo_ids': [(6, 0, self.ids)]},
        }

    def action_view_product(self):
        self.ensure_one()
        if not self.product_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'Producto Odoo',
            'res_model': 'product.product',
            'view_mode': 'form',
            'res_id': self.product_id.id,
        }


def _zero_all(rec):
    """Pone en cero todos los precios calculados de un combo descontinuado."""
    price_fields = [
        'cost_maquila_usd', 'cost_bag_usd', 'cost_seasoning_usd',
        'cost_box_usd', 'cost_pallet_usd', 'price_exw',
        'logistics_origin_per_bag', 'price_fob', 'logistics_intl_per_bag',
        'customs_per_bag', 'price_ddp', 'delta_fob_exw', 'delta_ddp_fob',
        'price_wholesale_direct', 'price_wholesale_distributor', 'price_msrp',
        'price_dtc', 'profit_dtc', 'margin_pct_direct', 'margin_pct_distributor',
        'margin_pct_dtc', 'price_per_oz_msrp', 'vs_benchmark_per_oz',
        'container_total_exw', 'container_total_fob', 'container_total_ddp',
        'container_ddp_per_kg',
    ]
    for f in price_fields:
        setattr(rec, f, 0.0)
    rec.benchmark_status = 'competitive'
