from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrContainerSim(models.Model):
    """
    Simulador de contenedor — equivale a la hoja '📊 Calculadora' del Excel.
    Permite definir cuántos contenedores de cada formato se maquilarán,
    qué mix de sabores va en cada contenedor, qué mix de canales de venta se usará,
    y proyectar ingresos y ganancias mensuales/anuales.
    """
    _name = 'hr.container.sim'
    _description = 'Happy Roots — Simulador de Contenedor y Proyección'
    _order = 'date desc, name'
    _rec_name = 'name'

    name = fields.Char('Nombre del escenario', required=True,
                        default='Proyección Mensual')
    date = fields.Date('Fecha del escenario', default=fields.Date.today)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
    ], default='draft', string='Estado')
    notes = fields.Text('Notas / Supuestos adicionales')

    # ─── 1. CONFIGURACIÓN DE PRODUCCIÓN ──────────────────────────────────────
    containers_126g_month = fields.Integer(
        'Contenedores 126g por mes', default=2,
        help='Cada contenedor 126g = 33,264 bolsas.')
    containers_340g_month = fields.Integer(
        'Contenedores 340g por mes', default=1,
        help='Cada contenedor 340g = 7,920 bolsas.')
    opex_monthly_usd = fields.Float(
        'OPEX fijo mensual (USD)', default=15000.0, digits=(10, 2),
        help='Marketing, salarios, oficina, software, contabilidad, etc.')

    # ─── 2. MIX DE CANALES DE VENTA ──────────────────────────────────────────
    channel_direct_pct = fields.Float(
        '% Direct-to-Retailer', default=0.40, digits=(6, 4),
        help='Whole Foods, Sprouts, tiendas naturistas directas.')
    channel_distributor_pct = fields.Float(
        '% Vía Distribuidor (UNFI/KeHE)', default=0.40, digits=(6, 4))
    channel_dtc_pct = fields.Float(
        '% DTC (Shopify/Amazon)', default=0.20, digits=(6, 4))
    channel_total_pct = fields.Float(
        'Total canales (%)', compute='_compute_channel_total',
        store=True, digits=(6, 4))
    channel_mix_valid = fields.Boolean(
        compute='_compute_channel_total', store=True,
        string='Mix de canales válido (suma 100%)')

    # ─── 3. MIX DE COMBOS EN CONTENEDOR 126g ─────────────────────────────────
    mix_126g_ids = fields.One2many(
        'hr.container.sim.line', 'sim_id', 'Mix contenedor 126g',
        domain=[('format_type', '=', '126g')])
    mix_340g_ids = fields.One2many(
        'hr.container.sim.line', 'sim_id', 'Mix contenedor 340g',
        domain=[('format_type', '=', '340g')])

    # ─── 4. RESULTADO POR CONTENEDOR ─────────────────────────────────────────
    # 126g
    avg_ddp_126g = fields.Float(
        'DDP promedio 126g (USD/bolsa)',
        compute='_compute_results', store=True, digits=(10, 6))
    avg_wholesale_direct_126g = fields.Float(
        'Wholesale directo promedio 126g',
        compute='_compute_results', store=True, digits=(10, 6))
    avg_wholesale_dist_126g = fields.Float(
        'Wholesale distribuidor promedio 126g',
        compute='_compute_results', store=True, digits=(10, 6))
    avg_dtc_profit_126g = fields.Float(
        'Ganancia DTC promedio 126g',
        compute='_compute_results', store=True, digits=(10, 6))
    container_cost_ddp_126g = fields.Float(
        'Costo DDP 1 contenedor 126g',
        compute='_compute_results', store=True, digits=(10, 2))
    container_revenue_126g = fields.Float(
        'Ingreso 1 contenedor 126g (mix canales)',
        compute='_compute_results', store=True, digits=(10, 2))
    container_gross_profit_126g = fields.Float(
        'Ganancia bruta 1 contenedor 126g',
        compute='_compute_results', store=True, digits=(10, 2))

    # 340g
    avg_ddp_340g = fields.Float(
        'DDP promedio 340g (USD/bolsa)',
        compute='_compute_results', store=True, digits=(10, 6))
    container_cost_ddp_340g = fields.Float(
        'Costo DDP 1 contenedor 340g',
        compute='_compute_results', store=True, digits=(10, 2))
    container_revenue_340g = fields.Float(
        'Ingreso 1 contenedor 340g (mix canales)',
        compute='_compute_results', store=True, digits=(10, 2))
    container_gross_profit_340g = fields.Float(
        'Ganancia bruta 1 contenedor 340g',
        compute='_compute_results', store=True, digits=(10, 2))

    # ─── 5. PROYECCIÓN MENSUAL Y ANUAL ───────────────────────────────────────
    total_containers_month = fields.Integer(
        compute='_compute_projection', store=True,
        string='Total contenedores/mes')
    total_bags_month = fields.Integer(
        compute='_compute_projection', store=True,
        string='Total bolsas/mes')
    total_kg_month = fields.Float(
        compute='_compute_projection', store=True,
        string='Total kg neto/mes', digits=(10, 2))
    total_cost_ddp_month = fields.Float(
        compute='_compute_projection', store=True,
        string='Costo DDP total/mes (USD)', digits=(10, 2))
    total_revenue_month = fields.Float(
        compute='_compute_projection', store=True,
        string='Ingreso total/mes (USD)', digits=(10, 2))
    total_gross_profit_month = fields.Float(
        compute='_compute_projection', store=True,
        string='Ganancia bruta/mes (USD)', digits=(10, 2))
    gross_margin_pct = fields.Float(
        compute='_compute_projection', store=True,
        string='Margen bruto (%)', digits=(6, 4))
    total_net_profit_month = fields.Float(
        compute='_compute_projection', store=True,
        string='Ganancia neta/mes (USD, después OPEX)', digits=(10, 2))
    total_revenue_year = fields.Float(
        compute='_compute_projection', store=True,
        string='Ingreso anual (USD)', digits=(10, 2))
    total_gross_profit_year = fields.Float(
        compute='_compute_projection', store=True,
        string='Ganancia bruta anual (USD)', digits=(10, 2))
    total_net_profit_year = fields.Float(
        compute='_compute_projection', store=True,
        string='Ganancia neta anual (USD)', digits=(10, 2))

    # ─── 6. BREAK-EVEN ───────────────────────────────────────────────────────
    breakeven_containers = fields.Float(
        compute='_compute_breakeven', store=True,
        string='Contenedores para break-even (OPEX)', digits=(10, 2))

    # ─── 7. ESCENARIOS CANAL 100% ────────────────────────────────────────────
    revenue_100pct_direct = fields.Float(
        compute='_compute_channel_scenarios', store=True,
        string='Ingreso si 100% direct (USD/mes)', digits=(10, 2))
    profit_100pct_direct = fields.Float(
        compute='_compute_channel_scenarios', store=True,
        string='Ganancia bruta 100% direct', digits=(10, 2))
    revenue_100pct_distributor = fields.Float(
        compute='_compute_channel_scenarios', store=True,
        string='Ingreso si 100% distribuidor', digits=(10, 2))
    profit_100pct_distributor = fields.Float(
        compute='_compute_channel_scenarios', store=True,
        string='Ganancia bruta 100% distribuidor', digits=(10, 2))
    revenue_100pct_dtc = fields.Float(
        compute='_compute_channel_scenarios', store=True,
        string='Ingreso si 100% DTC', digits=(10, 2))
    profit_100pct_dtc = fields.Float(
        compute='_compute_channel_scenarios', store=True,
        string='Ganancia bruta 100% DTC', digits=(10, 2))

    # ─── COMPUTED ─────────────────────────────────────────────────────────────
    @api.depends('channel_direct_pct', 'channel_distributor_pct', 'channel_dtc_pct')
    def _compute_channel_total(self):
        for rec in self:
            total = (rec.channel_direct_pct
                     + rec.channel_distributor_pct
                     + rec.channel_dtc_pct)
            rec.channel_total_pct = total
            rec.channel_mix_valid = abs(total - 1.0) < 0.001

    @api.depends(
        'mix_126g_ids.pct_in_mix', 'mix_126g_ids.combo_id.price_ddp',
        'mix_126g_ids.combo_id.price_wholesale_direct',
        'mix_126g_ids.combo_id.price_wholesale_distributor',
        'mix_126g_ids.combo_id.profit_dtc',
        'mix_340g_ids.pct_in_mix', 'mix_340g_ids.combo_id.price_ddp',
        'mix_340g_ids.combo_id.price_wholesale_direct',
        'mix_340g_ids.combo_id.price_wholesale_distributor',
        'mix_340g_ids.combo_id.profit_dtc',
        'channel_direct_pct', 'channel_distributor_pct', 'channel_dtc_pct',
    )
    def _compute_results(self):
        for rec in self:
            # 126g
            bags_126 = 33264
            avg_ddp_126 = sum(
                l.pct_in_mix * l.combo_id.price_ddp
                for l in rec.mix_126g_ids if l.combo_id
            )
            avg_ws_direct_126 = sum(
                l.pct_in_mix * l.combo_id.price_wholesale_direct
                for l in rec.mix_126g_ids if l.combo_id
            )
            avg_ws_dist_126 = sum(
                l.pct_in_mix * l.combo_id.price_wholesale_distributor
                for l in rec.mix_126g_ids if l.combo_id
            )
            avg_dtc_profit_126 = sum(
                l.pct_in_mix * l.combo_id.profit_dtc
                for l in rec.mix_126g_ids if l.combo_id
            )
            cost_126 = avg_ddp_126 * bags_126
            config = self.env['hr.pricing.config'].get_config()
            rev_direct_126 = avg_ws_direct_126 * bags_126
            rev_dist_126 = avg_ws_dist_126 * bags_126
            # DTC ingreso bruto = msrp * bags (HR recibe precio_dtc * (1-fees))
            avg_msrp_126 = sum(
                l.pct_in_mix * l.combo_id.price_msrp
                for l in rec.mix_126g_ids if l.combo_id
            )
            rev_dtc_126 = (
                avg_msrp_126 * (1.0 - config.dtc_fees_pct) * bags_126
            )
            revenue_126 = (
                rec.channel_direct_pct * rev_direct_126
                + rec.channel_distributor_pct * rev_dist_126
                + rec.channel_dtc_pct * rev_dtc_126
            )

            rec.avg_ddp_126g = avg_ddp_126
            rec.avg_wholesale_direct_126g = avg_ws_direct_126
            rec.avg_wholesale_dist_126g = avg_ws_dist_126
            rec.avg_dtc_profit_126g = avg_dtc_profit_126
            rec.container_cost_ddp_126g = cost_126
            rec.container_revenue_126g = revenue_126
            rec.container_gross_profit_126g = revenue_126 - cost_126

            # 340g
            bags_340 = 7920
            avg_ddp_340 = sum(
                l.pct_in_mix * l.combo_id.price_ddp
                for l in rec.mix_340g_ids if l.combo_id
            )
            avg_ws_direct_340 = sum(
                l.pct_in_mix * l.combo_id.price_wholesale_direct
                for l in rec.mix_340g_ids if l.combo_id
            )
            avg_ws_dist_340 = sum(
                l.pct_in_mix * l.combo_id.price_wholesale_distributor
                for l in rec.mix_340g_ids if l.combo_id
            )
            avg_msrp_340 = sum(
                l.pct_in_mix * l.combo_id.price_msrp
                for l in rec.mix_340g_ids if l.combo_id
            )
            cost_340 = avg_ddp_340 * bags_340
            rev_direct_340 = avg_ws_direct_340 * bags_340
            rev_dist_340 = avg_ws_dist_340 * bags_340
            rev_dtc_340 = avg_msrp_340 * (1.0 - config.dtc_fees_pct) * bags_340
            revenue_340 = (
                rec.channel_direct_pct * rev_direct_340
                + rec.channel_distributor_pct * rev_dist_340
                + rec.channel_dtc_pct * rev_dtc_340
            )
            rec.avg_ddp_340g = avg_ddp_340
            rec.container_cost_ddp_340g = cost_340
            rec.container_revenue_340g = revenue_340
            rec.container_gross_profit_340g = revenue_340 - cost_340

    @api.depends(
        'containers_126g_month', 'containers_340g_month',
        'container_cost_ddp_126g', 'container_cost_ddp_340g',
        'container_revenue_126g', 'container_revenue_340g',
        'opex_monthly_usd',
    )
    def _compute_projection(self):
        for rec in self:
            n126 = rec.containers_126g_month
            n340 = rec.containers_340g_month
            total_cont = n126 + n340
            total_bags = n126 * 33264 + n340 * 7920
            kg_126 = n126 * 33264 * 126 / 1000.0
            kg_340 = n340 * 7920 * 340 / 1000.0
            cost = n126 * rec.container_cost_ddp_126g + n340 * rec.container_cost_ddp_340g
            rev = n126 * rec.container_revenue_126g + n340 * rec.container_revenue_340g
            gross = rev - cost
            margin = gross / rev if rev else 0.0
            net = gross - rec.opex_monthly_usd

            rec.total_containers_month = total_cont
            rec.total_bags_month = total_bags
            rec.total_kg_month = kg_126 + kg_340
            rec.total_cost_ddp_month = cost
            rec.total_revenue_month = rev
            rec.total_gross_profit_month = gross
            rec.gross_margin_pct = margin
            rec.total_net_profit_month = net
            rec.total_revenue_year = rev * 12
            rec.total_gross_profit_year = gross * 12
            rec.total_net_profit_year = net * 12

    @api.depends('total_gross_profit_month', 'opex_monthly_usd',
                 'container_gross_profit_126g', 'container_gross_profit_340g',
                 'containers_126g_month', 'containers_340g_month')
    def _compute_breakeven(self):
        for rec in self:
            total_cont = (
                rec.containers_126g_month + rec.containers_340g_month
            ) or 1
            avg_profit_per_container = (
                rec.total_gross_profit_month / total_cont
                if total_cont else 0.0
            )
            rec.breakeven_containers = (
                rec.opex_monthly_usd / avg_profit_per_container
                if avg_profit_per_container > 0 else 0.0
            )

    @api.depends(
        'containers_126g_month', 'containers_340g_month',
        'container_cost_ddp_126g', 'container_cost_ddp_340g',
        'avg_wholesale_direct_126g', 'avg_wholesale_dist_126g',
    )
    def _compute_channel_scenarios(self):
        config = self.env['hr.pricing.config'].get_config()
        for rec in self:
            n126 = rec.containers_126g_month
            n340 = rec.containers_340g_month
            bags_126 = n126 * 33264
            bags_340 = n340 * 7920
            cost = (n126 * rec.container_cost_ddp_126g
                    + n340 * rec.container_cost_ddp_340g)

            # Direct
            avg_ws_340 = sum(
                l.pct_in_mix * l.combo_id.price_wholesale_direct
                for l in rec.mix_340g_ids if l.combo_id
            )
            rev_d = (
                rec.avg_wholesale_direct_126g * bags_126
                + avg_ws_340 * bags_340
            )
            rec.revenue_100pct_direct = rev_d
            rec.profit_100pct_direct = rev_d - cost

            # Distributor
            avg_ws_dist_340 = sum(
                l.pct_in_mix * l.combo_id.price_wholesale_distributor
                for l in rec.mix_340g_ids if l.combo_id
            )
            rev_dist = (
                rec.avg_wholesale_dist_126g * bags_126
                + avg_ws_dist_340 * bags_340
            )
            rec.revenue_100pct_distributor = rev_dist
            rec.profit_100pct_distributor = rev_dist - cost

            # DTC
            avg_msrp_126 = sum(
                l.pct_in_mix * l.combo_id.price_msrp
                for l in rec.mix_126g_ids if l.combo_id
            )
            avg_msrp_340 = sum(
                l.pct_in_mix * l.combo_id.price_msrp
                for l in rec.mix_340g_ids if l.combo_id
            )
            fees = config.dtc_fees_pct
            rev_dtc = (
                avg_msrp_126 * (1.0 - fees) * bags_126
                + avg_msrp_340 * (1.0 - fees) * bags_340
            )
            rec.revenue_100pct_dtc = rev_dtc
            rec.profit_100pct_dtc = rev_dtc - cost

    @api.constrains('channel_direct_pct', 'channel_distributor_pct', 'channel_dtc_pct')
    def _check_channel_mix(self):
        for rec in self:
            total = (rec.channel_direct_pct
                     + rec.channel_distributor_pct
                     + rec.channel_dtc_pct)
            if abs(total - 1.0) > 0.001:
                raise ValidationError(
                    f'El mix de canales debe sumar 100%. Actual: {total * 100:.1f}%')


