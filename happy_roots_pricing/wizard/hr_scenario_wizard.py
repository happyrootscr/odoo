from odoo import api, fields, models


class HrScenarioWizard(models.TransientModel):
    """
    Simulador de escenarios what-if — equivale a la 'Tabla de Decisión'
    de la hoja Benchmark y la funcionalidad de cambio de supuestos del Excel.
    Permite cambiar TC, sección 122, márgenes y ver el impacto
    en TODOS los combos SIN guardar cambios en la configuración real.
    """
    _name = 'hr.scenario.wizard'
    _description = 'Happy Roots — Simulador de Escenarios What-If'

    config_id = fields.Many2one('hr.pricing.config', 'Configuración base')

    # ── Supuestos modificables ──────────────────────────────────────────────
    exchange_rate_crc_usd = fields.Float(
        'Tipo de cambio (CRC/USD)', digits=(12, 4))
    section_122_active = fields.Boolean('Section 122 activo')
    section_122_pct = fields.Float('Section 122 (%)', digits=(6, 4))
    margin_hr_pct = fields.Float('Margen HR (%)', digits=(6, 4))
    margin_retailer_pct = fields.Float('Margen retailer (%)', digits=(6, 4))
    freight_maritime_usd = fields.Float('Flete marítimo (USD/cont.)', digits=(10, 2))

    # ── Resultados simulados (líneas por combo) ─────────────────────────────
    result_ids = fields.One2many(
        'hr.scenario.wizard.line', 'wizard_id', 'Resultados simulados')

    scenario_label = fields.Char('Etiqueta del escenario',
                                  default='Simulación personalizada')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        config = self.env['hr.pricing.config'].get_config()
        res.update({
            'config_id': config.id,
            'exchange_rate_crc_usd': config.exchange_rate_crc_usd,
            'section_122_active': config.section_122_active,
            'section_122_pct': config.section_122_pct,
            'margin_hr_pct': config.margin_hr_pct,
            'margin_retailer_pct': config.margin_retailer_pct,
            'freight_maritime_usd': config.freight_maritime_usd,
        })
        return res

    def action_simulate(self):
        """Calcula precios con los supuestos del wizard (sin guardar en config real)."""
        self.ensure_one()
        combos = self.env['hr.product.combo'].search([('state', '=', 'active')])

        # Limpiar resultados anteriores
        self.result_ids.unlink()

        config = self.config_id or self.env['hr.pricing.config'].get_config()
        lines = []

        for combo in combos:
            tc = self.exchange_rate_crc_usd or 1.0
            weight_kg = combo.base_id.format_weight_g / 1000.0
            bags = combo.base_id.bags_per_container or 1

            # EXW
            maquila = combo.base_id.maquila_cost_crc_per_kg * weight_kg / tc
            exw = (maquila + combo.base_id.bag_cost_usd
                   + combo.seasoning_id.price_per_kg_usd * combo.dosification_kg_per_bag
                   + combo.base_id.box_cost_usd / (combo.base_id.bags_per_box or 1)
                   + config.pallet_cost_usd * config.pallets_per_container / bags)

            # FOB
            fob = exw + config.logistics_origin_total_usd / bags

            # DDP
            freight_per_bag = self.freight_maritime_usd / bags
            insurance_per_bag = fob * config.insurance_pct
            dest_per_bag = config.trucking_destination_usd / bags
            cif_container = fob * bags
            section_122 = (
                cif_container * self.section_122_pct
                if self.section_122_active else 0.0
            )
            hmf = cif_container * config.hmf_pct
            customs_per_bag = (
                section_122 + hmf + config.fixed_fees_per_entry_usd
            ) / bags
            ddp = fob + freight_per_bag + insurance_per_bag + dest_per_bag + customs_per_bag

            # Wholesale / MSRP (simplificado — usa el DDP simulado de este combo)
            margin = self.margin_hr_pct
            retailer_margin = self.margin_retailer_pct
            wholesale = ddp / (1.0 - margin) if margin < 1.0 else 0.0
            msrp = wholesale / (1.0 - retailer_margin) if retailer_margin < 1.0 else 0.0
            oz = combo.base_id.format_weight_oz or 1.0

            lines.append({
                'wizard_id': self.id,
                'combo_id': combo.id,
                'price_exw_sim': exw,
                'price_ddp_sim': ddp,
                'price_wholesale_sim': wholesale,
                'price_msrp_sim': msrp,
                'price_per_oz_sim': msrp / oz,
                'ddp_delta_pct': (
                    (ddp - combo.price_ddp) / combo.price_ddp * 100
                    if combo.price_ddp else 0.0
                ),
                'msrp_delta_pct': (
                    (msrp - combo.price_msrp) / combo.price_msrp * 100
                    if combo.price_msrp else 0.0
                ),
            })

        self.env['hr.scenario.wizard.line'].create(lines)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.scenario.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply_to_config(self):
        """Aplica los supuestos del wizard a la configuración real."""
        self.ensure_one()
        config = self.config_id or self.env['hr.pricing.config'].get_config()
        config.write({
            'exchange_rate_crc_usd': self.exchange_rate_crc_usd,
            'section_122_active': self.section_122_active,
            'section_122_pct': self.section_122_pct,
            'margin_hr_pct': self.margin_hr_pct,
            'margin_retailer_pct': self.margin_retailer_pct,
            'freight_maritime_usd': self.freight_maritime_usd,
            'last_updated': fields.Date.today(),
            'last_updated_by': self.env.user.id,
        })
        config.action_recalculate_all()
        return {'type': 'ir.actions.act_window_close'}


class HrScenarioWizardLine(models.TransientModel):
    """Línea de resultado simulado por combo."""
    _name = 'hr.scenario.wizard.line'
    _description = 'Línea de resultado simulado'
    _order = 'combo_id'

    wizard_id = fields.Many2one('hr.scenario.wizard', ondelete='cascade')
    combo_id = fields.Many2one('hr.product.combo', 'Combo', readonly=True)

    # Precios actuales (referencia)
    price_ddp_current = fields.Float(
        'DDP actual', related='combo_id.price_ddp', digits=(10, 6))
    price_msrp_current = fields.Float(
        'MSRP actual', related='combo_id.price_msrp', digits=(10, 6))

    # Precios simulados
    price_exw_sim = fields.Float('EXW simulado', digits=(10, 6))
    price_ddp_sim = fields.Float('DDP simulado', digits=(10, 6))
    price_wholesale_sim = fields.Float('Wholesale simulado', digits=(10, 6))
    price_msrp_sim = fields.Float('MSRP simulado', digits=(10, 6))
    price_per_oz_sim = fields.Float('USD/oz simulado', digits=(10, 4))

    # Deltas
    ddp_delta_pct = fields.Float('Δ DDP (%)', digits=(6, 2))
    msrp_delta_pct = fields.Float('Δ MSRP (%)', digits=(6, 2))
