# Checklist review — unapproved drafts, 2026-10-21

Compare against the fixture files without modifying them. All arrows show fixture → draft. PD = product_data; SD = system_drawing; all = no role restriction; — = absent/null. Row IDs are stable for this review: F01–F06 and L01–L50 follow draft array order; F07 and L51 are missing fixture rows.

Mark keep/edit/delete by row ID. No reviewed checklist exists and no reviewed_at date has been set. “Added” means absent from the fixture, not validated or approved. Notes are source checks, not automatic edits.

Numeric eq/gte/lte cannot compare the draft’s string yes/available/provided values. The existing exists operator reports a failure when a claim is absent; keeping those rows requires resolving the conflict with the pass rule that unconfirmed evidence is not a failure. Generic PD/SD roles do not distinguish screw-in lamps, batteries, drivers and whole luminaires.

## 07 84 00

Draft: `data/requirements/07_84_00.draft.json`. Fixture: `data/fixtures/specs/07_84_00.json`.

| Row | Paragraph | Property | Operator | Value | Unit | Severity | Applies to | Mark / source check | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F01 | 2.02.B | voc_g_per_l | lte | 250 | g/L | major | PD | changed; 250 is also in the fixture, but is not a numeric limit stated in this PDF; confirm the applicable Rule 1168 category. |  |
| F02 | 2.02.C | astm_g21_rating | eq | 0 | — | major | PD | added; Source supports ASTM G21 rating zero. |  |
| F03 | 2.03.D | f_rating_hr | gte | — | hr | critical | PD/SD | added; data sheet can't show this: the required assembly rating comes from project drawings; null is not a comparison target. |  |
| F04 | 2.04.A.1 | t_rating_hr | eq_ref → gte | f_rating_hr → — | hr | critical → major | all → PD/SD | changed; Lost T=F: fixture eq_ref/f_rating_hr/critical became gte/null/major. |  |
| F05 | 1.04.A.1 | listing_agency | any_of | UL (FRD), FM (AG), ITS (DIR) | — | major | PD/SD | added; Listing-agency requirement; does not replace the missing test-standard row F07. |  |
| F06 | 1.03.C | warranty_years | gte | 1 | yr | major | PD | added; Unsupported warranty: 1.03.C asks for product data and states no one-year warranty; recommend delete. |  |
| F07 | — | standards | any_of | astm e814, ul 1479 | — | major | PD | missing; fixture row absent from draft |  |

Comparison totals: 4 added, 2 changed, 1 missing, 1 cannot_show.

## 26 51 00

Draft: `data/requirements/26_51_00.draft.json`. Fixture: `data/fixtures/specs/26_51_00.json`.

