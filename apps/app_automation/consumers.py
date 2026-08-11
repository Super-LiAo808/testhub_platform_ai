import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class AppExecutionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        try:
            self.execution_id = self.scope["url_route"]["kwargs"]["execution_id"]
            self.group_name = f"app_execution_{self.execution_id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(f"WebSocket 连接成功: execution_id={self.execution_id}")
        except Exception as e:
            logger.error(f"WebSocket 连接失败: {e}")
            await self.close()

    async def disconnect(self, close_code):
        try:
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
                logger.info(f"WebSocket 断开: execution_id={self.execution_id}, code={close_code}")
        except Exception as e:
            logger.error(f"WebSocket 断开处理失败: {e}")

    async def execution_update(self, event):
        try:
            await self.send_json(event)
        except Exception as e:
            logger.error(f"WebSocket 推送消息失败: {e}")


class AppRecordingConsumer(AsyncJsonWebsocketConsumer):
    """Realtime screen frames + gesture uplink for APP recording."""

    async def connect(self):
        try:
            self.session_id = self.scope['url_route']['kwargs']['session_id']
            self.group_name = f'app_recording_{self.session_id}'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info('Recording WS connected session=%s', self.session_id)
        except Exception as e:
            logger.error('Recording WS connect failed: %s', e)
            await self.close()

    async def disconnect(self, close_code):
        try:
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception as e:
            logger.error('Recording WS disconnect failed: %s', e)

    async def receive_json(self, content, **kwargs):
        try:
            from apps.app_automation.services.recording import enqueue_recording_event
            await sync_to_async(enqueue_recording_event)(int(self.session_id), content)
        except Exception as e:
            logger.warning('Recording WS receive failed: %s', e)
            await self.send_json({'event': 'error', 'message': str(e)})

    async def recording_update(self, event):
        try:
            data = {k: v for k, v in event.items() if k != 'type'}
            await self.send_json(data)
        except Exception as e:
            logger.error('Recording WS push failed: %s', e)
