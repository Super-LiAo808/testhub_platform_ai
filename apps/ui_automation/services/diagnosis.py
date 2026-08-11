"""Failure diagnosis and semi-automatic fix proposals."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_llm():
    """Reuse browser_use_text AIModelConfig via LangChain ChatOpenAI."""
    import os
    from langchain_openai import ChatOpenAI
    from apps.requirement_analysis.models import AIModelConfig

    config = AIModelConfig.objects.filter(role='browser_use_text', is_active=True).first()
    if not config:
        config = AIModelConfig.objects.filter(is_active=True).first()
    if not config:
        raise ValueError('未配置可用的 AI 模型，请先在配置中心添加模型')

    return ChatOpenAI(
        model=config.model_name,
        api_key=config.api_key or os.getenv('AUTH_TOKEN'),
        base_url=config.base_url or os.getenv('BASE_URL') or None,
        temperature=0,
    ), config


def _rule_based_diagnosis(logs: str, error_message: str = '') -> Dict[str, Any]:
    text = f'{logs or ""}\n{error_message or ""}'.lower()
    if any(k in text for k in ('timeout', 'waiting for', 'timed out', '等待超时')):
        return {
            'category': 'timing',
            'confidence': 0.7,
            'summary': '疑似等待/超时问题，可增大 wait_timeout 或增加显式等待。',
            'suggested_fix': {'type': 'increase_wait', 'wait_timeout': 15},
        }
    if any(k in text for k in ('strict mode', 'not found', 'no node', 'locator', '定位', 'unable to locate')):
        return {
            'category': 'locator_break',
            'confidence': 0.75,
            'summary': '疑似元素定位失效，建议更新主定位器或补充 backup_locators。',
            'suggested_fix': {'type': 'update_locator'},
        }
    if any(k in text for k in ('chrome', 'webdriver', 'browser', 'connection refused', 'chrome not')):
        return {
            'category': 'env',
            'confidence': 0.7,
            'summary': '疑似浏览器/驱动/环境问题。',
            'suggested_fix': {'type': 'check_environment'},
        }
    if any(k in text for k in ('assert', 'assertion', 'expected', '断言失败', '文案', '文案不符')):
        return {
            'category': 'product_bug',
            'confidence': 0.55,
            'summary': '断言失败，可能是产品行为/文案变更。',
            'suggested_fix': {'type': 'create_defect'},
        }
    return {
        'category': 'unknown',
        'confidence': 0.3,
        'summary': '无法高置信度分类，请人工查看日志与截图。',
        'suggested_fix': {},
    }


def _llm_diagnosis(logs: str, error_message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        llm, _ = _get_llm()
        prompt = f"""你是 UI 自动化失败诊断专家。根据日志判断失败类别，只返回 JSON：
{{
  "category": "locator_break|timing|env|flaky|script_bug|product_bug|unknown",
  "confidence": 0.0-1.0,
  "summary": "一句话中文摘要",
  "suggested_fix": {{
     "type": "update_locator|increase_wait|fix_step|create_defect|product_code_patch|none",
     "details": "...",
     "locator": {{"strategy":"css","value":"..."}},
     "wait_timeout": 10,
     "diff": "可选的业务代码补丁unified diff"
  }}
}}

