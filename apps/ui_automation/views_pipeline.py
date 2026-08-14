"""APIs for recording, compile-to-testcase, codegen, and failure diagnosis."""
from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    AICase,
    AIExecutionRecord,
    AutoFixProposal,
    FailureDiagnosis,
    RecordingSession,
    TestCase,
    TestCaseExecution,
    UIActionTrace,
    UiProject,
)
from .serializers import (
    AutoFixProposalSerializer,
    FailureDiagnosisSerializer,
    RecordingSessionSerializer,
    TestCaseSerializer,
    TestScriptSerializer,
    UIActionTraceSerializer,
)
from .services.action_trace import normalize_actions_from_trace, normalize_recording_events
from .services.codegen import export_testcase_to_script
from .services.compiler import compile_actions_to_testcase, compile_trace_to_testcase, preview_compile
from .services.diagnosis import (
    apply_test_asset_fix,
    create_defect_from_diagnosis,
    diagnose_failure,
    enrich_fix_payload,
    rollback_test_asset_fix,
)
from .services.recording import (
    finalize_and_compile,
    get_live_events,
    start_recording_session,
    stop_recording_session,
)

logger = logging.getLogger(__name__)


class UIActionTraceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UIActionTraceSerializer
    queryset = UIActionTrace.objects.all().order_by('-created_at')

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    @action(detail=True, methods=['post'])
    def compile(self, request, pk=None):
        trace = self.get_object()
        name = request.data.get('name') or f'录制用例-{trace.id}'
        description = request.data.get('description') or ''
        commit = request.data.get('commit', True)
        try:
            if not trace.normalized_actions and trace.raw_events:
                trace.normalized_actions = normalize_recording_events(trace.raw_events)
                trace.save(update_fields=['normalized_actions', 'updated_at'])
            test_case, preview = compile_trace_to_testcase(
                trace,
                name=name,
                description=description,
                created_by=request.user,
                commit=bool(commit),
            )
            data = {'preview': preview}
            if test_case:
                if commit:
                    try:
                        script, meta = export_testcase_to_script(
                            test_case, engine='playwright', force=False
                        )
                        data['script'] = TestScriptSerializer(script).data
                        data['script_meta'] = meta
                        preview = dict(preview or {})
                        preview['linked_script_id'] = script.id
                        preview['script_skipped_overwrite'] = bool(meta.get('skipped'))
                        data['preview'] = preview
                    except Exception:
                        logger.exception('sync linked script after trace compile failed')
                data['test_case'] = TestCaseSerializer(test_case).data
            return Response(data)
        except Exception as exc:
            logger.exception('compile trace failed')
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class RecordingSessionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = RecordingSessionSerializer
    queryset = RecordingSession.objects.all().order_by('-created_at')
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def create(self, request, *args, **kwargs):
        project_id = request.data.get('project_id') or request.data.get('project')
        if not project_id:
            return Response({'error': '缺少 project_id'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = UiProject.objects.get(id=project_id)
        except UiProject.DoesNotExist:
            return Response({'error': '项目不存在'}, status=status.HTTP_404_NOT_FOUND)

        session = RecordingSession.objects.create(
            project=project,
            name=request.data.get('name') or f'录制-{timezone.now().strftime("%Y%m%d%H%M%S")}',
            start_url=request.data.get('start_url') or project.base_url or '',
            status='idle',
            created_by=request.user,
        )
        try:
            start_recording_session(session)
        except Exception as exc:
            session.status = 'failed'
            session.error_message = str(exc)
            session.save(update_fields=['status', 'error_message', 'updated_at'])
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(RecordingSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        session = self.get_object()
        auto_compile = request.data.get('auto_compile', True)
        case_name = request.data.get('name') or session.name or ''
        try:
            stop_recording_session(session)
            session.refresh_from_db()
            data = {
                'session': RecordingSessionSerializer(session).data,
            }
            if session.action_trace_id:
                data['action_trace_id'] = session.action_trace_id
                data['event_count'] = len(session.action_trace.raw_events or [])
            if auto_compile and session.action_trace_id and session.status in ('stopped', 'failed'):
                try:
                    test_case, preview = finalize_and_compile(
                        session,
                        name=case_name,
                        created_by=request.user,
                        auto_compile=True,
                    )
                    data['preview'] = preview
                    if test_case:
                        data['test_case'] = TestCaseSerializer(test_case).data
                        script_id = (preview or {}).get('linked_script_id')
                        if script_id:
                            data['script_id'] = script_id
                            data['message'] = (
                                f'录制已停止，已生成回归用例 #{test_case.id} 及配套脚本 #{script_id}'
                            )
                        else:
                            data['message'] = f'录制已停止，已生成回归用例 #{test_case.id}'
                    else:
                        data['message'] = '录制已停止，但未生成用例'
                except Exception as compile_exc:
                    logger.exception('auto compile after stop failed')
                    data['compile_error'] = str(compile_exc)
                    data['message'] = f'录制已停止，但编译失败: {compile_exc}'
            elif not session.action_trace_id:
                data['message'] = session.error_message or '录制已停止，但没有操作轨迹'
            else:
                data['message'] = '录制已停止'
            return Response(data)
        except Exception as exc:
            logger.exception('stop recording failed')
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='compile')
    def compile_session(self, request, pk=None):
        """手动将已停止会话编译为 TestCase。"""
        session = self.get_object()
        try:
            test_case, preview = finalize_and_compile(
                session,
                name=request.data.get('name') or session.name,
                created_by=request.user,
                auto_compile=True,
            )
            data = {'preview': preview, 'session': RecordingSessionSerializer(session).data}
            if test_case:
                data['test_case'] = TestCaseSerializer(test_case).data
                script_id = (preview or {}).get('linked_script_id')
                if script_id:
                    data['script_id'] = script_id
            return Response(data)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        session = self.get_object()
        live = get_live_events(session.id)
        events = live or (session.action_trace.raw_events if session.action_trace_id else [])
        return Response({
            'status': session.status,
            'events': events,
            'action_trace_id': session.action_trace_id,
            'ready': bool(_get_runtime_ready(session.id)),
            'error_message': session.error_message or '',
        })


def _get_runtime_ready(session_id: int) -> bool:
    from .services.recording import _get_runtime
    return bool(_get_runtime(session_id).get('ready'))


class FailureDiagnosisViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FailureDiagnosisSerializer
    queryset = FailureDiagnosis.objects.all().prefetch_related('fix_proposals').order_by('-created_at')

    def get_queryset(self):
        qs = super().get_queryset()
        execution_type = self.request.query_params.get('execution_type')
        execution_id = self.request.query_params.get('execution_id')
        project_id = self.request.query_params.get('project') or self.request.query_params.get('project_id')
        category = self.request.query_params.get('category')
        status_q = self.request.query_params.get('status')
        if execution_type:
            qs = qs.filter(execution_type=execution_type)
        if execution_id:
            qs = qs.filter(execution_id=execution_id)
        if project_id:
            qs = qs.filter(project_id=project_id)
        if category:
            qs = qs.filter(category=category)
        if status_q:
            qs = qs.filter(status=status_q)
        return qs

    @action(detail=True, methods=['post'], url_path='apply-script-fix')
    def apply_script_fix(self, request, pk=None):
        diagnosis = self.get_object()
        proposal_id = request.data.get('proposal_id')
        proposals = diagnosis.fix_proposals.filter(target='test_asset')
        if proposal_id:
            proposals = proposals.filter(id=proposal_id)
        proposal = proposals.order_by('-created_at').first()
        if not proposal:
            return Response({'error': '没有可应用的测试侧修复提案'}, status=status.HTTP_400_BAD_REQUEST)
        payload = dict(proposal.patch_payload or {})
        for key in ('element_id', 'step_id', 'locator', 'wait_timeout', 'type', 'replace_primary', 'candidate_locators'):
            if key in request.data:
                payload[key] = request.data[key]
        evidence_ctx = {}
        if isinstance(diagnosis.evidence, dict):
            evidence_ctx = dict(diagnosis.evidence.get('context') or {})
        for key in ('element_id', 'step_id', 'locator'):
            if key in request.data:
                evidence_ctx[key] = request.data[key]
        payload = enrich_fix_payload(payload, evidence_ctx, category=diagnosis.category)
        proposal.patch_payload = payload
        proposal.save(update_fields=['patch_payload', 'updated_at'])
        run_verify = request.data.get('verify', True)
        try:
            result = apply_test_asset_fix(
                proposal, applied_by=request.user, run_verify=bool(run_verify)
            )
            if result.get('verify_status') == 'failed':
                result['hint'] = '验证失败，建议回滚修复'
            return Response(result)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='rollback-script-fix')
    def rollback_script_fix(self, request, pk=None):
        diagnosis = self.get_object()
        proposal_id = request.data.get('proposal_id')
        proposals = diagnosis.fix_proposals.filter(target='test_asset', status='applied')
        if proposal_id:
            proposals = proposals.filter(id=proposal_id)
        proposal = proposals.order_by('-applied_at', '-created_at').first()
        if not proposal:
            return Response({'error': '没有可回滚的已应用提案'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = rollback_test_asset_fix(proposal, rolled_back_by=request.user)
            return Response(result)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='create-defect')
    def create_defect(self, request, pk=None):
        diagnosis = self.get_object()
        project_id = request.data.get('project_id')
        try:
            result = create_defect_from_diagnosis(
                diagnosis, user=request.user, project_id=project_id
            )
            return Response(result)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AutoFixProposalViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AutoFixProposalSerializer
    queryset = AutoFixProposal.objects.all().order_by('-created_at')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        proposal = self.get_object()
        if proposal.target == 'test_asset':
            # approving test asset still requires apply-script-fix for safety
            proposal.status = 'approved'
        else:
            # product code: approve only — never auto-apply to repo
            proposal.status = 'approved'
        proposal.reviewed_by = request.user
        proposal.reviewed_at = timezone.now()
        proposal.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
        return Response(AutoFixProposalSerializer(proposal).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        proposal = self.get_object()
        proposal.status = 'rejected'
        proposal.reviewed_by = request.user
        proposal.reviewed_at = timezone.now()
        proposal.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
        if proposal.diagnosis_id:
            proposal.diagnosis.status = 'rejected'
            proposal.diagnosis.save(update_fields=['status', 'updated_at'])
        return Response(AutoFixProposalSerializer(proposal).data)


def persist_ai_action_trace(execution_record: AIExecutionRecord, history, *, auto_compile: bool = True) -> None:
    """Write structured action_trace after AI run; sync elements; optionally compile TestCase."""
    from .services.action_trace import (
        build_step_trace_from_history,
        extract_action_trace_from_history,
        enhance_step_info,
        normalize_actions_from_trace,
    )
    from .services.compiler import compile_actions_to_testcase
    from .services.element_sync import sync_elements_from_actions

    try:
        step_trace = build_step_trace_from_history(history)
        normalized = normalize_actions_from_trace(step_trace) if step_trace else extract_action_trace_from_history(history)
        execution_record.action_trace = normalized
        # Also refresh steps_completed with richer info when possible
        steps_raw = []
        if history is not None:
            if hasattr(history, 'history'):
                steps_raw = list(history.history or [])
            elif hasattr(history, 'steps'):
                steps_raw = list(history.steps or [])
        if steps_raw:
            execution_record.steps_completed = [
                enhance_step_info(s, i) for i, s in enumerate(steps_raw)
            ]
        execution_record.save(update_fields=['action_trace', 'steps_completed'])

        if execution_record.project_id and (normalized or step_trace):
            UIActionTrace.objects.create(
                project=execution_record.project,
                source='ai_agent',
                raw_events=step_trace or normalized,
                normalized_actions=normalized,
                ai_execution=execution_record,
                created_by=execution_record.executed_by,
            )

        # Always sync elements when project + actions exist (independent of compile)
        if execution_record.project_id and normalized:
            sync_stats = sync_elements_from_actions(
                execution_record.project,
                normalized,
                created_by=execution_record.executed_by,
                source='ai_discovered',
                skip_unstable=True,
            )
            execution_record.logs = (execution_record.logs or '') + (
                f'\n[System] 已同步 {sync_stats.get("total", 0)} 个元素到元素管理'
                f'（新建 {sync_stats.get("created", 0)}，更新 {sync_stats.get("updated", 0)}，'
                f'跳过不稳定 {sync_stats.get("skipped", 0)}）。\n'
            )
            execution_record.save(update_fields=['logs'])
        elif not execution_record.project_id:
            execution_record.logs = (execution_record.logs or '') + (
                '\n[System] 未关联 UI 项目，跳过元素同步与用例固化。\n'
            )
            execution_record.save(update_fields=['logs'])

        if not auto_compile:
            return
        if execution_record.derived_test_case_id:
            return
        if not execution_record.project_id:
            return
        if not normalized:
            execution_record.logs = (execution_record.logs or '') + (
                '\n[System] 无有效操作轨迹，跳过自动固化回归用例。\n'
            )
            execution_record.save(update_fields=['logs'])
            return

        case_name = f"{execution_record.case_name or 'AI任务'}-回归用例"
        test_case, preview = compile_actions_to_testcase(
            project=execution_record.project,
            normalized_actions=normalized,
            name=case_name,
            description=execution_record.task_description or '',
            source='ai_compiled',
            created_by=execution_record.executed_by,
            commit=True,
        )
        if test_case:
            execution_record.derived_test_case = test_case
            execution_record.logs = (execution_record.logs or '') + (
                f'\n[System] 已自动固化回归用例 #{test_case.id}（{preview.get("step_count", 0)} 步）。\n'
            )
            execution_record.save(update_fields=['derived_test_case', 'logs'])
            if execution_record.ai_case_id:
                AICase.objects.filter(id=execution_record.ai_case_id).update(
                    linked_test_case=test_case,
                    preferred_mode='script_replay',
                )
            logger.info(
                'AI execution %s auto-compiled to TestCase %s',
                execution_record.id,
                test_case.id,
            )
    except Exception:
        logger.exception('Failed to persist AI action_trace for execution %s', execution_record.id)
        try:
            execution_record.logs = (execution_record.logs or '') + (
                '\n[System] 轨迹落库/元素同步/固化失败，可在执行报告中手动重试。\n'
            )
            execution_record.save(update_fields=['logs'])
        except Exception:
            pass


def sync_ai_execution_elements(execution_record: AIExecutionRecord, request) -> Response:
    """Manually re-sync elements from action_trace into Element management."""
    from .services.element_sync import sync_elements_from_actions

    actions = execution_record.action_trace or []
    if not actions:
        return Response({'error': '该执行记录没有 action_trace'}, status=400)
    if not execution_record.project_id:
        return Response({'error': '执行记录未关联 UI 项目'}, status=400)
    try:
        stats = sync_elements_from_actions(
            execution_record.project,
            actions,
            created_by=request.user,
            source='ai_discovered',
            skip_unstable=True,
        )
        return Response({'success': True, **stats})
    except Exception as exc:
        logger.exception('sync elements failed')
        return Response({'error': str(exc)}, status=400)


def compile_ai_execution_to_testcase(execution_record: AIExecutionRecord, request) -> Response:
    name = request.data.get('name') or f"{execution_record.case_name}-回归用例"
    description = request.data.get('description') or execution_record.task_description or ''
    commit = request.data.get('commit', True)
    link_ai_case = request.data.get('link_ai_case', True)

    actions = execution_record.action_trace or []
    if not actions:
        return Response({'error': '该执行记录没有可编译的 action_trace，请重新执行 AI 任务'}, status=400)
    if not execution_record.project_id:
        return Response({'error': '执行记录未关联 UI 项目'}, status=400)

    try:
        test_case, preview = compile_actions_to_testcase(
            project=execution_record.project,
            normalized_actions=actions,
            name=name,
            description=description,
            source='ai_compiled',
            created_by=request.user,
            commit=bool(commit),
        )
        if test_case:
            execution_record.derived_test_case = test_case
            execution_record.save(update_fields=['derived_test_case'])
            if link_ai_case and execution_record.ai_case_id:
                AICase.objects.filter(id=execution_record.ai_case_id).update(
                    linked_test_case=test_case,
                    preferred_mode='script_replay',
                )
        data = {'preview': preview}
        if test_case:
            data['test_case'] = TestCaseSerializer(test_case).data
        return Response(data)
    except Exception as exc:
        logger.exception('compile ai execution failed')
        return Response({'error': str(exc)}, status=400)


def export_testcase_script_response(test_case: TestCase, request) -> Response:
    engine = (request.data.get('engine') or 'playwright').lower()
    if engine not in ('playwright', 'selenium'):
        return Response({'error': 'engine 须为 playwright 或 selenium'}, status=400)
    force = bool(request.data.get('force', False))
    script, meta = export_testcase_to_script(test_case, engine=engine, force=force)
    payload = {
        **TestScriptSerializer(script).data,
        'meta': meta,
        'sync_status': meta.get('sync_status'),
    }
    if meta.get('skipped'):
        return Response(payload, status=status.HTTP_409_CONFLICT)
    return Response(payload, status=status.HTTP_201_CREATED if meta.get('created') else status.HTTP_200_OK)


def diagnose_ai_execution(execution_record: AIExecutionRecord, request) -> Response:
    from .services.diagnosis import resolve_ai_failure_context

    context = resolve_ai_failure_context(
        execution_record,
        extra={
            'element_id': request.data.get('element_id'),
            'step_id': request.data.get('step_id'),
            'locator': request.data.get('locator'),
        },
    )
    diagnosis, proposals = diagnose_failure(
        execution_type='ai',
        execution_id=execution_record.id,
        project=execution_record.project,
        logs=execution_record.logs or '',
        error_message='',
        context=context,
        created_by=request.user,
        use_llm=request.data.get('use_llm', True),
    )
    return Response({
        'diagnosis': FailureDiagnosisSerializer(diagnosis).data,
        'proposals': AutoFixProposalSerializer(proposals, many=True).data,
    })


def diagnose_testcase_execution(execution: TestCaseExecution, request) -> Response:
    from .services.diagnosis import resolve_testcase_failure_context

    context = resolve_testcase_failure_context(
        execution,
        extra={
            'element_id': request.data.get('element_id'),
            'step_id': request.data.get('step_id'),
            'locator': request.data.get('locator'),
        },
    )
    diagnosis, proposals = diagnose_failure(
        execution_type='testcase',
        execution_id=execution.id,
        project=execution.project,
        logs=execution.execution_logs or '',
        error_message=execution.error_message or '',
        context=context,
        created_by=request.user,
        use_llm=request.data.get('use_llm', True),
    )
    return Response({
        'diagnosis': FailureDiagnosisSerializer(diagnosis).data,
        'proposals': AutoFixProposalSerializer(proposals, many=True).data,
    })
