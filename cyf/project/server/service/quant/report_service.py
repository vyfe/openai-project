from __future__ import annotations

from service.quant.report_generation_service import (
    ANALYSIS_BUNDLE_VERSION,
    REPORT_DRAFT_VERSION,
    build_analysis_bundle,
    create_report_for_run,
    generate_report_draft,
    get_report,
    list_reports,
    preview_report_for_run,
    render_report_markdown,
)
from service.quant.report_prompt_service import (
    DEFAULT_REPORT_MODEL_NAME,
    DEFAULT_REPORT_TEMPLATE,
    create_prompt_template,
    delete_prompt_template,
    get_prompt_template,
    latest_prompt,
    list_prompt_templates,
    normalize_report_type,
    resolve_model_name,
    update_prompt_template,
)