上下文: {json.dumps(context, ensure_ascii=False)[:2000]}
错误: {(error_message or '')[:1500]}
日志尾部:
{(logs or '')[-4000:]}
"""
        resp = llm.invoke(prompt)
        content = getattr(resp, 'content', None) or str(resp)
        match = re.search(r'\{[\s\S]*\}', content)
        if not match:
            return None
        data = json.loads(match.group(0))
        if 'category' not in data:
            return None
        data.setdefault('confidence', 0.5)
        data.setdefault('summary', '')
        data.setdefault('suggested_fix', {})
        return data
    except Exception as exc:
        logger.warning('LLM diagnosis failed: %s', exc)
        return None


def diagnose_failure(
    *,
    execution_type: str,
    execution_id: int,
    project=None,
    logs: str = '',
    error_message: str = '',
    context: Optional[Dict[str, Any]] = None,
    created_by=None,
    use_llm: bool = True,
):
    from apps.ui_automation.models import AutoFixProposal, FailureDiagnosis

    context = context or {}
    result = None
    if use_llm:
        result = _llm_diagnosis(logs, error_message, context)
    if not result:
        result = _rule_based_diagnosis(logs, error_message)

    diagnosis = FailureDiagnosis.objects.create(
        execution_type=execution_type,
        execution_id=execution_id,
        project=project,
        category=result.get('category') or 'unknown',
        confidence=float(result.get('confidence') or 0),
        summary=result.get('summary') or '',
        evidence={
            'logs_tail': (logs or '')[-3000:],
            'error_message': error_message or '',
            'context': context,
        },
        suggested_fix=result.get('suggested_fix') or {},
        status='proposed',
        created_by=created_by,
    )

    proposals = []
    fix = result.get('suggested_fix') or {}
    category = diagnosis.category

    if category in ('locator_break', 'script_bug', 'timing'):
        proposals.append(AutoFixProposal.objects.create(
            diagnosis=diagnosis,
            target='test_asset',
            title=f'测试侧修复建议: {category}',
            description=diagnosis.summary,
            diff=json.dumps(fix, ensure_ascii=False, indent=2),
            patch_payload=fix,
            status='proposed',
            created_by=created_by,
        ))

    if category == 'product_bug' or fix.get('type') in ('create_defect', 'product_code_patch'):
        proposals.append(AutoFixProposal.objects.create(
            diagnosis=diagnosis,
            target='product_code',
            title='产品缺陷 / 代码补丁提案',
            description=diagnosis.summary,
            diff=fix.get('diff') or '',
            patch_payload=fix,
            status='proposed',
            created_by=created_by,
        ))

    return diagnosis, proposals


def apply_test_asset_fix(proposal, applied_by=None) -> Dict[str, Any]:
    """Apply locator/wait fixes to Element / TestCaseStep. Never touches product code."""
    from apps.ui_automation.models import Element, TestCaseStep

    if proposal.target != 'test_asset':
        raise ValueError('仅测试资产提案可直接应用')
    if proposal.status == 'applied':
        return {'message': '已应用过'}

    payload = proposal.patch_payload or {}
    fix_type = payload.get('type')
    applied = []

    element_id = payload.get('element_id')
    step_id = payload.get('step_id')

    if fix_type == 'increase_wait':
        timeout = int(payload.get('wait_timeout') or 15)
        if element_id:
            el = Element.objects.filter(id=element_id).first()
            if el:
                el.wait_timeout = timeout
                el.last_healed_at = timezone.now()
                el.heal_count = (el.heal_count or 0) + 1
                el.save(update_fields=['wait_timeout', 'last_healed_at', 'heal_count', 'updated_at'])
                applied.append(f'element#{el.id}.wait_timeout={timeout}')
        if step_id:
            step = TestCaseStep.objects.filter(id=step_id).first()
            if step:
                step.wait_time = timeout * 1000
                step.save(update_fields=['wait_time'])
                applied.append(f'step#{step.id}.wait_time={timeout * 1000}')

    elif fix_type in ('update_locator', 'add_backup_locator'):
        locator = payload.get('locator') or {}
        if element_id and locator.get('value'):
            el = Element.objects.filter(id=element_id).first()
            if el:
                backups = list(el.backup_locators or [])
                entry = {
                    'strategy': locator.get('strategy') or 'css',
                    'value': locator['value'],
                }
                if fix_type == 'update_locator' and payload.get('replace_primary'):
                    # Keep old primary as backup
                    backups.insert(0, {
                        'strategy': el.locator_strategy.name,
                        'value': el.locator_value,
                    })
                    from apps.ui_automation.services.compiler import _get_or_create_strategy
                    el.locator_strategy = _get_or_create_strategy(entry['strategy'])
                    el.locator_value = entry['value']
                else:
                    if entry not in backups:
                        backups.append(entry)
                el.backup_locators = backups
                el.last_healed_at = timezone.now()
                el.heal_count = (el.heal_count or 0) + 1
                el.save()
                applied.append(f'element#{el.id} locator updated')

    proposal.status = 'applied'
    proposal.reviewed_by = applied_by
    proposal.reviewed_at = timezone.now()
    proposal.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
    proposal.diagnosis.status = 'applied'
    proposal.diagnosis.save(update_fields=['status', 'updated_at'])

    return {'applied': applied, 'proposal_id': proposal.id}


def create_defect_from_diagnosis(diagnosis, *, user, project_id: Optional[int] = None) -> Dict[str, Any]:
    """Create apps.defects.Defect from diagnosis. Requires projects.Project id."""
    from apps.defects.models import Defect
    from apps.projects.models import Project

    if not project_id:
        # Try name match with UiProject
        if diagnosis.project_id:
            matched = Project.objects.filter(name=diagnosis.project.name).first()
            if matched:
                project_id = matched.id
    if not project_id:
        raise ValueError('创建缺陷需要 projects.Project 的 project_id（与 UI 项目不同）')

    project = Project.objects.get(id=project_id)
    defect = Defect.objects.create(
        title=(diagnosis.summary or f'UI自动化失败诊断#{diagnosis.id}')[:300],
        description=diagnosis.summary,
        reproduce_steps=json.dumps(diagnosis.evidence, ensure_ascii=False)[:5000],
        actual_result=(diagnosis.evidence or {}).get('error_message') or '',
        expected_result='用例通过',
        project=project,
        severity='major',
        priority='p2',
        defect_type='ui',
        source='ui_automation',
        reporter=user,
    )
    for proposal in diagnosis.fix_proposals.filter(target='product_code'):
        proposal.defect_id = defect.id
        proposal.save(update_fields=['defect_id', 'updated_at'])
    return {'defect_id': defect.id, 'code': defect.code}