| Row | Paragraph | Property | Operator | Value | Unit | Severity | Applies to | Mark / source check | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L01 | 1.04.D.1.a | t_rating_hr | gte | 50000 | hours | major | PD/SD | added; Wrong property and reference: this is L70 life, not t_rating_hr; 50,000-hour threshold is at 2.02.S.3. |  |
| L02 | 2.06.B.5 | cri | gte | 80 | — | major | all → PD | changed; Fixture value retained; source is in the lamp section. Confirm applicability to integrated LED luminaires. |  |
| L03 | 1.10.B.1 | warranty_years | gte | 5 | yr → years | major | all → PD/SD | changed; LED luminaire warranty; fixture unit yr becomes years. Separate product term from executed warranty paperwork. |  |
| L04 | 1.10.B.2 | warranty_years | gte | 3 | years | major | PD | added; Screw-in lamps only; do not apply this three-year term to every luminaire. |  |
| L05 | 1.10.C.1 | warranty_years | gte | 5 | years | major | PD/SD | added; Emergency-unit batteries only; repeated generic warranty_years property needs scope. |  |
| L06 | 1.10.C.2 | warranty_years | gte | 5 | years | major | PD/SD | added; Exit/area-of-rescue batteries only; repeated generic warranty_years property needs scope. |  |
| L07 | 2.02.B.1 | listed_ul_1598 | eq | yes | — | major | PD/SD | added; UL 1598 product listing; eq yes is not supported by the current numeric eq comparator. |  |
| L08 | 2.03.A | listed_ul_924 | eq | yes | — | major | PD/SD | added; Emergency lighting only; eq yes needs a supported representation. |  |
| L09 | 2.04.A | listed_ul_924 | eq | yes | — | major | PD/SD | added; Exit signs only; duplicate property with different product scope; eq yes needs editing. |  |
| L10 | 2.09.S.1 | listed_ul_8750 | eq | yes | — | major | PD/SD | added; Paragraph should be 2.02.S.1; component listing; eq yes needs editing. |  |
| L11 | 1.04.D.1.b | tested_ies_lm79 | eq | available | — | major | PD | added; data sheet can't show this: delivery of an LM-79 test report upon request is separate paperwork. |  |
| L12 | 2.09.S.2 | tested_ies_lm80 | eq | yes | — | major | PD/SD | added; Paragraph should be 2.02.S.2; do not omit LM-79 when retaining this test-standard requirement; eq yes needs editing. |  |
| L13 | 1.04.D.2 | photometric_ies_lm63 | eq | available | — | major | PD | added; data sheet can't show this: delivery of an electronic IES LM-63 photometric file is separate paperwork. |  |
| L14 | 1.04.F.2 | dlc_listed | any_of → eq | dlc standard, dlc premium → yes | — | major | all → PD | changed; Fixture any_of [dlc standard, dlc premium] became eq yes; listing requirement is at 2.02.H, not just documentation at 1.04.F.2. |  |
| L15 | 2.09.S.4 | doe_lighting_facts | eq | yes | — | major | PD/SD | added; Paragraph should be 2.02.S.4; product label may be documented; eq yes needs editing. |  |
| L16 | 2.06.B.7 | ansi_c78_379_compliant | eq | yes | — | major | PD | added; Reflector lamps only; eq yes needs editing. |  |
| L17 | 2.09.S.5 | ansi_nema_c78_377_compliant | eq | yes | — | major | PD/SD | added; Paragraph should be 2.02.S.5; eq yes needs editing. |  |
| L18 | 2.09.S.6 | macadam_ellipse_max_step | lte | 3 | — | major | PD/SD | added; Paragraph should be 2.02.S.6; product color-consistency limit. |  |
| L19 | 2.05.B.2 | ansi_c82_ssl1_compliant | eq | yes | — | major | PD/SD | added; Driver standard; eq yes needs editing. |  |
| L20 | 2.05.B.2 | ansi_c82_77_compliant | eq | yes | — | major | PD/SD | added; Driver harmonic-emission standard; eq yes needs editing. |  |
| L21 | 2.05.C.4 | fcc_part18_compliant | eq | yes | — | major | PD/SD | added; Driver EMI/RFI standard; eq yes needs editing. |  |
| L22 | 2.05.B.4 | driver_temp_rating | eq_ref | fixture_temp_rating | — | major | PD/SD | added; data sheet can't show this: installed temperature is not supplied; source does not require equality to fixture_temp_rating. |  |
| L23 | 2.05.C.8 | driver_surge_tolerance_aic | gte | 10000 | aic | major | PD/SD | added; Source states 10,000 aic minimum; driver-specific. |  |
| L24 | 2.05.C.7 | driver_enclosure_type | eq | totally_enclosed_metallic | — | major | PD/SD | added; Driver enclosure construction; string eq cannot currently compare this value. |  |
| L25 | 2.05.C.1 | driver_dimming_range_min_percent | lte | 5 | % | major | PD/SD | added; Same dimming concept as missing fixture row L51, renamed; merge/edit explicitly rather than retain both. |  |
| L26 | 2.05.C.2 | driver_control_compat | eq | yes | — | major | PD/SD | added; data sheet can't show this: compatibility requires the project's selected dimming control. |  |
| L27 | 2.05.C.5 | driver_identical_within_type | eq | yes | — | major | PD/SD | added; data sheet can't show this: identical drivers across installed fixtures is a project-level condition. |  |
| L28 | 2.05.C.6 | driver_connection_types | eq | both_intgrl_and_remote | — | major | PD/SD | added; data sheet can't show this: complete installed connections are an execution requirement. |  |
| L29 | 2.05.C.9.a | remote_driver_location | eq | readily_accessible_dry_indoor_concealed | — | major | SD | added; data sheet can't show this: actual remote-driver installation location. |  |
| L30 | 2.05.C.9.b | remote_driver_wiring_in_conduit | eq | yes | — | major | SD | added; data sheet can't show this: actual installation of wiring in conduit. |  |
| L31 | 2.05.C.9.c | remote_driver_enclosure_chicago_plenum_rated | eq | yes | — | major | SD | added; Remote-enclosure product rating, not a generic luminaire rating; role SD is unsuitable for proving a product rating. |  |
| L32 | 2.05.C.9.d | remote_driver_distance_limit | eq_ref | manufacturer_specified_limit | — | major | SD | added; data sheet can't show this: compare actual installed distance with the manufacturer's limit; equality is not the stated rule. |  |
| L33 | 2.05.C.9.b | remote_driver_ventilated_metal_enclosure | eq | yes | — | major | SD | added; data sheet can't show this: provision of a separate ventilated enclosure in the installation. |  |
| L34 | 1.04.D.3 | input_watts | exists | — | watts | major | PD | added; Data-sheet field can show input watts; exists treats an absent claim as a failure, not unconfirmed. |  |
| L35 | 1.04.D.3 | remote_driver_mount_dist_limit | exists | — | — | major | PD | added; Remote-driver data-sheet field; duplicates L44; review absence handling. |  |
| L36 | 1.04.D.3 | remote_driver_wire_size | exists | — | awg | major | PD | added; Remote-driver data-sheet field; duplicates L45; review absence handling. |  |
| L37 | 1.04.D.3 | driver_dimming_type_range | exists | — | — | major | PD | added; Data-sheet field; overlaps numeric dimming row L25; review absence handling. |  |
| L38 | 1.04.D.4 | led_modules_per_tag | exists | — | — | major | PD | added; data sheet can't show this: coverage per project luminaire tag needs the project schedule. |  |
| L39 | 1.04.D.5 | screw_in_lamp_life_hr | gte | 20000 | hours | major | PD | added; Screw-in lamps only; 20,000-hour threshold is at 2.06.C.1.a, not 1.04.D.5. |  |
| L40 | 1.04.D.5 | screw_in_lamp_color_temp | exists | — | kelvin | major | PD | added; Screw-in lamps only; required data field, no fixed color temperature. |  |
| L41 | 1.04.D.5 | screw_in_lamp_cri | exists | — | — | major | PD | added; Screw-in lamps only; duplicates the CRI concept; review scope and absence handling. |  |
| L42 | 1.04.D.5 | screw_in_lamp_lumen_output | exists | — | lumens | major | PD | added; Screw-in lamps only; required data field, no fixed lumen target. |  |
| L43 | 1.04.D.6 | battery_charger_info | exists | — | — | major | PD | added; Emergency lighting only; describes required information without a measurable value. |  |
| L44 | 1.04.D.7 | remote_driver_mount_dist_limit | exists | — | — | major | PD | added; Remote-driver data-sheet field; duplicates L35; review absence handling. |  |
| L45 | 1.04.D.7 | remote_driver_wire_size | exists | — | awg | major | PD | added; Remote-driver data-sheet field; duplicates L36; review absence handling. |  |
| L46 | 1.04.D.8 | efficiency_data | exists | — | — | major | PD | added; Required efficiency information; no numeric minimum supplied; review absence handling. |  |
| L47 | 1.04.D.9 | special_warranty_doc | eq | provided | — | major | PD | added; data sheet can't show this: submitted special-warranty documentation is separate paperwork. |  |
| L48 | 1.04.F.1 | mercury_content_lamp_life | exists | — | — | major | PD | added; Property and text disagree: mercury_content_lamp_life versus DOE Lighting Facts; edit or delete. |  |
| L49 | 1.04.F.2 | dlc_listing_status | exists | — | — | major | PD | added; Listing-status information; overlaps L14; distinguish a missing statement from a failed listing. |  |
| L50 | 1.04.F.3 | efficacy_info | exists | — | — | major | PD | added; Required efficacy information; no numeric minimum supplied; review absence handling. |  |
| L51 | — | dim_min_percent | lte | 5 | % | major | all | missing; fixture row absent from draft; same concept is renamed at L25 |  |

Comparison totals: 47 added, 3 changed, 1 missing, 12 cannot_show.

## Source and review limits

Firestopping source control: 02_07/01/2025. Lighting source control: 04_08/09/2024. The controls match the existing project records; no spec revision change is established. The full source PDFs remain under ignored data/raw/specs/.

Firestopping 2.02.B refers to SCAQMD 1168 without stating 250 g/L; 1.03.C asks for product data, not a one-year warranty. Lighting 2.02.S.3 supplies L70 ≥50,000 h; 2.02.H supplies the applicable DLC listing requirement; 2.05.C.1 supplies the 5% dimming limit. These are review findings; fixture expectations and draft rows have not been edited.

Lighting input was 61,820 characters and the existing prompt exposed its first 60,000. That truncation is recorded rather than silently changing defaults before the live baseline.

Draft calls: firestopping $0.002106, lighting $0.010855, both json_schema with thinking off and 0 reasoning tokens. Pass ledger after drafting: $0.013187 Token Factory and 6 Tavily credits.

Kyle requested dashboard reconciliation after the c03 and c07 live runs; neither case has run live yet.
