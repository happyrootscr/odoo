from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrPricingConfig(models.Model):
    """
    Singleton de supuestos globales — equivale a la hoja 'Supuestos' del Excel.
    Todas las fórmulas del motor de pricing leen de este registro.
    Sólo puede existir un registro activo al mismo tiempo.
    """
    _name = 'hr.pricing.config'
    _description = 'Happy Roots — Supuestos Globales de Pricing'
    _rec_name = 'name'

    name = fields.Char(default='Configuración Global', required=True, copy=False)
    active = fields.Boolean(default=True)
    notes = fields.Text('Notas / Historial de cambios')
    last_updated = fields.Date('Última actualización', default=fields.Date.today)
    last_updated_by = fields.Many2one('res.users', 'Actualizado por',
                                      default=lambda self: self.env.user)

    # ─── 1. TIPO DE CAMBIO ────────────────────────────────────────────────────
    exchange_rate_crc_usd = fields.Float(
        'Tipo de cambio (CRC/USD)', default=455.0, digits=(12, 4),
        help='Colones costarricenses por 1 dólar US. Fuente: BCCR. '
             'Actualizar mensualmente o antes de cada cotización formal.')
    exchange_rate_source = fields.Char(
        'Fuente TC', default='BCCR · venta promedio abril 2026')

    # ─── 2. EMPAQUE TERCIARIO (tarimas) ──────────────────────────────────────
    pallet_cost_usd = fields.Float(
        'Costo tarima (stretch + pallet USD)', default=18.0, digits=(10, 4),
        help='Costo por tarima: stretch film + pallet de madera. SUPUESTO — cotizar.')
    pallets_per_container = fields.Integer(
        'Tarimas por contenedor', default=22,
        help='Configuración estándar ADM Don Mariano para contenedor 40HC.')

    # ─── 2b. EMPAQUE PRIMARIO — BOLSAS INDELSA ────────────────────────────────
    bag_film_price_usd_per_kg = fields.Float(
        'Precio film bolsa INDELSA (USD/kg)', default=10.0, digits=(10, 4),
        help='Precio por kilogramo de film BOPP de INDELSA (Industrias Elegantes S.A.). '
             'Aplica igual a todos los formatos. '
             'Costo/bolsa = precio_film ÷ rendimiento_bolsa (bolsas/kg). '
             'Cotización CR Farm — mayo 2026. Mínimo 100 kg ±10%.')

    # ─── 3. LOGÍSTICA ORIGEN (Costa Rica) ─────────────────────────────────────
    trucking_origin_usd = fields.Float(
        'Trucking Sarapiquí → Puerto Limón (USD/cont.)', default=500.0, digits=(10, 2),
        help='SUPUESTO — cotizar con 2-3 transportistas. Rango esperado $450-550.')
    handling_port_usd = fields.Float(
        'Handling portuario Limón (USD/cont.)', default=350.0, digits=(10, 2),
        help='JAPDEVA + agente portuario. Rango típico $300-400.')
    documentation_usd = fields.Float(
        'Documentación exportación (BL, CAFTA, inspecciones USD/cont.)',
        default=280.0, digits=(10, 2),
        help='Bill of Lading + certificado de origen CAFTA-DR + inspecciones fitosanitarias. '
             'Agente de aduanas CR.')
    logistics_origin_total_usd = fields.Float(
        'Total logística origen (USD/cont.)',
        compute='_compute_logistics_origin_total', store=True, digits=(10, 2))

    # ─── 4. LOGÍSTICA INTERNACIONAL ──────────────────────────────────────────
    freight_maritime_usd = fields.Float(
        'Flete marítimo port-to-port Limón → Miami (USD/cont.)', default=3900.0,
        digits=(10, 2),
        help='Estimado King Ocean D/D $4,710. Precio P2P (port-to-port) con Lisa Vázquez.')
    insurance_pct = fields.Float(
        'Seguro marítimo (% sobre FOB)', default=0.005, digits=(6, 4),
        help='Tasa típica para carga seca CR-US. 0.5% sobre valor FOB del contenedor.')
    freight_carrier = fields.Char('Naviera', default='King Ocean · contacto Lisa Vázquez')

    # ─── 5. LOGÍSTICA DESTINO USA ─────────────────────────────────────────────
    trucking_destination_usd = fields.Float(
        'Trucking Puerto Miami → bodega 3PL (USD/cont.)', default=650.0, digits=(10, 2),
        help='Rango típico Puerto Miami → 3PL sur de Florida.')
    threePL_name = fields.Char('3PL / Bodega USA', default='Por definir')

    # ─── 6. ARANCELES Y FEES USA ──────────────────────────────────────────────
    hts_code = fields.Char(
        'HTS Code', default='2008.99',
        help='Código arancelario: preparaciones de yuca/plátano fritos en aceite (chips). '
             'Verificar con broker antes del primer embarque formal.')
    cafta_duty_pct = fields.Float(
        'Duty CAFTA-DR base (% sobre CIF)', default=0.0, digits=(6, 4),
        help='0% por origen Costa Rica bajo CAFTA-DR. '
             'Requiere certificado de origen válido.')
    section_122_active = fields.Boolean(
        'Section 122 activo', default=True,
        help='Sobretasa temporal Trump. Activa feb-2026. '
             'Poner False cuando venza en julio 2026.')
    section_122_pct = fields.Float(
        'Section 122 Temporary Import Surcharge (%)', default=0.10, digits=(6, 4),
        help='10% sobre CIF. Vigente feb-jul 2026. '
             'Cambiar a 0 en Supuestos cuando venza para simular escenario post-surcharge.')
    section_122_expiry = fields.Date(
        'Vencimiento Section 122', default='2026-07-31')
    hmf_pct = fields.Float(
        'Harbor Maintenance Fee (% sobre CIF)', default=0.00125, digits=(6, 5),
        help='0.125% sobre CIF. Solo carga marítima. CAFTA no exime. '
             'USACE — Army Corps of Engineers.')
    mpf_exempt = fields.Boolean(
        'MPF exento por CAFTA-DR', default=True,
        help='Merchandise Processing Fee (0.3464% CIF) exenta bajo CAFTA-DR. '
             'Gran ventaja competitiva.')
    broker_fda_isf_usd = fields.Float(
        'Broker + ISF + FDA Prior Notice (USD/entry)', default=450.0, digits=(10, 2),
        help='Fee fijo por entrada. Incluye Customs Broker, '
             'Importer Security Filing y FDA Prior Notice.')
    entry_bond_usd = fields.Float(
        'Single Entry Bond (USD/entry)', default=150.0, digits=(10, 2),
        help='Fianza aduanal por embarque individual. '
             'Alternativa: Continuous Bond ~$500-700/año si frecuencia > 6 embarques.')
    fixed_fees_per_entry_usd = fields.Float(
        'Total fees fijos por entrada (USD)',
        compute='_compute_fixed_fees', store=True, digits=(10, 2))

    # ─── 7. MÁRGENES Y MARKUPS ────────────────────────────────────────────────
    margin_hr_pct = fields.Float(
        'Margen bruto Happy Roots (%)', default=0.4267, digits=(6, 4),
        help='Margen aplicado sobre DDP para calcular precio Wholesale al retailer directo. '
             'Equivale a: Wholesale = DDP / (1 - margen). '
             'Benchmark Miami sugiere subir a 50% para MSRP ~$3.50.')
    margin_retailer_pct = fields.Float(
        'Margen del retailer (%)', default=0.40, digits=(6, 4),
        help='Margen que el supermercado aplica. '
             'Natural channel (Whole Foods, Sprouts): 35-45%. Default 40%.')
    distributor_discount_pct = fields.Float(
        'Descuento distribuidor UNFI/KeHE (%)', default=0.20, digits=(6, 4),
        help='HR vende al distribuidor con 20% de descuento sobre el Wholesale Direct. '
             'El distribuidor revende al retailer al precio Wholesale Direct.')
    dtc_fees_pct = fields.Float(
        'Fees plataforma DTC (%)', default=0.20, digits=(6, 4),
        help='Shopify + Stripe + Amazon ≈ 20%. '
             'HR recibe: Precio_DTC × (1 - fees) - DDP.')
    dtc_margin_target_pct = fields.Float(
        'Margen objetivo DTC (%)', default=0.55, digits=(6, 4),
        help='Margen HR objetivo en canal DTC después de fees de plataforma.')

    # ─── 8. BENCHMARK REFERENCIA ──────────────────────────────────────────────
    benchmark_ref_per_oz = fields.Float(
        'Precio benchmark referencia (USD/oz)', default=1.20, digits=(6, 4),
        help='Referencia de mercado para comparar competitividad del MSRP. '
             'Tier 1 Premium promedio: $1.29/oz. Tier 2 Ethnic: $0.81/oz.')

    # ─── COMPUTED TOTALS ──────────────────────────────────────────────────────
    @api.depends('trucking_origin_usd', 'handling_port_usd', 'documentation_usd')
    def _compute_logistics_origin_total(self):
        for rec in self:
            rec.logistics_origin_total_usd = (
                rec.trucking_origin_usd
                + rec.handling_port_usd
                + rec.documentation_usd
            )

    @api.depends('broker_fda_isf_usd', 'entry_bond_usd')
    def _compute_fixed_fees(self):
        for rec in self:
            rec.fixed_fees_per_entry_usd = (
                rec.broker_fda_isf_usd + rec.entry_bond_usd
            )

    @api.constrains('margin_hr_pct', 'margin_retailer_pct', 'dtc_fees_pct',
                    'distributor_discount_pct', 'dtc_margin_target_pct')
    def _check_percentages(self):
        for rec in self:
            for fname, label in [
                ('margin_hr_pct', 'Margen HR'),
                ('margin_retailer_pct', 'Margen retailer'),
                ('dtc_fees_pct', 'Fees DTC'),
                ('distributor_discount_pct', 'Descuento distribuidor'),
            ]:
                val = getattr(rec, fname)
                if not (0.0 <= val < 1.0):
                    raise ValidationError(
                        f'{label} debe estar entre 0% y 99%. Valor actual: {val * 100:.2f}%')

    @api.model
    def get_config(self):
        """Retorna el registro singleton activo. Lo crea con defaults si no existe."""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            config = self.create({'name': 'Configuración Global'})
        return config

    def write(self, vals):
        res = super().write(vals)
        # Cuando cambia cualquier supuesto que afecte precios, recomputa todo automáticamente
        # Cuando cambia el precio de film, actualizar costo de bolsa en todas las bases
        if 'bag_film_price_usd_per_kg' in vals:
            new_price = vals['bag_film_price_usd_per_kg']
            bases = self.env['hr.product.base'].search([('bag_rendimiento', '>', 0)])
            for base in bases:
                base.bag_cost_usd = new_price / base.bag_rendimiento

        price_affecting = {
            'exchange_rate_crc_usd', 'pallet_cost_usd', 'pallets_per_container',
            'trucking_origin_usd', 'handling_port_usd', 'documentation_usd',
            'freight_maritime_usd', 'insurance_pct', 'trucking_destination_usd',
            'cafta_duty_pct', 'section_122_active', 'section_122_pct',
            'hmf_pct', 'mpf_exempt', 'broker_fda_isf_usd', 'entry_bond_usd',
            'margin_hr_pct', 'margin_retailer_pct', 'distributor_discount_pct',
            'dtc_fees_pct', 'dtc_margin_target_pct', 'bag_film_price_usd_per_kg',
        }
        if price_affecting & set(vals.keys()):
            combos = self.env['hr.product.combo'].search([('state', '=', 'active')])
            if combos:
                combos._compute_all_prices()
            # Los precios de destino dependen de combo.price_fob via @api.depends,
            # pero también de los márgenes del config. Los recomputamos explícitamente.
            dest_prices = self.env['hr.destination.price'].search([])
            if dest_prices:
                dest_prices._compute_prices()
                # Sincronizar pricelists con los nuevos precios
                dest_prices._auto_sync_pricelists()
        return res

    def action_recalculate_all(self):
        """Recálculo manual completo: combos + destinos + pricelists."""
        self.ensure_one()
        combos = self.env['hr.product.combo'].search([('state', '=', 'active')])
        combos._compute_all_prices()
        dest_prices = self.env['hr.destination.price'].search([])
        dest_prices._compute_prices()
        dest_prices._auto_sync_pricelists()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Recálculo completado',
                'message': f'{len(combos)} combos · {len(dest_prices)} precios destino · pricelists actualizadas.',
                'type': 'success',
                'sticky': False,
            },
        }

    def action_initial_setup(self):
        """
        Configuración inicial — corre UNA VEZ después de instalar el módulo.
        1. Crea product.product para cada combo activo
        2. Crea hr.destination.price para cada combo × destino
        3. Sincroniza todas las pricelists
        4. Crea BoMs si mrp está instalado
        """
        self.ensure_one()
        combos = self.env['hr.product.combo'].search([('state', '=', 'active')])
        n_products = 0
        for combo in combos:
            if not combo.product_id:
                combo._ensure_product_variant()
                n_products += 1
            combo._ensure_destination_prices()

        # Recomputar y sincronizar
        combos._compute_all_prices()
        dest_prices = self.env['hr.destination.price'].search([])
        dest_prices._compute_prices()
        dest_prices._auto_sync_pricelists()

        # BoMs si mrp está instalado
        n_boms = 0
        mrp_installed = self.env['ir.module.module'].search_count([
            ('name', '=', 'mrp'), ('state', '=', 'installed')
        ])
        if mrp_installed:
            for combo in combos:
                if combo.product_id:
                    combo._ensure_bom()
                    n_boms += 1

        msg = (
            f'Setup completado: {n_products} productos creados · '
            f'{len(dest_prices)} precios por destino · '
            f'{n_boms} BoMs generadas'
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': 'Setup inicial OK', 'message': msg,
                       'type': 'success', 'sticky': True},
        }

    @api.model
    def _cron_check_section_122(self):
        """
        Cron diario: alerta automática cuando Section 122 vence en 30 días.
        Envía notificación interna al grupo de pricing managers.
        """
        from datetime import date, timedelta
        config = self.get_config()
        if not config.section_122_active or not config.section_122_expiry:
            return

        today = date.today()
        expiry = config.section_122_expiry
        days_left = (expiry - today).days

        if 0 <= days_left <= 30:
            managers = self.env.ref(
                'happy_roots_pricing.group_hr_pricing_manager',
                raise_if_not_found=False)
            if not managers:
                return
            users = managers.users
            msg = (
                f'⚠️ Section 122 vence en {days_left} días ({expiry}). '
                f'Cuando venza, deshabilita "Section 122 activo" en Supuestos Globales. '
                f'Odoo recalculará todos los precios automáticamente.'
            )
            for user in users:
                self.env['mail.message'].create({
                    'message_type': 'notification',
                    'body': msg,
                    'partner_ids': [(4, user.partner_id.id)],
                    'subtype_id': self.env.ref('mail.mt_note').id,
                })

    def action_open_scenario_wizard(self):
        """Abre el wizard de simulación de escenarios."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Simulador de Escenarios',
            'res_model': 'hr.scenario.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_config_id': self.id},
        }
