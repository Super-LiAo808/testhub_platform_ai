# -*- coding: utf-8 -*-
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from apps.app_automation.models import (
    AppRecordingSession,
    AppProject,
    AppDevice,
    AppTestCase,
)
from apps.app_automation.services.recording import (
    start_app_recording_session,
    stop_app_recording_session,
    save_recording_as_testcase,
    enqueue_recording_event,
    get_latest_frame,
    set_recording_stream_quality,
    resolve_stream_quality,
)


class AppRecordingSessionSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    device_name = serializers.SerializerMethodField()
    test_case_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = AppRecordingSession
        fields = [
            'id', 'project', 'project_name', 'device', 'device_name', 'name',
            'status', 'ui_flow', 'screen_width', 'screen_height',
            'error_message', 'test_case', 'test_case_id',
            'started_at', 'stopped_at', 'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = [
            'status', 'ui_flow', 'screen_width', 'screen_height',
            'error_message', 'test_case', 'started_at', 'stopped_at',
            'created_at', 'updated_at', 'created_by',
        ]

    def get_device_name(self, obj):
        if not obj.device_id:
            return ''
        return obj.device.name or obj.device.device_id


class AppRecordingSessionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AppRecordingSessionSerializer
    queryset = AppRecordingSession.objects.all().select_related('project', 'device', 'test_case')

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get('project')
        if project:
            qs = qs.filter(project_id=project)
        return qs

    def create(self, request, *args, **kwargs):
        project_id = request.data.get('project_id') or request.data.get('project')
        device_id = request.data.get('device_id') or request.data.get('device')
        if not project_id or not device_id:
            return Response({'error': '需要 project_id 与 device_id'}, status=400)
        try:
            project = AppProject.objects.get(id=project_id)
            device = AppDevice.objects.get(id=device_id)
        except (AppProject.DoesNotExist, AppDevice.DoesNotExist):
            return Response({'error': '项目或设备不存在'}, status=404)

        session = AppRecordingSession.objects.create(
            project=project,
            device=device,
            name=request.data.get('name') or f'APP录制-{timezone.now().strftime("%Y%m%d%H%M%S")}',
            status='idle',
            created_by=request.user,
        )
        stream_quality = request.data.get('stream_quality') or 'balanced'
        try:
            # Validate early for clearer error
            resolve_stream_quality(stream_quality)
            start_app_recording_session(session, stream_quality=stream_quality)
        except Exception as exc:
            err = str(exc)
            # Surface Appium install / PATH hints clearly for the frontend
            if 'Appium' in err or 'appium' in err.lower():
                if '请' not in err:
                    err = (
                        f'{err}。请确认已安装 Node.js 与 Appium '
                        '（npm i -g appium && appium driver install uiautomator2），'
                        '并在 APP 自动化配置中检查 Server 地址与启动命令。'
                    )
            session.status = 'failed'
            session.error_message = err[:2000]
            session.save(update_fields=['status', 'error_message', 'updated_at'])
            return Response({'error': err}, status=500)
        session.refresh_from_db()
        return Response(AppRecordingSessionSerializer(session).data, status=201)

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        session = self.get_object()
        auto_save = request.data.get('auto_save', True)
        case_name = request.data.get('name') or session.name
        try:
            stop_app_recording_session(session)
            session.refresh_from_db()
            data = {'session': AppRecordingSessionSerializer(session).data}
            if auto_save and session.ui_flow:
                try:
                    case = save_recording_as_testcase(
                        session, name=case_name, created_by=request.user
                    )
                    data['test_case'] = {
                        'id': case.id,
                        'name': case.name,
                    }
                    data['message'] = f'录制已停止，已生成用例 #{case.id}'
                except Exception as exc:
                    data['save_error'] = str(exc)
                    data['message'] = f'录制已停止，但保存用例失败: {exc}'
            else:
                data['message'] = '录制已停止'
            return Response(data)
        except Exception as exc:
            return Response({'error': str(exc)}, status=500)

    @action(detail=True, methods=['post'], url_path='save-case')
    def save_case(self, request, pk=None):
        session = self.get_object()
        try:
            case = save_recording_as_testcase(
                session,
                name=request.data.get('name') or session.name,
                created_by=request.user,
            )
            return Response({'test_case': {'id': case.id, 'name': case.name}})
        except Exception as exc:
            return Response({'error': str(exc)}, status=400)

    @action(detail=True, methods=['post'])
    def event(self, request, pk=None):
        """HTTP fallback for gestures when WS uplink is unavailable."""
        session = self.get_object()
        if session.status != 'recording':
            return Response({'error': '会话未在录制中'}, status=400)
        try:
            enqueue_recording_event(session.id, dict(request.data))
            return Response({'ok': True})
        except Exception as exc:
            return Response({'error': str(exc)}, status=400)

    @action(detail=True, methods=['post'], url_path='stream-settings')
    def stream_settings(self, request, pk=None):
        """Update live recording stream settings (e.g. quality)."""
        session = self.get_object()
        if session.status != 'recording':
            return Response({'error': '会话未在录制中'}, status=400)
        quality = request.data.get('stream_quality')
        if not quality:
            return Response({'error': '需要 stream_quality（fast/balanced/clear）'}, status=400)
        try:
            preset = set_recording_stream_quality(session.id, quality)
            return Response({
                'ok': True,
                'stream_quality': preset['mode'],
                'max_w': preset['max_w'],
                'quality': preset['quality'],
                'frame_interval': preset['frame_interval'],
            })
        except Exception as exc:
            return Response({'error': str(exc)}, status=400)

    @action(detail=True, methods=['get'])
    def frame(self, request, pk=None):
        """HTTP polling fallback for screen frames when WebSocket is unavailable."""
        session = self.get_object()
        data = get_latest_frame(session.id)
        # Prefer DB sizes if runtime not ready yet
        if not data.get('device_width'):
            data['device_width'] = session.screen_width or 0
        if not data.get('device_height'):
            data['device_height'] = session.screen_height or 0
        data['session_status'] = session.status
        if not data.get('steps') and session.ui_flow:
            data['steps'] = list(session.ui_flow or [])
        return Response(data)
