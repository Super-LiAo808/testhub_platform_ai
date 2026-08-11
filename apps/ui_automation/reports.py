"""
AI测试报告生成器
用于生成AI智能测试执行的各类报告
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
import re
import json

logger = logging.getLogger('django')


class AIExecutionReportGenerator:
    """AI执行报告生成器"""

    def __init__(self, execution_record):
        """
        初始化报告生成器

        Args:
            execution_record: AIExecutionRecord 实例
        """
        self.record = execution_record

    def generate_summary_report(self) -> Dict[str, Any]:
        """
        生成执行摘要报告

        Returns:
            包含摘要报告数据的字典
        """
        planned_tasks = self.record.planned_tasks or []
        logs = self.record.logs or ''

        # 统计任务状态
        task_statistics = self._calculate_task_statistics(planned_tasks)

        # 解析日志获取步骤信息
        step_info = self._parse_execution_logs(logs)

        # 添加性能分析摘要数据
        steps_completed = self.record.steps_completed or []
        performance_metrics = None
        action_distribution = None

        if steps_completed or logs:
            # 计算性能指标
            step_performance = self._analyze_step_performance(steps_completed)
            performance_metrics = self._calculate_performance_metrics(step_performance)

            # 分析操作分布
            action_distribution = self._analyze_action_distribution(logs)

        # 构建报告数据
        report = {
            'overview': self._generate_overview(task_statistics, step_info),
            'statistics': task_statistics,
            'timeline': self._generate_timeline(planned_tasks),
            'steps': step_info,
            'metrics': performance_metrics,  # 添加性能指标
            'action_distribution': action_distribution,  # 添加操作分布
            'execution_details': {
                'case_name': self.record.case_name,
                'execution_mode': self.record.get_execution_mode_display(),
                'status': self.record.get_status_display(),
                'start_time': self.record.start_time.isoformat() if self.record.start_time else None,
                'end_time': self.record.end_time.isoformat() if self.record.end_time else None,
                'duration': self.record.duration,
                'total_tasks': len(planned_tasks),
            },
            'gif_path': self.record.gif_path,  # 添加GIF路径
            'derived_test_case_id': self.record.derived_test_case_id,
            'derived_test_case_name': (
                self.record.derived_test_case.name if self.record.derived_test_case_id else None
            ),
            'project_id': self.record.project_id,
            'synced_element_hint': self._count_ai_elements(),
        }

        return report

    def _count_ai_elements(self) -> int:
        if not self.record.project_id:
            return 0
        try:
            from apps.ui_automation.models import Element
            return Element.objects.filter(
                project_id=self.record.project_id,
                discovery_source='ai_discovered',
            ).count()
        except Exception:
            return 0

    def _calculate_task_statistics(self, planned_tasks: List[Dict]) -> Dict[str, Any]:
        """
        计算任务统计数据

        Args:
            planned_tasks: 规划的任务列表

        Returns:
            任务统计数据
        """
        total = len(planned_tasks)

        if total == 0:
            return {
                'total': 0,
                'completed': 0,
                'pending': 0,
                'failed': 0,
                'completion_rate': 0,
                'success_rate': 0
            }

        completed = sum(1 for task in planned_tasks if task.get('status') == 'completed')
        pending = sum(1 for task in planned_tasks if task.get('status') == 'pending')
        failed = sum(1 for task in planned_tasks if task.get('status') == 'failed')
        skipped = sum(1 for task in planned_tasks if task.get('status') == 'skipped')
        in_progress = sum(1 for task in planned_tasks if task.get('status') == 'in_progress')

        completion_rate = round((completed / total) * 100, 2) if total > 0 else 0
        attempted = completed + failed
        success_rate = round((completed / attempted) * 100, 2) if attempted > 0 else 0

        return {
            'total': total,
            'completed': completed,
            'pending': pending,
            'failed': failed,
            'skipped': skipped,
            'in_progress': in_progress,
            'completion_rate': completion_rate,
            'success_rate': success_rate
        }

    def _parse_execution_logs(self, logs: str) -> Dict[str, Any]:
        """
        解析执行日志，提取步骤信息

        Args:
            logs: 执行日志字符串

        Returns:
            步骤信息字典
        """
        steps = []
        total_actions = 0

        # 解析 [Step X] 格式的步骤
        step_pattern = r'\[Step (\d+)\]\n执行: (.+?)\n'
        matches = re.findall(step_pattern, logs)

        for step_num, action_str in matches:
            total_actions += len(action_str.split(' | ')) if action_str else 0
            steps.append({
                'step_number': int(step_num),
                'actions': action_str
            })

        return {
            'total_steps': len(steps),
            'total_actions': total_actions,
            'steps': steps
        }

    def _generate_overview(self, task_stats: Dict, step_info: Dict) -> Dict[str, Any]:
        """
        生成概览信息

        Args:
            task_stats: 任务统计数据
            step_info: 步骤信息

        Returns:
            概览数据
        """
        # 计算平均每步耗时
        duration = self.record.duration or 0
        avg_step_time = 0
        if step_info['total_steps'] > 0:
            avg_step_time = round(duration / step_info['total_steps'], 2)

        # 确定执行状态颜色
        status_color = self._get_status_color(self.record.status)

        return {
            'status': self.record.get_status_display(),
            'status_color': status_color,
            'duration': duration,
            'duration_formatted': self._format_duration(duration),
            'avg_step_time': avg_step_time,
            'total_steps': step_info['total_steps'],
            'total_actions': step_info['total_actions'],
            'completion_rate': task_stats['completion_rate'],
        }

    def _generate_timeline(self, planned_tasks: List[Dict]) -> List[Dict[str, Any]]:
        """
        生成任务时间线

        Args:
            planned_tasks: 规划的任务列表

        Returns:
            时间线数据
        """
        timeline = []
        for task in planned_tasks:
            timeline.append({
                'id': task.get('id'),
                'description': task.get('description', ''),
                'status': task.get('status', 'pending'),
                'status_display': self._get_task_status_display(task.get('status', 'pending'))
            })

        return timeline

    def _get_status_color(self, status: str) -> str:
        """获取状态对应的颜色"""
        color_map = {
            'passed': 'success',
            'failed': 'danger',
            'running': 'warning',
            'pending': 'info',
            'stopped': 'warning'
        }
        return color_map.get(status, 'info')

    def _get_task_status_display(self, status: str) -> str:
        """获取任务状态的显示文本"""
        status_map = {
            'completed': '已完成',
            'pending': '待执行',
            'failed': '失败',
            'skipped': '已跳过',
            'in_progress': '执行中'
        }
        return status_map.get(status, status)

    def _format_duration(self, duration: float) -> str:
        """
        格式化时长显示

        Args:
            duration: 时长（秒）

        Returns:
            格式化后的时长字符串
        """
        if duration < 60:
            return f"{duration:.2f}秒"
        elif duration < 3600:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            return f"{minutes}分{seconds}秒"
        else:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            return f"{hours}小时{minutes}分{seconds}秒"

    def generate_detailed_report(self) -> Dict[str, Any]:
        """
        生成详细步骤报告

        Returns:
            包含详细报告数据的字典
        """
        planned_tasks = self.record.planned_tasks or []
        logs = self.record.logs or ''
        steps_completed = self.record.steps_completed or []

        # 解析详细步骤信息
        detailed_steps = self._parse_detailed_steps(logs, steps_completed)

        # 解析错误信息
        errors = self._parse_errors(logs)

        # 获取截图序列（如果有）
        screenshots = self._get_screenshots_from_steps(steps_completed)

        return {
            'overview': self._generate_overview(
                self._calculate_task_statistics(planned_tasks),
                {'total_steps': len(detailed_steps), 'total_actions': 0}
            ),
            'statistics': self._calculate_task_statistics(planned_tasks),  # 添加统计信息
            'detailed_steps': detailed_steps,
            'errors': errors,
            'screenshots': screenshots,
            'task_progression': self._generate_task_progression(planned_tasks),
            'execution_details': {
                'case_name': self.record.case_name,
                'execution_mode': self.record.get_execution_mode_display(),
                'status': self.record.get_status_display(),
                'start_time': self.record.start_time.isoformat() if self.record.start_time else None,
                'end_time': self.record.end_time.isoformat() if self.record.end_time else None,
                'duration': self.record.duration,
            },
            'gif_path': self.record.gif_path  # 添加GIF路径
        }

    def generate_performance_report(self) -> Dict[str, Any]:
        """
        生成性能分析报告

        Returns:
            包含性能分析数据的字典
        """
        logs = self.record.logs or ''
        steps_completed = self.record.steps_completed or []

        # 分析各步骤性能
        step_performance = self._analyze_step_performance(steps_completed)

        # 识别性能瓶颈
        bottlenecks = self._identify_bottlenecks(step_performance)

        # 统计操作类型分布
        action_distribution = self._analyze_action_distribution(logs)

        # 计算性能指标
        metrics = self._calculate_performance_metrics(step_performance)

        return {
            'metrics': metrics,
            'step_performance': step_performance,
            'bottlenecks': bottlenecks,
            'action_distribution': action_distribution,
            'recommendations': self._generate_performance_recommendations(bottlenecks, metrics),
            'execution_details': {
                'case_name': self.record.case_name,
                'duration': self.record.duration,
                'total_steps': len(steps_completed),
            },
            'gif_path': self.record.gif_path  # 添加GIF路径
        }

    def _parse_detailed_steps(self, logs: str, steps_completed: List) -> List[Dict[str, Any]]:
        """解析详细步骤信息"""
        detailed_steps = []

        # 先从 steps_completed 中提取信息
        for step in steps_completed:
            detailed_steps.append({
                'step_number': step.get('step_number', 0),
                'action': step.get('action', ''),
                'element': step.get('element', ''),
                'status': step.get('status', 'completed'),
                'timestamp': step.get('timestamp', ''),
                'thinking': step.get('thinking', ''),
                'screenshot': step.get('screenshot', ''),
            })

        # 如果没有 steps_completed，从日志中解析
        if not detailed_steps:
            step_pattern = r'\[Step (\d+)\]\n执行: (.+?)(?:\n|$)'
            matches = re.findall(step_pattern, logs)

            for step_num, action_str in matches:
                detailed_steps.append({
                    'step_number': int(step_num),
                    'action': action_str,
                    'status': 'completed',
                    'timestamp': '',
                })

        return detailed_steps

    def _parse_errors(self, logs: str) -> List[Dict[str, Any]]:
        """解析错误信息"""
        errors = []

        # 查找错误行
        error_patterns = [
            r'ERROR: (.+)',
            r'Exception: (.+)',
            r'失败: (.+)',
            r'错误: (.+)',
        ]

        for pattern in error_patterns:
            matches = re.findall(pattern, logs)
            for match in matches:
                errors.append({
                    'message': match,
                    'type': 'error',
                })

        # 查找警告
        warning_patterns = [
            r'WARNING: (.+)',
            r'警告: (.+)',
        ]

        for pattern in warning_patterns:
            matches = re.findall(pattern, logs)
            for match in matches:
                errors.append({
                    'message': match,
                    'type': 'warning',
                })

        return errors

    def _get_screenshots_from_steps(self, steps_completed: List) -> List[str]:
        """从步骤中提取截图"""
        screenshots = []
        for step in steps_completed:
            if step.get('screenshot'):
                screenshots.append(step['screenshot'])
        return screenshots

    def _generate_task_progression(self, planned_tasks: List[Dict]) -> List[Dict[str, Any]]:
        """生成任务进度跟踪"""
        progression = []
        for task in planned_tasks:
            progression.append({
                'id': task.get('id'),
                'description': task.get('description', ''),
                'status': task.get('status', 'pending'),
                'status_display': self._get_task_status_display(task.get('status', 'pending')),
            })
        return progression

    def _analyze_step_performance(self, steps_completed: List) -> List[Dict[str, Any]]:
        """分析步骤性能 - 基于操作复杂度分配时间权重"""
        performance = []

        # 收集所有步骤（优先从 steps_completed，否则从日志解析）
        all_steps = []
        if steps_completed:
            for i, step in enumerate(steps_completed):
                action_desc = step.get('action', '')
                if not action_desc:
                    thinking = step.get('thinking', '')
                    element = step.get('element', '')
                    action_desc = f"{thinking} {element}".strip() or f"步骤 {i + 1}"
                all_steps.append({
                    'step_number': step.get('step_number', i + 1),
                    'action': action_desc
                })
        else:
            # 从日志中解析步骤
            logs = self.record.logs or ''
            step_pattern = r'\[Step (\d+)\]\n执行: (.+?)(?:\n|$)'
            matches = re.findall(step_pattern, logs)
            for step_num, action_str in matches:
                all_steps.append({
                    'step_number': int(step_num),
                    'action': action_str
                })

        if not all_steps:
            return performance

        total_duration = self.record.duration or 0
        step_count = len(all_steps)

        if total_duration == 0 or step_count == 0:
            # 无效时长，返回空数据
            for step in all_steps:
                performance.append({
                    'step_number': step['step_number'],
                    'action': step['action'],
                    'estimated_duration': 0,
                })
            return performance

        # 基于操作复杂度分配权重
        def get_step_complexity(action_str):
            """根据操作类型返回复杂度权重"""
            if not action_str:
                return 1.0

            # 导航类操作权重最高（页面加载）
            if '访问:' in action_str or 'go_to_url' in action_str or 'navigate' in action_str:
                return 2.0

            # 输入操作次之
            if "输入:" in action_str or 'input_text' in action_str:
                return 1.5

            # 切换标签
            if '切换标签' in action_str or 'switch_tab' in action_str:
                return 1.2

            # 新标签打开
            if '新标签打开' in action_str or 'open_new_tab' in action_str:
                return 1.8

            # 点击操作
            if '点击[' in action_str or 'click_element' in action_str:
                return 1.0

            # 滚动操作较快
            if 'scroll' in action_str.lower():
                return 0.6

            # 等待
            if '等待' in action_str or 'wait' in action_str.lower():
                return 0.8

            # 其他操作默认权重
            return 1.0

        # 计算每个步骤的复杂度权重
        weights = [get_step_complexity(step['action']) for step in all_steps]
        total_weight = sum(weights)

        # 根据权重分配总时长
        for step, weight in zip(all_steps, weights):
            # 按权重比例分配时间，确保总时长匹配
            allocated_time = (weight / total_weight) * total_duration if total_weight > 0 else 0
            performance.append({
                'step_number': step['step_number'],
                'action': step['action'],
                'estimated_duration': round(allocated_time, 2),
            })

        return performance

    def _identify_bottlenecks(self, step_performance: List[Dict]) -> List[Dict[str, Any]]:
        """识别性能瓶颈"""
        bottlenecks = []

        # 如果没有步骤数据或所有耗时都是0，返回空
        if not step_performance:
            return bottlenecks

        # 获取所有非零耗时
        durations = [s['estimated_duration'] for s in step_performance if s['estimated_duration'] > 0]

        # 如果所有耗时都是0或相等，无法识别瓶颈
        if not durations or len(set(durations)) <= 1:
            return bottlenecks

        avg_duration = sum(durations) / len(durations)

        # 找出耗时超过平均1.2倍的步骤（降低阈值以获得更多结果）
        for step in step_performance:
            if step['estimated_duration'] > avg_duration * 1.2:
                bottlenecks.append({
                    'step_number': step['step_number'],
                    'action': step['action'],
                    'duration': step['estimated_duration'],
                    'slower_than_avg_by': round((step['estimated_duration'] / avg_duration - 1) * 100, 2)
                })

        return bottlenecks

    def _analyze_action_distribution(self, logs: str) -> Dict[str, int]:
        """分析操作类型分布"""
        distribution = {
            'click': 0,
            'input': 0,
            'scroll': 0,
            'wait': 0,
            'switch_tab': 0,
            'navigate': 0,
            'open_tab': 0,
            'done': 0,
            'other': 0
        }

        # 统计各种操作类型 - 日志使用中文描述，需要匹配中文关键词
        # 格式: [Step 1]\n执行: 点击[1] | 输入: 'xxx' | 访问: url...
        distribution['click'] = len(re.findall(r'点击\[\d+\]', logs))
        distribution['input'] = len(re.findall(r"输入:\s*'[^']*'", logs))
        distribution['scroll'] = len(re.findall(r'scroll_down|scroll_up', logs, re.IGNORECASE))
        distribution['wait'] = len(re.findall(r'wait|sleep|等待', logs, re.IGNORECASE))
        distribution['switch_tab'] = len(re.findall(r'切换标签\s*\d+', logs))
        distribution['navigate'] = len(re.findall(r"访问:\s*\S+", logs))
        distribution['open_tab'] = len(re.findall(r"新标签打开:\s*\S+", logs))
        distribution['done'] = len(re.findall(r"任务完成", logs))

        # 其他操作（包括待机等）
        distribution['other'] = max(0, len(re.findall(r'\[Step \d+\]', logs)) - sum([
            distribution['click'], distribution['input'], distribution['scroll'],
            distribution['wait'], distribution['switch_tab'], distribution['navigate'],
            distribution['open_tab'], distribution['done']
        ]))

        return distribution

    def _calculate_performance_metrics(self, step_performance: List[Dict]) -> Dict[str, Any]:
        """计算性能指标"""
        if not step_performance:
            return {
                'total_steps': 0,
                'avg_step_duration': 0,
                'max_step_duration': 0,
                'min_step_duration': 0,
            }

        durations = [s['estimated_duration'] for s in step_performance if s['estimated_duration'] > 0]

        if not durations:
            return {
                'total_steps': len(step_performance),
                'avg_step_duration': 0,
                'max_step_duration': 0,
                'min_step_duration': 0,
            }

        return {
            'total_steps': len(step_performance),
            'avg_step_duration': round(sum(durations) / len(durations), 2),
            'max_step_duration': max(durations),
            'min_step_duration': min(durations),
        }

    def _generate_performance_recommendations(self, bottlenecks: List[Dict], metrics: Dict) -> List[str]:
        """生成性能优化建议"""
        recommendations = []

        if bottlenecks:
            recommendations.append(f"发现 {len(bottlenecks)} 个性能瓶颈步骤，建议优化相关操作")

        if metrics['avg_step_duration'] > 10:
            recommendations.append("平均步骤耗时较长，建议检查网络连接或页面响应速度")

        return recommendations


class AIReportComparison:
    """AI报告对比分析器"""

    @staticmethod
    def compare_executions(record1, record2) -> Dict[str, Any]:
        """
        对比两次执行记录

        Args:
            record1: 第一次执行记录
            record2: 第二次执行记录

        Returns:
            对比结果
        """
        gen1 = AIExecutionReportGenerator(record1)
        gen2 = AIExecutionReportGenerator(record2)

        stats1 = gen1._calculate_task_statistics(record1.planned_tasks or [])
        stats2 = gen2._calculate_task_statistics(record2.planned_tasks or [])

        return {
            'duration_diff': (record2.duration or 0) - (record1.duration or 0),
            'completion_rate_diff': stats2['completion_rate'] - stats1['completion_rate'],
            'steps_diff': stats2['total'] - stats1['total'],
            'status_changed': record1.status != record2.status,
        }