class HrContainerSimLine(models.Model):
    """Línea de mix de sabores dentro de un contenedor."""
    _name = 'hr.container.sim.line'
    _description = 'Línea de mix de contenedor'
    _order = 'sequence, id'

    sim_id = fields.Many2one('hr.container.sim', 'Simulación', ondelete='cascade')
    sequence = fields.Integer(default=10)
    format_type = fields.Selection([
        ('126g', 'Formato 126g'),
        ('340g', 'Formato 340g'),
    ], required=True, string='Formato')
    combo_id = fields.Many2one('hr.product.combo', 'Combo / Sabor', required=True)
    pct_in_mix = fields.Float(
        '% en mezcla del contenedor', digits=(6, 4), default=0.125,
        help='Porcentaje de este combo dentro del contenedor. Debe sumar 100% por formato.')
    bags_in_container = fields.Float(
        'Bolsas en contenedor', compute='_compute_bags', store=True, digits=(10, 0))

    # Precios del combo (related para fácil lectura en lista)
    price_ddp = fields.Float(related='combo_id.price_ddp', string='DDP/bolsa', digits=(10, 6))
    price_wholesale_direct = fields.Float(
        related='combo_id.price_wholesale_direct', string='Wholesale directo', digits=(10, 6))
    price_wholesale_distributor = fields.Float(
        related='combo_id.price_wholesale_distributor', string='Wholesale dist.', digits=(10, 6))
    price_dtc = fields.Float(related='combo_id.price_dtc', string='Precio DTC', digits=(10, 6))

    @api.depends('pct_in_mix', 'format_type')
    def _compute_bags(self):
        for rec in self:
            total = 33264 if rec.format_type == '126g' else 7920
            rec.bags_in_container = rec.pct_in_mix * total
